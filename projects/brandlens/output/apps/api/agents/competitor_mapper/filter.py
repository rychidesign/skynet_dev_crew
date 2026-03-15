import re
from typing import List, Dict, Tuple

from apps.api.agents.competitor_mapper.models import CompetitorMention

def _compute_position_rank(text: str, competitor_names: List[str]) -> Dict[str, int]:
    """Computes the position rank for each competitor based on their first appearance in the text."""
    mentions = []
    for competitor_name in competitor_names:
        # Find all occurrences of the competitor name, case-insensitive
        for match in re.finditer(re.escape(competitor_name), text, re.IGNORECASE):
            mentions.append((match.start(), competitor_name))

    # Sort mentions by their starting position to determine rank
    mentions.sort(key=lambda x: x[0])

    ranked_competitors = {}
    rank = 1
    seen_competitors = set()
    for _, competitor_name in mentions:
        if competitor_name not in seen_competitors:
            ranked_competitors[competitor_name] = rank
            seen_competitors.add(competitor_name)
            rank += 1
    return ranked_competitors

def filter_comparative_responses(responses: List[Dict]) -> List[Dict]:
    """Filters audit responses to include only those with 'comparative' or 'recommendation' intent."""
    filtered_responses = []
    for response in responses:
        if response.get('query_intent') in ['comparative', 'recommendation']:
            filtered_responses.append(response)
    return filtered_responses

def extract_competitor_mentions(
    response_text: str,
    competitor_names: List[str],
    brand_name: str,
) -> Tuple[List[CompetitorMention], List[CompetitorMention]]:
    """Extracts competitor and brand mentions from response text with context snippets and position ranks."""
    all_mentions = []
    all_competitor_names_and_brand = list(set(competitor_names + [brand_name]))
    position_ranks = _compute_position_rank(response_text, all_competitor_names_and_brand)

    brand_mentions: List[CompetitorMention] = []
    competitor_mentions: List[CompetitorMention] = []

    for competitor_or_brand_name in all_competitor_names_and_brand:
        # Find all occurrences of the competitor/brand name, case-insensitive
        for match in re.finditer(re.escape(competitor_or_brand_name), response_text, re.IGNORECASE):
            start, end = match.span()
            context_start = max(0, start - 100)
            context_end = min(len(response_text), end + 100)
            context_snippet = response_text[context_start:context_end]

            mention = CompetitorMention(
                competitor_name=competitor_or_brand_name,
                position_rank=position_ranks.get(competitor_or_brand_name, 0),
                context_snippet=context_snippet,
                is_recommendation=False,  # Will be classified later by aggregator
                comparative_sentiment="neutral",  # Will be classified later by aggregator
                response_id="",  # Will be filled by main agent
                platform="",  # Will be filled by main agent
            )
            if competitor_or_brand_name == brand_name:
                brand_mentions.append(mention)
            else:
                competitor_mentions.append(mention)
    return competitor_mentions, brand_mentions
