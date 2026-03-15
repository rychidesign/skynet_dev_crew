import httpx
import asyncio
import structlog
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from .scoring.score_models import ResponseData, HallucinationFinding

log = structlog.get_logger(__name__)

async def detect(
    responses: List[ResponseData],
    company_facts: Dict[str, Any],
    company_name: str,
    audit_id: str,
    http_client: httpx.AsyncClient,
) -> List[HallucinationFinding]:
    """
    Cross-references claims extracted from AI responses against company ground truth.
    """
    semaphore = asyncio.Semaphore(5)
    findings = []
    
    tasks = [
        _process_single_response(r, company_facts, company_name, audit_id, http_client, semaphore)
        for r in responses
    ]
    
    results = await asyncio.gather(*tasks)
    for res in results:
        findings.extend(res)
        
    return findings

async def _process_single_response(
    response: ResponseData,
    facts: Dict[str, Any],
    company_name: str,
    audit_id: str,
    http_client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore
) -> List[HallucinationFinding]:
    async with semaphore:
        claims = await _extract_claims(response.response_text, company_name, facts, http_client)
        findings = []
        for claim in claims:
            finding = _compare_claim_to_fact(claim, facts, response, audit_id)
            if finding:
                findings.append(finding)
        return findings

async def _extract_claims(
    text: str, 
    company_name: str, 
    facts: Dict[str, Any], 
    http_client: httpx.AsyncClient
) -> List[Dict[str, Any]]:
    # Simulated LLM call to extract claims from response text
    # In reality, this would use an LLM to identify specific factual statements
    # about the company and map them to fields in 'facts'.
    return []

def _compare_claim_to_fact(
    claim: Dict[str, Any], 
    facts: Dict[str, Any],
    response: ResponseData,
    audit_id: str
) -> Optional[HallucinationFinding]:
    field = claim.get("fact_field")
    actual = claim.get("actual_value")
    expected = str(facts.get(field)) if field in facts else None
    
    if expected and actual and actual.lower() != expected.lower():
        return HallucinationFinding(
            response_id=response.id,
            audit_id=audit_id,
            claim_text=claim.get("claim_text", ""),
            fact_field=field,
            expected_value=expected,
            actual_value=actual,
            severity=_classify_severity(field, expected, actual),
            platform=response.platform
        )
    return None

def _classify_severity(field: str, expected: str, actual: str) -> str:
    critical_fields = ["founding_date", "legal_name", "ceo", "headquarters"]
    major_fields = ["products", "key_figures", "events"]
    
    if field in critical_fields:
        return "critical"
    if field in major_fields:
        return "major"
    return "minor"
