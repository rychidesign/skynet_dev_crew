from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


class MetricCategory(str, Enum):
    entity_semantic = "entity_semantic"
    citations_trust = "citations_trust"
    content_technical = "content_technical"
    reputation_sentiment = "reputation_sentiment"


class MetricScore(BaseModel):
    metric_id: str
    metric_category: MetricCategory
    score: Optional[float] = Field(None, ge=0.0, le=100.0)
    components: dict[str, Any]
    weight: float
    weighted_contribution: float
    platform_scores: dict[str, Any]
    evidence_summary: Optional[str] = None


class HallucinationFinding(BaseModel):
    claim_text: str
    fact_field: str
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    severity: str = Field(..., pattern="^(critical|major|minor)$")
    platform: str


class TechnicalCheckResult(BaseModel):
    robots_txt_raw: Optional[str] = None
    crawler_permissions: dict[str, Any]
    sitemap_present: Optional[bool] = None
    sitemap_valid: Optional[bool] = None
    sitemap_url_count: Optional[int] = None
    sampled_pages: list[dict[str, Any]]
    avg_lastmod_days: Optional[float] = None
    update_frequency_monthly: Optional[float] = None
    current_year_content_pct: Optional[float] = None
    sitemap_sample: list[dict[str, Any]]


class AuditResult(BaseModel):
    global_geo_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    metrics: list[MetricScore]
    hallucinations: list[HallucinationFinding]
    technical_checks: Optional[TechnicalCheckResult] = None
