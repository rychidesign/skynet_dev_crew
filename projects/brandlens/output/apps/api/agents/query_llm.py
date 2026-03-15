"""LLM query generation for query generator agent."""
import json
from typing import Dict, List

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog

from core.config import settings
from models.audit import QueryIntent
from agents.query_prompts import build_system_prompt, build_user_prompt, CompanyProfile
from agents.query_validation import QuerySpec

logger = structlog.get_logger(__name__)

LLM_MODEL = "gpt-4o"
LLM_TEMPERATURE = 0.7

INTENT_METRIC_MAP: Dict[str, List[str]] = {
    QueryIntent.INFORMATIONAL.value: ["GEO-01-ENT-SAL", "GEO-03-ENT-CON", "GEO-04-TOP-AUTH"],
    QueryIntent.COMPARATIVE.value: ["GEO-14-CMP-PST", "GEO-01-ENT-SAL"],
    QueryIntent.RECOMMENDATION.value: ["GEO-14-CMP-PST", "GEO-13-SNT-POL"],
    QueryIntent.AUTHORITY.value: ["GEO-04-TOP-AUTH", "GEO-05-CIT-FRQ", "GEO-07-RAG-INC"],
    QueryIntent.FACTUAL.value: ["GEO-16-HAL-RSK", "GEO-03-ENT-CON", "GEO-01-ENT-SAL"],
    QueryIntent.NAVIGATIONAL.value: ["GEO-17-CRW-ACC", "GEO-11-FRS-REC", "GEO-01-ENT-SAL"],
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=8))
async def generate_queries_llm(
    profile: CompanyProfile, query_count: int, distribution: Dict[str, int]
) -> List[QuerySpec]:
    """Calls the LLM to generate queries based on company profile and distribution."""
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(profile, query_count, distribution)

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.OPENAI_API_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": LLM_TEMPERATURE,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        raw_output = response.json()["choices"][0]["message"]["content"]

        parsed_data = json.loads(raw_output)
        generated_queries_data = parsed_data.get("queries", [])

        queries: List[QuerySpec] = []
        for idx, item in enumerate(generated_queries_data):
            try:
                query_text = str(item["query_text"]).strip()
                intent = str(item["intent"]).strip()
                target_metrics = list(item["target_metrics"])

                if intent not in [i.value for i in QueryIntent]:
                    logger.warning(f"LLM generated invalid intent '{intent}', defaulting to informational.")
                    intent = QueryIntent.INFORMATIONAL.value

                valid_metrics = [m for m in target_metrics if m in INTENT_METRIC_MAP.get(intent, [])]
                if not valid_metrics:
                    logger.warning(f"LLM generated invalid or empty target_metrics for query '{query_text}', using default for intent.")
                    valid_metrics = INTENT_METRIC_MAP.get(intent, [])

                queries.append(
                    QuerySpec(
                        query_text=query_text,
                        intent=intent,
                        target_metrics=valid_metrics,
                        query_index=idx,
                    )
                )
            except (KeyError, TypeError) as e:
                logger.error(f"Failed to parse LLM generated query item: {item}. Error: {e}")
                continue

        return queries
