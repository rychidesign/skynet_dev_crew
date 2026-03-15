from typing import List, Dict, Any, Optional
from .score_models import MetricScoreResult, ScoringContext, METRIC_WEIGHTS, METRIC_CATEGORIES

def compute_geo11(context: ScoringContext) -> Optional[MetricScoreResult]:
    """GEO-11-FRS-REC: Freshness and Recency"""
    if not context.technical_checks:
        return None

    tech = context.technical_checks
    # PublicationRecency = normalized 1 / avg_lastmod_days (benchmark: 30 days = 1.0)
    avg_lastmod_days = tech.get("avg_lastmod_days", 365)
    publication_recency = 30.0 / max(avg_lastmod_days, 1)
    publication_recency = min(1.0, publication_recency)
    
    # UpdateFrequency = update_frequency_monthly / 4.0 (benchmark: 4/month)
    update_frequency_monthly = tech.get("update_frequency_monthly", 0.0)
    update_frequency = update_frequency_monthly / 4.0
    update_frequency = min(1.0, update_frequency)
    
    # TemporalRelevance = current_year_content_pct / 100
    current_year_content_pct = tech.get("current_year_content_pct", 0.0)
    temporal_relevance = current_year_content_pct / 100.0
    
    score = (0.4 * publication_recency + 0.3 * update_frequency + 0.3 * temporal_relevance) * 100
    score = min(100.0, score)
    
    return MetricScoreResult(
        metric_id="GEO-11-FRS-REC",
        metric_category=METRIC_CATEGORIES["GEO-11-FRS-REC"],
        score=round(score, 2),
        components={
            "publication_recency": round(publication_recency, 2),
            "update_frequency": round(update_frequency, 2),
            "temporal_relevance": round(temporal_relevance, 2)
        },
        weight=METRIC_WEIGHTS["GEO-11-FRS-REC"],
        weighted_contribution=0.0,
        platform_scores={},
        evidence_summary=f"Avg publication recency is {avg_lastmod_days} days."
    )

def compute_geo17(context: ScoringContext) -> Optional[MetricScoreResult]:
    """GEO-17-CRW-ACC: Crawl Accessibility"""
    if not context.technical_checks:
        return None

    tech = context.technical_checks
    # CrawlPermission = pct of AI crawlers allowed (GPTBot, ClaudeBot, Bingbot, Googlebot)
    crawler_permissions = tech.get("crawler_permissions", [])
    benchmark_crawlers = ["GPTBot", "ClaudeBot", "Bingbot", "Googlebot"]
    allowed_count = sum(1 for c in benchmark_crawlers if c in crawler_permissions)
    crawl_permission = allowed_count / 4.0
    
    # SitemapPresence = 1 if valid, 0.5 if partial, 0 if missing
    sitemap_status = 0.0
    if tech.get("sitemap_valid"):
        sitemap_status = 1.0
    elif tech.get("sitemap_present"):
        sitemap_status = 0.5
        
    # BasicAccessibility = pct of sampled pages returning 200 OK
    sampled_pages = tech.get("sampled_pages", [])
    ok_count = sum(1 for p in sampled_pages if p.get("status") == 200)
    basic_accessibility = (ok_count / len(sampled_pages)) if sampled_pages else 0.0
    
    score = (0.4 * crawl_permission + 0.3 * sitemap_status + 0.3 * basic_accessibility) * 100
    
    return MetricScoreResult(
        metric_id="GEO-17-CRW-ACC",
        metric_category=METRIC_CATEGORIES["GEO-17-CRW-ACC"],
        score=round(score, 2),
        components={
            "crawl_permission": round(crawl_permission, 2),
            "sitemap_status": sitemap_status,
            "basic_accessibility": round(basic_accessibility, 2)
        },
        weight=METRIC_WEIGHTS["GEO-17-CRW-ACC"],
        weighted_contribution=0.0,
        platform_scores={},
        evidence_summary=f"Crawlers allowed: {allowed_count}/4."
    )
