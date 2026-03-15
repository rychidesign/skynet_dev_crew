from typing import List, Dict, Any
from supabase_client import AsyncClient # Assuming this is how Supabase client is imported

from apps.api.agents.competitor_mapper.models import CompetitorStats, PlatformStats

async def fetch_company_competitors(db: AsyncClient, company_id: str) -> List[str]:
    """Fetches the list of competitors for a given company."""
    response = await db.from_("companies").select("competitors").eq("id", company_id).single()
    if response.data:
        return response.data.get("competitors", [])
    return []

async def fetch_comparative_responses(db: AsyncClient, audit_id: str) -> List[Dict]:
    """Fetches audit responses relevant for comparative analysis."""
    response = await db.from_("audit_responses")\
        .select("id, platform, response_text, audit_queries!inner(id, intent)")\
        .eq("audit_id", audit_id)\
        .in_("audit_queries.intent", ["comparative", "recommendation"])\
        .execute()

    if response.data:
        # Flatten the structure for easier processing in agents
        results = []
        for item in response.data:
            query_data = item.pop("audit_queries")
            results.append({
                "response_id": item["id"],
                "platform": item["platform"],
                "response_text": item["response_text"],
                "query_id": query_data["id"],
                "query_intent": query_data["intent"],
            })
        return results
    return []

async def upsert_competitors(db: AsyncClient, audit_id: str, competitors_stats: List[CompetitorStats]) -> None:
    """Upserts competitor statistics into the audit_competitors table."""
    data_to_upsert = []
    for stats in competitors_stats:
        # Convert PlatformStats objects to dictionaries for JSONB column
        platform_breakdown_dict = {
            platform: {
                "appearances": p_stats.appearances,
                "avg_position": p_stats.avg_position,
                "recommendation_count": p_stats.recommendation_count,
            }
            for platform, p_stats in stats.platform_breakdown.items()
        }

        data_to_upsert.append({
            "audit_id": audit_id,
            "competitor_name": stats.competitor_name,
            "competitor_domain": stats.competitor_domain,
            "avg_mention_position": stats.avg_mention_position,
            "recommendation_count": stats.recommendation_count,
            "total_appearances": stats.total_appearances,
            "positive_comparisons": stats.positive_comparisons,
            "negative_comparisons": stats.negative_comparisons,
            "neutral_comparisons": stats.neutral_comparisons,
            "platform_breakdown": platform_breakdown_dict,
        })

    if data_to_upsert:
        await db.from_("audit_competitors").upsert(data_to_upsert, on_conflict="audit_id,competitor_name").execute()
