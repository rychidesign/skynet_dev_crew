import pytest
from typing import Dict

from apps.api.agents.query_distribution_logic import compute_distribution
from apps.api.agents.query_constants import INTENT_MIN_RATIOS
from models.audit import QueryIntent

class TestComputeDistribution:
    @pytest.mark.parametrize("query_count, expected_distribution", [
        (10, {
            QueryIntent.INFORMATIONAL.value: 2,
            QueryIntent.COMPARATIVE.value: 2,
            QueryIntent.RECOMMENDATION.value: 1,
            QueryIntent.AUTHORITY.value: 1,
            QueryIntent.FACTUAL.value: 1,
            QueryIntent.NAVIGATIONAL.value: 3, # 10 - (2+2+1+1+1) = 3
        }),
        (50, {
            QueryIntent.INFORMATIONAL.value: 8,  # ceil(0.15 * 50) = 8
            QueryIntent.COMPARATIVE.value: 8,
            QueryIntent.RECOMMENDATION.value: 5, # ceil(0.10 * 50) = 5
            QueryIntent.AUTHORITY.value: 5,
            QueryIntent.FACTUAL.value: 5,
            QueryIntent.NAVIGATIONAL.value: 19, # 50 - (8+8+5+5+5) = 19
        }),
        (5, { # Test small N where sum of minimums might exceed total
            QueryIntent.INFORMATIONAL.value: 1, # ceil(0.15*5) = 1
            QueryIntent.COMPARATIVE.value: 1,
            QueryIntent.RECOMMENDATION.value: 1, # ceil(0.10*5) = 1
            QueryIntent.AUTHORITY.value: 1,
            QueryIntent.FACTUAL.value: 1,
            QueryIntent.NAVIGATIONAL.value: 0, # 5 - 5 = 0. Should not be negative.
        }),
        (200, {
            QueryIntent.INFORMATIONAL.value: 30, # ceil(0.15*200) = 30
            QueryIntent.COMPARATIVE.value: 30,
            QueryIntent.RECOMMENDATION.value: 20, # ceil(0.10*200) = 20
            QueryIntent.AUTHORITY.value: 20,
            QueryIntent.FACTUAL.value: 20,
            QueryIntent.NAVIGATIONAL.value: 80, # 200 - (30*2 + 20*3) = 200 - 120 = 80
        }),
    ])
    def test_compute_distribution_minimums_and_totals(self, query_count, expected_distribution):
        actual_distribution = compute_distribution(query_count)
        
        # Ensure all intents are present, even if 0
        all_intents = set(INTENT_MIN_RATIOS.keys()) | {QueryIntent.NAVIGATIONAL.value}
        assert set(actual_distribution.keys()) == all_intents

        for intent, expected_count in expected_distribution.items():
            assert actual_distribution[intent] == expected_count, f"Intent {intent} failed"
        
        assert sum(actual_distribution.values()) == query_count, "Total query count mismatch"
