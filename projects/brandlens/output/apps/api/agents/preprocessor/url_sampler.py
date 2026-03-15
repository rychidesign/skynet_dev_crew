"""URL sampler and HTTP status checker for crawl accessibility (GEO-17)."""
from __future__ import annotations

import asyncio
import random
import time

import httpx
import structlog

from models.technical_check import SampledPage, SitemapUrl

logger = structlog.get_logger(__name__)

COMMON_PATHS = ["/", "/about", "/contact", "/products", "/services", "/blog"]


def select_sample_urls(
    sitemap_urls: list[SitemapUrl],
    domain: str,
    count: int = 10,
) -> list[str]:
    """
    Select URLs to sample for accessibility check.
    Priority: sitemap URLs first, then common pages if needed.
    Returns exactly 'count' URLs (or fewer if unavailable).
    """
    result: list[str] = []

    if sitemap_urls:
        loc_urls = [u.loc for u in sitemap_urls if u.loc]
        sample_size = min(count, len(loc_urls))
        result = random.sample(loc_urls, sample_size)

    # Pad with common paths if needed
    if len(result) < count:
        base = f"https://{domain}"
        for path in COMMON_PATHS:
            if len(result) >= count:
                break
            candidate = f"{base}{path}"
            if candidate not in result:
                result.append(candidate)

    return result[:count]


async def check_url_status(
    url: str,
    client: httpx.AsyncClient,
    timeout: float = 10.0,
) -> SampledPage:
    """Check HTTP status for a single URL, return SampledPage with status and timing."""
    start = time.monotonic()
    try:
        response = await client.head(url, timeout=timeout)
        latency_ms = int((time.monotonic() - start) * 1000)
        return SampledPage(
            url=url,
            status_code=response.status_code,
            ok=response.status_code == 200,
            latency_ms=latency_ms,
        )
    except httpx.TimeoutException:
        logger.debug("URL check timed out", url=url)
        return SampledPage(url=url, status_code=0, ok=False, latency_ms=None)
    except httpx.RequestError as exc:
        logger.debug("URL check failed", url=url, error=str(exc))
        return SampledPage(url=url, status_code=0, ok=False, latency_ms=None)


async def sample_and_check_urls(
    sitemap_urls: list[SitemapUrl],
    domain: str,
    client: httpx.AsyncClient,
    sample_count: int = 10,
) -> list[SampledPage]:
    """
    Sample URLs and check their HTTP status in parallel.
    Uses asyncio.gather for concurrent checks.
    """
    urls = select_sample_urls(sitemap_urls, domain, sample_count)
    if not urls:
        return []

    tasks = [check_url_status(url, client) for url in urls]
    results: list[SampledPage] = await asyncio.gather(*tasks)
    return results
