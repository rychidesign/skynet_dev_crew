"""Competitor Mapper aggregator — pure aggregation logic."""
from __future__ import annotations

from typing import Dict, List

from .competitor_mapper_helpers import CompetitorMention, CompetitorStats


def aggregate_competitor_stats(
    mentions: list[CompetitorMention],
    known_competitors: list[str],
    competitor_domains: dict[str, str]
) -> list[CompetitorStats]:
    """
    Aggregate per-response mentions into per-competitor statistics.
    
    Only includes competitors found in known_competitors list (case-insensitive match).
    """
    # Normalize known competitors to lowercase for case-insensitive matching
    normalized_known = {c.lower(): c for c in known_competitors}
    normalized_domains = {k.lower(): v for k, v in competitor_domains.items()}
    
    # Group mentions by competitor name
    mentions_by_competitor: Dict[str, List[CompetitorMention]] = {}
    
    for mention in mentions:
        mention_name_lower = mention.competitor_name.lower()
        # Only include if this competitor is in known list
        if mention_name_lower in normalized_known:
            canonical_name = normalized_known[mention_name_lower]
            if canonical_name not in mentions_by_competitor:
                mentions_by_competitor[canonical_name] = []
            mentions_by_competitor[canonical_name].append(mention)
    
    # Build CompetitorStats for each competitor
    stats_list: list[CompetitorStats] = []
    
    for competitor_name, competitor_mentions in mentions_by_competitor.items():
        stats = CompetitorStats(
            competitor_name=competitor_name,
            competitor_domain=normalized_domains.get(competitor_name.lower()),
            total_appearances=len(competitor_mentions),
            mention_positions=[m.mention_position for m in competitor_mentions],
            recommendation_count=sum(1 for m in competitor_mentions if m.is_recommended_first),
            positive_comparisons=sum(1 for m in competitor_mentions if m.comparative_sentiment == "positive"),
            negative_comparisons=sum(1 for m in competitor_mentions if m.comparative_sentiment == "negative"),
            neutral_comparisons=sum(1 for m in competitor_mentions if m.comparative_sentiment == "neutral"),
            platform_data={}
        )
        
        # Build platform breakdown
        platform_stats: Dict[str, Dict] = {}
        for m in competitor_mentions:
            platform = m.platform
            if platform not in platform_stats:
                platform_stats[platform] = {
                    "appearances": 0,
                    "recommendation_count": 0,
                    "positions": []
                }
            platform_stats[platform]["appearances"] += 1
            if m.is_recommended_first:
                platform_stats[platform]["recommendation_count"] += 1
            platform_stats[platform]["positions"].append(m.mention_position)
        
        # Calculate avg_position per platform
        for platform, pdata in platform_stats.items():
            positions = pdata.pop("positions")
            pdata["avg_position"] = round(sum(positions) / len(positions), 2) if positions else 0.0
        
        stats.platform_data = platform_stats
        stats_list.append(stats)
    
    return stats_list
