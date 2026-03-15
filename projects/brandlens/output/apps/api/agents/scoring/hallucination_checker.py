import asyncio
import json
from typing import List, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential
import httpx
import structlog
from .score_models import HallucinationFinding, ScoringContext
from ...core.config import settings

log = structlog.get_logger(__name__)

async def call_llm_fact_check(prompt: str) -> str:
    """Actual LLM call to OpenAI gpt-4o-mini for fact checking."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a factual accuracy auditor. Compare AI response against ground truth. Return JSON array of findings."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

class HallucinationChecker:
    def __init__(self, semaphore_limit: int = 5):
        self.semaphore = asyncio.Semaphore(semaphore_limit)

    async def detect(self, context: ScoringContext) -> List[HallucinationFinding]:
        tasks = [self._check_response(resp, context) for resp in context.responses]
        results = await asyncio.gather(*tasks)
        return [finding for sublist in results for finding in sublist]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _check_response(self, response: Dict[str, Any], context: ScoringContext) -> List[HallucinationFinding]:
        async with self.semaphore:
            prompt = f"Ground Truth Facts: {json.dumps(context.company_facts)}\nAI Response: {response['response_text']}"
            try:
                res_content = await call_llm_fact_check(prompt)
                data = json.loads(res_content)
                findings_raw = data.get("findings", [])
                
                findings = []
                for f in findings_raw:
                    findings.append(HallucinationFinding(
                        response_id=response.get("id"),
                        claim_text=f.get("claim"),
                        fact_field=f.get("field"),
                        expected_value=str(f.get("expected")),
                        actual_value=str(f.get("actual")),
                        severity=self._classify_severity(f.get("field")),
                        platform=response.get("platform")
                    ))
                return findings
            except Exception as e:
                log.error("hallucination_check_failed", response_id=response.get("id"), error=str(e))
                return []

    def _classify_severity(self, field: str) -> str:
        critical_fields = ["founding_date", "company_name", "category", "legal_name"]
        major_fields = ["products", "leadership", "headquarters", "key_features"]
        if field in critical_fields: return "critical"
        if field in major_fields: return "major"
        return "minor"

async def detect(context: ScoringContext) -> List[HallucinationFinding]:
    return await HallucinationChecker().detect(context)
