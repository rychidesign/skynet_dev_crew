"""Progress publishing functions for query generator agent."""
from typing import Optional

import structlog
import redis.asyncio as redis_lib

from core.redis_client import get_redis_client
from models.progress import ProgressUpdate

logger = structlog.get_logger(__name__)

PROGRESS_CHANNEL_TTL = 3600


async def publish_progress(
    audit_id: str, message: str, progress: float, queries_generated: Optional[int] = None
) -> None:
    """Publishes audit progress updates to Redis."""
    redis_client: redis_lib.Redis = get_redis_client()
    progress_update = ProgressUpdate(
        audit_id=audit_id,
        status="generating",
        progress=progress,
        current_agent="query_generator",
        message=message,
        queries_generated=queries_generated,
    )
    await redis_client.set(
        f"audit:{audit_id}:progress", progress_update.model_dump_json(), ex=PROGRESS_CHANNEL_TTL
    )
    await redis_client.aclose()
    logger.debug(f"Published progress for audit {audit_id}: {message} ({progress*100:.0f}%)")
