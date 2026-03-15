import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from postgrest.exceptions import APIResponseError

from apps.api.agents.mention_analyzer import run, AGENT_NAME, ANALYSIS_SEMAPHORE_SIZE
from apps.api.agents.mention_analysis_helpers import MentionRecord, ResponseRow, make_absent_mention, build_analysis_prompt, parse_llm_output, SYSTEM_PROMPT
from apps.api.core.state import AuditState, AgentMessage
from apps.api.models.audit import AuditStatus, ProgressUpdate
from apps.api.core.config import settings

# Mock settings for consistent testing
@pytest.fixture(autouse=True)
def mock_settings():
    with patch('apps.api.core.config.settings') as mock_settings:
        mock_settings.OPENAI_API_KEY = "sk-test"
        mock_settings.OPENAI_API_BASE_URL = "https://api.openai.com/v1"
        mock_settings.OPENAI_MODEL_FAST_DEFAULT = "gpt-4o-mini"
        yield mock_settings

@pytest.fixture
def mock_db():
    mock = AsyncMock()
    mock.from_().select().eq().single().execute.return_value = MagicMock(data={'name': 'TestCompany'}, raise_for_status=lambda: None)
    mock.from_().select().eq().order().execute.return_value = MagicMock(data=[], raise_for_status=lambda: None)
    mock.from_().insert().execute.return_value = MagicMock(raise_for_status=lambda: None)
    return mock

@pytest.fixture
def mock_redis():
    mock = AsyncMock()
    mock.publish.return_value = None
    mock.close.return_value = None
    return mock

@pytest.fixture
def mock_http_client():
    mock = AsyncMock()
    mock.post.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "choices": [
                {"message": {"content": json.dumps({
                    "mentions": [
                        {
                            "entity_name": "TestCompany",
                            "mention_type": "primary",
                            "position_rank": 1,
                            "sentiment_score": 0.8,
                            "sentiment_label": "positive",
                            "authority_markers": ["leading"],
                            "is_authority_cite": True,
                            "extracted_attributes": {"category": "Software"},
                            "is_confused": False,
                            "confusion_note": None
                        }
                    ]
                })}}
            ]
        },
        raise_for_status=lambda: None
    )
    mock.aclose.return_value = None
    return mock

@pytest.fixture
def mock_log():
    return MagicMock()

@pytest.fixture
def audit_state():
    return AuditState(
        audit_id="test-audit-id",
        company_id="test-company-id",
        status=AuditStatus.INITIALIZED,
        messages=[],
        current_agent=None,
        error=None,
    )


@pytest.mark.asyncio
async def test_run_mention_analyzer_no_responses(audit_state, mock_db, mock_redis, mock_http_client, mock_log):
    with patch('apps.api.core.dependencies.get_service_db', return_value=mock_db),
         patch('apps.api.core.redis_client.get_redis_client', return_value=mock_redis),
         patch('httpx.AsyncClient', return_value=mock_http_client),
         patch('structlog.get_logger', return_value=mock_log):

        initial_state = audit_state
        initial_state.company_id = "company-123"

        # Mock get_service_db to return a company name
        mock_db.from_().select('name').eq('id', 'company-123').single().execute.return_value = AsyncMock(
            data={'name': 'TestCompany'},
            raise_for_status=lambda: None
        )

        # Mock no responses
        mock_db.from_('audit_responses').select().eq().order().execute.return_value = AsyncMock(
            data=[],
            raise_for_status=lambda: None
        )

        result_state = await run(initial_state)

        assert result_state.status == AuditStatus.ANALYZING # Should remain analyzing or be completed quickly
        assert any("No responses to analyze" in msg.message for msg in result_state.messages)
        mock_log.info.assert_any_call("No audit responses found for analysis.")
        mock_redis.publish.assert_called_once() # Progress should still be published
        mock_http_client.aclose.assert_called_once()


