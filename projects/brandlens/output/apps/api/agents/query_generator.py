"""
LangGraph node (Agent 1) that generates N semantically diverse queries from a company profile,
enforces distribution rules per intent type, tags each query with `intent` and `target_metrics`,
and batch-inserts them into `audit_queries`.
"""
import json
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from supabase._async.client import AsyncClient, create_client
import structlog

from apps.api.core.state import AuditState, AgentMessage
from apps.api.core.config import settings
from apps.api.models.audit import AuditConfig
from apps.api.agents.query_prompts import build_system_prompt, build_user_prompt
from apps.api.agents.query_constants import (
    LLM_MODEL, LLM_TEMPERATURE, REDIS_TTL_SECONDS,
    LLM_MAX_ATTEMPTS, LLM_WAIT_MIN_SECONDS, LLM_WAIT_MAX_SECONDS
)
from apps.api.agents.query_models import CompanyProfile, QuerySpec
from apps.api.agents.query_distribution_logic import compute_distribution
from apps.api.agents.query_validation_repair_logic import validate_and_build_specs, repair_distribution
from apps.api.core.redis_client import get_redis_client

logger = structlog.get_logger(__name__)


async def _get_supabase_client() -> AsyncClient:
    """Returns a Supabase AsyncClient."""
    return await create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


async def _fetch_company_profile(company_id: str) -> CompanyProfile:
    """Fetches company profile data from Supabase."""
    supabase = await _get_supabase_client()
    response = await supabase.from_("companies").select(
        "name, industry, description, competitors, core_topics, facts"
    ).eq("id", company_id).single().execute()

    if response.data:
        data = response.data
        return CompanyProfile(
            company_id=company_id, name=data["name"], industry=data.get("industry"),
            description=data.get("description"), competitors=data.get("competitors", []),
            core_topics=data.get("core_topics", []), facts=data.get("facts") or {},
        )
    raise ValueError(f"Company with ID {company_id} not found.")


