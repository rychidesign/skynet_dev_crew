"""Pydantic models for scoring system."""

from pydantic import BaseModel


class MetricInput(BaseModel):
    """Aggregated inputs gathered from DB for computing a single metric."""

    # GEO-01
    queries_where_brand_first: int = 0
    total_queries: int = 0
    avg_mention_rank: float = 0.0
    max_mention_rank: int = 1
    confusion_instances: int = 0
    total_mentions: int = 0

    # GEO-03
    conflicting_attributes: int = 0
    total_attributes_checked: int = 0

    # GEO-04
    times_cited_as_authority: int = 0
    total_topic_mentions: int = 0
    expert_language_count: int = 0
    exclusive_insight_count: int = 0
    total_claims: int = 0

    # GEO-05
    total_citations: int = 0
    benchmark_citations: float = 0.0
    normalized_per_100: bool = True

    # GEO-07
    brand_rag_hits: int = 0
    total_rag_results: int = 0
    avg_relevancy_score: float = 1.0

    # GEO-11 (from audit_technical_checks)
    avg_lastmod_days: float = 0.0
    update_frequency_monthly: float = 0.0
    current_year_content_pct: float = 0.0

    # GEO-13
    sentiment_scores: list[float] = []

    # GEO-14 (from audit_competitors)
    brand_avg_position: float = 1.0
    num_competitors: int = 1
    brand_recommendation_count: int = 0
    comparison_queries: int = 0
    positive_comparisons: int = 0
    negative_comparisons: int = 0
    total_comparisons: int = 0

    # GEO-16 (hallucinations)
    hallucination_findings: list = []
    total_verifiable_claims: int = 0

    # GEO-17 (from audit_technical_checks)
    crawler_permissions: dict[str, str] = {}
    sitemap_present: bool = False
    sitemap_valid: bool = False
    sampled_pages: list[dict] = []


class MetricScore(BaseModel):
    metric_id: str
    metric_category: str
    score: float
    components: dict
    weight: float
    weighted_contribution: float
    platform_scores: dict
    evidence_summary: str


class GlobalScoreResult(BaseModel):
    global_geo_score: float
    category_scores: dict[str, float]
    metric_scores: list[MetricScore]
