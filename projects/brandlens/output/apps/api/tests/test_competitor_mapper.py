import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Tuple

from apps.api.agents.competitor_mapper.main import run as competitor_mapper_run
from apps.api.agents.competitor_mapper_constants_and_types import (
    CompetitorMentionResult, FilteredResponse, CompetitorRecord, COMPARATIVE_INTENTS
)
from apps.api.agents.competitor_mapper_prompts import build_analysis_prompt, SYSTEM_PROMPT
from apps.api.agents.competitor_mapper_llm_parsing import parse_llm_output
from apps.api.agents.competitor_mapper_aggregation import aggregate_competitor_records, build_platform_breakdown, competitor_record_to_db_dict
from apps.api.core.state import AuditState, AgentMessage, AuditStatus
from apps.api.core.config import settings

# Mock structlog for tests
@pytest.fixture(autouse=True)
def mock_structlog():
    with patch("structlog.get_logger") as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        yield mock_logger

# Fixtures for common data
@pytest.fixture
def mock_audit_state():
    state = AuditState(
        audit_id="test-audit-id",
        company_id="test-company-id",
        user_id="test-user-id",
        organization_id="test-org-id",
        status=AuditStatus.RUNNING,
        messages=[],
        audit_config={},
        company_name="TestCompany",
        company_website="testcompany.com",
        company_facts=[],
        company_competitors=["CompetitorA", "CompetitorB.com", "CompetitorC"],
        company_core_topics=[],
        query_results=[],
        response_results=[],
        mention_results=[],
        competitor_results=[],
        metric_scores={},
        recommendations=[],
        technical_checks={},
        audit_events=[],
        brand_competitive_stats=[],
    )
    state.get_db = AsyncMock()
    state.get_db.return_value = MagicMock()
    return state

@pytest.fixture
def mock_db_client():
    db = AsyncMock()
    db.from_.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value = AsyncMock(data=[])
    db.from_.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = AsyncMock(data={})
    db.from_.return_value.upsert.return_value.on_conflict.return_value.execute.return_value = AsyncMock(data=[])
    return db

@pytest.fixture
def mock_redis_client():
    redis = AsyncMock()
    return redis

# --- Test competitor_mapper_prompts.py ---

def test_build_analysis_prompt():
    response_text = "This is a response mentioning CompetitorA and CompetitorB."
    competitors = ["CompetitorA", "CompetitorB"]
    platform = "ChatGPT"
    query_text = "Compare BrandX with its competitors."
    prompt = build_analysis_prompt(response_text, competitors, platform, query_text)
    assert "CompetitorA, CompetitorB" in prompt
    assert "ChatGPT" in prompt
    assert "This is a response" in prompt
    assert "position_rank" in prompt
    assert SYSTEM_PROMPT.strip() == """You are a competitive analysis extraction system. You analyze AI-generated responses and identify mentions of competitor brands. You MUST respond with valid JSON only. No explanation, no markdown, no prose."""


# --- Test competitor_mapper_llm_parsing.py ---

def test_parse_llm_output_valid_json(mock_structlog):
    raw_json = '''
    {
      "competitor_mentions": [
        {
          "competitor_name": "CompetitorA",
          "position_rank": 1,
          "is_recommended": true,
          "comparison_sentiment": "positive",
          "mention_count": 2
        },
        {
          "competitor_name": "CompetitorB",
          "position_rank": null,
          "is_recommended": false,
          "comparison_sentiment": "neutral",
          "mention_count": 1
        }
      ]
    }
    '''
    competitors = ["CompetitorA", "CompetitorB"]
    parsed = parse_llm_output(raw_json, "resp1", "audit1", competitors, mock_structlog)
    assert len(parsed) == 2
    assert parsed[0].competitor_name == "CompetitorA"
    assert parsed[0].position_rank == 1
    assert parsed[0].is_recommended is True
    assert parsed[0].comparison_sentiment == "positive"
    assert parsed[0].mention_count == 2

    assert parsed[1].competitor_name == "CompetitorB"
    assert parsed[1].position_rank is None
    assert parsed[1].is_recommended is False
    assert parsed[1].comparison_sentiment == "neutral"
    assert parsed[1].mention_count == 1
    mock_structlog.warning.assert_not_called()
    mock_structlog.error.assert_not_called()

