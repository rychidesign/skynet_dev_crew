import asyncio
import httpx
import structlog
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from typing import List, Dict, Any, Tuple

from postgrest import APIResponse
from supabase_py_async import AsyncClient

from apps.api.agents.competitor_mapper_constants_and_types import (
    ANALYSIS_SEMAPHORE_SIZE, LLM_TIMEOUT_SECONDS, LLM_TEMPERATURE, COMPARATIVE_INTENTS,
    FilteredResponse, CompetitorMentionResult
)
from apps.api.agents.competitor_mapper_prompts import build_analysis_prompt, SYSTEM_PROMPT
from apps.api.agents.competitor_mapper_llm_parsing import parse_llm_output
from apps.api.core.config import settings

log = structlog.get_logger(__name__)


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=8),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(httpx.HTTPStatusError),
    reraise=True,
)
async def call_analysis_llm(
    http_client: httpx.AsyncClient,
    prompt: str,
    audit_id: str,
    log_ctx: structlog.BoundLogger,
) -> str:
    """Async HTTP call to OpenAI with retry via tenacity."""
    log_ctx.debug("Calling LLM for competitor analysis")
    try:
        response = await http_client.post(
            settings.OPENAI_API_BASE_URL,
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.OPENAI_COMPLETION_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": LLM_TEMPERATURE,
                "timeout_ms": int(LLM_TIMEOUT_SECONDS * 1000),
            },
            timeout=LLM_TIMEOUT_SECONDS,
        )
        response.raise_for_status() # Raise an exception for 4xx or 5xx status codes
        return response.json()["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        log_ctx.error(
            "LLM API returned an error status",
            status_code=e.response.status_code,
            response_text=e.response.text,
            error=str(e),
            audit_id=audit_id,
        )
        raise # Re-raise to trigger tenacity retry
    except httpx.RequestError as e:
        log_ctx.error(
            "LLM API request failed",
            error=str(e),
            audit_id=audit_id,
        )
        raise
    except Exception as e:
        log_ctx.error(
            "Unexpected error during LLM call",
            error=str(e),
            audit_id=audit_id,
        )
        raise


async def analyze_single_response(
    response: FilteredResponse,
    competitors: List[str],
    semaphore: asyncio.Semaphore,
    http_client: httpx.AsyncClient,
    log_ctx: structlog.BoundLogger,
) -> Tuple[FilteredResponse, List[CompetitorMentionResult]]:
    """
    Wraps prompt build + LLM call + parse for one response.
    """
    async with semaphore:
        prompt = build_analysis_prompt(
            response_text=response.response_text,
            competitors=competitors,
            platform=response.platform,
            query_text=response.query_text,
        )
        try:
            raw_llm_output = await call_analysis_llm(http_client, prompt, response.audit_id, log_ctx)
            parsed_mentions = parse_llm_output(
                raw_text=raw_llm_output,
                response_id=response.response_id,
                audit_id=response.audit_id,
                competitors=competitors,
                log_ctx=log_ctx,
            )
            return response, parsed_mentions
        except Exception as e:
            log_ctx.error(
                "Failed to analyze single response with LLM",
                response_id=response.response_id,
                error=str(e),
                audit_id=response.audit_id,
            )
            return response, [] # Return empty mentions on failure


async def fetch_competitors(
    db: AsyncClient,
    company_id: str,
    log_ctx: structlog.BoundLogger,
) -> List[str]:
    """
    Queries companies.competitors[] array.
    """
    res: APIResponse = await db.from_("companies").select("competitors").eq("id", company_id).single().execute()
    if res.data and res.data.get("competitors"):
        return res.data["competitors"]
    log_ctx.warning("No competitors found for company", company_id=company_id)
    return []


async def fetch_filtered_responses(
    db: AsyncClient,
    audit_id: str,
    log_ctx: structlog.BoundLogger,
) -> List[FilteredResponse]:
    """
    Fetches audit_responses JOIN audit_queries where intent is comparative/recommendation.
    """
    res: APIResponse = await (
        db.from_("audit_responses")
        .select("id, response_text, platform, audit_queries(query_text, intent)")
        .eq("audit_id", audit_id)
        .in_("audit_queries.intent", list(COMPARATIVE_INTENTS))
        .execute()
    )

    if res.data:
        responses: List[FilteredResponse] = []
        for item in res.data:
            query_data = item.get("audit_queries")
            if query_data:
                responses.append(
                    FilteredResponse(
                        response_id=item["id"],
                        audit_id=audit_id,
                        response_text=item["response_text"],
                        platform=item["platform"],
                        query_text=query_data["query_text"],
                        query_intent=query_data["intent"],
                    )
                )
        return responses
    log_ctx.info("No comparative/recommendation responses found for audit", audit_id=audit_id)
    return []
