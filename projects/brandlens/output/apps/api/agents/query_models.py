"""
Dataclasses for the Query Generator agent.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass
class CompanyProfile:
    company_id: str
    name: str
    industry: Optional[str]
    description: Optional[str]
    competitors: List[str]
    core_topics: List[str]
    facts: Dict[str, Any]

@dataclass
class QuerySpec:
    query_text: str
    intent: str
    target_metrics: List[str]
    query_index: int