@pytest.mark.asyncio
@patch('apps.api.agents.mention_analyzer._call_llm_with_retry')
async def test_run_mention_analyzer_success(
    mock_call_llm_with_retry, audit_state, mock_db, mock_redis, mock_http_client, mock_log
):
    with patch('apps.api.core.dependencies.get_service_db', return_value=mock_db),
         patch('apps.api.core.redis_client.get_redis_client', return_value=mock_redis),
         patch('httpx.AsyncClient', return_value=mock_http_client),
         patch('structlog.get_logger', return_value=mock_log):

        company_name = "TestCompany"
        audit_id = audit_state.audit_id
        response_id_1 = "resp-1"
        response_id_2 = "resp-2"
        query_id_1 = "query-1"
        query_id_2 = "query-2"
        query_text_1 = "What is TestCompany?"
        query_text_2 = "TestCompany reviews"

        # Mock fetching company name
        mock_db.from_().select('name').eq('id', audit_state.company_id).single().execute.return_value = AsyncMock(
            data={'name': company_name},
            raise_for_status=lambda: None
        )
        
        # Mock fetching responses
        mock_db.from_('audit_responses').select(
            "id, response_text, platform, audit_queries(query_text)"
        ).eq('audit_id', audit_id).order('created_at').execute.return_value = AsyncMock(
            data=[
                {"id": response_id_1, "response_text": "TestCompany is great!", "platform": "ChatGPT", "audit_queries": {"query_text": query_text_1}},
                {"id": response_id_2, "response_text": "Reviews for TestCompany are mixed.", "platform": "Google", "audit_queries": {"query_text": query_text_2}}
            ],
            raise_for_status=lambda: None
        )

        # Mock LLM calls
        mock_call_llm_with_retry.side_effect = [
            json.dumps({"mentions": [{"entity_name": company_name, "mention_type": "primary", "position_rank": 1, "sentiment_score": 0.9, "sentiment_label": "positive", "authority_markers": [], "is_authority_cite": False, "extracted_attributes": {}, "is_confused": False, "confusion_note": None}]}),
            json.dumps({"mentions": [{"entity_name": company_name, "mention_type": "secondary", "position_rank": 2, "sentiment_score": 0.1, "sentiment_label": "neutral", "authority_markers": [], "is_authority_cite": False, "extracted_attributes": {}, "is_confused": False, "confusion_note": None}]})
        ]

        result_state = await run(audit_state)

        assert result_state.status == AuditStatus.ANALYZING  # Should still be analyzing until next agent
        assert any(f"Analyzed 2 mentions across 2 responses." in msg.message for msg in result_state.messages)
        assert mock_call_llm_with_retry.call_count == 2
        mock_db.from_('audit_mentions').insert.assert_called_once()
        inserted_mentions = mock_db.from_('audit_mentions').insert.call_args[0][0]
        assert len(inserted_mentions) == 2
        assert inserted_mentions[0]['response_id'] == response_id_1
        assert inserted_mentions[1]['response_id'] == response_id_2
        mock_redis.publish.assert_called_once()
        mock_http_client.aclose.assert_called_once()

@pytest.mark.asyncio
@patch('apps.api.agents.mention_analyzer._call_llm_with_retry')
async def test_run_mention_analyzer_llm_failure(
    mock_call_llm_with_retry, audit_state, mock_db, mock_redis, mock_http_client, mock_log
):
    with patch('apps.api.core.dependencies.get_service_db', return_value=mock_db),
         patch('apps.api.core.redis_client.get_redis_client', return_value=mock_redis),
         patch('httpx.AsyncClient', return_value=mock_http_client),
         patch('structlog.get_logger', return_value=mock_log):
        
        company_name = "TestCompany"
        audit_id = audit_state.audit_id
        response_id_1 = "resp-1"
        query_id_1 = "query-1"
        query_text_1 = "What is TestCompany?"

        # Mock fetching company name
        mock_db.from_().select('name').eq('id', audit_state.company_id).single().execute.return_value = AsyncMock(
            data={'name': company_name},
            raise_for_status=lambda: None
        )

        # Mock responses
        mock_db.from_('audit_responses').select(
            "id, response_text, platform, audit_queries(query_text)"
        ).eq('audit_id', audit_id).order('created_at').execute.return_value = AsyncMock(
            data=[
                {"id": response_id_1, "response_text": "TestCompany is great!", "platform": "ChatGPT", "audit_queries": {"query_text": query_text_1}}
            ],
            raise_for_status=lambda: None
        )

        # Mock LLM call to raise an exception
        mock_call_llm_with_retry.side_effect = Exception("LLM API error")

        result_state = await run(audit_state)

        assert result_state.status == AuditStatus.ANALYZING # Even with LLM failure, agent should try to process others
        assert any("An individual response analysis failed." in call.args[0] for call in mock_log.error.call_args_list) 
        mock_db.from_('audit_mentions').insert.assert_called_once() # Should insert the absent mention
        inserted_mentions = mock_db.from_('audit_mentions').insert.call_args[0][0]
        assert len(inserted_mentions) == 1
        assert inserted_mentions[0]['mention_type'] == 'absent'
        mock_redis.publish.assert_called_once()
        mock_http_client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_run_mention_analyzer_db_fetch_failure(audit_state, mock_db, mock_redis, mock_http_client, mock_log):
    with patch('apps.api.core.dependencies.get_service_db', return_value=mock_db),
         patch('apps.api.core.redis_client.get_redis_client', return_value=mock_redis),
         patch('httpx.AsyncClient', return_value=mock_http_client),
         patch('structlog.get_logger', return_value=mock_log):
        
        # Mock DB fetch to fail for company name
        mock_db.from_().select('name').eq('id', audit_state.company_id).single().execute.return_value = AsyncMock(
            data=None,
            raise_for_status=MagicMock(side_effect=APIResponseError("Not Found", 404))
        )

        result_state = await run(audit_state)

        assert result_state.status == AuditStatus.FAILED
        assert "Mention analysis failed" in result_state.error
        mock_log.error.assert_any_call("Mention Analyzer agent failed.", error=f"Mention analysis failed: Not Found") # Check the specific error message
        mock_http_client.aclose.assert_called_once()
        assert not mock_redis.publish.called # No progress update if initial fetch fails


