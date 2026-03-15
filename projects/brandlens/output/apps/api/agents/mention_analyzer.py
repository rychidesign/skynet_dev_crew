"""Mention Analyzer Agent - analyzes mentions in AI responses."""
import asyncio
import json
from typing import List, Any

import httpx
import structlog
from postgrest import APIResponse

from apps.api.core.state import AuditState, AgentMessage
from apps.api.core.redis_client import get_redis_client
from apps.api.core.config import settings
from apps.api.core.dependencies import get_service_db
from apps.api.models.audit import AuditStatus, ProgressUpdate

from apps.api.agents.mention_analysis_helpers import (
    MentionRecord, ResponseRow, make_absent_mention,
    build_analysis_prompt, parse_llm_output, mention_record_to_db_dict,
    SYSTEM_PROMPT, ANALYSIS_SEMAPHORE_SIZE, LLM_TIMEOUT_SECONDS, LLM_TEMPERATURE
)

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

log = structlog.get_logger(__name__)
AGENT_NAME = "mention_analyzer"

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8),
       retry=retry_if_exception_type(httpx.RequestError) | retry_if_exception_type(httpx.HTTPStatusError), reraise=True)
async def _call_analysis_llm(client: httpx.AsyncClient, prompt: str, audit_id: str, response_id: str, log_ctx: structlog.BoundLogger) -> str:
    """Helper to call LLM with retry logic."""
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
    model = getattr(settings, 'OPENAI_MODEL_FAST_DEFAULT', 'gpt-4o-mini') or 'gpt-4o-mini'
    payload = {"model": model, "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
               "response_format": {"type": "json_object"}, "temperature": LLM_TEMPERATURE}
    
    response = await client.post(settings.OPENAI_API_BASE_URL + "/chat/completions", headers=headers, json=payload, timeout=LLM_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

async def _analyze_single_response(response_data: ResponseRow, company_name: str, semaphore: asyncio.Semaphore,
                                    http_client: httpx.AsyncClient, log_ctx: structlog.BoundLogger) -> List[MentionRecord]:
    """For a single audit_response row, call LLM and extract MentionRecord list."""
    audit_id, response_id = response_data.audit_id, response_data.id
    if not response_data.response_text or not response_data.response_text.strip():
        return [make_absent_mention(response_id, audit_id, company_name)]
    
    async with semaphore:
        try:
            prompt = build_analysis_prompt(response_data.response_text, company_name, response_data.platform, response_data.query_text)
            raw_output = await _call_analysis_llm(http_client, prompt, audit_id, response_id, log_ctx)
            return parse_llm_output(raw_output, response_id, audit_id, company_name, log_ctx)
        except (httpx.HTTPStatusError, httpx.RequestError, json.JSONDecodeError, ValueError) as e:
            log_ctx.error("Failed to analyze response", error=str(e))
            return [make_absent_mention(response_id, audit_id, company_name)]

async def _batch_insert_mentions(db: Any, mentions: List[MentionRecord], audit_id: str, log_ctx: structlog.BoundLogger) -> None:
    """Batch insert all mention records into audit_mentions table."""
    if not mentions:
        log_ctx.info("No mentions to insert", audit_id=audit_id)
        return
    mentions_data = [mention_record_to_db_dict(m) for m in mentions]
    response: APIResponse = await db.from_("audit_mentions").insert(mentions_data).execute()
    log_ctx.info("Batch inserted mentions", audit_id=audit_id, count=len(mentions))

async def _publish_progress(redis_client: Any, audit_id: str, responses_count: int, mentions_count: int, log_ctx: structlog.BoundLogger) -> None:
    """Publish ProgressUpdate to Redis."""
    progress_update = ProgressUpdate(
        status=AuditStatus.analyzing, progress=0.85, current_agent=AGENT_NAME,
        message=f"Analyzed {mentions_count} mentions across {responses_count} responses.",
        mentions_analyzed=mentions_count, total_responses=responses_count)
    await redis_client.set(f"audit:{audit_id}:progress", progress_update.model_dump_json(), ex=3600)
    log_ctx.info("Published progress update", audit_id=audit_id, mentions_count=mentions_count)

async def _fetch_company_name(db: Any, company_id: str, log_ctx: structlog.BoundLogger) -> str:
    """Fetches the company name from the database."""
    resp = await db.from_("companies").select("name").eq("id", company_id).single().execute()
    if not resp.data:
        raise ValueError(f"Company with ID {company_id} not found.")
    return resp.data["name"]

async def _fetch_responses_with_queries(db: Any, audit_id: str, log_ctx: structlog.BoundLogger) -> List[ResponseRow]:
    """Fetches audit responses and their associated queries."""
    resp = await db.from_("audit_responses").select("id, response_text, platform, query_id").eq("audit_id", audit_id).order("created_at").execute()
    raw_responses = resp.data
    query_map = {}
    if raw_responses:
        query_ids = [r["query_id"] for r in raw_responses]
        q_resp = await db.from_("audit_queries").select("id, query_text").in_("id", query_ids).execute()
        query_map = {q["id"]: q["query_text"] for q in q_resp.data}
    return [ResponseRow(id=r["id"], response_text=r["response_text"], platform=r["platform"],
                        query_text=query_map.get(r["query_id"], ""), audit_id=audit_id) for r in raw_responses]

async def run(state: AuditState) -> AuditState:
    """LangGraph node: analyze mentions in all collected responses."""
    log_ctx = log.bind(audit_id=state.audit_id, agent=AGENT_NAME)
    log_ctx.info("Starting mention analysis")
    state.status = AuditStatus.analyzing
    state.messages.append(AgentMessage(agent=AGENT_NAME, content="Starting mention analysis...", metadata={"type": "info"}))

    db = await get_service_db()
    redis_client = get_redis_client()
    http_client = httpx.AsyncClient()

    try:
        company_name = await _fetch_company_name(db, state.company_id, log_ctx)
        responses = await _fetch_responses_with_queries(db, state.audit_id, log_ctx)
        total_responses = len(responses)
        
        if not responses:
            log_ctx.warning("No audit responses found")
            state.messages.append(AgentMessage(agent=AGENT_NAME, content="No responses to analyze.", metadata={"type": "warning"}))
            await _publish_progress(redis_client, state.audit_id, 0, 0, log_ctx)
            return state

        semaphore = asyncio.Semaphore(ANALYSIS_SEMAPHORE_SIZE)
        tasks = [_analyze_single_response(r, company_name, semaphore, http_client, log_ctx) for r in responses]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_mentions: List[MentionRecord] = []
        for res in results:
            if isinstance(res, list):
                all_mentions.extend(res)
            elif isinstance(res, Exception):
                log_ctx.error("Response analysis failed", error=str(res))

        log_ctx.info("Finished parallel mention analysis", total_mentions=len(all_mentions), total_responses=total_responses)
        await _batch_insert_mentions(db, all_mentions, state.audit_id, log_ctx)
        await _publish_progress(redis_client, state.audit_id, total_responses, len(all_mentions), log_ctx)

        state.messages.append(AgentMessage(agent=AGENT_NAME, content=f"Analyzed {len(all_mentions)} mentions across {total_responses} responses.",
                                           metadata={"mentions_count": len(all_mentions), "responses_analyzed": total_responses}))
        log_ctx.info("Mention analysis completed successfully")

    except (httpx.HTTPStatusError, httpx.RequestError, json.JSONDecodeError, ValueError) as e:
        log_ctx.error("Mention Analyzer agent failed", error=str(e))
        state.status = AuditStatus.failed
        state.error = f"Mention analysis failed: {str(e)}"
        state.messages.append(AgentMessage(agent=AGENT_NAME, content=f"Mention analysis failed: {str(e)}", metadata={"type": "error"}))
    finally:
        await http_client.aclose()

    return state
