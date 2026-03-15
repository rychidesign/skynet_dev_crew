from dataclasses import dataclass

# --- Constants ---
COMPETITOR_SEMAPHORE_SIZE = 5
LLM_TIMEOUT_SECONDS = 30
LLM_TEMPERATURE = 0.1

SYSTEM_PROMPT = """
You are an expert brand analyst. Your task is to analyze an AI search engine response and identify mentions of specific competitors, their sentiment, and their position within the text.

You will be provided with:
- The AI response text
- A list of competitor names to look for

For each competitor found, determine:
1. "name": The exact name of the competitor.
2. "position_rank": The approximate position of the first mention in the response. Rank 1 for very early, 2 for middle, 3 for late. If not found, do not include.
4. "is_recommended_first": True if the competitor is explicitly recommended as a primary choice, False otherwise.
5. "sentiment": "positive", "negative", or "neutral" regarding the competitor in the context of the response.
6. "domain": The competitor's website domain if mentioned or clearly implied, otherwise null.

Return a JSON object with a key "competitors_found" which is a list of objects for each competitor found.
If no competitors are found, return an empty list.

Example JSON output:
{
  "competitors_found": [
    {
      "name": "CompetitorX",
      "position_rank": 2,
      "is_recommended_first": false,
      "sentiment": "positive",
      "domain": "competitorx.com"
    }
  ]
}
"""

# --- Data Classes ---
@dataclass
class CompetitorRecord:
    audit_id: str
    competitor_name: str
    competitor_domain: str | None
    avg_mention_position: float
    recommendation_count: int
    total_appearances: int
    positive_comparisons: int
    negative_comparisons: int
    neutral_comparisons: int
    platform_breakdown: dict

@dataclass
class ResponseWithIntent:
    response_id: str
    audit_id: str
    response_text: str
    platform: str
    query_intent: str
