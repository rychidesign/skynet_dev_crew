"""Response Collector Agent - collects AI responses for all queries and platforms."""
from typing import List, Dict, Tuple
import hashlib
import json
import asyncio
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import structlog
from datetime import datetime, timedelta
from dataclasses import dataclass

from apps.api.core.state import AuditState, AgentMessage
from apps.api.core.rate_limiter import rate_limiter
from apps.api.core.cost_tracker import calculate_cost
from apps.api.core.redis_client import get_redis_client
from apps.api.core.config import settings
from apps.api.core.dependencies import get_service_db
from apps.api.models.audit import AiPlatform, AuditStatus, ProgressUpdate, AuditQuery, AuditResponse
from apps.api.agents.platform_adapters import get_adapter, PlatformAdapterResult, RateLimitError

log = structlog.get_logger()

@dataclass
class CollectedResponse:
    audit_id: str; query_id: str; platform: str; model_id: str; response_text: str
    citations: List[Dict]; rag_sources: List[Dict]; input_tokens: int; output_tokens: int
    cost_usd: float; latency_ms: int; served_from_cache: bool; cache_key: str; idempotency_key: str

AGENT_NAME = "response_collector"
BATCH_SIZE = 50

def _make_cache_key(query_text: str, platform: str, model_id: str) -> str:
    return hashlib.sha256(f"{query_text}:{platform}:{model_id}".encode()).hexdigest()

def _make_idempotency_key(audit_id: str, query_id: str, platform: str, model_id: str) -> str:
    return hashlib.sha256(f"{audit_id}:{query_id}:{platform}:{model_id}".encode()).hexdigest()

def _get_model_for_platform(platform: AiPlatform) -> str:
    if platform == AiPlatform.chatgpt: return getattr(settings, 'OPENAI_MODEL', 'gpt-4o')
    if platform == AiPlatform.claude: return getattr(settings, 'ANTHROPIC_MODEL', 'claude-3-5-sonnet-20240620')
    if platform == AiPlatform.perplexity: return getattr(settings, 'PERPLEXITY_MODEL', 'perplexity-sonar')
    return "unknown_model"

async def _collect_single_response_item(audit_id: str, company_id: str, company_name: str, company_domain: str,
                                         audit_query: AuditQuery, platform: AiPlatform, cache_ttl_hours: int) -> CollectedResponse:
    """Collects a single response for a given query and platform, utilizing Redis cache."""
    redis = get_redis_client()
    adapter = get_adapter(platform.value)
    model_id_for_cache = _get_model_for_platform(platform)
    cache_key = _make_cache_key(audit_query.query_text, platform.value, model_id_for_cache)
    
    cached_result_json = await redis.get(cache_key)
    if cached_result_json:
        log.info("Cache hit", cache_key=cache_key, audit_id=audit_id, platform=platform.value)
        cached_data = json.loads(cached_result_json)
        return CollectedResponse(audit_id=audit_id, query_id=audit_query.id, platform=platform.value,
            served_from_cache=True, idempotency_key=_make_idempotency_key(audit_id, audit_query.id, platform.value, cached_data.get('model_id', model_id_for_cache)), **cached_data)

    log.info("Cache miss, calling LLM", cache_key=cache_key, audit_id=audit_id, platform=platform.value)
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8),
           retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException, httpx.RequestError, RateLimitError)), reraise=True)
    async def call_adapter_with_retry():
        async with rate_limiter.acquire(platform.value):
            return await adapter.call(audit_query.query_text, company_name, company_domain)

    try:
        adapter_response = await call_adapter_with_retry()
        cost_usd = calculate_cost(adapter_response.model_id, adapter_response.input_tokens, adapter_response.output_tokens)
        idempotency_key = _make_idempotency_key(audit_id, audit_query.id, platform.value, adapter_response.model_id)
        
        collected_response = CollectedResponse(query_id=audit_query.id, audit_id=audit_id, platform=platform.value,
            model_id=adapter_response.model_id, response_text=adapter_response.response_text,
            citations=[c.model_dump() for c in adapter_response.citations], rag_sources=[rs.model_dump() for rs in adapter_response.rag_sources],
            input_tokens=adapter_response.input_tokens, output_tokens=adapter_response.output_tokens,
            cost_usd=cost_usd, latency_ms=adapter_response.latency_ms, served_from_cache=False,
            cache_key=_make_cache_key(audit_query.query_text, platform.value, adapter_response.model_id), idempotency_key=idempotency_key)
        
        cache_content = {k: v for k, v in collected_response.__dict__.items() if k not in ['audit_id', 'query_id', 'platform', 'served_from_cache', 'idempotency_key', 'cache_key']}
        await redis.setex(cache_key, timedelta(hours=cache_ttl_hours), json.dumps(cache_content))
        return collected_response

    except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException, RateLimitError) as e:
        log.error("Platform API error", audit_id=audit_id, platform=platform.value, error=str(e))
        return CollectedResponse(query_id=audit_query.id, audit_id=audit_id, platform=platform.value,
            model_id=model_id_for_cache, response_text=f"Error: {e}", citations=[], rag_sources=[],
            input_tokens=0, output_tokens=0, cost_usd=0.0, latency_ms=0, served_from_cache=False,
            cache_key=_make_cache_key(audit_query.query_text, platform.value, model_id_for_cache),
            idempotency_key=_make_idempotency_key(audit_id, audit_query.id, platform.value, model_id_for_cache))

