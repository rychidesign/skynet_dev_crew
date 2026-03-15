"""Competitor Mapper LLM operations — prompt building and LLM calls."""
from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from .competitor_mapper_helpers import (
    CompetitorMention,
    ResponseRow,
    build_analysis_prompt,
    parse_llm_output,
    LLM_TIMEOUT_SECONDS,
    LLM_MAX_ATTEMPTS,
    LLM_WAIT_MIN_SECONDS,
    LLM_WAIT_MAX_SECONDS,
)


async def _call_llm_with_retry(
    http_client: httpx.AsyncClient,
    prompt_payload: str,
    log_ctx: Any
) -> str:
    """Call LLM API with tenacity retry."""
    from core.config import settings
    
    @retry(
        stop=stop_after_attempt(LLM_MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=LLM_WAIT_MIN_SECONDS, max=LLM_WAIT_MAX_SECONDS),
        reraise=True
    )
    async def _make_request() -> str:
        response = await http_client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            content=prompt_payload,
            timeout=LLM_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    
    return await _make_request()


async def analyze_response_for_competitors(
    response: ResponseRow,
    competitors: list[str],
    semaphore: asyncio.Semaphore,
    http_client: httpx.AsyncClient,
    log_ctx: Any
) -> list[CompetitorMention]:
    """
    Analyze a single response for competitor mentions using LLM.
    
    Acquires semaphore for concurrency control.
    Returns empty list on failure (keeps pipeline alive).
    """
    async with semaphore:
        if not competitors:
            return []
        
        try:
            prompt_payload = build_analysis_prompt(
                response_text=response.response_text,
                competitors=competitors,
                platform=response.platform
            )
            
            raw_output = await _call_llm_with_retry(http_client, prompt_payload, log_ctx)
            
            mentions = parse_llm_output(
                raw_json=raw_output,
                response_id=response.response_id,
                platform=response.platform,
                log_ctx=log_ctx
            )
            
            log_ctx.debug(
                "analyzed_response_for_competitors",
                response_id=response.response_id,
                mention_count=len(mentions)
            )
            return mentions
            
        except httpx.RequestError as exc:
            log_ctx.warning(
                "llm_request_failed",
                response_id=response.response_id,
                error=str(exc)
            )
            return []
        except httpx.HTTPStatusError as exc:
            log_ctx.warning(
                "llm_http_error",
                response_id=response.response_id,
                status_code=exc.response.status_code if hasattr(exc, 'response') else None,
                error=str(exc)
            )
            return []
        except Exception as exc:
            log_ctx.warning(
                "llm_analysis_failed",
                response_id=response.response_id,
                error_type=type(exc).__name__,
                error=str(exc)
            )
            return []
