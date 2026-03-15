"""Validation and repair functions for query generator agent."""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import random
import structlog

from models.audit import QueryIntent

logger = structlog.get_logger(__name__)

INTENT_METRIC_MAP: Dict[str, List[str]] = {
    QueryIntent.INFORMATIONAL.value: ["GEO-01-ENT-SAL", "GEO-03-ENT-CON", "GEO-04-TOP-AUTH"],
    QueryIntent.COMPARATIVE.value: ["GEO-14-CMP-PST", "GEO-01-ENT-SAL"],
    QueryIntent.RECOMMENDATION.value: ["GEO-14-CMP-PST", "GEO-13-SNT-POL"],
    QueryIntent.AUTHORITY.value: ["GEO-04-TOP-AUTH", "GEO-05-CIT-FRQ", "GEO-07-RAG-INC"],
    QueryIntent.FACTUAL.value: ["GEO-16-HAL-RSK", "GEO-03-ENT-CON", "GEO-01-ENT-SAL"],
    QueryIntent.NAVIGATIONAL.value: ["GEO-17-CRW-ACC", "GEO-11-FRS-REC", "GEO-01-ENT-SAL"],
}

MAX_BRAND_NAME_RATIO = 0.60


@dataclass
class CompanyProfile:
    company_id: str
    name: str
    industry: Optional[str]
    description: Optional[str]
    competitors: List[str]
    core_topics: List[str]
    facts: Dict[str, Any]


@dataclass
class QuerySpec:
    query_text: str
    intent: str
    target_metrics: List[str]
    query_index: int


def validate_and_repair(
    queries: List[QuerySpec], distribution: Dict[str, int], profile: CompanyProfile, query_count: int
) -> List[QuerySpec]:
    """Validates generated queries against distribution and brand name ratio."""
    repaired_queries = list(queries)

    if len(repaired_queries) > query_count:
        logger.warning(f"Too many queries generated ({len(repaired_queries)} > {query_count}), truncating.")
        repaired_queries = repaired_queries[:query_count]

    current_intent_counts: Dict[str, int] = {intent: 0 for intent in QueryIntent}
    for q in repaired_queries:
        current_intent_counts[q.intent] += 1

    for intent, required_count in distribution.items():
        if current_intent_counts.get(intent, 0) < required_count:
            deficit = required_count - current_intent_counts.get(intent, 0)
            logger.info(f"Adding {deficit} synthetic queries for intent '{intent}'.")
            for i in range(deficit):
                fallback_query_text = (
                    f"What is {profile.name}'s {intent.lower()} information?"
                    if intent != QueryIntent.COMPARATIVE.value
                    else f"How does {profile.name} compare to its competitors?"
                )
                repaired_queries.append(
                    QuerySpec(
                        query_text=f"FALLBACK: {fallback_query_text} (intent: {intent})",
                        intent=intent,
                        target_metrics=INTENT_METRIC_MAP.get(intent, ["GEO-01-ENT-SAL"]),
                        query_index=len(repaired_queries)
                    )
                )

    for idx, q in enumerate(repaired_queries):
        q.query_index = idx

    queries_with_brand = [
        q for q in repaired_queries if profile.name.lower() in q.query_text.lower()
    ]
    if len(queries_with_brand) > query_count * MAX_BRAND_NAME_RATIO:
        excess_queries_count = int(len(queries_with_brand) - (query_count * MAX_BRAND_NAME_RATIO))
        logger.warning(f"Brand name ratio exceeded, stripping brand name from {excess_queries_count} queries.")
        random.shuffle(queries_with_brand)
        for i in range(min(excess_queries_count, len(queries_with_brand))):
            original_query = queries_with_brand[i].query_text
            new_query_text = original_query.replace(profile.name, "the company", 1)
            if new_query_text == original_query:
                new_query_text = f"Information about {queries_with_brand[i].intent.lower()} aspects."
            queries_with_brand[i].query_text = new_query_text

    if len(repaired_queries) > query_count:
        repaired_queries = repaired_queries[:query_count]
    while len(repaired_queries) < query_count:
        repaired_queries.append(
            QuerySpec(
                query_text="FALLBACK: General information about the industry.",
                intent=QueryIntent.NAVIGATIONAL.value,
                target_metrics=INTENT_METRIC_MAP.get(QueryIntent.NAVIGATIONAL.value, []),
                query_index=len(repaired_queries)
            )
        )

    for idx, q in enumerate(repaired_queries):
        q.query_index = idx

    return repaired_queries
