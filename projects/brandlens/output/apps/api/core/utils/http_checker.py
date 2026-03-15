"""HTTP accessibility checker — samples URLs and checks their HTTP status."""
from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from enum import Enum

import httpx
import structlog

log = structlog.get_logger(__name__)

HTTP_CHECK_TIMEOUT = 8.0  # seconds per request


class UrlStatus(str, Enum):
    """HTTP result status categories."""
    OK = "ok"
    REDIRECT = "redirect"
    CLIENT_ERROR = "client_error"
    SERVER_ERROR = "server_error"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    UNKNOWN = "unknown"


# Alias for backward compat / preprocessor.py import
PageStatus = UrlStatus


@dataclass
class PageCheckResult:
    url: str
    status_code: int | None     # None on connection error / timeout
    ok: bool                    # True if 200–299
    status: UrlStatus
    response_time_ms: int | None = None


@dataclass
class AccessibilityCheckResult:
    """Result of checking a batch of sampled URLs."""
    sampled_urls: list[PageCheckResult] = field(default_factory=list)
    accessibility_score: float = 0.0    # fraction of ok pages (0.0–1.0)
    avg_response_time_ms: float | None = None


# Backward-compat alias used by preprocessor.py
HttpCheckResult = AccessibilityCheckResult


# ---------------------------------------------------------------------------
# Per-URL check
# ---------------------------------------------------------------------------

def _classify_status(code: int) -> UrlStatus:
    if 200 <= code < 300:
        return UrlStatus.OK
    if 300 <= code < 400:
        return UrlStatus.REDIRECT
    if 400 <= code < 500:
        return UrlStatus.CLIENT_ERROR
    if 500 <= code < 600:
        return UrlStatus.SERVER_ERROR
    return UrlStatus.UNKNOWN


async def _check_single_url(url: str, client: httpx.AsyncClient) -> PageCheckResult:
    """
    Check a single URL via HEAD first, then GET on 405 (Method Not Allowed).
    Returns PageCheckResult with status code, ok flag, and response time.
    """
    start = time.monotonic()

    try:
        response = await client.head(url, timeout=HTTP_CHECK_TIMEOUT)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        if response.status_code == 405:
            start = time.monotonic()
            response = await client.get(url, timeout=HTTP_CHECK_TIMEOUT)
            elapsed_ms = int((time.monotonic() - start) * 1000)

        code = response.status_code
        ok = 200 <= code < 300
        return PageCheckResult(
            url=url,
            status_code=code,
            ok=ok,
            status=_classify_status(code),
            response_time_ms=elapsed_ms,
        )

    except httpx.TimeoutException:
        log.debug("http_check_timeout", url=url)
        return PageCheckResult(
            url=url,
            status_code=None,
            ok=False,
            status=UrlStatus.TIMEOUT,
            response_time_ms=None,
        )
    except httpx.ConnectError:
        log.debug("http_check_connect_error", url=url)
        return PageCheckResult(
            url=url,
            status_code=None,
            ok=False,
            status=UrlStatus.CONNECTION_ERROR,
            response_time_ms=None,
        )
    except httpx.RequestError as exc:
        log.debug("http_check_request_error", url=url, error=str(exc))
        return PageCheckResult(
            url=url,
            status_code=None,
            ok=False,
            status=UrlStatus.UNKNOWN,
            response_time_ms=None,
        )


# ---------------------------------------------------------------------------
# Sampling helper (exported for tests)
# ---------------------------------------------------------------------------

async def sample_urls_from_sitemap(
    urls: list[str],
    count: int = 10,
) -> list[str]:
    """
    Return a random sample of up to `count` URLs from the provided list.
    Exported for direct use in tests.
    """
    valid = [u for u in urls if u.startswith("http")]
    if not valid:
        return []
    return random.sample(valid, min(count, len(valid)))


# ---------------------------------------------------------------------------
# Core batch checker
# ---------------------------------------------------------------------------

async def check_sampled_pages(
    urls: list[str],
    client: httpx.AsyncClient,
    sample_size: int = 10,
) -> AccessibilityCheckResult:
    """
    Randomly sample up to `sample_size` URLs and check HTTP accessibility concurrently.

    Returns AccessibilityCheckResult with per-page results and aggregate accessibility_score.
    Score is 0.0 if no URLs are provided.
    """
    if not urls:
        return AccessibilityCheckResult(sampled_urls=[], accessibility_score=0.0)

    sampled = await sample_urls_from_sitemap(urls, count=sample_size)

    if not sampled:
        return AccessibilityCheckResult(sampled_urls=[], accessibility_score=0.0)

    raw_results = await asyncio.gather(
        *[_check_single_url(url, client) for url in sampled],
        return_exceptions=True,
    )

    page_results: list[PageCheckResult] = []
    for r in raw_results:
        if isinstance(r, BaseException):
            log.warning("http_check_unexpected_error", error=str(r))
            continue
        page_results.append(r)  # type: ignore[arg-type]

    ok_count = sum(1 for r in page_results if r.ok)
    score = ok_count / len(sampled) if sampled else 0.0

    response_times = [r.response_time_ms for r in page_results if r.response_time_ms is not None]
    avg_rt = round(sum(response_times) / len(response_times), 1) if response_times else None

    return AccessibilityCheckResult(
        sampled_urls=page_results,
        accessibility_score=round(score, 4),
        avg_response_time_ms=avg_rt,
    )


# ---------------------------------------------------------------------------
# Public convenience entry point
# ---------------------------------------------------------------------------

async def check_urls(
    urls: list[str],
    timeout: float = HTTP_CHECK_TIMEOUT,
    sample_size: int = 10,
    client: httpx.AsyncClient | None = None,
) -> AccessibilityCheckResult:
    """
    Check HTTP accessibility for a list of URLs.

    If `client` is provided (e.g. from tests), it is used directly.
    Otherwise a new AsyncClient is created internally.
    """
    if client is not None:
        return await check_sampled_pages(urls, client, sample_size=sample_size)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as auto_client:
        return await check_sampled_pages(urls, auto_client, sample_size=sample_size)
