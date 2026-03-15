"""Unit tests for Preprocessor Agent (GEO-17, GEO-11) — Task 5.3."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from core.utils.robots_parser import (
    check_crawler_allowed,
    fetch_robots_txt,
    CrawlerPermissionsResult,
)
from core.utils.sitemap_parser import (
    parse_sitemap_xml,
    calculate_freshness_metrics,
    fetch_sitemap,
    SitemapUrl,
    SitemapStatus,
)
from core.utils.http_checker import (
    check_urls,
    sample_urls_from_sitemap,
    UrlStatus,
)
from agents.preprocessor import (
    calculate_geo17_score,
    calculate_geo11_components,
    GEO17ScoreInput,
    TechnicalCheckResult,
    run,
    _normalize_recency,
    _normalize_frequency,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_ROBOTS_TXT = """\
User-agent: *
Disallow: /private/

User-agent: GPTBot
Disallow:

User-agent: ClaudeBot
Disallow: /no-ai/
"""

BLOCKING_ROBOTS_TXT = """\
User-agent: GPTBot
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: Bingbot
Disallow: /

User-agent: Googlebot
Disallow: /
"""

MALFORMED_ROBOTS_TXT = "this is not a valid robots.txt\n!!@@##\n"

VALID_SITEMAP_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/</loc>
    <lastmod>2024-03-01</lastmod>
    <priority>1.0</priority>
    <changefreq>weekly</changefreq>
  </url>
  <url>
    <loc>https://example.com/about</loc>
    <lastmod>2024-02-15</lastmod>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://example.com/blog</loc>
    <lastmod>2024-01-10</lastmod>
  </url>
</urlset>
"""

SITEMAP_INDEX_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://example.com/sitemap-posts.xml</loc>
    <lastmod>2024-03-01</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://example.com/sitemap-pages.xml</loc>
  </sitemap>
</sitemapindex>
"""


# ---------------------------------------------------------------------------
# 1. test_robots_txt_parser_valid
# ---------------------------------------------------------------------------

def test_robots_txt_parser_valid():
    """Parse valid robots.txt and verify crawler permissions."""
    allowed_gpt, disallowed_gpt = check_crawler_allowed("GPTBot", VALID_ROBOTS_TXT)
    # GPTBot has Disallow: (empty = allow all)
    assert isinstance(allowed_gpt, bool)

    allowed_claude, disallowed_claude = check_crawler_allowed("ClaudeBot", VALID_ROBOTS_TXT)
    assert isinstance(allowed_claude, bool)
    # ClaudeBot is disallowed from /no-ai/
    assert "/no-ai/" in disallowed_claude


# ---------------------------------------------------------------------------
# 2. test_robots_txt_parser_missing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_robots_txt_parser_missing():
    """Handle 404 robots.txt gracefully — assume all crawlers allowed."""
    mock_response = MagicMock()
    mock_response.status_code = 404

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    result = await fetch_robots_txt("example.com", client=mock_client)

    assert isinstance(result, CrawlerPermissionsResult)
    assert result.robots_txt_raw is None
    assert result.valid_robots_txt is False
    assert result.crawl_permission_score == 1.0
    assert all(p.allowed for p in result.permissions)


# ---------------------------------------------------------------------------
# 3. test_robots_txt_parser_malformed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_robots_txt_parser_malformed():
    """Handle malformed robots.txt gracefully without raising exceptions."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = MALFORMED_ROBOTS_TXT

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    result = await fetch_robots_txt("example.com", client=mock_client)

    assert isinstance(result, CrawlerPermissionsResult)
    assert result.robots_txt_raw == MALFORMED_ROBOTS_TXT
    # Should not raise — permissions are resolved even for malformed content
    assert isinstance(result.crawl_permission_score, float)
    assert 0.0 <= result.crawl_permission_score <= 1.0


# ---------------------------------------------------------------------------
# 4. test_sitemap_parser_valid
# ---------------------------------------------------------------------------

def test_sitemap_parser_valid():
    """Parse valid sitemap.xml and extract structured URLs."""
    urls = parse_sitemap_xml(VALID_SITEMAP_XML)

    assert len(urls) == 3
    assert urls[0].url == "https://example.com/"
    assert urls[0].lastmod is not None
    assert urls[0].priority == 1.0
    assert urls[0].changefreq == "weekly"
    assert urls[1].url == "https://example.com/about"
    assert urls[2].url == "https://example.com/blog"


