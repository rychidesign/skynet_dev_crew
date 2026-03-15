"""Distribution computation for query generator agent."""
import math
from typing import Dict

from models.audit import QueryIntent


INTENT_MIN_RATIOS: Dict[str, float] = {
    QueryIntent.INFORMATIONAL.value: 0.15,
    QueryIntent.COMPARATIVE.value: 0.15,
    QueryIntent.RECOMMENDATION.value: 0.10,
    QueryIntent.AUTHORITY.value: 0.10,
    QueryIntent.FACTUAL.value: 0.10,
}


def compute_distribution(query_count: int) -> Dict[str, int]:
    """Computes the required distribution of query intents."""
    distribution: Dict[str, int] = {}
    remaining_count = query_count

    for intent, ratio in INTENT_MIN_RATIOS.items():
        min_count = math.ceil(ratio * query_count)
        distribution[intent] = min_count
        remaining_count -= min_count

    if remaining_count < 0:
        sorted_intents = sorted(
            [i for i in distribution if i != QueryIntent.NAVIGATIONAL.value],
            key=lambda x: distribution[x], reverse=True
        )
        for intent in sorted_intents:
            if remaining_count >= 0:
                break
            reduction = min(distribution[intent], abs(remaining_count))
            distribution[intent] -= reduction
            remaining_count += reduction
        if remaining_count < 0:
            distribution[QueryIntent.NAVIGATIONAL.value] = 0
    else:
        distribution[QueryIntent.NAVIGATIONAL.value] = remaining_count

    current_total = sum(distribution.values())
    if current_total > query_count:
        overage = current_total - query_count
        if distribution.get(QueryIntent.NAVIGATIONAL.value, 0) >= overage:
            distribution[QueryIntent.NAVIGATIONAL.value] -= overage
        else:
            remaining_overage = overage - distribution.get(QueryIntent.NAVIGATIONAL.value, 0)
            if QueryIntent.NAVIGATIONAL.value in distribution:
                distribution[QueryIntent.NAVIGATIONAL.value] = 0

            intents_to_reduce = sorted([
                k for k in distribution if k != QueryIntent.NAVIGATIONAL.value
            ], key=lambda x: distribution[x], reverse=True)

            for intent_name in intents_to_reduce:
                if remaining_overage <= 0:
                    break
                can_reduce = min(distribution[intent_name], remaining_overage)
                distribution[intent_name] -= can_reduce
                remaining_overage -= can_reduce

    for intent in distribution:
        distribution[intent] = max(0, distribution[intent])

    return distribution
