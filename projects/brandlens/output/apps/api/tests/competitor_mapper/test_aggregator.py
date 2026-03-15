import pytest
from collections import defaultdict
from typing import List, Tuple, Dict, Optional

from apps.api.agents.competitor_mapper.models import (
    CompetitorMention,
    CompetitorStats,
    BrandCompetitiveStats,
    PlatformCompetitorBreakdown,
    BrandMentionExtraction,
)
from apps.api.agents.competitor_mapper import aggregator

# --- Fixtures ---

@pytest.fixture
def sample_competitor_data() -> Tuple[List[str], str, Dict[str, str]]:
    return ["Competitor A", "Competitor B"], "Our Brand", {"Competitor A": "compA.com", "Competitor B": "compB.com"}


# --- Tests for Aggregator ---

def test_aggregate_competitors_basic(sample_competitor_data):
    competitor_names, brand_name, competitor_domains = sample_competitor_data
    total_comparative_responses = 2

    all_competitor_mentions_per_response = [
        ("resp1", [CompetitorMention(
            competitor_name="Competitor A", platform="chatgpt", response_id="resp1", query_intent="comparative",
            mention_position=10, is_recommended_first=True, sentiment="positive", comparative_language="good stuff"
        )]),
        ("resp2", [CompetitorMention(
            competitor_name="Competitor B", platform="perplexity", response_id="resp2", query_intent="recommendation",
            mention_position=50, is_recommended_first=False, sentiment="negative", comparative_language="bad stuff"
        )]),
        ("resp2", [CompetitorMention(
            competitor_name="Competitor A", platform="perplexity", response_id="resp2", query_intent="recommendation",
            mention_position=20, is_recommended_first=False, sentiment="neutral", comparative_language="neutral stuff"
        )]),
    ]

    all_brand_mentions_per_response = [
        ("resp1", BrandMentionExtraction(mentioned=True, position=5, is_recommended_first=False, sentiment="neutral", comparative_snippet="brand mention")),
        ("resp2", BrandMentionExtraction(mentioned=True, position=60, is_recommended_first=True, sentiment="positive", comparative_snippet="brand recommended"))
    ]

    comp_stats, brand_stats = aggregator.aggregate_competitors(
        all_competitor_mentions_per_response,
        all_brand_mentions_per_response,
        competitor_names,
        competitor_domains,
        brand_name,
        total_comparative_responses
    )

    assert len(comp_stats) == 2
    comp_a_stats = next(s for s in comp_stats if s.competitor_name == "Competitor A")
    assert comp_a_stats.total_appearances == 2
    assert comp_a_stats.recommendation_count == 1
    assert comp_a_stats.avg_mention_position == 15.0 # (10+20)/2
    assert comp_a_stats.positive_comparisons == 1
    assert comp_a_stats.neutral_comparisons == 1
    assert "chatgpt" in comp_a_stats.platform_breakdown
    assert comp_a_stats.platform_breakdown["chatgpt"].appearances == 1
    assert comp_a_stats.platform_breakdown["chatgpt"].avg_position == 10.0

    comp_b_stats = next(s for s in comp_stats if s.competitor_name == "Competitor B")
    assert comp_b_stats.total_appearances == 1
    assert comp_b_stats.recommendation_count == 0
    assert comp_b_stats.negative_comparisons == 1

    assert brand_stats.brand_name == "Our Brand"
    assert brand_stats.total_comparative_responses == 2
    assert brand_stats.recommendation_count == 1
    assert brand_stats.positive_comparisons == 1
    assert brand_stats.avg_mention_position == 32.5 # (5+60)/2
