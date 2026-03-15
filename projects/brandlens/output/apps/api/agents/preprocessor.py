"""Preprocessor Agent — Stage 1 of the LangGraph audit pipeline (GEO-17, GEO-11)."""
from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from pydantic import BaseModel

from core.state import AuditState, AgentMessage
from core.utils.robots_parser import fetch_robots_txt, CrawlerPermissionsResult
from core.utils.sitemap_parser import fetch_sitemap, SitemapValidationResult, SitemapUrl
from core.utils.http_checker import check_urls, AccessibilityCheckResult

log = structlog.get_logger(__name__)

_PREPROCESSOR_TIMEOUT = 15.0
_SAMPLE_COUNT = 10


# ---------------------------------------------------------------------------
# Score input models
# ---------------------------------------------------------------------------

class GEO17ScoreInput(BaseModel):
    """Input components for GEO-17 Crawl Accessibility calculation."""

    crawl_permission: float     # 0.0–1.0
    sitemap_presence: float     # 0.0, 0.5, or 1.0
    basic_accessibility: float  # 0.0–1.0


class TechnicalCheckResult(BaseModel):
    """Final output from preprocessor for database storage."""

    audit_id: str
    robots_txt_raw: str | None
    crawler_permissions: dict[str, str]
    sitemap_present: bool
    sitemap_valid: bool
    sitemap_url_count: int
    sitemap_sample: list[dict[str, Any]]
    sampled_pages: list[dict[str, Any]]
    avg_lastmod_days: float | None
    update_frequency_monthly: float | None
    current_year_content_pct: float | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Score calculations
# ---------------------------------------------------------------------------

def calculate_geo17_score(geo17_input: GEO17ScoreInput) -> float:
    """
    GEO-17 Crawl Accessibility
    Score = (0.4 × CrawlPermission + 0.3 × SitemapPresence + 0.3 × BasicAccessibility) × 100
    """
    return (
        0.4 * geo17_input.crawl_permission
        + 0.3 * geo17_input.sitemap_presence
        + 0.3 * geo17_input.basic_accessibility
    ) * 100


def _normalize_recency(avg_days: float | None) -> float:
    """Normalize avg_lastmod_days to 0.0–1.0 score (fresher = higher)."""
    if avg_days is None:
        return 0.0
    if avg_days <= 7:
        return 1.0
    if avg_days >= 365:
        return 0.0
    return round(1.0 - (avg_days / 365), 4)


def _normalize_frequency(updates_per_month: float | None) -> float:
    """Normalize update_frequency_monthly to 0.0–1.0 score. Cap at 50 updates/month."""
    if updates_per_month is None:
        return 0.0
    return round(min(updates_per_month / 50.0, 1.0), 4)


def calculate_geo11_components(result: SitemapValidationResult) -> dict[str, float]:
    """
    GEO-11 Freshness components dict for synthesizer.
    Score = (0.4 × PublicationRecency + 0.3 × UpdateFrequency + 0.3 × TemporalRelevance) × 100
    """
    return {
        "publication_recency": _normalize_recency(result.avg_lastmod_days),
        "update_frequency": _normalize_frequency(result.update_frequency_monthly),
        "temporal_relevance": (
            result.current_year_content_pct / 100
            if result.current_year_content_pct is not None
            else 0.0
        ),
    }


def _sitemap_presence_score(sitemap: SitemapValidationResult) -> float:
    """Convert sitemap result to 0.0 / 0.5 / 1.0 presence score."""
    if not sitemap.sitemap_present:
        return 0.0
    if sitemap.sitemap_valid:
        return 1.0
    return 0.5


# ---------------------------------------------------------------------------
# Domain fetch
# ---------------------------------------------------------------------------

async def _get_company_domain(company_id: str) -> str | None:
    """Fetch domain from Supabase companies table using service role key."""
    try:
        from core.config import settings
        from supabase._async.client import create_client as _create_client

        db = await _create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        res = await db.table("companies").select("domain").eq("id", company_id).single().execute()
        return (res.data or {}).get("domain") or None
    except Exception as exc:
        log.warning("domain_fetch_failed", company_id=company_id, error=str(exc))
        return None


# ---------------------------------------------------------------------------
# Redis progress publisher
# ---------------------------------------------------------------------------

