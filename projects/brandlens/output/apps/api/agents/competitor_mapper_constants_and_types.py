from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, FrozenSet

# Constants
AGENT_NAME: str = "competitor_mapper"
ANALYSIS_SEMAPHORE_SIZE: int = 5          # Conservative: each call analyzes multiple competitors
LLM_TIMEOUT_SECONDS: float = 45.0           # Longer timeout — bigger prompts
LLM_TEMPERATURE: float = 0.1
COMPARATIVE_INTENTS: FrozenSet[str] = frozenset({"comparative", "recommendation"})


# Dataclass for parsed LLM mention results
@dataclass
class CompetitorMentionResult:
    competitor_name: str
    position_rank: Optional[int]
    is_recommended: bool
    comparison_sentiment: str # "positive" | "negative" | "neutral"
    mention_count: int

# Dataclass for one filtered response row (comparative/recommendation intent only)
@dataclass
class FilteredResponse:
    response_id: str
    audit_id: str
    response_text: str
    platform: str                             # ai_platform enum value
    query_text: str
    query_intent: str

# Dataclass: one row to be upserted into audit_competitors
@dataclass
class CompetitorRecord:
    audit_id: str
    competitor_name: str
    competitor_domain: Optional[str] = None          # matched from companies.competitors if domain provided
    avg_mention_position: Optional[float] = None     # mean of position_rank across all mentions
    recommendation_count: int = 0                    # times recommended first/prominently
    total_appearances: int = 0                       # total mention count across all responses
    positive_comparisons: int = 0
    negative_comparisons: int = 0
    neutral_comparisons: int = 0
    platform_breakdown: Dict[str, Any] = field(default_factory=dict) # {platform: {appearances, recommendation_count, avg_position, sentiment}}
