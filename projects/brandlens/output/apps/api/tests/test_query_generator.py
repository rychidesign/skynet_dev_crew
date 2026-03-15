import pytest
import asyncio
from unittest.mock import AsyncMock, patch
import json

from core.state import AuditState, AgentMessage
from models.audit import AuditConfig, QueryIntent
from models.progress import ProgressUpdate
from apps.api.agents.query_generator import (
    run, _fetch_company_profile, _compute_distribution, _call_llm,
    _validate_and_build_specs, _repair_distribution,
    _persist_queries, _publish_progress, CompanyProfile, QuerySpec
)
from apps.api.agents.query_constants import (
    INTENT_MIN_RATIOS, INTENT_METRIC_MAP, MAX_BRAND_NAME_RATIO, VALID_METRIC_IDS
)
from apps.api.agents.query_prompts import (
    build_system_prompt, build_user_prompt, FALLBACK_TEMPLATES
)
from core.config import settings
import httpx
import redis.asyncio as redis
from postgrest import APIResponse as AsyncPostgrestAPIResponse

# Fixtures for common test data

@pytest.fixture
def mock_audit_config():
    return AuditConfig(query_count=10, platform_configs=[])

@pytest.fixture
def mock_audit_state(mock_audit_config):
    return AuditState(
        audit_id="test-audit-id",
        company_id="test-company-id",
        user_id="test-user-id",
        organization_id="test-org-id",
        config=mock_audit_config,
        messages=[],
        error=None,
    )

@pytest.fixture
def mock_company_profile():
    return CompanyProfile(
        company_id="test-company-id",
        name="BrandLens Inc.",
        industry="Software",
        description="A company that measures brand visibility.",
        competitors=["Competitor A", "Competitor B"],
        core_topics=["brand visibility", "AI search", "marketing analytics"],
        facts={"founded_year": 2023, "ceo": "John Doe"},
    )

# --- Unit Tests for Pure Functions ---

class TestComputeDistribution:
    @pytest.mark.parametrize("query_count, expected_distribution", [
        (10, {
            QueryIntent.INFORMATIONAL.value: 2,
            QueryIntent.COMPARATIVE.value: 2,
            QueryIntent.RECOMMENDATION.value: 1,
            QueryIntent.AUTHORITY.value: 1,
            QueryIntent.FACTUAL.value: 1,
            QueryIntent.NAVIGATIONAL.value: 3, # 10 - (2+2+1+1+1) = 3
        }),
        (50, {
            QueryIntent.INFORMATIONAL.value: 8,  # ceil(0.15 * 50) = 8
            QueryIntent.COMPARATIVE.value: 8,
            QueryIntent.RECOMMENDATION.value: 5, # ceil(0.10 * 50) = 5
            QueryIntent.AUTHORITY.value: 5,
            QueryIntent.FACTUAL.value: 5,
            QueryIntent.NAVIGATIONAL.value: 19, # 50 - (8+8+5+5+5) = 19
        }),
        (5, { # Test small N where sum of minimums might exceed total
            QueryIntent.INFORMATIONAL.value: 1, # ceil(0.15*5) = 1
            QueryIntent.COMPARATIVE.value: 1,
            QueryIntent.RECOMMENDATION.value: 1, # ceil(0.10*5) = 1
            QueryIntent.AUTHORITY.value: 1,
            QueryIntent.FACTUAL.value: 1,
            QueryIntent.NAVIGATIONAL.value: 0, # 5 - 5 = 0. Should not be negative.
        }),
        (200, {
            QueryIntent.INFORMATIONAL.value: 30, # ceil(0.15*200) = 30
            QueryIntent.COMPARATIVE.value: 30,
            QueryIntent.RECOMMENDATION.value: 20, # ceil(0.10*200) = 20
            QueryIntent.AUTHORITY.value: 20,
            QueryIntent.FACTUAL.value: 20,
            QueryIntent.NAVIGATIONAL.value: 80, # 200 - (30*2 + 20*3) = 200 - 120 = 80
        }),
    ])
    def test_compute_distribution_minimums_and_totals(self, query_count, expected_distribution):
        actual_distribution = _compute_distribution(query_count)
        
        # Ensure all intents are present, even if 0
        all_intents = set(INTENT_MIN_RATIOS.keys()) | {QueryIntent.NAVIGATIONAL.value}
        assert set(actual_distribution.keys()) == all_intents

        for intent, expected_count in expected_distribution.items():
            assert actual_distribution[intent] == expected_count, f"Intent {intent} failed"
        
        assert sum(actual_distribution.values()) == query_count, "Total query count mismatch"

