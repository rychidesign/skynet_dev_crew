"""Sitemap.xml fetcher and parser — extracts URL count and lastmod dates for GEO-11/GEO-17."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum

import httpx
import structlog

log = structlog.get_logger(__name__)

SITEMAP_FETCH_TIMEOUT = 10.0  # seconds per request
MAX_ENTRIES = 500              # cap total entries in memory
MAX_CHILD_SITEMAPS = 3        # max child sitemaps to follow from a sitemap index

_NS_SITEMAP = "http://www.sitemaps.org/schemas/sitemap/0.9"


class SitemapStatus(str, Enum):
    VALID = "valid"
    PRESENT_INVALID = "present_invalid"
    MISSING = "missing"
    FETCH_ERROR = "fetch_error"


@dataclass
class SitemapUrl:
    url: str
    lastmod: date | None = None
    priority: float | None = None
    changefreq: str | None = None


@dataclass
class SitemapValidationResult:
    status: SitemapStatus
    sitemap_present: bool
    sitemap_valid: bool
    url_count: int
    urls: list[SitemapUrl] = field(default_factory=list)
    sitemap_score: float = 0.0          # 0.0, 0.5, or 1.0
    avg_lastmod_days: float | None = None
    update_frequency_monthly: float | None = None
    current_year_content_pct: float | None = None
    sitemap_url: str | None = None      # resolved sitemap URL
    fetch_error: str | None = None


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def _tag(name: str) -> str:
    return f"{{{_NS_SITEMAP}}}{name}"


def _find_text(element: ET.Element, tag: str) -> str | None:
    child = element.find(_tag(tag))
    if child is not None and child.text:
        return child.text.strip()
    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return None


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

def _parse_lastmod(value: str) -> date | None:
    """Parse ISO 8601 date strings like 2024-01-15 or 2024-01-15T10:00:00Z."""
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m"):
        try:
            return datetime.strptime(value[:len(fmt)], fmt).date()
        except ValueError:
            pass
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Freshness metrics (exported for tests)
# ---------------------------------------------------------------------------

def calculate_freshness_metrics(
    entries: list[SitemapUrl],
) -> tuple[float | None, float | None, float | None]:
    """
    Compute (avg_lastmod_days, update_frequency_monthly, current_year_content_pct).
    Returns (None, None, None) when no lastmod data is available.
    Exported for direct use in tests.
    """
    today = date.today()
    current_year = today.year

    dated = [e for e in entries if e.lastmod is not None]
    if not dated:
        return None, None, None

    days_list = [(today - e.lastmod).days for e in dated]
    avg_days = sum(days_list) / len(days_list)

    sorted_dates = sorted(e.lastmod for e in dated)
    update_freq: float | None = None
    if len(sorted_dates) >= 2:
        intervals = [
            (sorted_dates[i + 1] - sorted_dates[i]).days
            for i in range(len(sorted_dates) - 1)
        ]
        non_zero = [d for d in intervals if d > 0]
        if non_zero:
            avg_interval = sum(non_zero) / len(non_zero)
            update_freq = round(30.0 / avg_interval, 4)

    current_year_count = sum(1 for e in dated if e.lastmod.year == current_year)
    current_year_pct = round(current_year_count / len(dated) * 100, 2)

    return round(avg_days, 2), update_freq, current_year_pct


# ---------------------------------------------------------------------------
# XML parsers (exported for tests)
# ---------------------------------------------------------------------------

def _is_sitemapindex(xml_text: str) -> bool:
    """Return True if the root element is <sitemapindex>."""
    try:
        root = ET.fromstring(xml_text)
        tag_local = root.tag.split("}")[-1] if "}" in root.tag else root.tag
        return tag_local.lower() == "sitemapindex"
    except ET.ParseError:
        return False


def _parse_urlset_entries(xml_text: str) -> list[SitemapUrl]:
    """Parse a <urlset> document and return SitemapUrl entries."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    urls: list[SitemapUrl] = []
    for url_el in root:
        tag_local = url_el.tag.split("}")[-1] if "}" in url_el.tag else url_el.tag
        if tag_local.lower() != "url":
            continue

        loc = _find_text(url_el, "loc")
        if not loc:
            continue

        lastmod_str = _find_text(url_el, "lastmod")
        priority_str = _find_text(url_el, "priority")
        changefreq = _find_text(url_el, "changefreq")

        lastmod = _parse_lastmod(lastmod_str) if lastmod_str else None
        priority: float | None = None
        if priority_str:
            try:
                priority = float(priority_str)
            except ValueError:
                pass

        urls.append(SitemapUrl(url=loc, lastmod=lastmod, priority=priority, changefreq=changefreq))

    return urls


