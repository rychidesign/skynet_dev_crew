"""sitemap.xml fetcher, parser, and freshness metrics calculator."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from xml.etree import ElementTree

import httpx
import structlog

from models.technical_check import SitemapAnalysis, SitemapUrl

logger = structlog.get_logger(__name__)

SITEMAP_NAMESPACES = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "si": "http://www.sitemaps.org/schemas/sitemap-index/0.9",
}
SITEMAP_PATHS = ["/sitemap.xml", "/sitemap_index.xml"]
MAX_URLS = 100


async def fetch_sitemap(domain: str, client: httpx.AsyncClient) -> str | None:
    """Try common sitemap locations: /sitemap.xml, /sitemap_index.xml."""
    for path in SITEMAP_PATHS:
        url = f"https://{domain}{path}"
        try:
            response = await client.get(url, timeout=15.0)
            if response.status_code == 200:
                return response.text
        except httpx.TimeoutException:
            logger.warning("sitemap fetch timed out", url=url)
        except httpx.RequestError as exc:
            logger.warning("sitemap fetch failed", url=url, error=str(exc))
    return None


def _parse_date(datestr: str | None) -> datetime | None:
    """Parse ISO 8601 date string into UTC datetime."""
    if not datestr:
        return None
    datestr = datestr.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(datestr, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def parse_sitemap(content: str, max_urls: int = MAX_URLS) -> tuple[list[SitemapUrl], bool]:
    """
    Parse XML sitemap, extract URLs with lastmod dates.
    Returns (url_list, is_valid).
    Handles both urlset and sitemapindex.
    """
    urls: list[SitemapUrl] = []
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        logger.warning("sitemap XML parse error", error=str(exc))
        return [], False

    tag = root.tag.lower()
    ns_match = re.match(r"\{(.+)\}", root.tag)
    ns = ns_match.group(1) if ns_match else ""
    ns_prefix = f"{{{ns}}}" if ns else ""

    # Handle sitemapindex — extract <loc> entries (child sitemaps)
    if "sitemapindex" in tag:
        for sitemap_el in root.findall(f"{ns_prefix}sitemap")[:max_urls]:
            loc_el = sitemap_el.find(f"{ns_prefix}loc")
            lastmod_el = sitemap_el.find(f"{ns_prefix}lastmod")
            if loc_el is not None and loc_el.text:
                urls.append(
                    SitemapUrl(
                        loc=loc_el.text.strip(),
                        lastmod=lastmod_el.text.strip() if lastmod_el is not None and lastmod_el.text else None,
                    )
                )
        return urls, len(urls) > 0

    # Handle urlset
    if "urlset" in tag:
        for url_el in root.findall(f"{ns_prefix}url")[:max_urls]:
            loc_el = url_el.find(f"{ns_prefix}loc")
            lastmod_el = url_el.find(f"{ns_prefix}lastmod")
            changefreq_el = url_el.find(f"{ns_prefix}changefreq")
            priority_el = url_el.find(f"{ns_prefix}priority")

            if loc_el is not None and loc_el.text:
                priority: float | None = None
                if priority_el is not None and priority_el.text:
                    try:
                        priority = float(priority_el.text.strip())
                    except ValueError:
                        pass

                urls.append(
                    SitemapUrl(
                        loc=loc_el.text.strip(),
                        lastmod=lastmod_el.text.strip() if lastmod_el is not None and lastmod_el.text else None,
                        changefreq=changefreq_el.text.strip() if changefreq_el is not None and changefreq_el.text else None,
                        priority=priority,
                    )
                )
        return urls, len(urls) > 0

    logger.warning("sitemap: unrecognised root element", tag=root.tag)
    return [], False


def calculate_freshness_metrics(
    urls: list[SitemapUrl],
) -> tuple[float | None, float | None, float | None]:
    """
    Calculate freshness metrics from lastmod dates.
    Returns (avg_lastmod_days, update_frequency_monthly, current_year_content_pct).
    Returns (None, None, None) if no valid lastmod dates.
    """
    now = datetime.now(timezone.utc)
    current_year = now.year

    parsed_dates: list[datetime] = []
    current_year_count = 0

    for url in urls:
        dt = _parse_date(url.lastmod)
        if dt is None:
            continue
        parsed_dates.append(dt)
        if dt.year == current_year:
            current_year_count += 1

    if not parsed_dates:
        return None, None, None

    # avg_lastmod_days: average days since last modification
    total_days = sum((now - dt).total_seconds() / 86400.0 for dt in parsed_dates)
    avg_lastmod_days = total_days / len(parsed_dates)

    # update_frequency_monthly: count URLs updated within the last 30 days / 1 month
    recent_count = sum(1 for dt in parsed_dates if (now - dt).days <= 30)
    update_frequency_monthly = float(recent_count)

    # current_year_content_pct: % of dated URLs with current year
    current_year_content_pct = (current_year_count / len(parsed_dates)) * 100.0

    return avg_lastmod_days, update_frequency_monthly, current_year_content_pct


async def analyze_sitemap(domain: str, client: httpx.AsyncClient) -> SitemapAnalysis:
    """Orchestrates fetch + parse + metrics calculation, returns SitemapAnalysis."""
    raw_content = await fetch_sitemap(domain, client)

    if raw_content is None:
        return SitemapAnalysis(present=False, valid=False, url_count=0, urls=[])

    urls, is_valid = parse_sitemap(raw_content)
    avg_days, update_freq, current_year_pct = calculate_freshness_metrics(urls)

    return SitemapAnalysis(
        present=True,
        valid=is_valid,
        url_count=len(urls),
        urls=urls,
        avg_lastmod_days=avg_days,
        update_frequency_monthly=update_freq,
        current_year_content_pct=current_year_pct,
    )