class TestValidateAndRepair:
    
    @pytest.mark.parametrize("initial_queries, expected_final_count, expected_brand_ratio_cap", [
        (
            [
                QuerySpec(query_text="BrandLens is great", intent=QueryIntent.INFORMATIONAL.value, target_metrics=[], query_index=0),
                QuerySpec(query_text="BrandLens vs Competitor A", intent=QueryIntent.COMPARATIVE.value, target_metrics=[], query_index=1),
                QuerySpec(query_text="Another query about BrandLens", intent=QueryIntent.INFORMATIONAL.value, target_metrics=[], query_index=2),
                QuerySpec(query_text="General topic query", intent=QueryIntent.INFORMATIONAL.value, target_metrics=[], query_index=3),
                QuerySpec(query_text="Yet another BrandLens query", intent=QueryIntent.INFORMATIONAL.value, target_metrics=[], query_index=4),
            ],
            5, # query_count
            3 # 5 * 0.6 = 3
        ),
        (
            [
                QuerySpec(query_text="BrandLens", intent=QueryIntent.INFORMATIONAL.value, target_metrics=[], query_index=0),
                QuerySpec(query_text="BrandLens product", intent=QueryIntent.INFORMATIONAL.value, target_metrics=[], query_index=1),
                QuerySpec(query_text="BrandLens review", intent=QueryIntent.INFORMATIONAL.value, target_metrics=[], query_index=2),
                QuerySpec(query_text="BrandLens comparison", intent=QueryIntent.COMPARATIVE.value, target_metrics=[], query_index=3),
                QuerySpec(query_text="Features of BrandLens", intent=QueryIntent.INFORMATIONAL.value, target_metrics=[], query_index=4),
                QuerySpec(query_text="Cost of BrandLens", intent=QueryIntent.FACTUAL.value, target_metrics=[], query_index=5),
                QuerySpec(query_text="General search", intent=QueryIntent.NAVIGATIONAL.value, target_metrics=[], query_index=6),
            ],
            5, # query_count
            3 # 5 * 0.6 = 3
        )
    ])
    def test_validate_brand_ratio_capped(self, mock_company_profile, initial_queries, expected_final_count, expected_brand_ratio_cap):
        
        query_count = expected_final_count
        distribution = _compute_distribution(query_count) # Generate a valid distribution for query_count

        repaired_queries = _repair_distribution(initial_queries, distribution, mock_company_profile)
        
        # 1. Check final count
        assert len(repaired_queries) == query_count

        # 2. Check brand name ratio
        brand_name = mock_company_profile.name.lower()
        brand_mentions = sum(1 for q in repaired_queries if brand_name in q.query_text.lower())
        assert brand_mentions <= expected_brand_ratio_cap

        # 3. Check intent distribution (best effort for synthetic queries)
        actual_intent_counts = {intent: 0 for intent in distribution}
        for q in repaired_queries:
            actual_intent_counts[q.intent] += 1
        
        for intent, required_count in distribution.items():
            assert actual_intent_counts[intent] >= required_count * 0.8 # Allow some flexibility after repair due to stripping brand names / general fallbacks.
            # This is a soft check. More precise checks for specific synthetic queries might be too brittle.

    def test_validate_intent_distribution_repaired(self, mock_company_profile):
        query_count = 10
        distribution = _compute_distribution(query_count)
        
        # Start with queries that don't meet minimums
        initial_queries = [
            QuerySpec(query_text="Initial informational query", intent=QueryIntent.INFORMATIONAL.value, target_metrics=[], query_index=0),
            QuerySpec(query_text="Another informational query", intent=QueryIntent.INFORMATIONAL.value, target_metrics=[], query_index=1),
            QuerySpec(query_text="Comparative query", intent=QueryIntent.COMPARATIVE.value, target_metrics=[], query_index=2),
            QuerySpec(query_text="Navigational query", intent=QueryIntent.NAVIGATIONAL.value, target_metrics=[], query_index=3),
        ] # Total 4 queries, far from 10, and missing many intents

        repaired_queries = _repair_distribution(initial_queries, distribution, mock_company_profile)

        assert len(repaired_queries) == query_count

        actual_intent_counts = {intent: 0 for intent in distribution}
        for q in repaired_queries:
            actual_intent_counts[q.intent] += 1
        
        # After repair, all required intents should at least have their minimum count (or be very close)
        for intent, required_count in distribution.items():
            assert actual_intent_counts[intent] >= required_count or (required_count == 0 and actual_intent_counts[intent] == 0)
            # More specific check for fallbacks could be added but might be brittle.
            # The important part is that the counts are met or padded.

# --- Mocked Integration Tests for run() ---

