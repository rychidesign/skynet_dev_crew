"""
Constants used by the Query Generator agent and its helper modules.
"""
from typing import Dict, List
from models.audit import QueryIntent

# --- Metric Mappings ---
INTENT_METRIC_MAP: Dict[str, List[str]] = {
    QueryIntent.INFORMATIONAL.value: ["GEO-01-ENT-SAL", "GEO-03-ENT-CON", "GEO-04-TOP-AUTH"],
    QueryIntent.COMPARATIVE.value:   ["GEO-14-CMP-PST", "GEO-01-ENT-SAL"],
    QueryIntent.RECOMMENDATION.value:["GEO-14-CMP-PST", "GEO-13-SNT-POL"],
    QueryIntent.AUTHORITY.value:     ["GEO-04-TOP-AUTH", "GEO-05-CIT-FRQ", "GEO-07-RAG-INC"],
    QueryIntent.FACTUAL.value:       ["GEO-16-HAL-RSK", "GEO-03-ENT-CON", "GEO-01-ENT-SAL"],
    QueryIntent.NAVIGATIONAL.value:  ["GEO-17-CRW-ACC", "GEO-11-FRS-REC", "GEO-01-ENT-SAL"],
}

VALID_METRIC_IDS: frozenset[str] = frozenset({
    "GEO-01-ENT-SAL", "GEO-03-ENT-CON", "GEO-04-TOP-AUTH",
    "GEO-05-CIT-FRQ", "GEO-07-RAG-INC", "GEO-11-FRS-REC",
    "GEO-17-CRW-ACC", "GEO-13-SNT-POL", "GEO-14-CMP-PST", "GEO-16-HAL-RSK",
})

# --- Query Distribution Ratios ---
INTENT_MIN_RATIOS: Dict[str, float] = {
    QueryIntent.INFORMATIONAL.value: 0.15,
    QueryIntent.COMPARATIVE.value:   0.15,
    QueryIntent.RECOMMENDATION.value:0.10,
    QueryIntent.AUTHORITY.value:     0.10,
    QueryIntent.FACTUAL.value:       0.10,
    # Navigational is the remainder
}

# --- LLM and Agent Configuration ---
LLM_MODEL = "gpt-4o"
LLM_TEMPERATURE = 0.7
MAX_BRAND_NAME_RATIO = 0.60
MIN_QUERIES_PER_METRIC = 3 # best-effort
REDIS_TTL_SECONDS = 3600
LLM_MAX_ATTEMPTS = 3
LLM_WAIT_MIN_SECONDS = 2.0
LLM_WAIT_MAX_SECONDS = 8.0
DESCRIPTION_MAX_CHARS: int = 500
