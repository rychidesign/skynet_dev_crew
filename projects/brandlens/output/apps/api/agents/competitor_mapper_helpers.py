"""Competitor Mapper helpers — data structures, constants, and utilities."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

# Constants
AGENT_NAME = "competitor_mapper"
COMPARATIVE_INTENTS = {"comparative", "recommendation"}
LLM_MODEL = "gpt-4o-mini"
LLM_TEMPERATURE = 0.0
LLM_TIMEOUT_SECONDS = 30.0
LLM_MAX_ATTEMPTS = 3
LLM_WAIT_MIN_SECONDS = 2
LLM_WAIT_MAX_SECONDS = 8
ANALYSIS_SEMAPHORE_SIZE = 5
REDIS_TTL_SECONDS = 3600
PROGRESS_VALUE = 0.80


class CompetitorMention(BaseModel):
    """Extracted competitor mention from a single response."""
    competitor_name: str = Field(..., description="Must match one from the known competitors list")
    mention_position: int = Field(..., ge=1, description="1-indexed rank in the response")
    is_recommended_first: bool = Field(..., description="True if competitor is recommended above brand")
    comparative_sentiment: str = Field(..., pattern="^(positive|negative|neutral)$")
    platform: str = Field(..., description="AI platform enum value")


class ResponseRow(BaseModel):
    """Minimal response data fetched from audit_responses + audit_queries join."""
    response_id: str
    query_id: str
    platform: str
    response_text: str
    query_intent: str


@dataclass
class CompetitorStats:
    """Accumulated stats for a single competitor across all responses."""
    competitor_name: str
    competitor_domain: Optional[str] = None
    total_appearances: int = 0
    mention_positions: List[int] = field(default_factory=list)
    recommendation_count: int = 0
    positive_comparisons: int = 0
    negative_comparisons: int = 0
    neutral_comparisons: int = 0
    platform_data: Dict[str, Dict] = field(default_factory=dict)


def build_analysis_prompt(response_text: str, competitors: list[str], platform: str) -> str:
    """Construct LLM prompt for competitor extraction."""
    system_prompt = (
        "You are an AI response analyst. Extract competitor mentions from AI-generated text. "
        "Return a JSON array of competitor objects. Only include competitors from the provided list."
    )
    
    competitors_str = ", ".join(competitors) if competitors else "None"
    
    user_prompt = f"""Known competitors: [{competitors_str}]
Platform: {platform}
Response text: {response_text}

For each competitor found, return:
{{
  "competitor_name": string (must match one from the list exactly),
  "mention_position": integer (1 = first mentioned),
  "is_recommended_first": boolean,
  "comparative_sentiment": "positive" | "negative" | "neutral"
}}
Return empty array [] if no known competitors are mentioned."""
    
    return json.dumps({
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": LLM_TEMPERATURE,
        "response_format": {"type": "json_object"}
    })


def parse_llm_output(
    raw_json: str, 
    response_id: str, 
    platform: str, 
    log_ctx
) -> list[CompetitorMention]:
    """Parse JSON array from LLM, validate each field, return empty list on parse failure."""
    import structlog
    
    try:
        data = json.loads(raw_json)
        # Handle both direct array and wrapped object
        mentions_data = data if isinstance(data, list) else data.get("competitors", [])
        if not isinstance(mentions_data, list):
            mentions_data = []
        
        mentions = []
        for item in mentions_data:
            try:
                mention = CompetitorMention(
                    competitor_name=item["competitor_name"],
                    mention_position=item["mention_position"],
                    is_recommended_first=item["is_recommended_first"],
                    comparative_sentiment=item["comparative_sentiment"],
                    platform=platform
                )
                mentions.append(mention)
            except (KeyError, ValueError) as e:
                log_ctx.warning(
                    "invalid_mention_data",
                    response_id=response_id,
                    item=item,
                    error=str(e)
                )
        return mentions
    except json.JSONDecodeError as e:
        log_ctx.warning(
            "llm_output_parse_failed",
            response_id=response_id,
            raw_output=raw_json[:200],
            error=str(e)
        )
        return []


def stats_to_db_dict(stats: CompetitorStats, audit_id: str) -> dict[str, Any]:
    """Convert CompetitorStats to row dict matching audit_competitors schema."""
    import statistics
    
    avg_position = (
        round(statistics.mean(stats.mention_positions), 2)
        if stats.mention_positions
        else 0.0
    )
    
    return {
        "audit_id": audit_id,
        "competitor_name": stats.competitor_name,
        "competitor_domain": stats.competitor_domain,
        "avg_mention_position": avg_position,
        "recommendation_count": stats.recommendation_count,
        "total_appearances": stats.total_appearances,
        "positive_comparisons": stats.positive_comparisons,
        "negative_comparisons": stats.negative_comparisons,
        "neutral_comparisons": stats.neutral_comparisons,
        "platform_breakdown": stats.platform_data,
    }
