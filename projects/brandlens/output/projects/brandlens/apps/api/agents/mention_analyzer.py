import asyncio
from typing import List, Any

import httpx
import structlog
from postgrest import APIResponse as SupabaseAPIResponse

from apps.api.core.state import AuditState, AgentMessage
from apps.api.core.redis_client import get_redis_client
from apps.api.core.config import settings
from apps.api.core.dependencies import get_service_db
from apps.api.models.audit import AuditStatus, ProgressUpdate

from apps.api.agents.mention_analysis_helpers import (
    MentionRecord, ResponseRow, make_absent_mention, 
    build_analysis_prompt, parse_llm_output, 
    mention_record_to_db_dict, 
    SYSTEM_PROMPT, ANALYSIS_SEMAPHORE_SIZE, LLM_TIMEOUT_SECONDS, LLM_TEMPERATURE
)

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Initialize structlog logger
log = structlog.get_logger(__name__)

AGENT_NAME = "mention_analyzer"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_exception_type(httpx.RequestError) | retry_if_exception_type(httpx.HTTPStatusError),
    reraise=True # Reraise the last exception if all retries fail
)
async def _call_analysis_llm(
    client: httpx.AsyncClient,
    prompt: str,
    audit_id: str,
    response_id: str,
    log: structlog.BoundLogger,
) -> str:
    """Helper to call LLM with retry logic and rate limit handling."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
    }
    payload = {
        "model": settings.OPENAI_MODEL_FAST_DEFAULT, # Use faster model for NLP tasks
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": LLM_TEMPERATURE,
    }
    
    # Ensure model is set, fallback if not configured
    if not payload["model"]:
        payload["model"] = "gpt-4o-mini" 
        log.warning("OPENAI_MODEL_FAST_DEFAULT is not set, using gpt-4o-mini as fallback.")

    try:
        response = await client.post(settings.OPENAI_API_BASE_URL + "/chat/completions", headers=headers, json=payload, timeout=LLM_TIMEOUT_SECONDS)
        response.raise_for_status()  # Raise an exception for 4xx or 5xx responses
        
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "60"))
            log.warning("LLM rate limit hit (429), retrying after delay.", retry_after=retry_after)
            await asyncio.sleep(retry_after) # Wait before next retry attempt
            # After waiting, the tenacity decorator will re-attempt the whole function
            response.raise_for_status() # Re-raise to trigger tenacity retry
        
        return response.json()["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        log.error("LLM API returned an error status.", status_code=e.response.status_code, response_text=e.response.text, audit_id=audit_id, response_id=response_id)
        raise e
    except httpx.RequestError as e:
        log.error("LLM request failed.", error=str(e), audit_id=audit_id, response_id=response_id)
        raise e
    except (KeyError, IndexError) as e:
        log.error("Failed to parse LLM response structure.", error=str(e), raw_response=response.text, audit_id=audit_id, response_id=response_id)
        raise ValueError("Malformed LLM response structure") from e


async def _analyze_single_response(
    response_data: ResponseRow,
    company_name: str,
    semaphore: asyncio.Semaphore,
    http_client: httpx.AsyncClient,
    log: structlog.BoundLogger,
) -> List[MentionRecord]:
    """
    For a single audit_response row, call LLM and extract MentionRecord list.
    Returns at least one MentionRecord (absent if brand not found).
    """
    audit_id = response_data.audit_id
    response_id = response_data.id
    response_text = response_data.response_text
    platform = response_data.platform
    query_text = response_data.query_text

    response_log = log.bind(audit_id=audit_id, response_id=response_id, platform=platform)

    # If response text is empty, no need to call LLM
    if not response_text or not response_text.strip():
        response_log.info("Empty response text, creating an absent mention record.")
        return [make_absent_mention(response_id, audit_id, company_name)]

    async with semaphore:
        try:
            prompt = build_analysis_prompt(response_text, company_name, platform, query_text)
            
            raw_llm_output = await _call_analysis_llm(
                http_client,
                prompt,
                audit_id,
                response_id,
                response_log
            )
            
            mentions = parse_llm_output(raw_llm_output, response_id, audit_id, company_name, response_log)
            return mentions
        except Exception as e:
            response_log.error("Failed to analyze response with LLM.", error=str(e))
            return [make_absent_mention(response_id, audit_id, company_name)]


async def _batch_insert_mentions(
    db: Any, # Supabase client
    mentions: List[MentionRecord],
    audit_id: str,
    log: structlog.BoundLogger,
) -> None:
    """Batch insert all mention records into audit_mentions table."""
    if not mentions:
        log.info("No mentions to insert for audit.", audit_id=audit_id)
        return

    mentions_data = [mention_record_to_db_dict(m) for m in mentions]
    
    # Supabase expects a list of dictionaries for bulk insert
    try:
        response: SupabaseAPIResponse = await db.from_("audit_mentions").insert(mentions_data).execute()
        response.raise_for_status() # Raises HTTPStatusError for 4xx/5xx
        log.info("Successfully batch inserted mentions.", audit_id=audit_id, count=len(mentions))
    except Exception as e:
        log.error("Failed to batch insert mentions.", audit_id=audit_id, error=str(e))
        raise # Re-raise to propagate the error


async def _publish_progress(
    redis_client: Any, # Redis client
    audit_id: str,
    responses_count: int,
    mentions_count: int,
    log: structlog.BoundLogger,
) -> None:
    """Publish ProgressUpdate to Redis after analysis completes."""
    try:
        progress_update = ProgressUpdate(
            audit_id=audit_id,
            agent=AGENT_NAME,
            status=AuditStatus.ANALYZING, # Keep ANALYZING status until all agents are done
            progress=0.85,   # Agent 3 is ~85% through the pipeline (approximate)
            current_step=responses_count, # Number of responses processed
            total_steps=responses_count,  # Total responses to process
            message=f"Analyzed {mentions_count} mentions across {responses_count} responses."
        )
        await redis_client.set(
            f"audit:{audit_id}:progress",
            progress_update.model_dump_json(),
            ex=3600   # 1h TTL per pipeline spec
        )
        log.info("Published progress update to Redis.", audit_id=audit_id, agent=AGENT_NAME, mentions_count=mentions_count, responses_count=responses_count)
    except Exception as e:
        log.error("Failed to publish progress update to Redis.", audit_id=audit_id, error=str(e))


async def _fetch_company_name(db: Any, company_id: str, log: structlog.BoundLogger) -> str:
    """Fetches the company name from the database."""
    company_response = await db.from_("companies").select("name").eq("id", company_id).single().execute()
    company_response.raise_for_status()
    if not company_response.data:
        raise ValueError(f"Company with ID {company_id} not found.")
    log.info("Fetched company name.", company_name=company_response.data["name"])
    return company_response.data["name"]


async def _fetch_responses_with_queries(db: Any, audit_id: str, log: structlog.BoundLogger) -> List[ResponseRow]:
    """Fetches audit responses and their associated queries from the database."""
    responses_db_resp = await db.from_("audit_responses") \
        .select("id, response_text, platform, query_id") \
        .eq("audit_id", audit_id) \
        .order("created_at") \
        .execute()
    responses_db_resp.raise_for_status()
    raw_responses = responses_db_resp.data

    query_map: dict[str, str] = {}
    if raw_responses:
        query_ids = [r["query_id"] for r in raw_responses]
        queries_db_resp = await db.from_("audit_queries") \
            .select("id, query_text") \
            .in_("id", query_ids) \
            .execute()
        queries_db_resp.raise_for_status()
        query_map = {q["id"]: q["query_text"] for q in queries_db_resp.data}

    audit_responses: List[ResponseRow] = [
        ResponseRow(
            id=r["id"],
            response_text=r["response_text"],
            platform=r["platform"],
            query_text=query_map.get(r["query_id"], ""),
            audit_id=audit_id # Pass audit_id to ResponseRow
        )
        for r in raw_responses
    ]
    log.info("Fetched audit responses.", count=len(audit_responses))
    return audit_responses


async def run(state: AuditState) -> AuditState:
    """LangGraph node: analyze mentions in all collected responses."""
    current_log = log.bind(audit_id=state.audit_id, agent=AGENT_NAME)
    current_log.info("Starting mention analysis.")

    state.status = AuditStatus.ANALYZING 
    state.messages.append(AgentMessage(agent=AGENT_NAME, message="Starting mention analysis..."))

    db = get_service_db()
    redis_client = get_redis_client()
    http_client = httpx.AsyncClient()

    try:
        company_name = await _fetch_company_name(db, state.company_id, current_log)
        responses: List[ResponseRow] = await _fetch_responses_with_queries(db, state.audit_id, current_log)
        
        total_responses = len(responses)
        if not responses:
            current_log.warning("No audit responses found for analysis.")
            state.messages.append(AgentMessage(agent=AGENT_NAME, message="No responses to analyze."))
            await _publish_progress(redis_client, state.audit_id, 0, 0, current_log)
            return state

        semaphore = asyncio.Semaphore(ANALYSIS_SEMAPHORE_SIZE)
        tasks = [
            _analyze_single_response(response, company_name, semaphore, http_client, current_log)
            for response in responses
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_mentions: List[MentionRecord] = []
        for res in results:
            if isinstance(res, Exception):
                current_log.error("An individual response analysis failed.", error=str(res))
                # _analyze_single_response already returns an absent mention on failure, so nothing extra needed here
            elif isinstance(res, list):
                all_mentions.extend(res)

        current_log.info("Finished parallel mention analysis.", total_mentions=len(all_mentions), total_responses=total_responses)
        
        await _batch_insert_mentions(db, all_mentions, state.audit_id, current_log)
        await _publish_progress(redis_client, state.audit_id, total_responses, len(all_mentions), current_log)

        state.messages.append(AgentMessage(agent=AGENT_NAME, message=f"Analyzed {len(all_mentions)} mentions across {total_responses} responses.", metadata={"mentions_count": len(all_mentions), "responses_analyzed": total_responses}))
        current_log.info("Mention analysis completed successfully.")

    except Exception as e:
        current_log.error("Mention Analyzer agent failed.", error=str(e))
        state.status = AuditStatus.FAILED
        state.error = f"Mention analysis failed: {str(e)}"
        state.messages.append(AgentMessage(agent=AGENT_NAME, message=f"Mention analysis failed: {str(e)}", is_error=True))
    finally:
        await http_client.aclose()
        if redis_client:
            await redis_client.close()

    return state
