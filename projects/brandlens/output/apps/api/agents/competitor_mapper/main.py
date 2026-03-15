import asyncio
import httpx
import structlog
from typing import List, Dict, Any

from apps.api.agents.competitor_mapper_constants_and_types import AGENT_NAME, ANALYSIS_SEMAPHORE_SIZE, CompetitorRecord
from apps.api.agents.competitor_mapper_data_and_llm_ops import fetch_competitors, fetch_filtered_responses, analyze_single_response
from apps.api.agents.competitor_mapper_aggregation import aggregate_competitor_records
from apps.api.agents.competitor_mapper_db_and_cache import upsert_competitors, publish_progress
from apps.api.core.state import AuditState, AgentMessage, AuditStatus
from apps.api.core.redis_client import get_redis_client

log = structlog.get_logger(__name__)


async def run(state: AuditState) -> AuditState:
    """
    LangGraph node entry point for Competitor Mapper agent.
    """
    audit_id = str(state.audit_id)
    company_id = str(state.company_id)
    log_ctx = log.bind(audit_id=audit_id, agent=AGENT_NAME)
    
    db = await state.get_db()
    redis_client = await get_redis_client()

    state.messages.append(AgentMessage(sender=AGENT_NAME, content="Starting competitor mapping."))
    await publish_progress(redis_client, audit_id, 0, 0, log_ctx) # Initial progress update

    try:
        competitors = await fetch_competitors(db, company_id, log_ctx)
        if not competitors:
            state.messages.append(AgentMessage(sender=AGENT_NAME, content="No competitors configured for this company."))
            await redis_client.close()
            return state

        filtered_responses = await fetch_filtered_responses(db, audit_id, log_ctx)
        if not filtered_responses:
            state.messages.append(AgentMessage(sender=AGENT_NAME, content="No comparative/recommendation responses found."))
            await redis_client.close()
            return state

        async with httpx.AsyncClient() as http_client:
            semaphore = asyncio.Semaphore(ANALYSIS_SEMAPHORE_SIZE)
            tasks = [
                analyze_single_response(res, competitors, semaphore, http_client, log_ctx)
                for res in filtered_responses
            ]
            # Collect results, ignoring exceptions for individual response analyses
            all_mentions_across_responses = [
                result for result in await asyncio.gather(*tasks, return_exceptions=False) 
                if isinstance(result, tuple) and result[1] # Filter out failed tasks and empty mention lists
            ]
        
        # Aggregate and create records
        competitor_records: List[CompetitorRecord] = aggregate_competitor_records(
            all_mentions_across_responses=all_mentions_across_responses,
            all_competitors=competitors,
            audit_id=audit_id,
            log_ctx=log_ctx,
        )

        # Upsert into DB
        await upsert_competitors(db, competitor_records, audit_id, log_ctx)

        # state.brand_competitive_stats = [rec.model_dump() for rec in competitor_records] # For Pydantic v2
        state.brand_competitive_stats = [rec.__dict__ for rec in competitor_records] # For dataclasses
        state.messages.append(AgentMessage(sender=AGENT_NAME, content=f"Successfully mapped {len(competitor_records)} competitors."))
        await publish_progress(redis_client, audit_id, len(competitor_records), len(filtered_responses), log_ctx)

    except Exception as e:
        log_ctx.error(
            "Competitor Mapper agent failed",
            error=str(e),
            audit_id=audit_id,
        )
        state.status = AuditStatus.FAILED
        state.error = str(e)
        state.messages.append(AgentMessage(sender=AGENT_NAME, content=f"Competitor mapping failed: {e}"))
    finally:
        await redis_client.close()

    return state
