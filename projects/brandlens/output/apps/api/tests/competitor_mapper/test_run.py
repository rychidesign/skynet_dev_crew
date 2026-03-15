import pytest
import asyncio
import json
import httpx
import structlog
from unittest.mock import AsyncMock, MagicMock
from typing import List, Tuple, Dict, Optional

from apps.api.core.state import AuditState, AgentMessage
from apps.api.models.audit import AuditStatus
from apps.api.agents.competitor_mapper.models import (
    ResponseRow, CompetitorMention, BrandMentionExtraction, CompetitorStats, BrandCompetitiveStats
)
from apps.api.agents.competitor_mapper import db_ops, extractor, aggregator, progress
from apps.api.agents.competitor_mapper.run import run as competitor_mapper_run # Import the run function to test

# Mock structlog for tests
log = structlog.get_logger()

# --- Fixtures ---

@pytest.fixture
def mock_db_client():
    return AsyncMock()

@pytest.fixture
def mock_redis_client():
    return AsyncMock()

@pytest.fixture
def mock_http_client():
    mock = AsyncMock(spec=httpx.AsyncClient)
    mock.post.return_value = MagicMock(spec=httpx.Response, status_code=200)
    mock.post.return_value.json.return_value = {
        "choices": [{"message": {"content": json.dumps({
            "competitors_found": [],
            "brand_mention": {"mentioned": False}
        })}]}
    }
    return mock

@pytest.fixture
def sample_response_rows() -> List[ResponseRow]:
    return [
        ResponseRow(id="resp1", response_text="This is about Competitor A and brand.", platform="chatgpt", query_id="q1", query_text="compare", query_intent="comparative", audit_id="audit1"),
        ResponseRow(id="resp2", response_text="Consider Competitor B over brand.", platform="perplexity", query_id="q2", query_text="recommend", query_intent="recommendation", audit_id="audit1"),
    ]

@pytest.fixture
def sample_competitor_data() -> Tuple[List[str], str, Dict[str, str]]:
    return ["Competitor A", "Competitor B"], "Our Brand", {"Competitor A": "compA.com", "Competitor B": "compB.com"}

@pytest.fixture
def mock_log_ctx():
    return MagicMock(spec=structlog.BoundLogger)

# --- Tests for the full agent run ---

@pytest.mark.asyncio
async def test_competitor_mapper_run_success(mock_db_client, mock_redis_client, mock_http_client, sample_response_rows, sample_competitor_data):
    # Mock db_ops functions
    mock_db_client.from_.return_value.select.return_value.eq.return_value.in_.return_value.data = [
        {"id": "resp1", "response_text": "text1", "platform": "chatgpt", "query_id": "q1", "audit_id": "audit1", "audit_queries": {"id": "q1", "query_text": "qtext1", "intent": "comparative"}},
        {"id": "resp2", "response_text": "text2", "platform": "perplexity", "query_id": "q2", "audit_id": "audit1", "audit_queries": {"id": "q2", "query_text": "qtext2", "intent": "recommendation"}},
    ]
    mock_db_client.from_.return_value.select.return_value.eq.return_value.in_.return_value.count = 2

    mock_db_client.from_.return_value.select.return_value.eq.return_value.single.return_value.data = {
        "name": "Our Brand",
        "competitors": [
            {"name": "Competitor A", "domain": "compA.com"},
            {"name": "Competitor B", "domain": "compB.com"}
        ]
    }
    mock_db_client.from_.return_value.upsert.return_value.error = None

    # Mock extractor, aggregator, progress to simplify test of `run` orchestration
    competitor_mapper_run.extractor.extract_from_response = AsyncMock(side_effect=[
        ("resp1", [
            CompetitorMention(competitor_name="Competitor A", platform="chatgpt", response_id="resp1", query_intent="comparative", mention_position=10, is_recommended_first=True, sentiment="positive", comparative_language="A is good")]
        , BrandMentionExtraction(mentioned=True, position=5, is_recommended_first=False, sentiment="neutral")), # type: ignore
        ("resp2", [
            CompetitorMention(competitor_name="Competitor B", platform="perplexity", response_id="resp2", query_intent="recommendation", mention_position=50, is_recommended_first=False, sentiment="negative", comparative_language="B is bad")]
        , BrandMentionExtraction(mentioned=False)), # type: ignore
    ])
    competitor_mapper_run.aggregator.aggregate_competitors = MagicMock(return_value=(
        [
            CompetitorStats(competitor_name="Competitor A", competitor_domain="compA.com", total_appearances=1, recommendation_count=1, positive_comparisons=1),
            CompetitorStats(competitor_name="Competitor B", competitor_domain="compB.com", total_appearances=1, recommendation_count=0, negative_comparisons=1),
        ],
        BrandCompetitiveStats(brand_name="Our Brand", total_comparative_responses=2, recommendation_count=0, neutral_comparisons=1)
    ))
    competitor_mapper_run.progress.publish_progress = AsyncMock()

    # Mock dependencies setup for the agent `run` function
    with (MagicMock(return_value=mock_db_client) as get_db_client_mock,
          MagicMock(return_value=mock_redis_client) as get_redis_client_mock,
          MagicMock(return_value=mock_http_client) as AsyncClient_mock):

        competitor_mapper_run.db_ops.get_db_client = get_db_client_mock # Mock internal module dependency
        competitor_mapper_run.progress.get_redis_client = get_redis_client_mock # Mock internal module dependency
        competitor_mapper_run.httpx.AsyncClient = AsyncClient_mock # Mock httpx client
        competitor_mapper_run.get_db_client = get_db_client_mock # Mock directly used dependencies in run.py
        competitor_mapper_run.get_redis_client = get_redis_client_mock # Mock directly used dependencies in run.py


        initial_state = AuditState(audit_id="audit1", company_id="company1", messages=[], company_name="Our Brand")
        initial_state.response_rows = sample_response_rows # Add response_rows to state for cleaner testing
        final_state = await competitor_mapper_run.run(initial_state)

        assert final_state.competitor_mapper_done is True
        assert final_state.error is None
        assert len(final_state.competitor_results) == 2
        assert final_state.brand_competitive_stats is not None
        assert final_state.brand_competitive_stats.brand_name == "Our Brand"

        mock_db_client.from_.return_value.select.assert_called()
        mock_db_client.from_.return_value.upsert.assert_called_once()
        competitor_mapper_run.extractor.extract_from_response.assert_called_with(
            initial_state.response_rows[0], ['Competitor A', 'Competitor B'], 'Our Brand', 
            competitor_mapper_run.asyncio.Semaphore(5), mock_http_client, competitor_mapper_run.log.bind(audit_id='audit1', company_id='company1', agent='competitor_mapper')
        )
        competitor_mapper_run.progress.publish_progress.assert_called_once()
        mock_http_client.aclose.assert_called_once()