def test_parse_llm_output_malformed_json(mock_structlog):
    raw_json = "{invalid json"
    competitors = ["CompetitorA"]
    parsed = parse_llm_output(raw_json, "resp1", "audit1", competitors, mock_structlog)
    assert len(parsed) == 0
    mock_structlog.error.assert_called_once()

def test_parse_llm_output_invalid_competitor(mock_structlog):
    raw_json = '''
    {
      "competitor_mentions": [
        {
          "competitor_name": "UnknownComp",
          "position_rank": 1,
          "is_recommended": true,
          "comparison_sentiment": "positive",
          "mention_count": 1
        }
      ]
    }
    '''
    competitors = ["CompetitorA"]
    parsed = parse_llm_output(raw_json, "resp1", "audit1", competitors, mock_structlog)
    assert len(parsed) == 0
    mock_structlog.warning.assert_called_once_with(
        "LLM returned invalid competitor name or one not in list",
        raw_name="UnknownComp",
        response_id="resp1",
        audit_id="audit1",
    )

def test_parse_llm_output_invalid_sentiment(mock_structlog):
    raw_json = '''
    {
      "competitor_mentions": [
        {
          "competitor_name": "CompetitorA",
          "position_rank": 1,
          "is_recommended": true,
          "comparison_sentiment": "unknown_sentiment",
          "mention_count": 1
        }
      ]
    }
    '''
    competitors = ["CompetitorA"]
    parsed = parse_llm_output(raw_json, "resp1", "audit1", competitors, mock_structlog)
    assert len(parsed) == 1
    assert parsed[0].comparison_sentiment == "neutral"
    mock_structlog.warning.assert_called_once_with(
        "LLM returned invalid comparison_sentiment",
        sentiment="unknown_sentiment",
        competitor_name="CompetitorA",
        response_id="resp1",
        audit_id="audit1",
    )


# --- Test competitor_mapper_aggregation.py ---

def test_build_platform_breakdown():
    per_platform_data = {
        "ChatGPT": {
            "appearances": 2,
            "recommendation_count": 1,
            "position_ranks": [1, 3],
            "sentiments": ["positive", "neutral"],
        },
        "Gemini": {
            "appearances": 1,
            "recommendation_count": 0,
            "position_ranks": [2],
            "sentiments": ["negative"],
        },
    }
    breakdown = build_platform_breakdown(per_platform_data)
    assert "ChatGPT" in breakdown
    assert breakdown["ChatGPT"]["appearances"] == 2
    assert breakdown["ChatGPT"]["recommendation_count"] == 1
    assert breakdown["ChatGPT"]["avg_position"] == 2.0
    assert breakdown["ChatGPT"]["dominant_sentiment"] == "neutral" # Positive and neutral, so neutral is fine here.

    assert "Gemini" in breakdown
    assert breakdown["Gemini"]["appearances"] == 1
    assert breakdown["Gemini"]["recommendation_count"] == 0
    assert breakdown["Gemini"]["avg_position"] == 2.0
    assert breakdown["Gemini"]["dominant_sentiment"] == "negative"

