import asyncio
import time
from contextlib import asynccontextmanager
import structlog
from core.redis_client import get_redis_client

logger = structlog.get_logger(__name__)

# Max parallel concurrent requests to an AI platform per worker instance
PLATFORM_CONCURRENCY_LIMITS = {
    "chatgpt": 10,
    "claude": 5,
    "perplexity": 3,
    "google_aio": 5,
    "copilot": 5
}

# Max Requests Per Minute across ALL distributed workers
PLATFORM_RPM_LIMITS = {
    "chatgpt": 500,
    "claude": 50,
    "perplexity": 50,
    "google_aio": 60,
    "copilot": 60
}

class PlatformRateLimiter:
    """
    Combines local asyncio.Semaphore (for concurrency limiting) with 
    distributed Redis-backed Fixed Window counter (for RPM limiting).
    """
    
    def __init__(self):
        # Maps platform names to their respective asyncio.Semaphore
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        
    def _get_semaphore(self, platform: str) -> asyncio.Semaphore:
        """
        Lazily initializes the asyncio Semaphore. 
        MUST be called within an active async event loop.
        """
        if platform not in self._semaphores:
            limit = PLATFORM_CONCURRENCY_LIMITS.get(platform, 3)
            self._semaphores[platform] = asyncio.Semaphore(limit)
        return self._semaphores[platform]
        
    async def _wait_for_capacity(self, platform: str) -> None:
        """
        Enforces distributed rate limiting using Redis.
        Sleeps if the RPM limit is exceeded for the current minute window.
        """
        redis = get_redis_client()
        rpm_limit = PLATFORM_RPM_LIMITS.get(platform, 50)
        
        while True:
            # Generate the key based on the current minute block
            current_minute = int(time.time() // 60)
            key = f"ratelimit:{platform}:{current_minute}"
            
            # Atomically increment counter and optionally set expiry
            # Upstash pipeline executes commands atomically
            pipeline = redis.pipeline()
            pipeline.incr(key)
            pipeline.expire(key, 60) # Expire the key after 60 seconds
            
            # Execute pipeline
            results = await pipeline.exec()
            
            # results[0] is the result of INCR
            current_usage = results[0]
            
            if current_usage <= rpm_limit:
                # Capacity available
                break
                
            # Capacity exceeded. Wait until the next minute starts
            now = time.time()
            next_minute_start = (current_minute + 1) * 60
            sleep_time = next_minute_start - now + 0.1 # Small buffer
            
            logger.warning(
                "Rate limit exceeded, sleeping", 
                platform=platform, 
                current_usage=current_usage, 
                rpm_limit=rpm_limit, 
                sleep_seconds=round(sleep_time, 2)
            )
            
            await asyncio.sleep(sleep_time)

    @asynccontextmanager
    async def acquire(self, platform: str):
        """
        Context manager to acquire capacity to call an external API.
        1. Waits for a slot in the local concurrency semaphore.
        2. Checks global RPM capacity via Redis.
        """
        semaphore = self._get_semaphore(platform)
        
        # 1. Acquire local concurrency slot
        async with semaphore:
            # 2. Verify global distributed capacity
            await self._wait_for_capacity(platform)
            # 3. Yield back to the block doing the actual request
            yield
            
# Create a singleton instance for global use across the backend
rate_limiter = PlatformRateLimiter()
