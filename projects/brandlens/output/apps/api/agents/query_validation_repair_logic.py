"""
Logic for validating and repairing generated queries for the Query Generator agent.
This includes enforcing query text constraints, intent validity, metric mapping,
intent distribution minimums, and brand name ratio.
"""
import random
import structlog
from typing import Any, Dict, List

from apps.api.models.audit import QueryIntent
from apps.api.agents.query_models import CompanyProfile, QuerySpec
from apps.api.agents.query_constants import (
    INTENT_METRIC_MAP, VALID_METRIC_IDS, MAX_BRAND_NAME_RATIO, FALLBACK_TEMPLATES
)

logger = structlog.get_logger(__name__)

def validate_and_build_specs(
    raw_queries: List[Dict[str, Any]], query_count: int
) -> List[QuerySpec]:
    """Parses raw LLM output and validates it into QuerySpec objects."""
    queries: List[QuerySpec] = []
    for idx, item in enumerate(raw_queries):
        try:
            query_text = str(item.get("query_text", "")).strip()
            intent = str(item.get("intent", "")).strip()
            target_metrics = list(item.get("target_metrics", []))

            # Validate query_text length
            if len(query_text) < 3:
                logger.warning(f"Skipping query due to short text: '{query_text}'")
                continue
            if len(query_text) > 500:
                query_text = query_text[:500] + "..."

            # Validate intent
            if intent not in [i.value for i in QueryIntent]:
                logger.warning(f"LLM generated invalid intent '{intent}', defaulting to informational.")
                intent = QueryIntent.INFORMATIONAL.value
            
            # Validate target metrics against the map
            valid_metrics = [m for m in target_metrics if m in VALID_METRIC_IDS]
            if not valid_metrics:
                # If LLM failed, use defaults from INTENT_METRIC_MAP
                logger.warning(f"LLM generated invalid or empty target_metrics for query '{query_text}', using default for intent.")
                valid_metrics = INTENT_METRIC_MAP.get(intent, ["GEO-01-ENT-SAL"]) # Fallback to a core metric
            
            queries.append(
                QuerySpec(
                    query_text=query_text,
                    intent=intent,
                    target_metrics=valid_metrics,
                    query_index=idx,
                )
            )
        except (KeyError, TypeError) as e:
            logger.error(f"Failed to parse LLM generated query item: {item}. Error: {e}")
            continue
    
    # Truncate if LLM generated too many (unlikely after prompt, but for safety)
    if len(queries) > query_count:
        logger.warning(f"LLM generated {len(queries)} queries, truncating to {query_count}.")
        queries = queries[:query_count]

    return queries

def repair_distribution(
    queries: List[QuerySpec], distribution: Dict[str, int], profile: CompanyProfile
) -> List[QuerySpec]:
    """
    Repairs generated queries to enforce distribution minimums and brand name ratio.
    Adds synthetic queries for missing intents and adjusts brand mentions.
    """
    repaired_queries = list(queries) # Start with a mutable copy
    
    # Step 1: Fill missing intents
    current_intent_counts: Dict[str, int] = {i.value: 0 for i in QueryIntent}
    for q in repaired_queries:
        current_intent_counts[q.intent] += 1

    for intent, required_count in distribution.items():
        if current_intent_counts.get(intent, 0) < required_count:
            deficit = required_count - current_intent_counts.get(intent, 0)
            logger.info(f"Adding {deficit} synthetic queries for intent '{intent}'.")
            
            for i in range(deficit):
                # Use a random template for variety
                template = random.choice(FALLBACK_TEMPLATES.get(intent, ["Generic query about {name}"]))
                
                # Fill template variables dynamically
                filled_query_text = template.format(
                    name=profile.name,
                    industry=profile.industry or "technology",
                    competitor=profile.competitors[0] if profile.competitors else "competitors",
                    topic=profile.core_topics[0] if profile.core_topics else "this topic"
                )
                
                repaired_queries.append(
                    QuerySpec(
                        query_text=f"FALLBACK: {filled_query_text} (intent: {intent})",
                        intent=intent,
                        target_metrics=INTENT_METRIC_MAP.get(intent, ["GEO-01-ENT-SAL"]),
                        query_index=0 # Will be re-indexed later
                    )
                )

    # Re-index queries after potential additions to ensure correct indexing for brand ratio check
    for idx, q in enumerate(repaired_queries):
        q.query_index = idx

    # Step 2: Enforce brand name ratio
    queries_with_brand = [
        q for q in repaired_queries if profile.name.lower() in q.query_text.lower()
    ]
    if len(queries_with_brand) > len(repaired_queries) * MAX_BRAND_NAME_RATIO:
        excess_queries_count = int(len(queries_with_brand) - (len(repaired_queries) * MAX_BRAND_NAME_RATIO))
        logger.warning(f"Brand name ratio exceeded, attempting to strip brand name from {excess_queries_count} queries.")
        
        # Randomly select queries that contain the brand name to modify
        random.shuffle(queries_with_brand)
        for i in range(min(excess_queries_count, len(queries_with_brand))):
            original_query = queries_with_brand[i].query_text
            
            # Replace brand name with a generic placeholder or topic
            if profile.core_topics:
                replacement_phrase = random.choice(profile.core_topics)
            else:
                replacement_phrase = "the company"

            new_query_text = original_query.replace(profile.name, replacement_phrase, 1) # Replace only first occurrence
            
            if new_query_text == original_query: # Fallback if direct replace didn't work (e.g., case mismatch)
                new_query_text = f"Information about {queries_with_brand[i].intent.lower()} aspects of {replacement_phrase}."
            
            queries_with_brand[i].query_text = new_query_text

    # Step 3: Final truncation/padding to exact query_count
    # This is done *after* intent repair and brand ratio enforcement
    final_query_count = sum(distribution.values()) # Should be equal to initial query_count but for safety

    if len(repaired_queries) > final_query_count:
        logger.warning(f"After repair, {len(repaired_queries)} queries, truncating to target {final_query_count}.")
        repaired_queries = repaired_queries[:final_query_count]
    while len(repaired_queries) < final_query_count:
        logger.warning(f"After repair, {len(repaired_queries)} queries, padding to target {final_query_count} with navigational.")
        repaired_queries.append(
            QuerySpec(
                query_text=f"FALLBACK: General search about the industry. (PADDED)",
                intent=QueryIntent.NAVIGATIONAL.value,
                target_metrics=INTENT_METRIC_MAP.get(QueryIntent.NAVIGATIONAL.value, []),
                query_index=0 # Will be re-indexed
            )
        )
    
    # Final re-index of all queries to ensure sequential 0-based indexing
    for idx, q in enumerate(repaired_queries):
        q.query_index = idx

    return repaired_queries
