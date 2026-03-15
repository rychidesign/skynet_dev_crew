import httpx
import json
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from apps.api.core.config import settings
from apps.api.agents.competitor_mapper.models import LLMExtractionResult

LLM_MAX_RETRIES = 3
LLM_MAX_WAIT = 8
LLM_TIMEOUT = 30.0
COMPETITOR_LLM_MODEL = settings.OPENAI_MODEL_FAST or "gpt-4o-mini"

log = structlog.get_logger(__name__)

@retry(
    stop=stop_after_attempt(LLM_MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=LLM_MAX_WAIT),
    retry=retry_if_exception_type(httpx.RequestError),
    reraise=True,
)
async def _call_llm(client: httpx.AsyncClient, system_prompt: str, user_prompt: str, log_ctx: structlog.BoundLogger) -> str:
    """
    Calls the LLM with retry logic.
    """
    response = await client.post(
        f"{settings.OPENAI_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": COMPETITOR_LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
        },
        timeout=LLM_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

async def extract_competitor_data_with_llm(
    system_prompt: str,
    user_prompt: str,
    log_ctx: structlog.BoundLogger,
) -> LLMExtractionResult:
    """
    Uses LLM to extract competitor and brand mention data from a response.
    """
    async with httpx.AsyncClient() as client:
        try:
            llm_response_content = await _call_llm(
                client, system_prompt, user_prompt, log_ctx
            )
            log_ctx.debug(
                "LLM extraction raw response", llm_response=llm_response_content
            )
            return LLMExtractionResult.model_validate_json(llm_response_content)
        except httpx.HTTPStatusError as e:
            log_ctx.error(
                "LLM API returned an error status",
                status_code=e.response.status_code,
                response_text=e.response.text,
                error=str(e),
            )
            raise
        except httpx.RequestError as e:
            log_ctx.error("LLM API request failed", error=str(e))
            raise
        except json.JSONDecodeError as e:
            log_ctx.error(
                "Failed to parse LLM response as JSON",
                raw_response=llm_response_content,
                error=str(e),
            )
            raise
        except Exception as e:
            log_ctx.error("Unexpected error during LLM call", error=str(e))
            raise