def _parse_sitemapindex_entries(xml_text: str) -> list[SitemapUrl]:
    """
    Parse a <sitemapindex> document and return child sitemap URLs as SitemapUrl entries.
    (loc = sitemap child URL, lastmod = sitemap lastmod if present)
    Used by parse_sitemap_xml for the flat return contract.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    entries: list[SitemapUrl] = []
    for sitemap_el in root:
        tag_local = sitemap_el.tag.split("}")[-1] if "}" in sitemap_el.tag else sitemap_el.tag
        if tag_local.lower() != "sitemap":
            continue
        loc = _find_text(sitemap_el, "loc")
        if loc and loc.startswith("http"):
            lastmod_str = _find_text(sitemap_el, "lastmod")
            lastmod = _parse_lastmod(lastmod_str) if lastmod_str else None
            entries.append(SitemapUrl(url=loc, lastmod=lastmod))

    return entries


def _parse_sitemapindex_urls(xml_text: str) -> list[str]:
    """Return list of child sitemap URL strings from a <sitemapindex>."""
    return [e.url for e in _parse_sitemapindex_entries(xml_text)]


def parse_sitemap_xml(xml_text: str) -> list[SitemapUrl]:
    """
    Parse a sitemap XML string.
    - If <urlset>: returns page URL entries.
    - If <sitemapindex>: returns child sitemap entries (each entry.url is a child sitemap URL).
    Exported for direct use in tests.
    """
    if _is_sitemapindex(xml_text):
        return _parse_sitemapindex_entries(xml_text)
    return _parse_urlset_entries(xml_text)


# ---------------------------------------------------------------------------
# HTTP fetch helper
# ---------------------------------------------------------------------------

async def _fetch_xml(url: str, client: httpx.AsyncClient) -> str | None:
    try:
        response = await client.get(url, timeout=SITEMAP_FETCH_TIMEOUT)
        if response.status_code == 200:
            return response.text
        log.debug("sitemap_fetch_non_200", url=url, status=response.status_code)
        return None
    except httpx.TimeoutException as exc:
        log.warning("sitemap_fetch_timeout", url=url, error=str(exc))
        return None
    except httpx.ConnectError as exc:
        log.warning("sitemap_fetch_connect_error", url=url, error=str(exc))
        return None
    except httpx.RequestError as exc:
        log.warning("sitemap_fetch_request_error", url=url, error=str(exc))
        return None


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------

async def parse_sitemap(
    domain: str,
    client: httpx.AsyncClient,
    sitemap_url_hint: str | None = None,
) -> SitemapValidationResult:
    """
    Fetch and parse sitemap.xml for the given domain.

    Priority: sitemap_url_hint → /sitemap.xml → /sitemap_index.xml.
    Handles sitemap index files by following up to MAX_CHILD_SITEMAPS children.
    """
    candidates: list[str] = []
    if sitemap_url_hint:
        candidates.append(sitemap_url_hint)
    candidates.append(f"https://{domain}/sitemap.xml")
    candidates.append(f"https://{domain}/sitemap_index.xml")

    xml_text: str | None = None
    resolved_url: str | None = None
    fetch_error: str | None = None

    for candidate in candidates:
        xml_text = await _fetch_xml(candidate, client)
        if xml_text:
            resolved_url = candidate
            break
        fetch_error = f"Could not fetch sitemap from {candidate}"

    if not xml_text:
        return SitemapValidationResult(
            status=SitemapStatus.MISSING,
            sitemap_present=False,
            sitemap_valid=False,
            url_count=0,
            urls=[],
            sitemap_score=0.0,
            sitemap_url=resolved_url,
            fetch_error=fetch_error,
        )

    all_entries: list[SitemapUrl] = []

    try:
        if _is_sitemapindex(xml_text):
            child_urls = _parse_sitemapindex_urls(xml_text)[:MAX_CHILD_SITEMAPS]
            for child_url in child_urls:
                if len(all_entries) >= MAX_ENTRIES:
                    break
                child_xml = await _fetch_xml(child_url, client)
                if child_xml:
                    entries = _parse_urlset_entries(child_xml)
                    remaining = MAX_ENTRIES - len(all_entries)
                    all_entries.extend(entries[:remaining])
        else:
            all_entries = _parse_urlset_entries(xml_text)[:MAX_ENTRIES]
    except Exception as exc:
        log.error("sitemap_parse_error", domain=domain, error=str(exc))
        return SitemapValidationResult(
            status=SitemapStatus.PRESENT_INVALID,
            sitemap_present=True,
            sitemap_valid=False,
            url_count=0,
            urls=[],
            sitemap_score=0.5,
            sitemap_url=resolved_url,
            fetch_error=str(exc),
        )

    if not all_entries:
        return SitemapValidationResult(
            status=SitemapStatus.PRESENT_INVALID,
            sitemap_present=True,
            sitemap_valid=False,
            url_count=0,
            urls=[],
            sitemap_score=0.5,
            sitemap_url=resolved_url,
            fetch_error="Sitemap present but contains no URLs",
        )

    avg_days, update_freq, current_year_pct = calculate_freshness_metrics(all_entries)

    return SitemapValidationResult(
        status=SitemapStatus.VALID,
        sitemap_present=True,
        sitemap_valid=True,
        url_count=len(all_entries),
        urls=all_entries,
        sitemap_score=1.0,
        avg_lastmod_days=avg_days,
        update_frequency_monthly=update_freq,
        current_year_content_pct=current_year_pct,
        sitemap_url=resolved_url,
        fetch_error=None,
    )


# Alias used by preprocessor.py and tests
fetch_sitemap = parse_sitemap
