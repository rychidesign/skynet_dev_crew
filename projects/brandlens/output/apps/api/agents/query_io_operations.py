"""
I/O operations for the Query Generator agent, including fetching company profile,
calling the LLM, persisting queries to the database, and publishing progress to Redis.
"""
import json
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from supabase._async.client import AsyncClient, create_client
import structlog

from apps.api.core.config import settings
from apps.api.agents.query_models import CompanyProfile, QuerySpec
from apps.api.agents.query_constants import (
    LLM_MODEL, LLM_TEMPERATURE, REDIS_TTL_SECONDS,
    LLM_MAX_ATTEMPTS, LLM_WAIT_MIN_SECONDS, LLM_WAIT_MAX_SECONDS
)
from apps.api.core.redis_client import get_redis_client

logger = structlog.get_logger(__name__)


async def _get_supabase_client() -> AsyncClient:
    """Returns a Supabase AsyncClient."""
    return await create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY,
    )


async def fetch_company_profile(company_id: str) -> CompanyProfile:
    """Fetches company profile data from Supabase."""
    supabase = await _get_supabase_client()
    response = await supabase.from_("companies").select(
        "name, industry, description, competitors, core_topics, facts"
    ).eq("id", company_id).single().execute()

    if response.data:
        data = response.data
        return CompanyProfile(
            company_id=company_id,
            name=data["name"],
            industry=data.get("industry"),
            description=data.get("description"),
            competitors=data.get("competitors", []),
            core_topics=data.get("core_topics", []),
            facts=data.get("facts") or {},
        )
    raise ValueError(f"Company with ID {company_id} not found.")


@retry(
    stop=stop_after_attempt(LLM_MAX_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=LLM_WAIT_MIN_SECONDS, max=LLM_WAIT_MAX_SECONDS),
    retry=retry_if_exception_type((httpx.HTTPStatusError, json.JSONDecodeError, KeyError))
)
async def call_llm(
    system_prompt: str, user_prompt: str
) -> List[Dict[str, Any]]:
    """Calls the LLM to generate queries based on company profile and distribution."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.OPENAI_API_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": LLM_TEMPERATURE,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        raw_output = response.json()["choices"][0]["message"]["content"]
        parsed_json = json.loads(raw_output)
        generated_queries_data = parsed_json["queries"]
        return generated_queries_data


async def persist_queries(audit_id: str, queries: List[QuerySpec]) -> None:
    """Deletes existing audit queries and batch inserts new ones, then updates audit status."""
    supabase = await _get_supabase_client()
    
    # Idempotency: Delete existing queries for this audit
    await supabase.from_("audit_queries").delete().eq("audit_id", audit_id).execute()
    logger.debug(f"Deleted existing audit_queries for audit {audit_id} (idempotency).")

    # Prepare data for batch insert
    insert_data = [
        {
            "audit_id": audit_id,
            "query_text": q.query_text,
            "intent": q.intent,
            "target_metrics": q.target_metrics,
            "query_index": q.query_index,
        }
        for q in queries
    ]

    # Batch insert new queries
    if insert_data:
        response = await supabase.from_("audit_queries").insert(insert_data).execute()
        if response.data is None:
            logger.info(f"Successfully inserted {len(insert_data)} queries for audit {audit_id}.")
        elif response.status_code != 201:
            raise RuntimeError(f"Failed to insert queries: {response.status_code}")
    else:
        logger.warning(f"No queries to insert for audit {audit_id}.")

    # Update audit status
    update_response = await supabase.from_("audits").update({"status": "collecting"}).eq("id", audit_id).execute()
    if update_response.data is None:
        logger.info(f"Audit {audit_id} status updated to 'collecting'.")
    elif update_response.status_code != 200:
        raise RuntimeError(f"Failed to update audit status: {update_response.status_code}")


async def publish_progress(
    audit_id: str, message: str, progress: float, queries_generated: Optional[int] = None
) -> None:
    """Publishes audit progress updates to Redis."""
    redis_client = get_redis_client()
    progress_data = {
        "audit_id": audit_id,
        "status": "generating",
        "progress": progress,
        "current_agent": "query_generator",
        "message": message,
        "queries_generated": queries_generated,
    }
    await redis_client.set(
        f"audit:{audit_id}:progress", json.dumps(progress_data), ex=REDIS_TTL_SECONDS
    )
    logger.debug(f"Published progress for audit {audit_id}: {message} ({progress*100:.0f}%)")
