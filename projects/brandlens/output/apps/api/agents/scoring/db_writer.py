from typing import List, Dict, Any
import structlog
from .score_models import MetricScoreResult, HallucinationFinding

log = structlog.get_logger(__name__)

async def write_scores(db, audit_id: str, scores: List[MetricScoreResult], hallucinations: List[HallucinationFinding]):
    """Writes audit_metric_scores and audit_hallucinations rows to Supabase"""
    
    # 1. Write Metric Scores
    score_rows = []
    for s in scores:
        row = {
            "audit_id": audit_id,
            "metric_id": s.metric_id,
            "metric_category": s.metric_category,
            "score": s.score,
            "components": s.components,
            "weight": s.weight,
            "weighted_contribution": s.weighted_contribution,
            "platform_scores": s.platform_scores,
            "evidence_summary": s.evidence_summary
        }
        score_rows.append(row)
    
    if score_rows:
        try:
            # Using Supabase client (passed as db)
            await db.from_("audit_metric_scores").upsert(score_rows).execute()
            log.info("scores_written_to_db", audit_id=audit_id, count=len(score_rows))
        except Exception as e:
            log.error("scores_write_failed", audit_id=audit_id, error=str(e))
            raise

    # 2. Write Hallucinations
    hallucination_rows = []
    for h in hallucinations:
        row = {
            "audit_id": audit_id,
            "response_id": h.response_id,
            "claim_text": h.claim_text,
            "fact_field": h.fact_field,
            "expected_value": h.expected_value,
            "actual_value": h.actual_value,
            "severity": h.severity,
            "platform": h.platform
        }
        hallucination_rows.append(row)
        
    if hallucination_rows:
        try:
            await db.from_("audit_hallucinations").insert(hallucination_rows).execute()
            log.info("hallucinations_written_to_db", audit_id=audit_id, count=len(hallucination_rows))
        except Exception as e:
            log.error("hallucinations_write_failed", audit_id=audit_id, error=str(e))
            raise
            
    # Note: Global score is written to audits table by synthesizer or next task
