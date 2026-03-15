from typing import List, Optional, Dict, Any
from .scoring.score_models import MentionData, ResponseData, TechnicalCheckData, CompetitorData, MetricScoreRecord, HallucinationFinding
from .scoring.score_constants import METRIC_DEFINITIONS, CATEGORY_WEIGHTS
from .scoring.metrics_calc import (
    compute_geo_01, compute_geo_03, compute_geo_04,
    compute_geo_05, compute_geo_07, compute_geo_11,
    compute_geo_13, compute_geo_14, compute_geo_16,
    compute_geo_17
)

def compute_all_metrics(
    mentions: List[MentionData],
    responses: List[ResponseData],
    tech: Optional[TechnicalCheckData],
    competitors: List[CompetitorData],
    brand_name: str,
    hallucinations: List[HallucinationFinding],
    total_claims: int,
    total_queries: int,
    total_topic_mentions: int,
    platforms: List[str]
) -> List[MetricScoreRecord]:
    """Compute all 10 metrics using exact formulas from specs/metrics.md."""
    metric_scores = [
        compute_geo_01(mentions, total_queries),
        compute_geo_03(mentions, platforms),
        compute_geo_04(mentions, total_topic_mentions),
        compute_geo_05(responses),
        compute_geo_07(responses),
        compute_geo_11(tech),
        compute_geo_13(mentions),
        compute_geo_14(competitors, brand_name),
        compute_geo_16(hallucinations, total_claims),
        compute_geo_17(tech)
    ]
    
    # Pre-calculate weighted contributions for the DB
    cat_weight_sums = {cat: sum(m.weight for m in metric_scores if m.metric_category == cat) for cat in CATEGORY_WEIGHTS}
    
    for ms in metric_scores:
        cat_weight = CATEGORY_WEIGHTS.get(ms.metric_category, 0.0)
        total_cat_weight = cat_weight_sums.get(ms.metric_category, 1.0)
        if total_cat_weight > 0:
            ms.weighted_contribution = (ms.weight / total_cat_weight) * ms.score * cat_weight
        
        # Breakdown per platform
        for p in platforms:
            p_mentions = [m for m in mentions if m.platform == p]
            if p_mentions:
                # Basic per-platform score simulation for breakdown
                ms.platform_scores[p] = sum(m.sentiment_score for m in p_mentions) / len(p_mentions)
                
    return metric_scores

def compute_global_score(metric_scores: List[MetricScoreRecord]) -> float:
    """Compute Global GEO Score using category weights."""
    global_score = sum(ms.weighted_contribution for ms in metric_scores)
    return round(global_score, 2)
