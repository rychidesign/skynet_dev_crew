"""Pydantic models for preprocessor technical check results (GEO-17, GEO-11)."""
from enum import Enum
from pydantic import BaseModel, Field


class CrawlerPermission(str, Enum):
    allowed = "allowed"
    disallowed = "disallowed"
    partial = "partial"


class CrawlerStatus(BaseModel):
    crawler_name: str  # GPTBot, ClaudeBot, Bingbot, Googlebot
    permission: CrawlerPermission
    user_agent_match: str | None = None


class RobotsAnalysis(BaseModel):
    raw_content: str | None = None
    crawler_permissions: dict[str, CrawlerPermission] = Field(default_factory=dict)
    has_ai_crawler_rules: bool = False


class SitemapUrl(BaseModel):
    loc: str
    lastmod: str | None = None
    changefreq: str | None = None
    priority: float | None = None


class SitemapAnalysis(BaseModel):
    present: bool = False
    valid: bool = False
    url_count: int = 0
    urls: list[SitemapUrl] = Field(default_factory=list)
    avg_lastmod_days: float | None = None
    update_frequency_monthly: float | None = None
    current_year_content_pct: float | None = None


class SampledPage(BaseModel):
    url: str
    status_code: int
    ok: bool  # True if 200
    latency_ms: int | None = None


class TechnicalCheckResult(BaseModel):
    robots_analysis: RobotsAnalysis
    sitemap_analysis: SitemapAnalysis
    sampled_pages: list[SampledPage] = Field(default_factory=list)
    # Computed scores (stored for later use by Synthesizer)
    crawl_permission_score: float = Field(0.0, ge=0.0, le=1.0)
    sitemap_presence_score: float = Field(0.0, ge=0.0, le=1.0)
    basic_accessibility_score: float = Field(0.0, ge=0.0, le=1.0)
    publication_recency_score: float | None = None
    update_frequency_score: float | None = None
    temporal_relevance_score: float | None = None
