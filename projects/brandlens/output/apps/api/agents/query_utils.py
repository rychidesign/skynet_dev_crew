"""Utility functions and helpers for query generator agent."""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import json
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

INTENT_MIN_RATIOS: Dict[str, float] = {
    QueryIntent.INFORMATIONAL.value: 0.15,
    QueryIntent.COMPARATIVE.value: 0.15,
    QueryIntent.RECOMMENDATION.value: 0.10,
    QueryIntent.AUTHORITY.value: 0.10,
    QueryIntent.FACTUAL.value: 0.10,
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


def compute_distribution(query_count: int) -> Dict[str, int]:
    """Computes the required distribution of query intents."""
    import math
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


def build_system_prompt() -> str:
    """Builds the system prompt for the LLM."""
    intent_values = ", ".join([i.value for i in QueryIntent])
    return f'''You are an expert SEO and brand visibility strategist. Your task is to generate
diverse search queries for various AI search engines (ChatGPT, Claude, Perplexity, Gemini, Copilot)
to assess a company's online presence.

Generate queries that cover different user intents and target specific aspects of the company.
The queries should be natural language questions or phrases, suitable for a general user.
Avoid overly technical or promotional language.

You MUST provide your response as a JSON object with a single key "queries" containing an array of objects, where each object has the
following structure:
{{
    "queries": [
        {{
            "query_text": "string",          // The actual search query
            "intent": "string",              // One of: {intent_values}
            "target_metrics": ["string"]     // List of metric IDs relevant to this query, e.g., ["GEO-01-ENT-SAL", "GEO-04-TOP-AUTH"]
        }}
    ]
}}

Ensure that the intent values are strictly from the allowed list.
Ensure `target_metrics` are valid and relevant to the query.
'''


def build_user_prompt(
    profile: CompanyProfile, query_count: int, distribution: Dict[str, int]
) -> str:
    """Builds the user prompt for the LLM."""
    competitors_str = ", ".join(profile.competitors) if profile.competitors else "N/A"
    topics_str = ", ".join(profile.core_topics) if profile.core_topics else "N/A"
    facts_str = json.dumps(profile.facts, indent=2) if profile.facts else "N/A"

    intent_breakdown_str = "\n".join(
        [f"- {intent.capitalize()}: {count} queries" for intent, count in distribution.items()]
    )

    brand_name_cap = int(query_count * MAX_BRAND_NAME_RATIO)

    return f'''Generate {query_count} distinct search queries for the company "{profile.name}".

Company Details:
- Name: {profile.name}
- Industry: {profile.industry or "Not specified"}
- Description: {profile.description or "No description provided."}
- Core Topics: {topics_str}
- Key Competitors: {competitors_str}
- Factual Information (ground truth):
```json
{facts_str}
```

Target Query Distribution by Intent (MUST be followed exactly):
{intent_breakdown_str}

Important constraints:
1. The brand name "{profile.name}" should appear in no more than {brand_name_cap} of the generated queries.
2. Each query MUST be unique.
3. If an intent has 0 queries in the distribution, do not generate any queries for that intent.
4. For `target_metrics`, choose relevant metrics from the following mapping for each intent:
{json.dumps(INTENT_METRIC_MAP, indent=2)}
'''


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