async def _publish_progress(audit_id: str, message: str, progress: float) -> None:
    try:
        from core.config import settings
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.REDIS_URL)
        payload = json.dumps({
            "status": "preprocessing",
            "progress": progress,
            "current_agent": "preprocessor",
            "message": message,
        })
        await r.set(f"audit:{audit_id}:progress", payload, ex=3600)
        await r.aclose()
    except Exception as exc:
        log.warning("redis_publish_failed", audit_id=audit_id, error=str(exc))


# ---------------------------------------------------------------------------
# DB persistence
# ---------------------------------------------------------------------------

async def _persist_results(audit_id: str, tc: TechnicalCheckResult) -> None:
    from core.config import settings
    from supabase._async.client import create_client as _create_client

    db = await _create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

    row: dict[str, Any] = {
        "audit_id": audit_id,
        "robots_txt_raw": tc.robots_txt_raw,
        "crawler_permissions": tc.crawler_permissions,
        "sitemap_present": tc.sitemap_present,
        "sitemap_valid": tc.sitemap_valid,
        "sitemap_url_count": tc.sitemap_url_count,
        "sitemap_sample": tc.sitemap_sample,
        "sampled_pages": tc.sampled_pages,
        "avg_lastmod_days": tc.avg_lastmod_days,
        "update_frequency_monthly": tc.update_frequency_monthly,
        "current_year_content_pct": tc.current_year_content_pct,
    }

    await db.table("audit_technical_checks").insert(row).execute()
    await db.table("audits").update({"status": "generating"}).eq("id", audit_id).execute()


# ---------------------------------------------------------------------------
# Build helpers
# ---------------------------------------------------------------------------

def _sample_sitemap_urls(urls: list[SitemapUrl], count: int = _SAMPLE_COUNT) -> list[str]:
    all_urls = [u.url for u in urls if u.url.startswith("http")]
    if not all_urls:
        return []
    return random.sample(all_urls, min(count, len(all_urls)))


def _build_sitemap_sample(urls: list[SitemapUrl], max_items: int = 10) -> list[dict[str, Any]]:
    return [
        {
            "url": u.url,
            "lastmod": u.lastmod.isoformat() if u.lastmod else None,
            "priority": u.priority,
            "changefreq": u.changefreq,
        }
        for u in urls[:max_items]
    ]


def _build_sampled_pages(result: AccessibilityCheckResult) -> list[dict[str, Any]]:
    return [
        {
            "url": r.url,
            "status_code": r.status_code,
            "status": r.status.value,
            "ok": r.ok,
            "response_time_ms": r.response_time_ms,
        }
        for r in result.sampled_urls
    ]


# ---------------------------------------------------------------------------
# Main agent entry point
# ---------------------------------------------------------------------------