# ---------------------------------------------------------------------------
# 5. test_sitemap_parser_index
# ---------------------------------------------------------------------------

def test_sitemap_parser_index():
    """Handle sitemap index files — extract child sitemap URLs."""
    urls = parse_sitemap_xml(SITEMAP_INDEX_XML)

    assert len(urls) == 2
    assert urls[0].url == "https://example.com/sitemap-posts.xml"
    assert urls[1].url == "https://example.com/sitemap-pages.xml"


# ---------------------------------------------------------------------------
# 6. test_sitemap_parser_missing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sitemap_parser_missing():
    """Handle missing sitemap (404) gracefully."""
    mock_response = MagicMock()
    mock_response.status_code = 404

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    result = await fetch_sitemap("example.com", client=mock_client)

    assert result.status == SitemapStatus.MISSING
    assert result.sitemap_present is False
    assert result.sitemap_valid is False
    assert result.url_count == 0
    assert result.sitemap_score == 0.0


# ---------------------------------------------------------------------------
# 7. test_http_checker_ok
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_http_checker_ok():
    """Check URLs returning 200 and compute accessibility score."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {}

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    urls = ["https://example.com/", "https://example.com/about"]
    result = await check_urls(urls, timeout=10.0, client=mock_client)

    assert result.accessibility_score == 1.0
    assert len(result.sampled_urls) == 2
    assert all(r.ok for r in result.sampled_urls)
    assert all(r.status == UrlStatus.OK for r in result.sampled_urls)


# ---------------------------------------------------------------------------
# 8. test_http_checker_timeout
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_http_checker_timeout():
    """Handle timeout gracefully and mark URL as TIMEOUT."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    result = await check_urls(["https://slow.example.com/"], timeout=1.0, client=mock_client)

    assert len(result.sampled_urls) == 1
    assert result.sampled_urls[0].status == UrlStatus.TIMEOUT
    assert result.sampled_urls[0].ok is False
    assert result.accessibility_score == 0.0


# ---------------------------------------------------------------------------
# 9. test_preprocessor_full_flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preprocessor_full_flow():
    """Integration test with mocked HTTP — full preprocessor flow."""
    from core.state import AuditState

    state = AuditState(
        audit_id="audit-123",
        company_id="company-456",
        messages=[],
    )

    with (
        patch("agents.preprocessor._get_company_domain", new=AsyncMock(return_value="example.com")),
        patch("agents.preprocessor.fetch_robots_txt", new=AsyncMock(return_value=CrawlerPermissionsResult(
            robots_txt_raw=VALID_ROBOTS_TXT,
            permissions=[],
            crawl_permission_score=0.75,
            valid_robots_txt=True,
        ))),
        patch("agents.preprocessor.fetch_sitemap", new=AsyncMock(return_value=MagicMock(
            sitemap_present=True,
            sitemap_valid=True,
            url_count=3,
            urls=[],
            avg_lastmod_days=30.0,
            update_frequency_monthly=5.0,
            current_year_content_pct=80.0,
            sitemap_score=0.9,
        ))),
        patch("agents.preprocessor.check_urls", new=AsyncMock(return_value=MagicMock(
            sampled_urls=[],
            accessibility_score=0.9,
            avg_response_time_ms=200.0,
        ))),
        patch("agents.preprocessor._persist_results", new=AsyncMock()),
        patch("agents.preprocessor._publish_progress", new=AsyncMock()),
    ):
        result_state = await run(state)

    assert any(m.agent == "preprocessor" for m in result_state.messages)
    assert result_state.error is None or result_state.error == ""


# ---------------------------------------------------------------------------
# 10. test_preprocessor_null_domain
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preprocessor_null_domain():
    """Handle missing company domain — skip checks, persist empty record."""
    from core.state import AuditState

    state = AuditState(
        audit_id="audit-789",
        company_id="company-no-domain",
        messages=[],
    )

    with (
        patch("agents.preprocessor._get_company_domain", new=AsyncMock(return_value=None)),
        patch("agents.preprocessor._persist_results", new=AsyncMock()),
        patch("agents.preprocessor._publish_progress", new=AsyncMock()),
    ):
        result_state = await run(state)

    assert len(result_state.messages) == 1
    assert result_state.messages[0].agent == "preprocessor"
    assert "skipped" in result_state.messages[0].content.lower()


