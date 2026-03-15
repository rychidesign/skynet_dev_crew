import asyncio
import httpx
import structlog
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from typing import List, Dict, Any, Tuple

from postgrest import APIResponse
from supabase_py_async import AsyncClient

from apps.api.agents.competitor_mapper_constants_and_types import (
    AGENT_NAME, ANALYSIS_SEMAPHORE_SIZE, LLM_TIMEOUT_SECONDS, LLM_TEMPERATURE, COMPARATIVE_INTENTS,
    FilteredResponse, CompetitorRecord
)
from apps.api.agents.competitor_mapper_prompts import build_analysis_prompt, SYSTEM_PROMPT
from apps.api.agents.competitor_mapper_llm_parsing import parse_llm_output
from apps.api.agents.competitor_mapper_aggregation import aggregate_competitor_records, competitor_record_to_db_dict
from apps.api.core.config import settings
from apps.api.core.state import AuditState, AgentMessage, AuditStatus
from apps.api.models.audit import ProgressUpdate
from apps.api.core.redis_client import get_redis_client

log = structlog.get_logger(__name__)


async def upsert_competitors(
    db: AsyncClient,
    records: List[CompetitorRecord],
    audit_id: str,
    log_ctx: structlog.BoundLogger,
) -> None:
    """
    Batch UPSERT into audit_competitors using ON CONFLICT(audit_id, competitor_name).
    """
    if not records:
        log_ctx.info("No competitor records to upsert", audit_id=audit_id)
        return

    db_dicts = [competitor_record_to_db_dict(record) for record in records]

    try:
        res: APIResponse = await (
            db.from_("audit_competitors")
            .upsert(db_dicts, on_conflict="audit_id,competitor_name")
            .execute()
        )
        res.raise_for_status()
        log_ctx.info("Successfully upserted competitor records", count=len(records), audit_id=audit_id)
    except Exception as e:
        log_ctx.error(
            "Failed to upsert competitor records",
            error=str(e),
            audit_id=audit_id,
            records_count=len(records),
        )
        raise


async def publish_progress(
    redis_client: Any, # Redis client type depends on actual library used, e.g., redis.asyncio.Redis
    audit_id: str,
    competitors_count: int,
    responses_count: int,
    log_ctx: structlog.BoundLogger,
) -> None:
    """
    Publishes ProgressUpdate to Redis.
    """
    progress_update = ProgressUpdate(
        status=AuditStatus.RUNNING,
        progress=0.80,
        current_agent=AGENT_NAME,
        message=f"Mapped {competitors_count} competitors across {responses_count} responses",
    )
    try:
        await redis_client.publish(f"audit:{audit_id}:progress", progress_update.model_dump_json())
        log_ctx.debug("Published progress update to Redis", audit_id=audit_id, progress=progress_update.progress)
    except Exception as e:
        log_ctx.error("Failed to publish progress to Redis", error=str(e), audit_id=audit_id)
