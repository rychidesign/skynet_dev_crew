"""
Logic for computing query intent distribution for the Query Generator agent.
"""
import math
from typing import Dict

from apps.api.agents.query_constants import INTENT_MIN_RATIOS
from apps.api.models.audit import QueryIntent

def compute_distribution(query_count: int) -> Dict[str, int]:
    """Computes the required distribution of query intents."""
    distribution: Dict[str, int] = {}
    remaining_count = query_count

    # Calculate minimums
    for intent, ratio in INTENT_MIN_RATIOS.items():
        min_count = max(1, math.ceil(ratio * query_count))
        distribution[intent] = min_count
        remaining_count -= min_count

    # Handle overflow if sum of minimums > query_count (for very small N)
    if remaining_count < 0:
        overflow = abs(remaining_count)
        # Prioritize reducing from informational/comparative if they are largest
        intents_to_reduce = sorted(
            [i for i in distribution if i != QueryIntent.NAVIGATIONAL.value],
            key=lambda x: distribution[x], reverse=True
        )
        for intent in intents_to_reduce:
            if overflow <= 0: break
            reduction = min(distribution[intent] - 1, overflow) # Leave at least 1
            if distribution[intent] > 1 and reduction > 0:
                distribution[intent] -= reduction
                overflow -= reduction
        remaining_count = -overflow # Recalculate remaining_count after reduction
    
    # Assign remaining to navigational, ensuring it's not negative
    distribution[QueryIntent.NAVIGATIONAL.value] = max(0, remaining_count)
    
    # Final adjustment to ensure total equals query_count due to rounding/reductions
    current_total = sum(distribution.values())
    if current_total != query_count:
        diff = query_count - current_total
        if diff > 0: # Need to add queries
            distribution[QueryIntent.NAVIGATIONAL.value] += diff
        else: # Need to remove queries (diff is negative)
            # Prefer reducing navigational first, then other large intents
            reduction_target = QueryIntent.NAVIGATIONAL.value
            if distribution[reduction_target] >= abs(diff):
                distribution[reduction_target] += diff
            else:
                # If navigational is not enough, distribute reduction among other intents
                remaining_diff = abs(diff) - distribution[reduction_target]
                distribution[reduction_target] = 0
                intents_to_reduce = sorted(
                    [i for i in distribution if i != QueryIntent.NAVIGATIONAL.value],
                    key=lambda x: distribution[x], reverse=True
                )
                for intent_name in intents_to_reduce:
                    if remaining_diff <= 0: break
                    can_reduce = min(distribution[intent_name], remaining_diff)
                    distribution[intent_name] -= can_reduce
                    remaining_diff -= can_reduce

    # Ensure no intent has negative count
    for intent in distribution:
        distribution[intent] = max(0, distribution[intent])

    return distribution
