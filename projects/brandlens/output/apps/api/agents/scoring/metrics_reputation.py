from typing import List, Dict, Any, Optional
import statistics
from .score_models import MetricScoreResult, ScoringContext, METRIC_WEIGHTS, METRIC_CATEGORIES, HallucinationFinding

def compute_geo13(context: ScoringContext) -> MetricScoreResult:
    """GEO-13-SNT-POL: Sentiment Polarity"""
    brand_mentions = [m for m in context.mentions if m.get("entity_name") == context.company_name]
    
    # Sort responses by created_at to identify recent 25% if available
    # For now, simple weighted average of sentiment_scores
    sentiments = [m.get("sentiment_score") for m in brand_mentions if m.get("sentiment_score") is not None]
    avg_sentiment = statistics.mean(sentiments) if sentiments else 0.0
    
    score = ((avg_sentiment + 1) / 2) * 100
    
    return MetricScoreResult(
        metric_id="GEO-13-SNT-POL",
        metric_category=METRIC_CATEGORIES["GEO-13-SNT-POL"],
        score=round(score, 2),
        components={"avg_sentiment": round(avg_sentiment, 2)},
        weight=METRIC_WEIGHTS["GEO-13-SNT-POL"],
        weighted_contribution=0.0
    )

def compute_geo14(context: ScoringContext) -> MetricScoreResult:
    """GEO-14-CMP-PST: Competitive Position"""
    # Use brand_competitive_stats from state or competitors_data list
    # brand_avg_pos = context.competitors_data.get("brand_avg_position", 1.0)
    # Since competitors_data is a list of rows, we look for brand row
    brand_row = next((r for r in context.competitors_data if r.get("entity_name") == context.company_name), {})
    brand_avg_pos = brand_row.get("avg_rank", 1.0)
    
    num_competitors = len(context.competitors)
    mention_order = max(0, 1 - (brand_avg_pos - 1) / max(num_competitors, 1))
    
    # Recommendation rate: times mentioned first in comparison context
    recommendation_rate = brand_row.get("share_of_voice", 0.0) 
    # Comparative advantage: positive mentions / total comparisons
    comp_adv = brand_row.get("sentiment_avg", 0.0)
    
    score = (0.4 * mention_order + 0.3 * recommendation_rate + 0.3 * comp_adv) * 100
    
    return MetricScoreResult(
        metric_id="GEO-14-CMP-PST",
        metric_category=METRIC_CATEGORIES["GEO-14-CMP-PST"],
        score=round(score, 2),
        components={
            "mention_order": round(mention_order, 2),
            "recommendation_rate": round(recommendation_rate, 2),
            "comparative_advantage": round(comp_adv, 2)
        },
        weight=METRIC_WEIGHTS["GEO-14-CMP-PST"],
        weighted_contribution=0.0
    )

def compute_geo16(context: ScoringContext, hallucinations: List[HallucinationFinding]) -> MetricScoreResult:
    """GEO-16-HAL-RSK: Hallucination Risk"""
    weighted_hallucinations = 0.0
    for h in hallucinations:
        if h.severity == "critical": weighted_hallucinations += 2.0
        elif h.severity == "major": weighted_hallucinations += 1.0
        else: weighted_hallucinations += 0.5
            
    # Estimate total_claims based on mention attributes extracted
    total_claims = sum(len(m.get("extracted_attributes", {})) for m in context.mentions)
    total_claims = max(total_claims, len(context.responses) * 2) # Fallback estimate
    
    hallucination_rate = weighted_hallucinations / max(total_claims, 1)
    score = max(0.0, (1 - hallucination_rate) * 100)
    
    return MetricScoreResult(
        metric_id="GEO-16-HAL-RSK",
        metric_category=METRIC_CATEGORIES["GEO-16-HAL-RSK"],
        score=round(score, 2),
        components={
            "weighted_hallucinations": weighted_hallucinations,
            "total_claims": total_claims
        },
        weight=METRIC_WEIGHTS["GEO-16-HAL-RSK"],
        weighted_contribution=0.0
    )
