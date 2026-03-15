"""Database operations for audit_technical_checks table."""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from pydantic import BaseModel
from supabase._async.client import AsyncClient

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Data model returned from the DB layer
# ---------------------------------------------------------------------------

class TechnicalCheckRecord(BaseModel):
    """Mirrors the audit_technical_checks DB row for typed returns."""

    audit_id: str
    robots_txt_raw: str | None = None
    crawler_permissions: dict[str, str] = {}
    sitemap_present: bool = False
    sitemap_valid: bool = False
    sitemap_url_count: int = 0
    sitemap_sample: list[dict] = []
    sampled_pages: list[dict] = []
    avg_lastmod_days: float | None = None
    update_frequency_monthly: float | None = None
    current_year_content_pct: float | None = None
    created_at: datetime = datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def create_technical_check(
    db: AsyncClient,
    audit_id: str,
    robots_txt_raw: str | None,
    crawler_permissions: dict[str, str],
    sitemap_present: bool,
    sitemap_valid: bool,
    sitemap_url_count: int,
    sitemap_sample: list[dict],
    sampled_pages: list[dict],
    avg_lastmod_days: float | None,
    update_frequency_monthly: float | None,
    current_year_content_pct: float | None,
) -> dict:
    """Insert technical check results into audit_technical_checks."""
    row = {
        "audit_id": audit_id,
        "robots_txt_raw": robots_txt_raw,
        "crawler_permissions": crawler_permissions,
        "sitemap_present": sitemap_present,
        "sitemap_valid": sitemap_valid,
        "sitemap_url_count": sitemap_url_count,
        "sitemap_sample": sitemap_sample,
        "sampled_pages": sampled_pages,
        "avg_lastmod_days": avg_lastmod_days,
        "update_frequency_monthly": update_frequency_monthly,
        "current_year_content_pct": current_year_content_pct,
    }

    try:
        result = await db.table("audit_technical_checks").insert(row).execute()
        log.info("technical_check_created", audit_id=audit_id)
        return result.data[0] if result.data else {}
    except Exception as exc:
        log.error("technical_check_insert_failed", audit_id=audit_id, error=str(exc))
        raise


async def get_technical_check(
    db: AsyncClient,
    audit_id: str,
) -> TechnicalCheckRecord | None:
    """Retrieve technical check results for an audit."""
    try:
        result = (
            await db.table("audit_technical_checks")
            .select(
                "audit_id, robots_txt_raw, crawler_permissions, sitemap_present, "
                "sitemap_valid, sitemap_url_count, sitemap_sample, sampled_pages, "
                "avg_lastmod_days, update_frequency_monthly, current_year_content_pct, created_at"
            )
            .eq("audit_id", audit_id)
            .single()
            .execute()
        )
        if not result.data:
            return None
        return TechnicalCheckRecord(**result.data)
    except Exception as exc:
        log.warning("technical_check_fetch_failed", audit_id=audit_id, error=str(exc))
        return None


async def mark_preprocessing_complete(
    db: AsyncClient,
    audit_id: str,
) -> None:
    """Update audit status to 'generating' after preprocessing."""
    try:
        await (
            db.table("audits")
            .update({"status": "generating"})
            .eq("id", audit_id)
            .execute()
        )
        log.info("audit_status_generating", audit_id=audit_id)
    except Exception as exc:
        log.error("audit_status_update_failed", audit_id=audit_id, error=str(exc))
        raise