@pytest.fixture(autouse=True)
def mock_settings_openai(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "mock-openai-key")
    monkeypatch.setattr(settings, "OPENAI_API_BASE_URL", "http://mock-openai-api")
    monkeypatch.setattr(settings, "SUPABASE_URL", "http://mock-supabase-url")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "mock-supabase-service-key")
    monkeypatch.setattr(settings, "UPSTASH_REDIS_REST_URL", "http://mock-redis-url")
    monkeypatch.setattr(settings, "UPSTASH_REDIS_REST_TOKEN", "mock-redis-token")


class TestQueryGeneratorAgent:

    @pytest.mark.asyncio
    async def test_run_persists_queries(self, mock_audit_state, mock_company_profile):
        with (
            patch("apps.api.agents.query_generator.create_supabase_client") as mock_create_supabase_client,
            patch("httpx.AsyncClient") as mock_httpx_client,
            patch("apps.api.agents.query_generator.create_redis_client") as mock_create_redis_client,
            patch("apps.api.agents.query_prompts.build_system_prompt", return_value="mock system prompt"),
            patch("apps.api.agents.query_prompts.build_user_prompt", return_value="mock user prompt"),
        ):
            # Mock Supabase client
            mock_supabase_client = AsyncMock()
            mock_create_supabase_client.return_value = mock_supabase_client

            # Mock company fetch
            mock_supabase_client.from_.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = AsyncPostgrestAPIResponse(
                data=mock_company_profile.__dict__, count=1, status=200, status_text="OK"
            )

            # Mock httpx (LLM call)
            mock_response = AsyncMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": json.dumps({
                    "queries": [
                        {"query_text": f"BrandLens informational query {{i}}", "intent": QueryIntent.INFORMATIONAL.value, "target_metrics": ["GEO-01-ENT-SAL"]},
                        {"query_text": f"BrandLens comparative query {{i}}", "intent": QueryIntent.COMPARATIVE.value, "target_metrics": ["GEO-14-CMP-PST"]},
                    ] * (mock_audit_state.config.query_count // 2)
                })}}]} # Generate enough queries
            }
            mock_httpx_client.return_value.__aenter__.return_value.post.return_value = mock_response

            # Mock Redis client
            mock_redis_client = AsyncMock()
            mock_create_redis_client.return_value = mock_redis_client

            # Run the agent
            final_state = await run(mock_audit_state)

            # Assertions
            assert final_state.error is None
            assert len(final_state.messages) == 1
            assert final_state.messages[0].sender == "query_generator"
            assert final_state.messages[0].payload["queries_generated"] == mock_audit_state.config.query_count

            # Verify Supabase calls
            mock_create_supabase_client.assert_called_with(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
            
            # Company fetch call
            mock_supabase_client.from_.assert_any_call("companies")
            mock_supabase_client.from_.return_value.select.assert_called_once_with(
                "name, industry, description, competitors, core_topics, facts"
            )
            mock_supabase_client.from_.return_value.select.return_value.eq.assert_called_once_with("id", mock_audit_state.company_id)
            mock_supabase_client.from_.return_value.select.return_value.eq.return_value.single.assert_called_once()

            # Delete call
            mock_supabase_client.from_.assert_any_call("audit_queries")
            mock_supabase_client.from_.return_value.delete.assert_called_once()
            mock_supabase_client.from_.return_value.delete.return_value.eq.assert_called_once_with("audit_id", mock_audit_state.audit_id)

            # Insert call
            mock_supabase_client.from_.return_value.insert.assert_called_once()
            inserted_data = mock_supabase_client.from_.return_value.insert.call_args[0][0]
            assert len(inserted_data) == mock_audit_state.config.query_count
            assert all(item["audit_id"] == mock_audit_state.audit_id for item in inserted_data)
            assert all("query_text" in item and "intent" in item and "target_metrics" in item for item in inserted_data)

            # Update audit status call
            mock_supabase_client.from_.assert_any_call("audits")
            mock_supabase_client.from_.return_value.update.assert_called_once_with({"status": "collecting"})
            mock_supabase_client.from_.return_value.update.return_value.eq.assert_called_once_with("id", mock_audit_state.audit_id)

            # Verify Redis calls (progress updates)
            assert mock_redis_client.set.call_count >= 3 # Start, LLM, Validate, Persist, End
            set_calls = [call for call in mock_redis_client.set.call_args_list]
            assert any(f"audit:{mock_audit_state.audit_id}:progress" in call.args[0] for call in set_calls)

    @pytest.mark.asyncio
    async def test_run_handles_llm_failure(self, mock_audit_state, mock_company_profile):
        with (
            patch("apps.api.agents.query_generator.create_supabase_client") as mock_create_supabase_client,
            patch("httpx.AsyncClient") as mock_httpx_client,
            patch("apps.api.agents.query_generator.create_redis_client") as mock_create_redis_client,
            patch("apps.api.agents.query_prompts.build_system_prompt", return_value="mock system prompt"),
            patch("apps.api.agents.query_prompts.build_user_prompt", return_value="mock user prompt"),
        ):
            mock_supabase_client = AsyncMock()
            mock_create_supabase_client.return_value = mock_supabase_client
            mock_supabase_client.from_.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = AsyncPostgrestAPIResponse(
                data=mock_company_profile.__dict__, count=1, status=200, status_text="OK"
            )

            # Mock httpx to raise an error
            mock_httpx_client.return_value.__aenter__.return_value.post.side_effect = httpx.HTTPStatusError(
                "LLM Error", request=httpx.Request("POST", "http://mock-openai-api"), response=httpx.Response(500)
            )

            mock_redis_client = AsyncMock()
            mock_create_redis_client.return_value = mock_redis_client

            final_state = await run(mock_audit_state)

            assert final_state.error is not None
            assert "LLM query generation failed" in final_state.error
            
            # Verify progress update with error
            set_calls = [call for call in mock_redis_client.set.call_args_list]
            assert any("Error calling LLM" in json.loads(call.args[1])["message"] for call in set_calls)
            assert any(json.loads(call.args[1])["progress"] == 0.99 for call in set_calls)

    @pytest.mark.asyncio
    async def test_run_handles_company_not_found(self, mock_audit_state):
        with (
            patch("apps.api.agents.query_generator.create_supabase_client") as mock_create_supabase_client,
            patch("apps.api.agents.query_generator.create_redis_client") as mock_create_redis_client,
            patch("apps.api.agents.query_prompts.build_system_prompt", return_value="mock system prompt"),
            patch("apps.api.agents.query_prompts.build_user_prompt", return_value="mock user prompt"),
        ):
            mock_supabase_client = AsyncMock()
            mock_create_supabase_client.return_value = mock_supabase_client
            # Mock company fetch to return no data
            mock_supabase_client.from_.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = AsyncPostgrestAPIResponse(
                data=None, count=0, status=200, status_text="OK"
            )

            mock_redis_client = AsyncMock()
            mock_create_redis_client.return_value = mock_redis_client

            final_state = await run(mock_audit_state)

            assert final_state.error is not None
            assert f"Company with ID {mock_audit_state.company_id} not found." in final_state.error
            
            # Verify progress update with error
            set_calls = [call for call in mock_redis_client.set.call_args_list]
            assert any(f"Error: Company with ID {mock_audit_state.company_id} not found." in json.loads(call.args[1])["message"] for call in set_calls)
            assert any(json.loads(call.args[1])["progress"] == 0.99 for call in set_calls)

    @pytest.mark.asyncio
    async def test_run_handles_invalid_llm_json(self, mock_audit_state, mock_company_profile):
        with (
            patch("apps.api.agents.query_generator.create_supabase_client") as mock_create_supabase_client,
            patch("httpx.AsyncClient") as mock_httpx_client,
            patch("apps.api.agents.query_generator.create_redis_client") as mock_create_redis_client,
            patch("apps.api.agents.query_prompts.build_system_prompt", return_value="mock system prompt"),
            patch("apps.api.agents.query_prompts.build_user_prompt", return_value="mock user prompt"),
        ):
            mock_supabase_client = AsyncMock()
            mock_create_supabase_client.return_value = mock_supabase_client
            mock_supabase_client.from_.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = AsyncPostgrestAPIResponse(
                data=mock_company_profile.__dict__, count=1, status=200, status_text="OK"
            )

            mock_response = AsyncMock()
            # LLM returns invalid JSON
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "This is not valid JSON"}}]
            }
            mock_httpx_client.return_value.__aenter__.return_value.post.return_value = mock_response

            mock_redis_client = AsyncMock()
            mock_create_redis_client.return_value = mock_redis_client

            final_state = await run(mock_audit_state)

            assert final_state.error is not None
            assert "LLM returned invalid JSON" in final_state.error
            
            # Verify progress update with error
            set_calls = [call for call in mock_redis_client.set.call_args_list]
            assert any("Error parsing LLM response" in json.loads(call.args[1])["message"] for call in set_calls)
            assert any(json.loads(call.args[1])["progress"] == 0.99 for call in set_calls)

    @pytest.mark.asyncio
    async def test_publish_progress_closes_redis_client(self, mock_audit_state):
        with patch("apps.api.agents.query_generator.create_redis_client") as mock_create_redis_client:
            mock_redis_client = AsyncMock()
            mock_create_redis_client.return_value = mock_redis_client

            await _publish_progress(mock_audit_state.audit_id, "test message", 0.5)

            mock_redis_client.set.assert_called_once()
            mock_redis_client.aclose.assert_called_once() # Ensure aclose is called
