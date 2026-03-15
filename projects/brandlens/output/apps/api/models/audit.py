from enum import Enum
from typing import Optional, Any, List
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime


class AuditStatus(str, Enum):
    pending = "pending"
    preprocessing = "preprocessing"
    generating = "generating"
    collecting = "collecting"
    analyzing = "analyzing"
    synthesizing = "synthesizing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class AiPlatform(str, Enum):
    chatgpt = "chatgpt"
    claude = "claude"
    perplexity = "perplexity"
    google_aio = "google_aio"
    copilot = "copilot"


class QueryIntent(str, Enum):
    informational = "informational"
    comparative = "comparative"
    navigational = "navigational"
    recommendation = "recommendation"
    authority = "authority"
    factual = "factual"


class MentionType(str, Enum):
    primary = "primary"
    secondary = "secondary"
    citation = "citation"
    comparison = "comparison"
    recommendation = "recommendation"
    absent = "absent"


class EventSeverity(str, Enum):
    debug = "debug"
    info = "info"
    warning = "warning"
    error = "error"
    critical = "critical"


class AuditConfig(BaseModel):
    query_count: int = Field(..., ge=1, le=200)
    platforms: list[AiPlatform]
    cache_ttl_hours: int = Field(24, ge=0)


class AuditRequest(BaseModel):
    company_id: UUID
    config: AuditConfig


class AuditQuery(BaseModel):
    id: str
    audit_id: str
    query_text: str
    intent: str
    target_metrics: List[str]
    query_index: int
    created_at: datetime


class AuditResponse(BaseModel):
    id: Optional[str] = None
    audit_id: str
    query_id: str
    platform: AiPlatform
    model_id: str
    response_text: str
    citations: List[dict]
    rag_sources: List[dict]
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    served_from_cache: bool
    idempotency_key: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GeneratedQuery(BaseModel):
    query_text: str = Field(..., min_length=3)
    intent: QueryIntent
    target_metrics: list[str]
    query_index: int = Field(..., ge=0)


class PlatformResponse(BaseModel):
    platform: AiPlatform
    model_id: str
    response_text: str
    citations: list[dict[str, Any]]
    rag_sources: list[dict[str, Any]]
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    served_from_cache: bool
    cache_key: Optional[str] = None
    idempotency_key: str


class MentionAnalysis(BaseModel):
    entity_name: str
    mention_type: MentionType
    position_rank: Optional[int] = None
    sentiment_score: Optional[float] = Field(None, ge=-1.0, le=1.0)
    sentiment_label: Optional[str] = None
    authority_markers: list[str]
    is_authority_cite: bool
    extracted_attributes: dict[str, Any]
    is_confused: bool
    confusion_note: Optional[str] = None


class CompetitorMapping(BaseModel):
    competitor_name: str
    competitor_domain: Optional[str] = None
    avg_mention_position: Optional[float] = None
    recommendation_count: int
    total_appearances: int
    positive_comparisons: int
    negative_comparisons: int
    neutral_comparisons: int
    platform_breakdown: dict[str, Any]


class ProgressUpdate(BaseModel):
    status: AuditStatus
    progress: float = Field(..., ge=0.0, le=1.0)
    current_agent: str
    message: str
    queries_generated: Optional[int] = None
    responses_collected: Optional[int] = None
    total_responses: Optional[int] = None
    mentions_analyzed: Optional[int] = None