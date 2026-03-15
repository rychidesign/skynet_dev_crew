# FastAPI and Backend Rules

## App Structure
- Entry point: `main.py` creates FastAPI app, includes routers, sets up middleware
- Routers: one file per domain in `api/` (audits.py, companies.py, webhooks.py)
- Dependency injection: use `Depends()` for auth, DB sessions, plan checks

## Route Handlers
- Max 20 lines per handler — delegate logic to services
- Always use Pydantic models for request bodies and responses
- Return explicit status codes: 201 for creation, 200 for success, 403 for plan limits, 404 for not found
- Use `HTTPException` for error responses with structured detail

### Example Pattern
```python
@router.post("/audits/run", status_code=201)
async def trigger_audit(
    request: AuditRequest,
    user: AuthUser = Depends(get_current_user),
    db: AsyncClient = Depends(get_supabase),
):
    await enforce_plan_limits(db, user.organization_id, request.config)
    audit = await audit_service.create_and_run(db, request, user)
    return AuditResponse(id=audit.id, status=audit.status)
```

## Pydantic Models
- All models in `models/` directory, grouped by domain
- Use `Field()` with descriptions for API documentation
- Validate constraints: `Field(ge=0, le=100)` for scores, `Field(min_length=3)` for queries
- Enum fields use Python enums matching database enum types

## LangGraph Agents
- Each agent file exports a single async function: `async def run(state: AuditState) -> AuditState`
- Agents are pure state transformers — input state in, modified state out
- No direct HTTP endpoint calls from agents — only DB writes and LLM calls
- Use `state.messages` list for inter-agent communication (AgentMessage schema)

## Async Patterns
- All I/O operations must be async: DB queries, HTTP calls, Redis operations
- Use `httpx.AsyncClient` for AI platform API calls (not `requests`)
- Use `asyncio.gather()` for parallel operations (e.g., querying multiple platforms)
- Rate limiting: `asyncio.Semaphore` per platform (defined in core/rate_limiter.py)

## Error Handling
- Catch specific exceptions, not bare `Exception`
- Use `tenacity` for retry logic on AI API calls (max 3, exponential backoff)
- Log all errors with `structlog` including context (audit_id, platform, agent)
- On pipeline failure: update audit status to `failed`, log error event, publish to Redis

## Configuration
- All settings via environment variables, loaded in `core/config.py`
- Use Pydantic `BaseSettings` for typed config with validation
- Plan limits defined as constant dict in `core/config.py`
- Never hardcode API keys, URLs, or limits in agent code

## Logging
- Use `structlog` for all logging — structured JSON output
- Bind context per audit: `log = log.bind(audit_id=audit_id, agent="response_collector")`
- Log levels: DEBUG for detailed flow, INFO for stage transitions, WARNING for retries, ERROR for failures
