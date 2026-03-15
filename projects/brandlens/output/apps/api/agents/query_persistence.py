"""Database persistence functions for query generator agent."""
from typing import List

from supabase._async.client import AsyncClient, create_client
import structlog

from apps.api.core.config import settings
from apps.api.agents.query_models import CompanyProfile, QuerySpec

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


async def persist_queries(audit_id: str, queries: List[QuerySpec]) -> None:
    """Deletes existing audit queries and batch inserts new ones, then updates audit status."""
    supabase = await _get_supabase_client()

    await supabase.from_("audit_queries").delete().eq("audit_id", audit_id).execute()

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

    if insert_data:
        await supabase.from_("audit_queries").insert(insert_data).execute()
        logger.info(f"Successfully inserted {len(insert_data)} queries for audit {audit_id}.")
    else:
        logger.warning(f"No queries to insert for audit {audit_id}.")

    await supabase.from_("audits").update({"status": "collecting"}).eq("id", audit_id).execute()
    logger.info(f"Audit {audit_id} status updated to 'collecting'.")
