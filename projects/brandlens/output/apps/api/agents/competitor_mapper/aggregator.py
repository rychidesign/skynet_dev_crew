from typing import List, Dict, Tuple, Optional
from collections import defaultdict

from apps.api.agents.competitor_mapper.models import (
    CompetitorMention,
    BrandMentionExtraction,
    CompetitorStats,
    PlatformCompetitorBreakdown,
    BrandCompetitiveStats,
)

def aggregate_competitor_stats(
    all_competitor_mentions: List[CompetitorMention],
    all_brand_mentions: List[BrandMentionExtraction], # Note: Expects platform attribute added in extractor
    competitor_names: List[str],
    competitor_domains: Dict[str, str],
    brand_name: str,
    total_comparative_responses: int,
) -> Tuple[List[CompetitorStats], BrandCompetitiveStats]:
    """
    Aggregates competitor and brand mention statistics.
    """

    competitor_stats_map: Dict[str, CompetitorStats] = defaultdict(
        lambda: CompetitorStats(competitor_name="", platform_breakdown={})
    )

    # Aggregate Competitor Mentions
    for mention in all_competitor_mentions:
        comp_name = mention.competitor_name
        if comp_name not in competitor_stats_map:
            competitor_stats_map[comp_name].competitor_name = comp_name
            competitor_stats_map[comp_name].competitor_domain = competitor_domains.get(comp_name)
        
        stats = competitor_stats_map[comp_name]
        stats.total_appearances += 1
        if mention.is_recommended_first: 
            stats.recommendation_count += 1
        
        if mention.sentiment == "positive":
            stats.positive_comparisons += 1
        elif mention.sentiment == "negative":
            stats.negative_comparisons += 1
        else:
            stats.neutral_comparisons += 1

        # Platform breakdown
        if mention.platform not in stats.platform_breakdown:
            stats.platform_breakdown[mention.platform] = PlatformCompetitorBreakdown(
                appearances=0, avg_position=None, recommendation_count=0, positive_comparisons=0, negative_comparisons=0, neutral_comparisons=0
            )
        platform_breakdown = stats.platform_breakdown[mention.platform]
        platform_breakdown.appearances += 1
        if mention.is_recommended_first:
            platform_breakdown.recommendation_count += 1
        if mention.sentiment == "positive":
            platform_breakdown.positive_comparisons += 1
        elif mention.sentiment == "negative":
            platform_breakdown.negative_comparisons += 1
        else:
            platform_breakdown.neutral_comparisons += 1
        
        # For avg_position, we need to collect all positions per platform first then average
        # This will be done in a second pass or accumulated.
        # For now, we will store the sum of positions and count to calculate average later.
        if not hasattr(stats.platform_breakdown[mention.platform], '_sum_positions'):
            setattr(stats.platform_breakdown[mention.platform], '_sum_positions', 0)
        stats.platform_breakdown[mention.platform]._sum_positions += mention.mention_position
    
    # Calculate average positions for competitors
    for comp_name, stats in competitor_stats_map.items():
        total_positions = 0
        total_mentions_for_avg = 0
        for platform, breakdown in stats.platform_breakdown.items():
            if hasattr(breakdown, '_sum_positions') and breakdown.appearances > 0:
                breakdown.avg_position = breakdown._sum_positions / breakdown.appearances
                total_positions += breakdown._sum_positions
                total_mentions_for_avg += breakdown.appearances
            # Clean up temporary attribute
            if hasattr(breakdown, '_sum_positions'):
                delattr(breakdown, '_sum_positions')
        
        if total_mentions_for_avg > 0:
            stats.avg_mention_position = total_positions / total_mentions_for_avg


    # Aggregate Brand Mentions
    brand_competitive_stats = BrandCompetitiveStats(
        brand_name=brand_name,
        total_comparative_responses=total_comparative_responses,
    )
    brand_platform_breakdown: Dict[str, PlatformCompetitorBreakdown] = defaultdict(
        lambda: PlatformCompetitorBreakdown(
            appearances=0, avg_position=None, recommendation_count=0, positive_comparisons=0, negative_comparisons=0, neutral_comparisons=0
        )
    )
    brand_total_positions = 0
    brand_total_mentions_for_avg = 0

    for brand_mention in all_brand_mentions:
        # Ensure platform is present, added during extraction
        platform = getattr(brand_mention, 'platform', 'unknown')

        brand_competitive_stats.total_comparative_responses += 1 # This should be the total number of responses, not per mention

        if brand_mention.is_recommended_first:
            brand_competitive_stats.recommendation_count += 1
            brand_platform_breakdown[platform].recommendation_count += 1
        
        if brand_mention.sentiment == "positive":
            brand_competitive_stats.positive_comparisons += 1
            brand_platform_breakdown[platform].positive_comparisons += 1
        elif brand_mention.sentiment == "negative":
            brand_competitive_stats.negative_comparisons += 1
            brand_platform_breakdown[platform].negative_comparisons += 1
        else:
            brand_competitive_stats.neutral_comparisons += 1
            brand_platform_breakdown[platform].neutral_comparisons += 1

        if brand_mention.mentioned and brand_mention.position is not None:
            brand_platform_breakdown[platform].appearances += 1
            brand_total_positions += brand_mention.position
            brand_total_mentions_for_avg += 1
            
            if not hasattr(brand_platform_breakdown[platform], '_sum_positions'):
                setattr(brand_platform_breakdown[platform], '_sum_positions', 0)
            brand_platform_breakdown[platform]._sum_positions += brand_mention.position
    
    # Calculate average positions for brand
    for platform, breakdown in brand_platform_breakdown.items():
        if hasattr(breakdown, '_sum_positions') and breakdown.appearances > 0:
            breakdown.avg_position = breakdown._sum_positions / breakdown.appearances
        if hasattr(breakdown, '_sum_positions'):
            delattr(breakdown, '_sum_positions') # Clean up temp attribute
    
    if brand_total_mentions_for_avg > 0:
        brand_competitive_stats.avg_mention_position = brand_total_positions / brand_total_mentions_for_avg

    brand_competitive_stats.platform_breakdown = dict(brand_platform_breakdown)

    return list(competitor_stats_map.values()), brand_competitive_stats