def test_aggregate_competitor_records(mock_structlog):
    responses = [
        FilteredResponse("r1", "a1", "text1", "ChatGPT", "q1", "comparative"),
        FilteredResponse("r2", "a1", "text2", "Gemini", "q2", "recommendation"),
    ]
    mentions = [
        CompetitorMentionResult("CompA", 1, True, "positive", 1),
        CompetitorMentionResult("CompB", 2, False, "neutral", 1),
    ]
    mentions2 = [
        CompetitorMentionResult("CompA", 3, False, "negative", 1),
    ]

    all_mentions_across_responses = [
        (responses[0], mentions),
        (responses[1], mentions2),
    ]
    all_competitors = ["CompA", "CompB"]
    audit_id = "a1"

    records = aggregate_competitor_records(all_mentions_across_responses, all_competitors, audit_id, mock_structlog)

    assert len(records) == 2
    comp_a_record = next(r for r in records if r.competitor_name == "CompA")
    comp_b_record = next(r for r in records if r.competitor_name == "CompB")

    assert comp_a_record.audit_id == "a1"
    assert comp_a_record.competitor_name == "CompA"
    assert comp_a_record.avg_mention_position == 2.0 # (1+3)/2
    assert comp_a_record.recommendation_count == 1
    assert comp_a_record.total_appearances == 2
    assert comp_a_record.positive_comparisons == 1
    assert comp_a_record.negative_comparisons == 1
    assert comp_a_record.neutral_comparisons == 0
    assert "ChatGPT" in comp_a_record.platform_breakdown
    assert comp_a_record.platform_breakdown["ChatGPT"]["appearances"] == 1
    assert comp_a_record.platform_breakdown["Gemini"]["dominant_sentiment"] == "negative"

    assert comp_b_record.audit_id == "a1"
    assert comp_b_record.competitor_name == "CompB"
    assert comp_b_record.avg_mention_position == 2.0
    assert comp_b_record.recommendation_count == 0
    assert comp_b_record.total_appearances == 1
    assert comp_b_record.positive_comparisons == 0
    assert comp_b_record.negative_comparisons == 0
    assert comp_b_record.neutral_comparisons == 1
    assert "ChatGPT" in comp_b_record.platform_breakdown
    assert comp_b_record.platform_breakdown["ChatGPT"]["appearances"] == 1
    assert comp_b_record.platform_breakdown["ChatGPT"]["dominant_sentiment"] == "neutral"

def test_competitor_record_to_db_dict():
    record = CompetitorRecord(
        audit_id="a1",
        competitor_name="CompX",
        competitor_domain="compx.com",
        avg_mention_position=1.5,
        recommendation_count=1,
        total_appearances=2,
        positive_comparisons=1,
        negative_comparisons=0,
        neutral_comparisons=1,
        platform_breakdown={"ChatGPT": {"appearances": 2, "avg_position": 1.5}}
    )
    db_dict = competitor_record_to_db_dict(record)
    assert db_dict["audit_id"] == "a1"
    assert db_dict["competitor_name"] == "CompX"
    assert db_dict["competitor_domain"] == "compx.com"
    assert db_dict["avg_mention_position"] == 1.5
    assert db_dict["platform_breakdown"]["ChatGPT"]["appearances"] == 2


# --- Test competitor_mapper/main.py (integration with mocked dependencies) ---

@pytest.mark.asyncio
async def test_competitor_mapper_run_success(
    mock_audit_state, mock_db_client, mock_redis_client, mock_structlog
):
    mock_audit_state.get_db.return_value = mock_db_client

    # Mock fetch_competitors
    mock_db_client.from_.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {"competitors": ["CompA", "CompB"]}

    # Mock fetch_filtered_responses
    mock_db_client.from_.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = [
        {"id": "r1", "response_text": "text1 CompA is great", "platform": "ChatGPT", "audit_queries": {"query_text": "q1", "intent": "comparative"}},
        {"id": "r2", "response_text": "text2 CompB is bad", "platform": "Gemini", "audit_queries": {"query_text": "q2", "intent": "recommendation"}},
    ]

    # Mock LLM calls
    with patch("apps.api.agents.competitor_mapper_data_and_llm_ops.call_analysis_llm", new_callable=AsyncMock) as mock_call_llm:
        mock_call_llm.side_effect = [
            '''{"competitor_mentions": [{"competitor_name": "CompA", "position_rank": 1, "is_recommended": true, "comparison_sentiment": "positive", "mention_count": 1}]}}''',
            '''{"competitor_mentions": [{"competitor_name": "CompB", "position_rank": 1, "is_recommended": false, "comparison_sentiment": "negative", "mention_count": 1}]}'''
        ]
        
        # Mock redis client
        with patch("apps.api.agents.competitor_mapper.main.get_redis_client") as mock_get_redis_client:
            mock_get_redis_client.return_value = mock_redis_client
            mock_redis_client.publish = AsyncMock()
            mock_redis_client.close = AsyncMock()

            final_state = await competitor_mapper_run(mock_audit_state)

            assert final_state.status == AuditStatus.RUNNING
            assert len(final_state.messages) == 3 # Initial, success, final progress
            assert "Successfully mapped 2 competitors." in final_state.messages[-1].content
            assert len(final_state.brand_competitive_stats) == 2
            assert final_state.brand_competitive_stats[0]["competitor_name"] == "CompA"
            mock_db_client.from_.return_value.upsert.assert_called_once()
            mock_redis_client.publish.assert_called()
            mock_redis_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_competitor_mapper_run_no_competitors(
    mock_audit_state, mock_db_client, mock_redis_client, mock_structlog
):
    mock_audit_state.get_db.return_value = mock_db_client
    # Mock fetch_competitors to return empty
    mock_db_client.from_.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = None
    
    with patch("apps.api.agents.competitor_mapper.main.get_redis_client") as mock_get_redis_client:
        mock_get_redis_client.return_value = mock_redis_client
        mock_redis_client.publish = AsyncMock()
        mock_redis_client.close = AsyncMock()

        final_state = await competitor_mapper_run(mock_audit_state)

        assert final_state.status == AuditStatus.RUNNING
        assert "No competitors configured for this company." in final_state.messages[-1].content
        mock_db_client.from_.return_value.upsert.assert_not_called()
        mock_redis_client.publish.assert_called_once() # Initial publish
        mock_redis_client.close.assert_called_once()

