"""Competitor Mapper Agent — Stage 4 of the LangGraph audit pipeline (GEO-14-CMP-PST)."""
from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import structlog

from core.state import AuditState, AgentMessage
from core.config import settings
from models.audit import AuditStatus

from .competitor_mapper_helpers import (
    AGENT_NAME, PROGRESS_VALUE, REDIS_TTL_SECONDS, ANALYSIS_SEMAPHORE_SIZE, CompetitorMention
)
from .competitor_mapper_db import fetch_comparative_responses, fetch_competitor_list, upsert_competitor_stats
from .competitor_mapper_llm import analyze_response_for_competitors
from .competitor_mapper_aggregator import aggregate_competitor_stats

log = structlog.get_logger(__name__)


async def _publish_progress(audit_id: str, message: str, progress: float) -> None:
    """Publish progress update to Redis."""
    try:
        import redis.asyncio as aioredis
        
        r = aioredis.from_url(settings.REDIS_URL)
        payload = json.dumps({
            "status": "analyzing",
            "progress": progress,
            "current_agent": AGENT_NAME,
            "message": message,
        })
        await r.set(f"audit:{audit_id}:progress", payload, ex=REDIS_TTL_SECONDS)
        await r.aclose()
    except Exception as exc:
        log.warning("redis_publish_failed", audit_id=audit_id, error=str(exc))


async def run(state: AuditState) -> AuditState:
    """LangGraph node: map competitors from comparative/recommendation responses."""
    bound_log = log.bind(audit_id=state.audit_id, agent=AGENT_NAME)
    bound_log.info("competitor_mapper_started")
    
    from supabase._async.client import create_client as _create_client
    db = await _create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    
    state.messages.append(AgentMessage(agent=AGENT_NAME, content="Starting competitor mapping analysis..."))
    
    try:
        responses = await fetch_comparative_responses(db, state.audit_id, bound_log)
        known_competitors, competitor_domains = await fetch_competitor_list(db, state.company_id, bound_log)
        
        # Early exit if no work
        if not known_competitors:
            bound_log.warning("no_competitors_configured", company_id=state.company_id)
            await _publish_progress(state.audit_id, "No competitors configured, skipping...", PROGRESS_VALUE)
            state.messages.append(AgentMessage(agent=AGENT_NAME, content="Skipped: no competitors configured."))
            return state
        
        if not responses:
            bound_log.info("no_comparative_responses", audit_id=state.audit_id)
            await _publish_progress(state.audit_id, "No comparative responses...", PROGRESS_VALUE)
            state.messages.append(AgentMessage(agent=AGENT_NAME, content="Skipped: no comparative responses found."))
            return state
        
        bound_log.info("starting_analysis", competitor_count=len(known_competitors), response_count=len(responses))
        
        # Analyze responses in parallel
        semaphore = asyncio.Semaphore(ANALYSIS_SEMAPHORE_SIZE)
        async with httpx.AsyncClient() as http_client:
            tasks = [analyze_response_for_competitors(r, known_competitors, semaphore, http_client, bound_log) for r in responses]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten results
        all_mentions: list[CompetitorMention] = []
        error_count = 0
        for result in results:
            if isinstance(result, Exception):
                error_count += 1
            else:
                all_mentions.extend(result)
        
        bound_log.info("analysis_complete", total_mentions=len(all_mentions), errors=error_count)
        
        # Aggregate and upsert
        stats_list = aggregate_competitor_stats(all_mentions, known_competitors, competitor_domains)
        await upsert_competitor_stats(db, stats_list, state.audit_id, bound_log)
        
        await _publish_progress(state.audit_id, f"Competitor mapping complete ({len(stats_list)} competitors)", PROGRESS_VALUE)
        
        state.messages.append(AgentMessage(
            agent=AGENT_NAME,
            content=f"Competitor mapping completed. Analyzed {len(responses)} responses, found {len(stats_list)} competitors.",
            metadata={"competitor_count": len(stats_list), "response_count": len(responses), "mention_count": len(all_mentions)}
        ))
        
        bound_log.info("competitor_mapper_completed", competitors_found=len(stats_list), mentions_found=len(all_mentions))
        
    except ValueError as exc:
        bound_log.error("value_error", error=str(exc))
        state.status = AuditStatus.failed
        state.error = f"Competitor mapper validation error: {exc}"
    except httpx.HTTPStatusError as exc:
        bound_log.error("http_error", status_code=exc.response.status_code if hasattr(exc, 'response') else None, error=str(exc))
        state.status = AuditStatus.failed
        state.error = f"Competitor mapper HTTP error: {exc}"
    except RuntimeError as exc:
        bound_log.error("runtime_error", error=str(exc))
        state.status = AuditStatus.failed
        state.error = f"Competitor mapper runtime error: {exc}"
    
    return state