@pytest.mark.asyncio
@patch('apps.api.agents.mention_analyzer._call_llm_with_retry')
async def test_run_mention_analyzer_empty_response_text(
    mock_call_llm_with_retry, audit_state, mock_db, mock_redis, mock_http_client, mock_log
):
    with patch('apps.api.core.dependencies.get_service_db', return_value=mock_db),
         patch('apps.api.core.redis_client.get_redis_client', return_value=mock_redis),
         patch('httpx.AsyncClient', return_value=mock_http_client),
         patch('structlog.get_logger', return_value=mock_log):
        
        company_name = "TestCompany"
        audit_id = audit_state.audit_id
        response_id_1 = "resp-1"
        query_id_1 = "query-1"
        query_text_1 = "What is TestCompany?"

        # Mock fetching company name
        mock_db.from_().select('name').eq('id', audit_state.company_id).single().execute.return_value = AsyncMock(
            data={'name': company_name},
            raise_for_status=lambda: None
        )

        # Mock responses with empty text
        mock_db.from_('audit_responses').select(
            "id, response_text, platform, audit_queries(query_text)"
        ).eq('audit_id', audit_id).order('created_at').execute.return_value = AsyncMock(
            data=[
                {"id": response_id_1, "response_text": "   ", "platform": "ChatGPT", "audit_queries": {"query_text": query_text_1}}
            ],
            raise_for_status=lambda: None
        )

        result_state = await run(audit_state)

        assert result_state.status == AuditStatus.ANALYZING
        mock_call_llm_with_retry.assert_not_called() # LLM should not be called for empty text
        mock_db.from_('audit_mentions').insert.assert_called_once()
        inserted_mentions = mock_db.from_('audit_mentions').insert.call_args[0][0]
        assert len(inserted_mentions) == 1
        assert inserted_mentions[0]['mention_type'] == 'absent'
        mock_log.info.assert_any_call("Empty response text, creating an absent mention record.")
        mock_redis.publish.assert_called_once()
        mock_http_client.aclose.assert_called_once()

