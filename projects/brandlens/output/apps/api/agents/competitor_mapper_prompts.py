from typing import List

SYSTEM_PROMPT: str = """You are a competitive analysis extraction system. You analyze AI-generated responses and identify mentions of competitor brands. You MUST respond with valid JSON only. No explanation, no markdown, no prose."""


def build_analysis_prompt(
    response_text: str,
    competitors: List[str],
    platform: str,
    query_text: str
) -> str:
    """
    Constructs LLM prompt instructing it to identify competitor mentions from a list, return JSON.
    """
    competitor_list_csv = ", ".join(competitors)

    return f"""Analyze the following AI response for mentions of these competitors: {competitor_list_csv}

Context:
- Platform: {platform}
- Query: {query_text}

Response to analyze:
---
{response_text}
---

Return JSON:
{{
  "competitor_mentions": [
    {{
      "competitor_name": "exact name from the list above",
      "position_rank": "<integer: ordinal position among all entities, or null>",
      "is_recommended": "<boolean: true if explicitly recommended first/prominently>",
      "comparison_sentiment": "positive|negative|neutral",
      "mention_count": "<integer: total times mentioned in this response>"
    }}
  ]
}}

Rules:
- Only include competitors from the provided list. Do not invent new names.
- If no competitor from the list appears, return "competitor_mentions": []
- position_rank counts ordinal position among ALL named entities (1 = first mentioned)
- is_recommended = true only if explicitly recommended above other options
- comparison_sentiment = overall tone of comparison toward this competitor
"""
