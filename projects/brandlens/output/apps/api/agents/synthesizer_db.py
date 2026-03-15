import structlog
from typing import List, Dict, Any, Tuple, Optional
from postgrest import AsyncPostgrestClient
from .scoring.score_models import (
    MentionData, ResponseData, TechnicalCheckData, 
    CompetitorData, MetricScoreRecord, HallucinationFinding
)

log = structlog.get_logger(__name__)

async def fetch_mentions_for_audit(db: AsyncPostgrestClient, audit_id: str) -> List[MentionData]:
    """Fetch mentions joined with response platform info."""
    res = await db.from_("audit_mentions")\
        .select("*, audit_responses(platform)")\
        .eq("audit_id", audit_id)\
        .execute()
    
    mentions = []
    for row in res.data:
        # Flatten platform from joined table
        platform = row.get("audit_responses", {}).get("platform", "unknown")
        mentions.append(MentionData(
            response_id=row["response_id"],
            entity_name=row["entity_name"],
            mention_type=row["mention_type"],
            position_rank=row["position_rank"],
            sentiment_score=float(row["sentiment_score"]) if row["sentiment_score"] else 0.0,
            is_authority_cite=row["is_authority_cite"],
            authority_markers=row["authority_markers"] or [],
            extracted_attributes=row["extracted_attributes"] or {},
            is_confused=row["is_confused"],
            platform=platform
        ))
    return mentions

async def fetch_responses_for_audit(db: AsyncPostgrestClient, audit_id: str) -> List[ResponseData]:
    """Fetch responses joined with query intent."""
    res = await db.from_("audit_responses")\
        .select("*, audit_queries(intent)")\
        .eq("audit_id", audit_id)\
        .execute()
    
    responses = []
    for row in res.data:
        intent = row.get("audit_queries", {}).get("intent", "informational")
        responses.append(ResponseData(
            id=row["id"],
            platform=row["platform"],
            query_id=row["query_id"],
            intent=intent,
            citations=row["citations"] or [],
            rag_sources=row["rag_sources"] or [],
            response_text=row["response_text"]
        ))
    return responses

async def fetch_technical_checks(db: AsyncPostgrestClient, audit_id: str) -> Optional[TechnicalCheckData]:
    """Fetch technical crawl data for the audit."""
    res = await db.from_("audit_technical_checks")\
        .select("*")\
        .eq("audit_id", audit_id)\
        .maybe_single()\
        .execute()
    
    if not res.data:
        return None
        
    row = res.data
    return TechnicalCheckData(
        crawler_permissions=row["crawler_permissions"] or {},
        sitemap_present=row["sitemap_present"],
        sitemap_valid=row["sitemap_valid"],
        sampled_pages=row["sampled_pages"] or [],
        avg_lastmod_days=float(row["avg_lastmod_days"]) if row["avg_lastmod_days"] else 0.0,
        update_frequency_monthly=float(row["update_frequency_monthly"]) if row["update_frequency_monthly"] else 0.0,
        current_year_content_pct=float(row["current_year_content_pct"]) if row["current_year_content_pct"] else 0.0
    )

async def fetch_competitor_stats(db: AsyncPostgrestClient, audit_id: str) -> List[CompetitorData]:
    """Fetch competitor analysis results."""
    res = await db.from_("audit_competitors")\
        .select("*")\
        .eq("audit_id", audit_id)\
        .execute()
    
    return [CompetitorData(
        competitor_name=row["competitor_name"],
        avg_mention_position=float(row["avg_mention_position"]),
        recommendation_count=row["recommendation_count"],
        total_appearances=row["total_appearances"],
        positive_comparisons=row["positive_comparisons"],
        negative_comparisons=row["negative_comparisons"],
        platform_breakdown=row["platform_breakdown"] or {}
    ) for row in res.data]

async def fetch_company_facts(db: AsyncPostgrestClient, company_id: str) -> Tuple[str, Dict[str, Any]]:
    """Fetch company name and ground truth facts."""
    res = await db.from_("companies")\
        .select("name, facts")\
        .eq("id", company_id)\
        .single()\
        .execute()
    return res.data["name"], res.data["facts"] or {}

async def batch_insert_metric_scores(db: AsyncPostgrestClient, scores: List[MetricScoreRecord], audit_id: str) -> None:
    """Batch insert metric scores into DB."""
    if not scores: return
    
    rows = []
    for s in scores:
        rows.append({
            "audit_id": audit_id,
            "metric_id": s.metric_id,
            "metric_category": s.metric_category,
            "score": s.score,
            "components": s.components,
            "weight": s.weight,
            "weighted_contribution": s.weighted_contribution,
            "platform_scores": s.platform_scores,
            "evidence_summary": s.evidence_summary
        })
    
    await db.from_("audit_metric_scores").upsert(rows, on_conflict="audit_id,metric_id").execute()

async def batch_insert_hallucinations(db: AsyncPostgrestClient, findings: List[HallucinationFinding], audit_id: str) -> None:
    """Batch insert detected hallucinations into DB."""
    if not findings: return
    
    rows = []
    for f in findings:
        rows.append({
            "audit_id": audit_id,
            "response_id": f.response_id,
            "claim_text": f.claim_text,
            "fact_field": f.fact_field,
            "expected_value": f.expected_value,
            "actual_value": f.actual_value,
            "severity": f.severity,
            "platform": f.platform
        })
    
    # We don't have a unique constraint on hallucinations, so we just insert
    await db.from_("audit_hallucinations").insert(rows).execute()

async def update_audit_scores(db: AsyncPostgrestClient, audit_id: str, global_score: float, breakdown: Dict[str, Any]) -> None:
    """Update final scores in the main audit record."""
    await db.from_("audits")\
        .update({"global_geo_score": global_score, "score_breakdown": breakdown})\
        .eq("id", audit_id)\
        .execute()