async def _batch_insert_responses(db, responses: List[CollectedResponse], audit_id: str,
                                    responses_collected_count: int, total_responses: int, redis_client):
    """Inserts a batch of collected responses into the database and publishes progress."""
    if not responses: return
    insert_data = [AuditResponse(audit_id=r.audit_id, query_id=r.query_id, platform=AiPlatform(r.platform),
        model_id=r.model_id, response_text=r.response_text, input_tokens=r.input_tokens, output_tokens=r.output_tokens,
        cost_usd=r.cost_usd, latency_ms=r.latency_ms, served_from_cache=r.served_from_cache, idempotency_key=r.idempotency_key,
        citations=r.citations, rag_sources=r.rag_sources, created_at=datetime.utcnow()).model_dump(exclude_unset=True) for r in responses]

    await db.from_("audit_responses").upsert(insert_data, on_conflict="idempotency_key", ignore_duplicates=True).execute()
    log.info("Batch inserted audit responses", audit_id=audit_id, count=len(responses))

    progress = responses_collected_count / total_responses if total_responses > 0 else 1.0
    progress_update = ProgressUpdate(status=AuditStatus.collecting, progress=round(progress, 2), current_agent=AGENT_NAME,
        message=f"Collected {responses_collected_count}/{total_responses} responses",
        responses_collected=responses_collected_count, total_responses=total_responses)
    await redis_client.set(f"audit:{audit_id}:progress", progress_update.model_dump_json(), ex=86400)

async def run(state: AuditState) -> AuditState:
    """LangGraph node: Collects AI responses for all queries and platforms."""
    audit_id = state.audit_id; company_id = state.company_id
    platforms = state.config.get("platforms", []); cache_ttl_hours = state.config.get("cache_ttl_hours", 24)

    log.info("Response Collector started", audit_id=audit_id, platforms=platforms)
    state.status = "collecting"
    state.messages.append(AgentMessage(agent=AGENT_NAME, content="Starting AI response collection...", metadata={"type": "info"}))

    db = await get_service_db(); redis = get_redis_client()
    company_response = await db.from_('companies').select('name, domain').eq('id', company_id).single().execute()
    company_name = company_response.data['name']; company_domain = company_response.data.get('domain', '').lower()

    query_response = await db.from_('audit_queries').select('*').eq('audit_id', audit_id).order('query_index').execute()
    audit_queries = [AuditQuery(**q) for q in query_response.data]
    log.info("Loaded audit queries", audit_id=audit_id, count=len(audit_queries))

    work_items = [(query, AiPlatform(platform_str)) for query in audit_queries for platform_str in platforms]
    total_responses = len(work_items); responses_processed_count = 0

    initial_progress = ProgressUpdate(status=AuditStatus.collecting, progress=0.0, current_agent=AGENT_NAME,
        message="Starting response collection", responses_collected=0, total_responses=total_responses)
    await redis.set(f"audit:{audit_id}:progress", initial_progress.model_dump_json(), ex=86400)

    tasks = []; collected_responses_buffer = []
    for i, (query, platform) in enumerate(work_items):
        tasks.append(_collect_single_response_item(audit_id, company_id, company_name, company_domain, query, platform, cache_ttl_hours))
        if len(tasks) >= BATCH_SIZE or (i == total_responses - 1 and tasks):
            results = await asyncio.gather(*tasks, return_exceptions=True); tasks = []
            for res in results:
                responses_processed_count += 1
                if isinstance(res, CollectedResponse): collected_responses_buffer.append(res)
                else: log.error("Failed to collect response", audit_id=audit_id, error=res)
            if collected_responses_buffer:
                await _batch_insert_responses(db, collected_responses_buffer, audit_id, responses_processed_count, total_responses, redis)
                collected_responses_buffer = []

    log.info("All responses collected and inserted", audit_id=audit_id)
    state.status = "analyzing"
    state.messages.append(AgentMessage(agent=AGENT_NAME, content="Finished collecting responses.", metadata={"type": "info"}))
    return state