@pytest.mark.asyncio
async def test_competitor_mapper_run_no_comparative_responses(mock_db_client, mock_redis_client, mock_http_client, sample_competitor_data):
    # Mock db_ops to return no responses
    mock_db_client.from_.return_value.select.return_value.eq.return_value.in_.return_value.data = []
    mock_db_client.from_.return_value.select.return_value.eq.return_value.in_.return_value.count = 0
    mock_db_client.from_.return_value.select.return_value.eq.return_value.single.return_value.data = {"name": "Our Brand", "competitors": []}

    competitor_mapper_run.progress.publish_progress = AsyncMock()

    with (MagicMock(return_value=mock_db_client) as get_db_client_mock,
          MagicMock(return_value=mock_redis_client) as get_redis_client_mock,
          MagicMock(return_value=mock_http_client) as AsyncClient_mock):

        competitor_mapper_run.db_ops.get_db_client = get_db_client_mock
        competitor_mapper_run.progress.get_redis_client = get_redis_client_mock
        competitor_mapper_run.httpx.AsyncClient = AsyncClient_mock
        competitor_mapper_run.get_db_client = get_db_client_mock # Mock directly used dependencies in run.py
        competitor_mapper_run.get_redis_client = get_redis_client_mock # Mock directly used dependencies in run.py

        initial_state = AuditState(audit_id="audit1", company_id="company1", messages=[], company_name="Our Brand")
        final_state = await competitor_mapper_run.run(initial_state)

        assert final_state.competitor_mapper_done is True
        assert final_state.error is None
        assert final_state.competitor_results is None
        assert final_state.brand_competitive_stats is None
        competitor_mapper_run.progress.publish_progress.assert_called_once_with(mock_redis_client, "audit1", 0, 0, 0, MagicMock())
        mock_http_client.aclose.assert_called_once()

@pytest.mark.asyncio
async def test_competitor_mapper_run_failure(mock_db_client, mock_redis_client, mock_http_client):
    # Mock db_ops to raise an exception
    mock_db_client.from_.return_value.select.side_effect = Exception("DB Error")

    with (MagicMock(return_value=mock_db_client) as get_db_client_mock,
          MagicMock(return_value=mock_redis_client) as get_redis_client_mock,
          MagicMock(return_value=mock_http_client) as AsyncClient_mock):

        competitor_mapper_run.db_ops.get_db_client = get_db_client_mock
        competitor_mapper_run.progress.get_redis_client = get_redis_client_mock
        competitor_mapper_run.httpx.AsyncClient = AsyncClient_mock
        competitor_mapper_run.get_db_client = get_db_client_mock # Mock directly used dependencies in run.py
        competitor_mapper_run.get_redis_client = get_redis_client_mock # Mock directly used dependencies in run.py

        initial_state = AuditState(audit_id="audit1", company_id="company1", messages=[], company_name="Our Brand")
        final_state = await competitor_mapper_run.run(initial_state)

        assert final_state.competitor_mapper_done is True
        assert final_state.error is not None
        assert final_state.error.type == "error"
        assert "DB Error" in final_state.error.content
        mock_http_client.aclose.assert_called_once()
