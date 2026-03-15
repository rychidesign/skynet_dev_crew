from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field

class CompetitorMention(BaseModel):
    competitor_name: str
    platform: str
    response_id: str
    query_intent: str
    mention_position: int  # 1-indexed
    is_recommended_first: bool
    sentiment: Literal["positive", "negative", "neutral"]
    comparative_language: str  # snippet

class PlatformCompetitorBreakdown(BaseModel):
    appearances: int
    avg_position: Optional[float]
    recommendation_count: int
    positive_comparisons: int
    negative_comparisons: int
    neutral_comparisons: int

class CompetitorStats(BaseModel):
    competitor_name: str
    competitor_domain: Optional[str] = None
    avg_mention_position: Optional[float] = None
    recommendation_count: int = 0
    total_appearances: int = 0
    positive_comparisons: int = 0
    negative_comparisons: int = 0
    neutral_comparisons: int = 0
    platform_breakdown: Dict[str, PlatformCompetitorBreakdown] = {}

class BrandCompetitiveStats(BaseModel):
    brand_name: str
    total_comparative_responses: int = 0
    recommendation_count: int = 0
    avg_mention_position: Optional[float] = None
    positive_comparisons: int = 0
    negative_comparisons: int = 0
    neutral_comparisons: int = 0
    platform_breakdown: Dict[str, PlatformCompetitorBreakdown] = {}

class ResponseRow(BaseModel):
    id: str
    response_text: str
    platform: str
    query_id: str
    query_text: str
    query_intent: str
    audit_id: str

class SingleCompetitorExtraction(BaseModel):
    name: str
    position: int
    is_recommended_first: bool
    sentiment: Literal["positive", "negative", "neutral"]
    comparative_snippet: str

class BrandMentionExtraction(BaseModel):
    mentioned: bool
    position: Optional[int] = None
    is_recommended_first: bool = False
    sentiment: Literal["positive", "negative", "neutral"] = "neutral"
    comparative_snippet: Optional[str] = None

class LLMExtractionResult(BaseModel):
    competitors_found: List[SingleCompetitorExtraction] = []
    brand_mention: BrandMentionExtraction = Field(default_factory=BrandMentionExtraction)