@pytest.mark.asyncio
@patch('apps.api.agents.mention_analyzer._call_llm_with_retry')
async def test_parse_llm_output_absent_mention_fallback(
    mock_call_llm_with_retry, audit_state, mock_db, mock_redis, mock_http_client, mock_log
):
    with patch('apps.api.core.dependencies.get_service_db', return_value=mock_db),
         patch('apps.api.core.redis_client.get_redis_client', return_value=mock_redis),
         patch('httpx.AsyncClient', return_value=mock_http_client),
         patch('structlog.get_logger', return_value=mock_log):
        
        company_name = "TestCompany"
        audit_id = audit_state.audit_id
        response_id = "resp-absent"
        query_text = "test query"

        # Mock company fetch
        mock_db.from_().select('name').eq('id', audit_state.company_id).single().execute.return_value = AsyncMock(
            data={'name': company_name},
            raise_for_status=lambda: None
        )

        # Mock responses
        mock_db.from_('audit_responses').select(
            "id, response_text, platform, audit_queries(query_text)"
        ).eq('audit_id', audit_id).order('created_at').execute.return_value = AsyncMock(
            data=[{"id": response_id, "response_text": "No mention here.", "platform": "ChatGPT", "audit_queries": {"query_text": query_text}}],
            raise_for_status=lambda: None
        )

        # Mock LLM output to be empty or malformed, triggering absent mention fallback
        mock_call_llm_with_retry.side_effect = [
            json.dumps({"mentions": []}), # Empty mentions list
        ]

        result_state = await run(audit_state)

        assert result_state.status == AuditStatus.ANALYZING
        mock_db.from_('audit_mentions').insert.assert_called_once()
        inserted_mentions = mock_db.from_('audit_mentions').insert.call_args[0][0]
        assert len(inserted_mentions) == 1
        assert inserted_mentions[0]['mention_type'] == 'absent'
        mock_log.warning.assert_any_call("LLM output yielded no valid mentions after parsing, creating a fallback absent mention.", response_id=response_id)
        mock_redis.publish.assert_called_once()
        mock_http_client.aclose.assert_called_once()


@pytest.mark.asyncio
@patch('apps.api.agents.mention_analyzer._call_llm_with_retry')
async def test_parse_llm_output_malformed_json_fallback(
    mock_call_llm_with_retry, audit_state, mock_db, mock_redis, mock_http_client, mock_log
):
    with patch('apps.api.core.dependencies.get_service_db', return_value=mock_db),
         patch('apps.api.core.redis_client.get_redis_client', return_value=mock_redis),
         patch('httpx.AsyncClient', return_value=mock_http_client),
         patch('structlog.get_logger', return_value=mock_log):
        
        company_name = "TestCompany"
        audit_id = audit_state.audit_id
        response_id = "resp-malformed"
        query_text = "test query"

        # Mock company fetch
        mock_db.from_().select('name').eq('id', audit_state.company_id).single().execute.return_value = AsyncMock(
            data={'name': company_name},
            raise_for_status=lambda: None
        )

        # Mock responses
        mock_db.from_('audit_responses').select(
            "id, response_text, platform, audit_queries(query_text)"
        ).eq('audit_id', audit_id).order('created_at').execute.return_value = AsyncMock(
            data=[{"id": response_id, "response_text": "No mention here.", "platform": "ChatGPT", "audit_queries": {"query_text": query_text}}],
            raise_for_status=lambda: None
        )

        # Mock LLM output to be malformed JSON
        mock_call_llm_with_retry.side_effect = [
            "This is not valid JSON"
        ]

        result_state = await run(audit_state)

        assert result_state.status == AuditStatus.ANALYZING
        mock_db.from_('audit_mentions').insert.assert_called_once()
        inserted_mentions = mock_db.from_('audit_mentions').insert.call_args[0][0]
        assert len(inserted_mentions) == 1
        assert inserted_mentions[0]['mention_type'] == 'absent'
        mock_log.error.assert_any_call("Failed to decode LLM JSON response.", error="Expecting value: line 1 column 1 (char 0)", raw_json="This is not valid JSON", response_id=response_id)
        mock_redis.publish.assert_called_once()
        mock_http_client.aclose.assert_called_once()

@pytest.mark.asyncio
@patch('apps.api.agents.mention_analyzer._call_llm_with_retry')
async def test_parse_llm_output_invalid_mention_type_fallback(
    mock_call_llm_with_retry, audit_state, mock_db, mock_redis, mock_http_client, mock_log
):
    with patch('apps.api.core.dependencies.get_service_db', return_value=mock_db),
         patch('apps.api.core.redis_client.get_redis_client', return_value=mock_redis),
         patch('httpx.AsyncClient', return_value=mock_http_client),
         patch('structlog.get_logger', return_value=mock_log):
        
        company_name = "TestCompany"
        audit_id = audit_state.audit_id
        response_id = "resp-invalid-type"
        query_text = "test query"

        # Mock company fetch
        mock_db.from_().select('name').eq('id', audit_state.company_id).single().execute.return_value = AsyncMock(
            data={'name': company_name},
            raise_for_status=lambda: None
        )

        # Mock responses
        mock_db.from_('audit_responses').select(
            "id, response_text, platform, audit_queries(query_text)"
        ).eq('audit_id', audit_id).order('created_at').execute.return_value = AsyncMock(
            data=[{"id": response_id, "response_text": "TestCompany is here.", "platform": "ChatGPT", "audit_queries": {"query_text": query_text}}],
            raise_for_status=lambda: None
        )

        # Mock LLM output with invalid mention_type
        mock_call_llm_with_retry.side_effect = [
            json.dumps({"mentions": [{"entity_name": company_name, "mention_type": "invalid", "position_rank": 1, "sentiment_score": 0.5, "sentiment_label": "positive", "authority_markers": [], "is_authority_cite": False, "extracted_attributes": {}, "is_confused": False, "confusion_note": None}]}),
        ]

        result_state = await run(audit_state)

        assert result_state.status == AuditStatus.ANALYZING
        mock_db.from_('audit_mentions').insert.assert_called_once()
        inserted_mentions = mock_db.from_('audit_mentions').insert.call_args[0][0]
        assert len(inserted_mentions) == 1
        assert inserted_mentions[0]['mention_type'] == 'secondary' # Should fallback to secondary
        mock_log.warning.assert_any_call("Invalid mention_type from LLM, defaulting to 'secondary'.", original_type="invalid")
        mock_redis.publish.assert_called_once()
        mock_http_client.aclose.assert_called_once()

