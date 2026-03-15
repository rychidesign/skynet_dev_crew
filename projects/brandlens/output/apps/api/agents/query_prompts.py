"""
Helper module for building system and user prompts for the Query Generator agent.
"""
import json
from typing import Dict, List, Any

from apps.api.models.audit import QueryIntent
from apps.api.agents.query_models import CompanyProfile
from apps.api.agents.query_constants import (
    INTENT_METRIC_MAP, MAX_BRAND_NAME_RATIO, DESCRIPTION_MAX_CHARS, FALLBACK_TEMPLATES
)


def build_system_prompt() -> str:
    """Builds the system prompt for the LLM."""
    all_intents = ", ".join([f"'{i.value}'" for i in QueryIntent])
    return f'''You are an expert SEO and brand visibility strategist. Your task is to generate
diverse search queries for various AI search engines (ChatGPT, Claude, Perplexity, Gemini, Copilot)
to assess a company's online presence.

Generate queries that cover different user intents and target specific aspects of the company.
The queries should be natural language questions or phrases, suitable for a general user.
Avoid overly technical or promotional language.

You MUST provide your response as a JSON object with a single top-level key "queries",
whose value is a JSON array of objects. Each object in the array MUST have the
following structure:
{{
    "query_text": "string",          // The actual search query, minimum 3 characters
    "intent": "string",              // One of: {all_intents}
    "target_metrics": ["string"]     // List of metric IDs relevant to this query, e.g., ["GEO-01-ENT-SAL", "GEO-04-TOP-AUTH"]
}}

Ensure that the intent values are strictly from the allowed list.
Ensure `target_metrics` are valid and relevant to the query based on the provided mapping.
All query texts should be in English.
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
    
    description_to_use = (profile.description[:DESCRIPTION_MAX_CHARS] + "...") if profile.description and len(profile.description) > DESCRIPTION_MAX_CHARS else (profile.description or "No description provided.")

    return f'''Generate {query_count} distinct search queries for the company "{profile.name}".

Company Details:
- Name: {profile.name}
- Industry: {profile.industry or "Not specified"}
- Description: {description_to_use}
- Core Topics: {topics_str}
- Key Competitors: {competitors_str}
- Factual Information (ground truth):
```json
{facts_str}
```

Target Query Distribution by Intent (MUST be followed exactly in total generated queries per intent):
{intent_breakdown_str}

Important constraints:
1. The brand name "{profile.name}" should appear in no more than {brand_name_cap} of the generated queries.
2. Each query MUST be unique and at least 3 characters long.
3. If an intent has 0 queries in the distribution, do not generate any queries for that intent.
4. For `target_metrics`, choose relevant metrics from the following mapping for each intent:
{json.dumps(INTENT_METRIC_MAP, indent=2)}
'''
