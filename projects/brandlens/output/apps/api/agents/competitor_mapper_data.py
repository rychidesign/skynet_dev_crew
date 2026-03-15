from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class ResponseRow:
    id: str
    audit_id: str
    query_id: str
    platform: str  # ai_platform enum value
    response_text: str
    query_text: str
    intent: str  # query_intent enum value

@dataclass
class CompetitorMention:
    response_id: str
    platform: str
    competitor_name: str
    position_rank: Optional[int]  # 1-based rank in response; None if absent
    is_recommended_first: bool  # True if recommended before brand
    sentiment: str  # "positive" | "negative" | "neutral"
    comparative_language: List[str]  # extracted phrases

@dataclass
class CompetitorStats:
    competitor_name: str
    competitor_domain: Optional[str]
    total_appearances: int
    avg_mention_position: Optional[float]
    recommendation_count: int  # times recommended in comparative/rec queries
    positive_comparisons: int
    negative_comparisons: int
    neutral_comparisons: int
    platform_breakdown: Dict[str, Dict[str, Any]]  # { "chatgpt": { appearances, avg_position, recommendation_count } }

# Constants

AGENT_NAME = "competitor_mapper"
SYSTEM_PROMPT = """You are an expert AI assistant tasked with analyzing AI search engine responses for competitor mentions and comparative language.
Your goal is to extract structured information about how specified competitors are mentioned in relation to a brand.

The user will provide you with:
1. The AI response text to analyze.
2. A list of known competitor names (and their common aliases) to look for.
3. The platform the response came from.
4. The original query text.

Your output MUST be a JSON array of objects, where each object represents a competitor mentioned in the response.
If no competitors from the provided list are found, return an empty array `[]`.

For each mentioned competitor, provide the following fields:
- "name": (string) The exact name of the competitor found. Must be one of the names from the provided competitor list.
- "position_rank": (integer or null) The 1-based numerical rank of this competitor's first mention in the response, relative to other distinct entities (brands, products, concepts). For example, if CompetitorA is mentioned first, then BrandX, then CompetitorB, CompetitorA is rank 1, BrandX is rank 2, CompetitorB is rank 3. If a competitor is mentioned, but its relative position cannot be clearly determined (e.g., in a general discussion without clear ordering), set to null. If the competitor is not mentioned at all, do not include it in the output.
- "is_recommended_first": (boolean) True if this competitor is explicitly recommended or highlighted *before* the primary brand, or if it's the *sole* recommendation in a comparative context. False otherwise.
- "sentiment": (string) Your assessment of the sentiment towards the competitor in the context of the response. Choose from "positive", "negative", or "neutral". "Positive" means the competitor is praised or presented as superior to the brand. "Negative" means the competitor is criticized or presented as inferior. "Neutral" means factual mention without strong positive or negative bias relative to the brand.
- "comparative_language": (array of strings) A list of exact phrases (max 10 words per phrase) from the response that directly compare the competitor to the brand, or describe the competitor's unique advantages/disadvantages. If no direct comparative language is found, return an empty array `[]`.

Example of expected JSON output:
```json
[
  {
    "name": "CompetitorA",
    "position_rank": 2,
    "is_recommended_first": false,
    "sentiment": "neutral",
    "comparative_language": ["offers similar features", "often chosen for budget"]
  },
  {
    "name": "CompetitorB",
    "position_rank": 1,
    "is_recommended_first": true,
    "sentiment": "positive",
    "comparative_language": ["superior performance", "industry leader", "more robust solution than BrandX"]
  }
]
```
If a competitor is mentioned multiple times, report only the first significant mention's details. Only include competitors from the provided list that are actually mentioned.
"""
LLM_TIMEOUT_SECONDS = 30
LLM_TEMPERATURE = 0.0
ANALYSIS_SEMAPHORE_SIZE = 8
COMPARATIVE_INTENTS = {"comparative", "recommendation"}