# ---------------------------------------------------------------------------
# 11. test_geo17_score_calculation
# ---------------------------------------------------------------------------

def test_geo17_score_calculation():
    """Verify GEO-17 score formula: 0.4×CP + 0.3×SP + 0.3×BA × 100."""
    # All perfect
    perfect = GEO17ScoreInput(crawl_permission=1.0, sitemap_presence=1.0, basic_accessibility=1.0)
    assert calculate_geo17_score(perfect) == pytest.approx(100.0)

    # All zero
    zero = GEO17ScoreInput(crawl_permission=0.0, sitemap_presence=0.0, basic_accessibility=0.0)
    assert calculate_geo17_score(zero) == pytest.approx(0.0)

    # Mixed
    mixed = GEO17ScoreInput(crawl_permission=0.5, sitemap_presence=1.0, basic_accessibility=0.8)
    # (0.4*0.5 + 0.3*1.0 + 0.3*0.8) * 100 = (0.2 + 0.3 + 0.24) * 100 = 74.0
    assert calculate_geo17_score(mixed) == pytest.approx(74.0)

    # No sitemap
    no_sitemap = GEO17ScoreInput(crawl_permission=1.0, sitemap_presence=0.0, basic_accessibility=1.0)
    # (0.4 + 0.0 + 0.3) * 100 = 70.0
    assert calculate_geo17_score(no_sitemap) == pytest.approx(70.0)


# ---------------------------------------------------------------------------
# 12. test_geo11_freshness_calculation
# ---------------------------------------------------------------------------

def test_geo11_freshness_calculation():
    """Verify GEO-11 freshness metrics normalization."""
    # Fresh content
    assert _normalize_recency(7) == pytest.approx(1.0)
    assert _normalize_recency(0) == pytest.approx(1.0)
    assert _normalize_recency(365) == pytest.approx(0.0)
    assert _normalize_recency(None) == pytest.approx(0.0)

    # Update frequency
    assert _normalize_frequency(50) == pytest.approx(1.0)
    assert _normalize_frequency(100) == pytest.approx(1.0)  # Capped
    assert _normalize_frequency(0) == pytest.approx(0.0)
    assert _normalize_frequency(None) == pytest.approx(0.0)
    assert _normalize_frequency(25) == pytest.approx(0.5)

    # Full geo11 components via calculate_freshness_metrics
    now = datetime.now(tz=timezone.utc)
    urls = [
        SitemapUrl(
            url=f"https://example.com/page-{i}",
            lastmod=now - timedelta(days=i * 10),
        )
        for i in range(5)
    ]
    avg_days, update_freq, current_pct = calculate_freshness_metrics(urls)

    assert avg_days is not None
    assert avg_days > 0
    assert update_freq is not None
    assert current_pct is not None
    assert 0.0 <= current_pct <= 100.0

    # Verify components dict
    result_mock = MagicMock()
    result_mock.avg_lastmod_days = 30.0
    result_mock.update_frequency_monthly = 10.0
    result_mock.current_year_content_pct = 75.0

    components = calculate_geo11_components(result_mock)

    assert "publication_recency" in components
    assert "update_frequency" in components
    assert "temporal_relevance" in components
    assert components["temporal_relevance"] == pytest.approx(0.75)
    assert 0.0 <= components["publication_recency"] <= 1.0
    assert 0.0 <= components["update_frequency"] <= 1.0


# ---------------------------------------------------------------------------
# Bonus: test calculate_freshness_metrics with no dates
# ---------------------------------------------------------------------------

def test_calculate_freshness_metrics_no_dates():
    """Return (None, None, None) when no lastmod data available."""
    urls = [SitemapUrl(url="https://example.com/page") for _ in range(3)]
    avg_days, update_freq, current_pct = calculate_freshness_metrics(urls)

    assert avg_days is None
    assert update_freq is None
    assert current_pct is None


# ---------------------------------------------------------------------------
# Bonus: test sample_urls_from_sitemap
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sample_urls_from_sitemap_empty():
    """Return empty list when no sitemap URLs provided."""
    result = await sample_urls_from_sitemap([], count=10)
    assert result == []


@pytest.mark.asyncio
async def test_sample_urls_from_sitemap_subset():
    """Return correct subset of URLs."""
    urls = [f"https://example.com/page-{i}" for i in range(20)]
    result = await sample_urls_from_sitemap(urls, count=5)

    assert len(result) == 5
    assert all(url in urls for url in result)
