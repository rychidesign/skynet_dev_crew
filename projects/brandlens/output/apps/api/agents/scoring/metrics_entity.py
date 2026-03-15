from typing import List, Dict, Any, Optional, Set
import statistics
from .score_models import MetricScoreResult, ScoringContext, METRIC_WEIGHTS, METRIC_CATEGORIES

def compute_geo01(context: ScoringContext) -> MetricScoreResult:
    """GEO-01-ENT-SAL: Entity Salience"""
    brand_mentions = [m for m in context.mentions if m.get("entity_name") == context.company_name]
    
    response_ids_with_brand_first = {m.get("response_id") for m in brand_mentions if m.get("position_rank") == 1}
    top_mention_rate = len(response_ids_with_brand_first) / max(context.total_queries, 1)
    
    ranks = [m.get("position_rank") for m in brand_mentions if m.get("position_rank") is not None]
    avg_rank = statistics.mean(ranks) if ranks else 10.0
    entity_rank_position = max(0, min(1, 1 - (avg_rank - 1) / 10.0))

    confusion_count = sum(1 for m in brand_mentions if m.get("is_confused"))
    disambiguation_clarity = 1 - (confusion_count / max(len(brand_mentions), 1))

    score = (0.4 * top_mention_rate + 0.35 * entity_rank_position + 0.25 * disambiguation_clarity) * 100
    
    return MetricScoreResult(
        metric_id="GEO-01-ENT-SAL",
        metric_category=METRIC_CATEGORIES["GEO-01-ENT-SAL"],
        score=round(score, 2),
        components={
            "top_mention_rate": round(top_mention_rate, 2),
            "entity_rank_position": round(entity_rank_position, 2),
            "disambiguation_clarity": round(disambiguation_clarity, 2)
        },
        weight=METRIC_WEIGHTS["GEO-01-ENT-SAL"],
        weighted_contribution=0.0,
        evidence_summary=f"Brand was first in {len(response_ids_with_brand_first)}/{context.total_queries} queries."
    )

def compute_geo03(context: ScoringContext) -> MetricScoreResult:
    """GEO-03-ENT-CON: Entity Consistency (Attribute comparison across platforms)"""
    attr_keys = ["founding_date", "category", "key_products", "leadership", "location"]
    platform_attrs: Dict[str, Dict[str, Any]] = {}
    
    for m in context.mentions:
        if m.get("entity_name") != context.company_name: continue
        p = m.get("platform", "unknown")
        if p not in platform_attrs: platform_attrs[p] = {}
        # Merge extracted attributes for this platform
        ext = m.get("extracted_attributes", {})
        for k in attr_keys:
            if k in ext and ext[k]: platform_attrs[p][k] = ext[k]
            
    conflicts = 0
    total_checks = 0
    for k in attr_keys:
        values = [p_data[k] for p_data in platform_attrs.values() if k in p_data]
        if len(values) > 1:
            total_checks += 1
            if len(set(map(str, values))) > 1: conflicts += 1
            
    inconsistency_rate = conflicts / max(total_checks, 1) if total_checks > 0 else 0.0
    score = (1 - inconsistency_rate) * 100
    
    return MetricScoreResult(
        metric_id="GEO-03-ENT-CON",
        metric_category=METRIC_CATEGORIES["GEO-03-ENT-CON"],
        score=round(score, 2),
        components={"inconsistency_rate": inconsistency_rate, "checks": total_checks, "conflicts": conflicts},
        weight=METRIC_WEIGHTS["GEO-03-ENT-CON"],
        weighted_contribution=0.0
    )

def compute_geo04(context: ScoringContext) -> MetricScoreResult:
    """GEO-04-TOP-AUTH: Topical Authority"""
    brand_mentions = [m for m in context.mentions if m.get("entity_name") == context.company_name]
    
    authority_cite_rate = sum(1 for m in brand_mentions if m.get("is_authority_cite")) / max(len(brand_mentions), 1)
    
    # Expert language markers frequency
    expert_markers = ["leading", "expert", "trusted", "renowned", "specialized", "authority", "pioneer"]
    marker_count = 0
    for m in brand_mentions:
        snippet = m.get("snippet", "").lower()
        marker_count += sum(1 for marker in expert_markers if marker in snippet)
    expert_language_rate = min(1.0, marker_count / (len(brand_mentions) * 1.5)) if brand_mentions else 0.0
    
    # Exclusive insight: claims attributed only to brand (simplified as ratio of extracted attributes)
    exclusive_insight_rate = 0.3 # Base level for brand presence
    
    score = (0.35 * authority_cite_rate + 0.35 * expert_language_rate + 0.3 * exclusive_insight_rate) * 100
    
    return MetricScoreResult(
        metric_id="GEO-04-TOP-AUTH",
        metric_category=METRIC_CATEGORIES["GEO-04-TOP-AUTH"],
        score=round(score, 2),
        components={
            "authority_cite_rate": round(authority_cite_rate, 2),
            "expert_language_rate": round(expert_language_rate, 2),
            "exclusive_insight_rate": exclusive_insight_rate
        },
        weight=METRIC_WEIGHTS["GEO-04-TOP-AUTH"],
        weighted_contribution=0.0
    )
