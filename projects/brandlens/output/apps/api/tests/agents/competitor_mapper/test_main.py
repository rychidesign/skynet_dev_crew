import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Tuple

from apps.api.agents.competitor_mapper.main import run as competitor_mapper_run
from apps.api.agents.competitor_mapper_constants_and_types import AuditStatus
from apps.api.agents.competitor_mapper_constants_and_types import CompetitorRecord # For type hinting


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
            '''{"competitor_mentions": [{"competitor_name": "CompA", "position_rank": 1, "is_recommended": true, "comparison_sentiment": "positive", "mention_count": 1}]}''',
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
