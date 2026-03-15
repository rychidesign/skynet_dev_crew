from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class ScoringData:
    audit_id: str
    mentions: List[Dict[str, Any]]
    responses: List[Dict[str, Any]]
    competitors: List[Dict[str, Any]]
    technical_checks: Dict[str, Any]
    facts: Dict[str, Any]
    total_queries: int
    comparison_queries: int

@dataclass
class MetricScore:
    metric_id: str
    metric_category: str
    score: float
    components: Dict[str, Any] = field(default_factory=dict)
    weight: float = 0.0
    weighted_contribution: float = 0.0
    platform_scores: Dict[str, float] = field(default_factory=dict)
    evidence_summary: str = ""

@dataclass
class HallucinationFinding:
    response_id: str
    claim_text: str
    fact_field: str
    expected_value: str
    actual_value: str
    severity: str
    platform: str
