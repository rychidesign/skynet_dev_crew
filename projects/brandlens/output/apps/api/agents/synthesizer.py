import structlog
import httpx
from typing import Dict, Any, List
from . import synthesizer_db
from . import score_calculator
from . import hallucination_detector
from ..core.state import AuditState, AuditStatus
from ..core.redis_client import redis_client

log = structlog.get_logger(__name__)

async def run(state: AuditState) -> AuditState:
    """
    Agent 5 (Synthesizer) — Scoring Half
    Orchestrates scoring flow, hallucination detection, and database persistence.
    """
    audit_id = state.audit_id
    company_id = state.company_id
    db = state.db
    
    log.info("agent_synthesizer_scoring_start", audit_id=audit_id)
    
    try:
        # 1. Fetch data from DB
        company_name, company_facts = await synthesizer_db.fetch_company_facts(db, company_id)
        mentions = await synthesizer_db.fetch_mentions_for_audit(db, audit_id)
        responses = await synthesizer_db.fetch_responses_for_audit(db, audit_id)
        tech_checks = await synthesizer_db.fetch_technical_checks(db, audit_id)
        competitors = await synthesizer_db.fetch_competitor_stats(db, audit_id)
        
        # 2. Detect hallucinations
        async with httpx.AsyncClient() as http_client:
            hallucinations = await hallucination_detector.detect(
                responses=responses,
                company_facts=company_facts,
                company_name=company_name,
                audit_id=audit_id,
                http_client=http_client
            )
        
        # 3. Compute scores
        total_queries = len(set(r.query_id for r in responses))
        total_claims = len(hallucinations) * 2  # Simplified heuristic for total claims
        platforms = list(set(r.platform for r in responses))
        
        metric_scores = score_calculator.compute_all_metrics(
            mentions=mentions,
            responses=responses,
            tech=tech_checks,
            competitors=competitors,
            brand_name=company_name,
            hallucinations=hallucinations,
            total_claims=max(total_claims, 1),
            total_queries=total_queries,
            total_topic_mentions=len(mentions),
            platforms=platforms
        )
        
        global_score = score_calculator.compute_global_score(metric_scores)
        
        # 4. Persist to DB
        await synthesizer_db.batch_insert_metric_scores(db, metric_scores, audit_id)
        await synthesizer_db.batch_insert_hallucinations(db, hallucinations, audit_id)
        
        score_breakdown = {m.metric_id: m.score for m in metric_scores}
        await synthesizer_db.update_audit_scores(db, audit_id, global_score, score_breakdown)
        
        # 5. Update Redis progress
        if redis_client:
            await redis_client.set(
                f"audit:{audit_id}:progress",
                {"status": "synthesizing", "progress": 0.9},
                ex=3600
            )
            
        log.info("agent_synthesizer_scoring_complete", audit_id=audit_id, global_score=global_score)
        return state

    except Exception as e:
        state.status = AuditStatus.failed
        log.error("agent_synthesizer_scoring_failed", audit_id=audit_id, error=str(e))
        raise e