@pytest.mark.asyncio
async def test_competitor_mapper_run_no_filtered_responses(
    mock_audit_state, mock_db_client, mock_redis_client, mock_structlog
):
    mock_audit_state.get_db.return_value = mock_db_client
    # Mock fetch_competitors
    mock_db_client.from_.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {"competitors": ["CompA"]}
    # Mock fetch_filtered_responses to return empty
    mock_db_client.from_.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = []

    with patch("apps.api.agents.competitor_mapper.main.get_redis_client") as mock_get_redis_client:
        mock_get_redis_client.return_value = mock_redis_client
        mock_redis_client.publish = AsyncMock()
        mock_redis_client.close = AsyncMock()

        final_state = await competitor_mapper_run(mock_audit_state)

        assert final_state.status == AuditStatus.RUNNING
        assert "No comparative/recommendation responses found." in final_state.messages[-1].content
        mock_db_client.from_.return_value.upsert.assert_not_called()
        mock_redis_client.publish.assert_called_once() # Initial publish
        mock_redis_client.close.assert_called_once()

@pytest.mark.asyncio
async def test_competitor_mapper_run_llm_failure(
    mock_audit_state, mock_db_client, mock_redis_client, mock_structlog
):
    mock_audit_state.get_db.return_value = mock_db_client
    mock_db_client.from_.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {"competitors": ["CompA"]}
    mock_db_client.from_.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value.data = [
        {"id": "r1", "response_text": "text1", "platform": "ChatGPT", "audit_queries": {"query_text": "q1", "intent": "comparative"}},
    ]

    with patch("apps.api.agents.competitor_mapper_data_and_llm_ops.call_analysis_llm", new_callable=AsyncMock) as mock_call_llm:
        mock_call_llm.side_effect = Exception("LLM connection error")

        with patch("apps.api.agents.competitor_mapper.main.get_redis_client") as mock_get_redis_client:
            mock_get_redis_client.return_value = mock_redis_client
            mock_redis_client.publish = AsyncMock()
            mock_redis_client.close = AsyncMock()
            
            final_state = await competitor_mapper_run(mock_audit_state)

            assert final_state.status == AuditStatus.FAILED
            assert "Competitor mapping failed" in final_state.messages[-1].content
            mock_structlog.error.assert_called_with(
                "Competitor Mapper agent failed",
                error="LLM connection error",
                audit_id="test-audit-id",
            )
            mock_db_client.from_.return_value.upsert.assert_not_called()
            mock_redis_client.publish.assert_called()
            mock_redis_client.close.assert_called_once()

