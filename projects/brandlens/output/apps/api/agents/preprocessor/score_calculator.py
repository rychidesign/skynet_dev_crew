"""GEO-17 (Crawl Accessibility) and GEO-11 (Freshness) score calculators."""
from models.technical_check import CrawlerPermission, SitemapAnalysis, SampledPage

# GEO-11 benchmark: 4 updates per month
UPDATE_FREQUENCY_BENCHMARK = 4.0
# Normalization constant for recency score: 30 days = score of 1.0
RECENCY_NORMALIZATION_DAYS = 30.0


def calculate_crawl_permission_score(permissions: dict[str, CrawlerPermission]) -> float:
    """
    GEO-17 component: CrawlPermission.
    Returns percentage of AI crawlers allowed (0.0-1.0).
    Formula: allowed_count / total_crawlers
    """
    if not permissions:
        return 1.0  # No robots.txt = all allowed
    allowed_count = sum(
        1 for p in permissions.values() if p == CrawlerPermission.allowed
    )
    return allowed_count / len(permissions)


def calculate_sitemap_presence_score(analysis: SitemapAnalysis) -> float:
    """
    GEO-17 component: SitemapPresence.
    Returns: 1.0 if valid, 0.5 if partial/invalid, 0.0 if missing.
    """
    if not analysis.present:
        return 0.0
    if analysis.valid:
        return 1.0
    return 0.5


def calculate_basic_accessibility_score(pages: list[SampledPage]) -> float:
    """
    GEO-17 component: BasicAccessibility.
    Returns percentage of pages returning 200 OK (0.0-1.0).
    """
    if not pages:
        return 0.0
    ok_count = sum(1 for p in pages if p.ok)
    return ok_count / len(pages)


def calculate_geo17_score(
    crawl_permission: float,
    sitemap_presence: float,
    basic_accessibility: float,
) -> float:
    """
    GEO-17: Crawl Accessibility.
    Score = (0.4 x CrawlPermission + 0.3 x SitemapPresence + 0.3 x BasicAccessibility) x 100
    Returns score 0-100.
    """
    raw = (
        0.4 * crawl_permission
        + 0.3 * sitemap_presence
        + 0.3 * basic_accessibility
    )
    return round(min(max(raw * 100, 0.0), 100.0), 2)


def calculate_publication_recency_score(avg_lastmod_days: float | None) -> float | None:
    """
    GEO-11 component: PublicationRecency.
    Formula: avg(1 / days_since_publication) normalized to 0-1.
    Returns None if no lastmod data available.
    """
    if avg_lastmod_days is None or avg_lastmod_days <= 0:
        return None
    # Normalize: 1 day → ~1.0, RECENCY_NORMALIZATION_DAYS → ~1/30 ≈ 0.033
    # Cap at 1.0
    score = min(1.0 / avg_lastmod_days * RECENCY_NORMALIZATION_DAYS, 1.0)
    return round(score, 4)


def calculate_update_frequency_score(updates_per_month: float | None) -> float | None:
    """
    GEO-11 component: UpdateFrequency.
    Formula: updates_per_month / benchmark_frequency (benchmark = 4/month).
    Returns None if no data.
    """
    if updates_per_month is None:
        return None
    score = min(updates_per_month / UPDATE_FREQUENCY_BENCHMARK, 1.0)
    return round(score, 4)


def calculate_temporal_relevance_score(current_year_pct: float | None) -> float | None:
    """
    GEO-11 component: TemporalRelevance.
    Returns percentage of content with current-year references (0.0-1.0).
    """
    if current_year_pct is None:
        return None
    return round(min(max(current_year_pct / 100.0, 0.0), 1.0), 4)


def calculate_geo11_score(
    publication_recency: float | None,
    update_frequency: float | None,
    temporal_relevance: float | None,
) -> float | None:
    """
    GEO-11: Freshness and Recency.
    Score = (0.4 x PublicationRecency + 0.3 x UpdateFrequency + 0.3 x TemporalRelevance) x 100
    Returns None if all components are None (no sitemap data).
    """
    if publication_recency is None and update_frequency is None and temporal_relevance is None:
        return None

    pr = publication_recency if publication_recency is not None else 0.0
    uf = update_frequency if update_frequency is not None else 0.0
    tr = temporal_relevance if temporal_relevance is not None else 0.0

    raw = 0.4 * pr + 0.3 * uf + 0.3 * tr
    return round(min(max(raw * 100, 0.0), 100.0), 2)
