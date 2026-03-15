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
    build_system_prompt, build_user_prompt
)
from core.config import settings
import httpx
import redis.asyncio as redis
from postgrest import APIResponse as AsyncPostgrestAPIResponse

# Fixtures for common test data (will be shared or duplicated for now, fine for separate files)
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

@pytest.fixture(autouse=True)
def mock_settings_openai(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "mock-openai-key")
    monkeypatch.setattr(settings, "OPENAI_API_BASE_URL", "http://mock-openai-api")
    monkeypatch.setattr(settings, "SUPABASE_URL", "http://mock-supabase-url")
    monkeypatch.setattr(settings, "SUPABASE_SERVICE_ROLE_KEY", "mock-supabase-service-key")
    monkeypatch.setattr(settings, "UPSTASH_REDIS_REST_URL", "http://mock-redis-url")
    monkeypatch.setattr(settings, "UPSTASH_REDIS_REST_TOKEN", "mock-redis-token")


class TestQueryGeneratorAgentIntegration:

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
    async def test_run_handles_supabase_persistence_error(self, mock_audit_state, mock_company_profile):
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

            mock_response_llm = AsyncMock()
            mock_response_llm.json.return_value = {
                "choices": [{"message": {"content": json.dumps({
                    "queries": [
                        {"query_text": f"Test query {i}", "intent": QueryIntent.INFORMATIONAL.value, "target_metrics": ["GEO-01-ENT-SAL"]}
                        for i in range(mock_audit_state.config.query_count)
                    ]
                })}}]
            }
            mock_httpx_client.return_value.__aenter__.return_value.post.return_value = mock_response_llm

            # Mock Supabase insert to raise an error
            mock_supabase_client.from_.return_value.insert.return_value.execute.side_effect = RuntimeError("DB insert failed")
            
            mock_redis_client = AsyncMock()
            mock_create_redis_client.return_value = mock_redis_client

            final_state = await run(mock_audit_state)

            assert final_state.error is not None
            assert "Query generation failed during database persistence: DB insert failed" in final_state.error
            
            set_calls = [call for call in mock_redis_client.set.call_args_list]
            assert any("Error persisting queries" in json.loads(call.args[1])["message"] for call in set_calls)
            assert any(json.loads(call.args[1])["progress"] == 0.99 for call in set_calls)

    @pytest.mark.asyncio
    async def test_publish_progress_closes_redis_client(self, mock_audit_state):
        with patch("apps.api.agents.query_generator.create_redis_client") as mock_create_redis_client:
            mock_redis_client = AsyncMock()
            mock_create_redis_client.return_value = mock_redis_client

            await _publish_progress(mock_audit_state.audit_id, "test message", 0.5)

            mock_redis_client.set.assert_called_once()
            mock_redis_client.aclose.assert_called_once() # Ensure aclose is called