@retry(
    stop=stop_after_attempt(LLM_MAX_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=LLM_WAIT_MIN_SECONDS, max=LLM_WAIT_MAX_SECONDS),
    retry=retry_if_exception_type((httpx.HTTPStatusError, json.JSONDecodeError, KeyError))
)
async def _call_llm(system_prompt: str, user_prompt: str) -> List[Dict[str, Any]]:
    """Calls the LLM to generate queries based on company profile and distribution."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.OPENAI_API_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": LLM_MODEL,
                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                "temperature": LLM_TEMPERATURE, "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        raw_output = response.json()["choices"][0]["message"]["content"]
        parsed_json = json.loads(raw_output)
        return parsed_json["queries"]


async def _persist_queries(audit_id: str, queries: List[QuerySpec]) -> None:
    """Deletes existing audit queries and batch inserts new ones, then updates audit status."""
    supabase = await _get_supabase_client()
    await supabase.from_("audit_queries").delete().eq("audit_id", audit_id).execute()
    logger.debug(f"Deleted existing audit_queries for audit {audit_id} (idempotency).")

    insert_data = [
        {"audit_id": audit_id, "query_text": q.query_text, "intent": q.intent,
         "target_metrics": q.target_metrics, "query_index": q.query_index}
        for q in queries
    ]

    if insert_data:
        response = await supabase.from_("audit_queries").insert(insert_data).execute()
        if response.data is None:
            logger.info(f"Successfully inserted {len(insert_data)} queries for audit {audit_id}.")
        elif response.status_code != 201:
            raise RuntimeError(f"Failed to insert queries: {response.status_code}")
    else:
        logger.warning(f"No queries to insert for audit {audit_id}.")

    update_response = await supabase.from_("audits").update({"status": "collecting"}).eq("id", audit_id).execute()
    if update_response.data is None:
        logger.info(f"Audit {audit_id} status updated to 'collecting'.")
    elif update_response.status_code != 200:
        raise RuntimeError(f"Failed to update audit status: {update_response.status_code}")


async def _publish_progress(audit_id: str, message: str, progress: float, queries_generated: Optional[int] = None) -> None:
    """Publishes audit progress updates to Redis."""
    redis_client = get_redis_client()
    progress_data = {"audit_id": audit_id, "status": "generating", "progress": progress,
                     "current_agent": "query_generator", "message": message, "queries_generated": queries_generated}
    await redis_client.set(f"audit:{audit_id}:progress", json.dumps(progress_data), ex=REDIS_TTL_SECONDS)
    logger.debug(f"Published progress for audit {audit_id}: {message} ({progress*100:.0f}%)")


async def run(state: AuditState) -> AuditState:
    """LangGraph node to generate search queries, validate, persist, and update audit status."""
    audit_id = state.audit_id
    company_id = state.company_id
    audit_config: AuditConfig = state.config
    log = logger.bind(audit_id=audit_id, agent="query_generator")
    log.info("Query Generator agent started.")

    try:
        await _publish_progress(audit_id, "Fetching company profile...", 0.15)
        company_profile = await _fetch_company_profile(company_id)
        log.info("Company profile fetched.", company_name=company_profile.name)

        query_count = audit_config.query_count
        if query_count <= 0:
            raise ValueError(f"Invalid query_count: {query_count}. Must be positive.")

        distribution = compute_distribution(query_count)
        log.info("Computed query intent distribution.", distribution=distribution)

        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(company_profile, query_count, distribution)

        await _publish_progress(audit_id, "Generating queries with LLM...", 0.20, queries_generated=0)
        raw_llm_queries = await _call_llm(system_prompt, user_prompt)
        log.info("LLM generated initial queries.", count=len(raw_llm_queries))

        await _publish_progress(audit_id, "Validating and building query specs...", 0.22, queries_generated=len(raw_llm_queries))
        validated_queries = validate_and_build_specs(raw_llm_queries, query_count)
        log.info("Queries validated.", count=len(validated_queries))

        await _publish_progress(audit_id, "Repairing query distribution and brand ratio...", 0.23, queries_generated=len(validated_queries))
        final_queries = repair_distribution(validated_queries, distribution, company_profile)
        log.info("Queries repaired.", final_count=len(final_queries))

        await _publish_progress(audit_id, "Persisting queries to database...", 0.24, queries_generated=len(final_queries))
        await _persist_queries(audit_id, final_queries)
        await _publish_progress(audit_id, "Query generation complete.", 0.25, queries_generated=len(final_queries))

        state.messages.append(
            AgentMessage(agent="query_generator", content=f"Generated {len(final_queries)} queries for audit {audit_id}.",
                          metadata={"queries_generated": len(final_queries)})
        )
        log.info("Query Generator agent finished successfully.")
        return state

    except ValueError as e:
        log.error("Query Generator failed due to configuration or data error.", error=str(e))
        state.error = f"Query generation failed: {str(e)}"
        await _publish_progress(audit_id, f"Error: {str(e)}", 0.99)
        return state
    except httpx.HTTPStatusError as e:
        log.error("LLM API call failed.", status_code=e.response.status_code, error=str(e))
        state.error = f"LLM query generation failed: {e.response.status_code} - {e.response.text}"
        await _publish_progress(audit_id, f"Error calling LLM: {str(e)}", 0.99)
        return state
    except (json.JSONDecodeError, KeyError) as e:
        log.error("LLM response was not valid JSON or missing 'queries' key.", error=str(e))
        state.error = f"LLM returned invalid JSON or missing key: {str(e)}"
        await _publish_progress(audit_id, f"Error parsing LLM response: {str(e)}", 0.99)
        return state
    except RuntimeError as e:
        log.error("Database operation failed in Query Generator.", error=str(e))
        state.error = f"Query generation failed during database persistence: {str(e)}"
        await _publish_progress(audit_id, f"Error persisting queries: {str(e)}", 0.99)
        return state
