"""Upstash Redis client factory using pydantic settings."""
from __future__ import annotations

from upstash_redis.asyncio import Redis

from core.config import settings

# Single module-level instance variable
_redis_client: Redis | None = None


def get_redis_client() -> Redis:
    """
    Returns an async instance of the Upstash Redis client.
    Initializes the client lazily on the first call.
    Uses settings from core.config for Upstash Redis REST credentials.
    """
    global _redis_client

    if _redis_client is None:
        redis_url = settings.UPSTASH_REDIS_REST_URL
        redis_token = settings.UPSTASH_REDIS_REST_TOKEN

        if not redis_url or not redis_token:
            raise RuntimeError(
                "Missing Upstash Redis credentials. "
                "Set UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN in environment."
            )

        _redis_client = Redis(url=redis_url, token=redis_token)

    return _redis_client