@pytest.mark.asyncio
@patch('apps.api.agents.mention_analyzer._call_llm_with_retry')
async def test_parse_llm_output_sentiment_clamping(
    mock_call_llm_with_retry, audit_state, mock_db, mock_redis, mock_http_client, mock_log
):
    with patch('apps.api.core.dependencies.get_service_db', return_value=mock_db),
         patch('apps.api.core.redis_client.get_redis_client', return_value=mock_redis),
         patch('httpx.AsyncClient', return_value=mock_http_client),
         patch('structlog.get_logger', return_value=mock_log):
        
        company_name = "TestCompany"
        audit_id = audit_state.audit_id
        response_id = "resp-clamping"
        query_text = "test query"

        # Mock company fetch
        mock_db.from_().select('name').eq('id', audit_state.company_id).single().execute.return_value = AsyncMock(
            data={'name': company_name},
            raise_for_status=lambda: None
        )

        # Mock responses
        mock_db.from_('audit_responses').select(
            "id, response_text, platform, audit_queries(query_text)"
        ).eq('audit_id', audit_id).order('created_at').execute.return_value = AsyncMock(
            data=[{"id": response_id, "response_text": "TestCompany is here.", "platform": "ChatGPT", "audit_queries": {"query_text": query_text}}],
            raise_for_status=lambda: None
        )

        # Mock LLM output with out-of-range sentiment score
        mock_call_llm_with_retry.side_effect = [
            json.dumps({"mentions": [{"entity_name": company_name, "mention_type": "primary", "position_rank": 1, "sentiment_score": 5.0, "sentiment_label": "positive", "authority_markers": [], "is_authority_cite": False, "extracted_attributes": {}, "is_confused": False, "confusion_note": None}]}),
        ]

        result_state = await run(audit_state)

        assert result_state.status == AuditStatus.ANALYZING
        mock_db.from_('audit_mentions').insert.assert_called_once()
        inserted_mentions = mock_db.from_('audit_mentions').insert.call_args[0][0]
        assert len(inserted_mentions) == 1
        assert inserted_mentions[0]['sentiment_score'] == 1.0 # Should be clamped to 1.0
        mock_log.warning.assert_any_call("Sentiment score from LLM out of range, clamping.", original_score=5.0)
        mock_redis.publish.assert_called_once()
        mock_http_client.aclose.assert_called_once()


