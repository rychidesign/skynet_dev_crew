from typing import List, Optional, Dict, Any, Tuple
import statistics
import logging

from apps.api.agents.competitor_mapper_constants_and_types import CompetitorMentionResult, FilteredResponse, CompetitorRecord

log = logging.getLogger(__name__)

def build_platform_breakdown(
    per_platform_data: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Assembles the JSONB platform_breakdown dict.
    """
    breakdown: Dict[str, Any] = {}
    for platform, data in per_platform_data.items():
        if not data:
            continue

        platform_appearances = data.get("appearances", 0)
        platform_recommendation_count = data.get("recommendation_count", 0)
        
        position_ranks = [p for p in data.get("position_ranks", []) if p is not None]
        platform_avg_position = statistics.mean(position_ranks) if position_ranks else None

        sentiments = data.get("sentiments", [])
        sentiment_counts = {
            "positive": sentiments.count("positive"),
            "negative": sentiments.count("negative"),
            "neutral": sentiments.count("neutral"),
        }
        
        dominant_sentiment = "neutral"
        if sentiment_counts["positive"] > sentiment_counts["negative"] and sentiment_counts["positive"] > sentiment_counts["neutral"]:
            dominant_sentiment = "positive"
        elif sentiment_counts["negative"] > sentiment_counts["positive"] and sentiment_counts["negative"] > sentiment_counts["neutral"]:
            dominant_sentiment = "negative"
        # If tie or all neutral/zero, remains neutral


        breakdown[platform] = {
            "appearances": platform_appearances,
            "recommendation_count": platform_recommendation_count,
            "avg_position": platform_avg_position,
            "dominant_sentiment": dominant_sentiment,
        }
    return breakdown


def aggregate_competitor_records(
    all_mentions_across_responses: List[Tuple[FilteredResponse, List[CompetitorMentionResult]]],
    all_competitors: List[str],
    audit_id: str,
    log_ctx: logging.Logger,
) -> List[CompetitorRecord]:
    """
    Aggregates all per-response LLM results into one CompetitorRecord per competitor.
    """
    competitor_data: Dict[str, Dict[str, Any]] = {
        comp: {
            "position_ranks": [],
            "recommendation_count": 0,
            "total_appearances": 0,
            "positive_comparisons": 0,
            "negative_comparisons": 0,
            "neutral_comparisons": 0,
            "platforms": {}, # {platform: {appearances, recommendation_count, position_ranks, sentiments}}
        } for comp in all_competitors
    }

    # Initialize platform data for each competitor
    for comp_name in all_competitors:
        competitor_data[comp_name]["platforms"] = {}

    for response, mentions in all_mentions_across_responses:
        for mention in mentions:
            comp_name = mention.competitor_name
            if comp_name not in competitor_data:
                log_ctx.warning(f"Competitor '{comp_name}' found in LLM output but not in initial list for audit {audit_id}. Skipping.")
                continue
            
            comp_data = competitor_data[comp_name]
            comp_data["total_appearances"] += 1

            # Aggregate overall stats
            if mention.position_rank is not None:
                comp_data["position_ranks"].append(mention.position_rank)
            if mention.is_recommended:
                comp_data["recommendation_count"] += 1
            if mention.comparison_sentiment == "positive":
                comp_data["positive_comparisons"] += 1
            elif mention.comparison_sentiment == "negative":
                comp_data["negative_comparisons"] += 1
            elif mention.comparison_sentiment == "neutral":
                comp_data["neutral_comparisons"] += 1
            
            # Aggregate per-platform stats
            platform = response.platform
            if platform not in comp_data["platforms"]:
                comp_data["platforms"][platform] = {
                    "appearances": 0,
                    "recommendation_count": 0,
                    "position_ranks": [],
                    "sentiments": [],
                }
            
            platform_data = comp_data["platforms"][platform]
            platform_data["appearances"] += 1
            if mention.position_rank is not None:
                platform_data["position_ranks"].append(mention.position_rank)
            if mention.is_recommended:
                platform_data["recommendation_count"] += 1
            platform_data["sentiments"].append(mention.comparison_sentiment)

    # Convert aggregated data into CompetitorRecord objects
    competitor_records: List[CompetitorRecord] = []
    for comp_name, data in competitor_data.items():
        avg_pos = statistics.mean(data["position_ranks"]) if data["position_ranks"] else None
        
        # Determine competitor domain if available (simple heuristic for now)
        competitor_domain = None
        for c in all_competitors:
            if c == comp_name and "." in c: # If the competitor name itself looks like a domain
                competitor_domain = c
                break
            
        platform_breakdown = build_platform_breakdown(data["platforms"])

        competitor_records.append(
            CompetitorRecord(
                audit_id=audit_id,
                competitor_name=comp_name,
                competitor_domain=competitor_domain,
                avg_mention_position=avg_pos,
                recommendation_count=data["recommendation_count"],
                total_appearances=data["total_appearances"],
                positive_comparisons=data["positive_comparisons"],
                negative_comparisons=data["negative_comparisons"],
                neutral_comparisons=data["neutral_comparisons"],
                platform_breakdown=platform_breakdown,
            )
        )
    return competitor_records
