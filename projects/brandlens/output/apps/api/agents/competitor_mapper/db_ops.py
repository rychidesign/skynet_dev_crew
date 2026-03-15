from typing import List, Dict, Tuple
import structlog
from supabase._async.client import AsyncClient

from apps.api.agents.competitor_mapper.models import CompetitorStats, PlatformCompetitorBreakdown

log = structlog.get_logger(__name__)

async def fetch_comparative_responses(
    db: AsyncClient, audit_id: str, log_ctx: structlog.BoundLogger
) -> List[Dict]:
    """
    Fetches audit responses with comparative or recommendation intent.
    Joins with audit_queries to get query_text and intent.
    Returns list of dicts with: id, response_text, platform, query_id, query_text, query_intent.
    """
    resp = await db.from_("audit_responses") \
        .select("id, response_text, platform, query_id, audit_queries!inner(id, query_text, intent)") \
        .eq("audit_id", audit_id) \
        .in_("audit_queries.intent", ["comparative", "recommendation"]) \
        .execute()
    
    results = []
    for item in (resp.data or []):
        query_data = item.pop("audit_queries", {})
        results.append({
            "id": item["id"],
            "response_text": item["response_text"],
            "platform": item["platform"],
            "query_id": query_data.get("id", ""),
            "query_text": query_data.get("query_text", ""),
            "query_intent": query_data.get("intent", "comparative"),
            "audit_id": audit_id,
        })
    return results

async def fetch_competitor_list(
    db: AsyncClient, company_id: str, log_ctx: structlog.BoundLogger
) -> Tuple[List[str], str, Dict[str, str]]:
    """
    Fetches the company's name, competitor names, and optional domain mappings.
    Returns: (competitor_names, brand_name, competitor_domains_map)
    competitor_domains_map: dict mapping competitor name → domain (if name contains a dot)
    """
    resp = await db.from_("companies") \
        .select("name, competitors") \
        .eq("id", company_id) \
        .single() \
        .execute()
    
    if not resp.data:
        raise ValueError(f"Company {company_id} not found")
    
    brand_name: str = resp.data["name"]
    competitors: List[str] = resp.data.get("competitors") or []
    
    # Build domain map: if competitor entry looks like a domain, map name→domain
    domains: Dict[str, str] = {}
    for c in competitors:
        if "." in c:
            domains[c] = c
    
    return competitors, brand_name, domains

async def upsert_audit_competitors(
    db: AsyncClient,
    audit_id: str,
    competitor_stats: List[CompetitorStats],
    log_ctx: structlog.BoundLogger,
) -> None:
    """
    Upserts competitor stats into audit_competitors table.
    Uses ON CONFLICT (audit_id, competitor_name) DO UPDATE.
    """
    if not competitor_stats:
        log_ctx.info("No competitor stats to upsert", audit_id=audit_id)
        return
    
    rows = []
    for stats in competitor_stats:
        platform_breakdown_serialized = {
            platform: breakdown.model_dump()
            for platform, breakdown in stats.platform_breakdown.items()
        }
        rows.append({
            "audit_id": audit_id,
            "competitor_name": stats.competitor_name,
            "competitor_domain": stats.competitor_domain,
            "avg_mention_position": stats.avg_mention_position,
            "recommendation_count": stats.recommendation_count,
            "total_appearances": stats.total_appearances,
            "positive_comparisons": stats.positive_comparisons,
            "negative_comparisons": stats.negative_comparisons,
            "neutral_comparisons": stats.neutral_comparisons,
            "platform_breakdown": platform_breakdown_serialized,
        })
    
    await db.from_("audit_competitors") \
        .upsert(rows, on_conflict="audit_id,competitor_name") \
        .execute()
    
    log_ctx.info("Upserted audit competitors", audit_id=audit_id, count=len(rows))
