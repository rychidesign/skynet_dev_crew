import pytest
import asyncio
import json
import httpx
import structlog
from unittest.mock import AsyncMock, MagicMock
from typing import List, Tuple, Dict

from apps.api.agents.competitor_mapper.models import (
    ResponseRow, CompetitorMention, BrandMentionExtraction, LLMExtractionResult, 
    SingleCompetitorExtraction, PlatformCompetitorBreakdown
)
from apps.api.agents.competitor_mapper import extractor

# Mock structlog for tests
log = structlog.get_logger()

# --- Fixtures ---

@pytest.fixture
def mock_http_client():
    mock = AsyncMock(spec=httpx.AsyncClient)
    mock.post.return_value = MagicMock(spec=httpx.Response, status_code=200)
    mock.post.return_value.json.return_value = {
        "choices": [{"message": {"content": json.dumps({
            "competitors_found": [
                {"name": "Competitor A", "position": 10, "is_recommended_first": True, "sentiment": "positive", "comparative_snippet": "Comp A is better"},
                {"name": "Competitor B", "position": 50, "is_recommended_first": False, "sentiment": "negative", "comparative_snippet": "Comp B is worse"},
            ],
            "brand_mention": {"mentioned": True, "position": 30, "is_recommended_first": False, "sentiment": "neutral", "comparative_snippet": "Our brand is ok"}
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


# --- Tests for Extractor ---

@pytest.mark.asyncio
async def test_extract_from_response_success(mock_http_client, sample_response_rows, sample_competitor_data, mock_log_ctx):
    competitor_names, brand_name, _ = sample_competitor_data
    semaphore = asyncio.Semaphore(1)

    mock_http_client.post.return_value.json.return_value = {
        "choices": [{"message": {"content": json.dumps({
            "competitors_found": [
                {"name": "Competitor A", "position": 10, "is_recommended_first": True, "sentiment": "positive", "comparative_snippet": "Comp A is great"}
            ],
            "brand_mention": {"mentioned": True, "position": 5, "is_recommended_first": False, "sentiment": "neutral", "comparative_snippet": "Brand is here"}
        })}]}
    }

    response_id, mentions, brand_mention = await extractor.extract_from_response(
        sample_response_rows[0], competitor_names, brand_name, semaphore, mock_http_client, mock_log_ctx
    )

    assert response_id == "resp1"
    assert len(mentions) == 1
    assert mentions[0].competitor_name == "Competitor A"
    assert brand_mention is not None
    assert brand_mention.mentioned is True
    mock_log_ctx.info.assert_called_once()

@pytest.mark.asyncio
async def test_extract_from_response_llm_json_error(mock_http_client, sample_response_rows, sample_competitor_data, mock_log_ctx):
    competitor_names, brand_name, _ = sample_competitor_data
    semaphore = asyncio.Semaphore(1)

    mock_http_client.post.return_value.json.return_value = {
        "choices": [{"message": {"content": "NOT VALID JSON"}}]
    }
    mock_http_client.post.return_value.raise_for_status = MagicMock()

    response_id, mentions, brand_mention = await extractor.extract_from_response(
        sample_response_rows[0], competitor_names, brand_name, semaphore, mock_http_client, mock_log_ctx
    )

    assert response_id == "resp1"
    assert len(mentions) == 0
    assert brand_mention is None
    mock_log_ctx.error.assert_called_once_with("Failed to parse LLM extraction result or invalid LLM response", exc=f"Failed to parse LLM response: {json.JSONDecodeError(\"Expecting value\", \"NOT VALID JSON\", 0)}")
