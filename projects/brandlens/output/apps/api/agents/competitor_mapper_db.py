"""Competitor Mapper database operations — fetch and upsert."""
from __future__ import annotations

import structlog
from typing import Any

from .competitor_mapper_helpers import (
    CompetitorStats,
    ResponseRow,
    stats_to_db_dict,
)


async def fetch_comparative_responses(
    db,
    audit_id: str,
    log_ctx
) -> list[ResponseRow]:
    """
    Fetch responses with comparative/recommendation intent.
    
    Joins audit_responses with audit_queries on query_id.
    """
    from .competitor_mapper_helpers import COMPARATIVE_INTENTS
    
    try:
        res = await db.table("audit_responses").select(
            "id, query_id, ai_platform, response_text, audit_queries!inner(intent)"
        ).eq("audit_id", audit_id).in_("audit_queries.intent", list(COMPARATIVE_INTENTS)).execute()
        
        rows = []
        for item in (res.data or []):
            # Handle nested query data
            query_intent = item.get("audit_queries", {}).get("intent", "") if isinstance(item.get("audit_queries"), dict) else ""
            
            rows.append(ResponseRow(
                response_id=item["id"],
                query_id=item["query_id"],
                platform=item["ai_platform"],
                response_text=item["response_text"],
                query_intent=query_intent
            ))
        
        log_ctx.info("fetched_comparative_responses", count=len(rows), audit_id=audit_id)
        return rows
    except Exception as exc:
        log_ctx.error("fetch_responses_failed", audit_id=audit_id, error=str(exc))
        raise RuntimeError(f"Failed to fetch comparative responses: {exc}") from exc


async def fetch_competitor_list(
    db,
    company_id: str,
    log_ctx
) -> tuple[list[str], dict[str, str]]:
    """
    Fetch competitors list from companies table.
    
    Returns (competitor_names, competitor_domains) where domains are parsed
    from entries containing a dot (e.g., "acme.com" → name="acme", domain="acme.com").
    """
    try:
        res = await db.table("companies").select("competitors").eq("id", company_id).single().execute()
        data = res.data or {}
        competitors_raw = data.get("competitors") or []
        
        competitor_names = []
        competitor_domains = {}
        
        for entry in competitors_raw:
            if not isinstance(entry, str):
                continue
            entry = entry.strip()
            if not entry:
                continue
            
            # Parse domain from entries containing a dot
            if "." in entry:
                # Extract name from domain (e.g., "acme.com" → "acme")
                parts = entry.split(".")
                name = parts[0] if parts else entry
                competitor_domains[name.lower()] = entry
                competitor_names.append(name)
            else:
                competitor_names.append(entry)
        
        log_ctx.info("fetched_competitor_list", count=len(competitor_names), company_id=company_id)
        return competitor_names, competitor_domains
    except Exception as exc:
        log_ctx.error("fetch_competitors_failed", company_id=company_id, error=str(exc))
        raise RuntimeError(f"Failed to fetch competitor list: {exc}") from exc


async def upsert_competitor_stats(
    db,
    stats_list: list[CompetitorStats],
    audit_id: str,
    log_ctx
) -> None:
    """
    Upsert competitor statistics into audit_competitors table.
    
    Uses UPSERT ON CONFLICT (audit_id, competitor_name) for idempotency.
    """
    if not stats_list:
        log_ctx.info("no_competitor_stats_to_upsert", audit_id=audit_id)
        return
    
    try:
        rows = [stats_to_db_dict(stats, audit_id) for stats in stats_list]
        
        await db.table("audit_competitors").upsert(
            rows,
            on_conflict="audit_id,competitor_name"
        ).execute()
        
        log_ctx.info(
            "upserted_competitor_stats",
            audit_id=audit_id,
            competitor_count=len(rows)
        )
    except Exception as exc:
        log_ctx.error("upsert_competitors_failed", audit_id=audit_id, error=str(exc))
        raise RuntimeError(f"Failed to upsert competitor stats: {exc}") from exc
