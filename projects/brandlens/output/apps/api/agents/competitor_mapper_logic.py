import json
from typing import List, Dict, Any
import structlog

from .competitor_mapper_data import CompetitorMention, CompetitorStats

def build_extraction_prompt(
    response_text: str,
    competitors: List[str],
    platform: str,
    query_text: str
) -> str:
    """Build JSON-requesting prompt asking LLM to find each competitor in response,
    their position rank, whether recommended before brand, sentiment toward competitor,
    and any comparative language phrases used."""
    competitors_str = ", ".join(competitors)
    prompt = f"""
AI Response from {platform} for query "{query_text}":
---
{response_text}
---

Analyze the AI response above and extract information about the following competitors: {competitors_str}.
Return a JSON array of objects as described in the system prompt.
"""
    return prompt

def parse_llm_output(
    raw_output: str,
    response_id: str,
    platform: str,
    competitors: List[str],
    log_ctx: structlog.BoundLogger
) -> List[CompetitorMention]:
    """Parse JSON list from LLM output into CompetitorMention list.
    Falls back to empty list on parse error (logged as warning)."""
    try:
        data = json.loads(raw_output)
        if not isinstance(data, list):
            log_ctx.warning("LLM output is not a JSON list", raw_output=raw_output)
            return []
        
        mentions = []
        for item in data:
            if not isinstance(item, dict):
                log_ctx.warning("LLM output item is not a dictionary", item=item)
                continue

            name = item.get("name")
            if not name or name not in competitors: # Ensure competitor is from our list
                continue

            mentions.append(
                CompetitorMention(
                    response_id=response_id,
                    platform=platform,
                    competitor_name=name,
                    position_rank=item.get("position_rank"),
                    is_recommended_first=item.get("is_recommended_first", False),
                    sentiment=item.get("sentiment", "neutral"),
                    comparative_language=item.get("comparative_language", [])
                )
            )
        return mentions
    except json.JSONDecodeError:
        log_ctx.warning("Failed to parse LLM output as JSON", raw_output=raw_output)
        return []
    except Exception as e:
        log_ctx.error("Error parsing LLM output", error=str(e), raw_output=raw_output)
        return []

def aggregate_competitor_stats(
    mentions: List[CompetitorMention],
    competitors: List[str],
    competitor_domains: Dict[str, str]
) -> List[CompetitorStats]:
    """
    For each known competitor:
    - Count total_appearances across all mentions
    - Compute avg_mention_position (mean of non-None position_ranks)
    - Count recommendation_count (sum of is_recommended_first=True)
    - Count positive/negative/neutral_comparisons by sentiment field
    - Build platform_breakdown dict: per platform { appearances, avg_position, recommendation_count }
    Returns a CompetitorStats per competitor (even if 0 appearances).
    """
    stats_map: Dict[str, CompetitorStats] = {
        comp: CompetitorStats(
            competitor_name=comp,
            competitor_domain=competitor_domains.get(comp),
            total_appearances=0,
            avg_mention_position=None,
            recommendation_count=0,
            positive_comparisons=0,
            negative_comparisons=0,
            neutral_comparisons=0,
            platform_breakdown={}
        ) for comp in competitors
    }

    for mention in mentions:
        comp_name = mention.competitor_name
        if comp_name not in stats_map:
            continue # Should not happen if parse_llm_output filters correctly

        stats = stats_map[comp_name]
        stats.total_appearances += 1
        
        if mention.is_recommended_first:
            stats.recommendation_count += 1
        
        if mention.sentiment == "positive":
            stats.positive_comparisons += 1
        elif mention.sentiment == "negative":
            stats.negative_comparisons += 1
        else: # neutral or unknown
            stats.neutral_comparisons += 1

        # Aggregate for platform breakdown
        platform_stats = stats.platform_breakdown.setdefault(mention.platform, {
            "appearances": 0,
            "position_ranks": [], # Store to calculate average later
            "recommendation_count": 0
        })
        platform_stats["appearances"] += 1
        if mention.position_rank is not None:
            platform_stats["position_ranks"].append(mention.position_rank)
        if mention.is_recommended_first:
            platform_stats["recommendation_count"] += 1

    # Finalize averages and remove temporary 'position_ranks'
    for comp_name, stats in stats_map.items():
        all_positions = [m.position_rank for m in mentions if m.competitor_name == comp_name and m.position_rank is not None]
        if all_positions:
            stats.avg_mention_position = round(sum(all_positions) / len(all_positions), 2)
        
        for platform, p_stats in stats.platform_breakdown.items():
            if p_stats["position_ranks"]:
                p_stats["avg_position"] = round(sum(p_stats["position_ranks"]) / len(p_stats["position_ranks"]), 2)
            else:
                p_stats["avg_position"] = None
            del p_stats["position_ranks"] # Remove temporary key

    return list(stats_map.values())

def competitor_stats_to_db_dict(stats: CompetitorStats, audit_id: str) -> Dict[str, Any]:
    """Convert CompetitorStats to dict matching audit_competitors table columns."""
    return {
        "audit_id": audit_id,
        "competitor_name": stats.competitor_name,
        "competitor_domain": stats.competitor_domain,
        "avg_mention_position": stats.avg_mention_position,
        "recommendation_count": stats.recommendation_count,
        "total_appearances": stats.total_appearances,
        "positive_comparisons": stats.positive_comparisons,
        "negative_comparisons": stats.negative_comparisons,
        "neutral_comparisons": stats.neutral_comparisons,
        "platform_breakdown": stats.platform_breakdown,
    }