@pytest.mark.asyncio
@patch('apps.api.agents.mention_analyzer._call_llm_with_retry')
async def test_parse_llm_output_extracted_attributes_invalid_key_products(
    mock_call_llm_with_retry, audit_state, mock_db, mock_redis, mock_http_client, mock_log
):
    with patch('apps.api.core.dependencies.get_service_db', return_value=mock_db),
         patch('apps.api.core.redis_client.get_redis_client', return_value=mock_redis),
         patch('httpx.AsyncClient', return_value=mock_http_client),
         patch('structlog.get_logger', return_value=mock_log):
        
        company_name = "TestCompany"
        audit_id = audit_state.audit_id
        response_id = "resp-invalid-key-products"
        query_text = "test query"

        # Mock company fetch
        mock_db.from_().select('name').eq('id', audit_state.company_id).single().execute.return_value = AsyncMock(
            data={'name': company_name},
            raise_for_status=lambda: None
        )

        # Mock responses
        mock_db.from_('audit_responses').select(
            "id, response_text, platform, audit_queries(query_text)"
        ).eq('audit_id', audit_id).order('created_at').execute.return_value = AsyncMock(
            data=[{"id": response_id, "response_text": "TestCompany has ProductA.", "platform": "ChatGPT", "audit_queries": {"query_text": query_text}}],
            raise_for_status=lambda: None
        )

        # Mock LLM output with invalid key_products
        mock_call_llm_with_retry.side_effect = [
            json.dumps({"mentions": [{"entity_name": company_name, "mention_type": "primary", "position_rank": 1, "sentiment_score": 0.5, "sentiment_label": "positive", "authority_markers": [], "is_authority_cite": False, "extracted_attributes": {"key_products": "ProductA"}, "is_confused": False, "confusion_note": None}]}),
        ]

        result_state = await run(audit_state)

        assert result_state.status == AuditStatus.ANALYZING
        mock_db.from_('audit_mentions').insert.assert_called_once()
        inserted_mentions = mock_db.from_('audit_mentions').insert.call_args[0][0]
        assert len(inserted_mentions) == 1
        assert inserted_mentions[0]['extracted_attributes']['key_products'] == [] # Should be an empty list
        mock_log.warning.assert_any_call("Invalid key_products format in extracted_attributes, defaulting to empty list.", original_key_products="ProductA")
        mock_redis.publish.assert_called_once()
        mock_http_client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_call_llm_with_retry_api_error_retries_and_fails(mock_http_client, mock_log):
    mock_http_client.post.side_effect = [
        httpx.HTTPStatusError("Bad Request", request=httpx.Request("GET", "http://test.com"), response=httpx.Response(400)),
        httpx.HTTPStatusError("Bad Request", request=httpx.Request("GET", "http://test.com"), response=httpx.Response(400)),
        httpx.HTTPStatusError("Bad Request", request=httpx.Request("GET", "http://test.com"), response=httpx.Response(400))
    ]

    with pytest.raises(httpx.HTTPStatusError):
        await run_test_call_llm_with_retry(mock_http_client, mock_log)
    
    assert mock_http_client.post.call_count == 3

async def run_test_call_llm_with_retry(mock_http_client, mock_log):
    from apps.api.agents.mention_analyzer import _call_llm_with_retry
    await _call_llm_with_retry(mock_http_client, "test prompt", "gpt-4o-mini", "test-key", mock_log)


@pytest.mark.asyncio
async def test_call_llm_with_retry_api_rate_limit_and_success(mock_http_client, mock_log):
    mock_http_client.post.side_effect = [
        MagicMock(
            status_code=429,
            headers={"Retry-After": "1"},
            raise_for_status=MagicMock(side_effect=httpx.HTTPStatusError("Too Many Requests", request=httpx.Request("GET", "http://test.com"), response=httpx.Response(429, headers={"Retry-After": "1"})))
        ),
        MagicMock(
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": "{}"}}]}, # Empty but valid JSON
            raise_for_status=lambda: None
        ),
    ]

    response_content = await run_test_call_llm_with_retry(mock_http_client, mock_log)
    assert response_content == "{}"
    assert mock_http_client.post.call_count == 2 # 1 failure + 1 success
    mock_log.warning.assert_any_call("LLM rate limit hit (429), retrying after delay.", retry_after=1)


@pytest.mark.asyncio
async def test_batch_insert_mentions_empty_list(mock_db, mock_log):
    from apps.api.agents.mention_analyzer import _batch_insert_mentions
    await _batch_insert_mentions(mock_db, [], "test-audit-id", mock_log)
    mock_db.from_.assert_not_called()
    mock_log.info.assert_any_call("No mentions to insert for audit.", audit_id="test-audit-id")

@pytest.mark.asyncio
async def test_batch_insert_mentions_db_failure(mock_db, mock_log):
    from apps.api.agents.mention_analyzer import _batch_insert_mentions
    mock_db.from_().insert().execute.return_value = MagicMock(raise_for_status=MagicMock(side_effect=APIResponseError("DB Error", 500)))
    mentions = [make_absent_mention("resp-1", "audit-1", "Company")]

    with pytest.raises(APIResponseError):
        await _batch_insert_mentions(mock_db, mentions, "audit-1", mock_log)
    
    mock_log.error.assert_any_call("Failed to batch insert mentions.", audit_id="audit-1", error="DB Error")