async def run(state: AuditState) -> AuditState:
    """
    Preprocessor agent: fetch robots.txt, sitemap.xml, sample pages.
    Writes results to audit_technical_checks table.
    LangGraph node signature: input state → output state.
    """
    bound_log = log.bind(audit_id=state.audit_id, agent="preprocessor")
    bound_log.info("preprocessor_started")

    await _publish_progress(state.audit_id, "Fetching technical checks…", 0.05)

    domain = await _get_company_domain(state.company_id)

    if not domain:
        bound_log.warning("no_domain_skip", company_id=state.company_id)
        tc_empty = TechnicalCheckResult(
            audit_id=state.audit_id,
            robots_txt_raw=None,
            crawler_permissions={},
            sitemap_present=False,
            sitemap_valid=False,
            sitemap_url_count=0,
            sitemap_sample=[],
            sampled_pages=[],
            avg_lastmod_days=None,
            update_frequency_monthly=None,
            current_year_content_pct=None,
            created_at=datetime.now(tz=timezone.utc),
        )
        try:
            await _persist_results(state.audit_id, tc_empty)
        except Exception as exc:
            bound_log.error("persist_empty_failed", error=str(exc))

        await _publish_progress(
            state.audit_id, "Preprocessor skipped (no domain)", 0.15
        )
        state.messages.append(AgentMessage(
            agent="preprocessor",
            content="Skipped: company has no domain configured.",
        ))
        return state

    bound_log.info("running_technical_checks", domain=domain)
    await _publish_progress(state.audit_id, "Fetching technical checks…", 0.08)

    try:
        async with httpx.AsyncClient(
            timeout=_PREPROCESSOR_TIMEOUT, follow_redirects=True
        ) as http_client:
            robots_result, sitemap_result = await asyncio.gather(
                fetch_robots_txt(domain, http_client),
                fetch_sitemap(domain, http_client),
                return_exceptions=True,
            )

        # Graceful degradation on individual tool failures
        if isinstance(robots_result, BaseException):
            bound_log.error("robots_check_failed", error=str(robots_result))
            robots_result = CrawlerPermissionsResult(
                robots_txt_raw=None,
                permissions=[],
                crawl_permission_score=0.0,
                valid_robots_txt=False,
            )

        if isinstance(sitemap_result, BaseException):
            bound_log.error("sitemap_check_failed", error=str(sitemap_result))
            from core.utils.sitemap_parser import SitemapStatus
            sitemap_result = SitemapValidationResult(
                status=SitemapStatus.MISSING,
                sitemap_present=False,
                sitemap_valid=False,
                url_count=0,
                urls=[],
                sitemap_score=0.0,
            )

        # HTTP checks depend on sitemap URLs — run after gather
        sampled_url_strs = _sample_sitemap_urls(sitemap_result.urls, _SAMPLE_COUNT)
        if not sampled_url_strs:
            sampled_url_strs = [f"https://{domain}/"]

        accessibility_result = await check_urls(sampled_url_strs, timeout=10.0)

    except Exception as exc:
        bound_log.error("preprocessor_checks_failed", error=str(exc))
        state.error = f"Preprocessor failed: {exc}"
        state.messages.append(AgentMessage(
            agent="preprocessor",
            content=f"Technical checks failed: {exc}",
        ))
        return state

    # Build crawler permissions map for DB column
    crawler_permissions: dict[str, str] = {
        p.crawler_name: ("allowed" if p.allowed else "disallowed")
        for p in robots_result.permissions
    }

    # Score components
    cp_score = robots_result.crawl_permission_score
    sp_score = _sitemap_presence_score(sitemap_result)
    ba_score = accessibility_result.accessibility_score

    geo17_input = GEO17ScoreInput(
        crawl_permission=cp_score,
        sitemap_presence=sp_score,
        basic_accessibility=ba_score,
    )
    geo17 = calculate_geo17_score(geo17_input)
    geo11_components = calculate_geo11_components(sitemap_result)
    geo11_approx = (
        geo11_components["publication_recency"] * 0.4
        + geo11_components["update_frequency"] * 0.3
        + geo11_components["temporal_relevance"] * 0.3
    ) * 100

    tc = TechnicalCheckResult(
        audit_id=state.audit_id,
        robots_txt_raw=robots_result.robots_txt_raw,
        crawler_permissions=crawler_permissions,
        sitemap_present=sitemap_result.sitemap_present,
        sitemap_valid=sitemap_result.sitemap_valid,
        sitemap_url_count=sitemap_result.url_count,
        sitemap_sample=_build_sitemap_sample(sitemap_result.urls),
        sampled_pages=_build_sampled_pages(accessibility_result),
        avg_lastmod_days=sitemap_result.avg_lastmod_days,
        update_frequency_monthly=sitemap_result.update_frequency_monthly,
        current_year_content_pct=sitemap_result.current_year_content_pct,
        created_at=datetime.now(tz=timezone.utc),
    )

    try:
        await _persist_results(state.audit_id, tc)
    except Exception as exc:
        bound_log.error("persist_failed", error=str(exc))
        # Non-fatal — log and continue pipeline

    await _publish_progress(
        state.audit_id, "Technical checks complete. Starting query generation…", 0.15
    )

    state.messages.append(AgentMessage(
        agent="preprocessor",
        content="Technical checks completed.",
        metadata={
            "technical_check_written": True,
            "domain": domain,
            "sitemap_url_count": sitemap_result.url_count,
            "crawl_permission_score": cp_score,
        },
    ))

    bound_log.info(
        "preprocessor_completed",
        geo17=round(geo17, 2),
        geo11_approx=round(geo11_approx, 2),
        sitemap_present=sitemap_result.sitemap_present,
        pages_checked=len(tc.sampled_pages),
    )
    return state
