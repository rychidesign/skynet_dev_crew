"""Constants for GEO metric scoring."""

METRIC_WEIGHTS = {
    "GEO-01-ENT-SAL": 0.15,
    "GEO-03-ENT-CON": 0.08,
    "GEO-04-TOP-AUTH": 0.10,
    "GEO-05-CIT-FRQ": 0.15,
    "GEO-07-RAG-INC": 0.12,
    "GEO-11-FRS-REC": 0.06,
    "GEO-17-CRW-ACC": 0.06,
    "GEO-13-SNT-POL": 0.10,
    "GEO-14-CMP-PST": 0.10,
    "GEO-16-HAL-RSK": 0.08,
}

METRIC_CATEGORIES = {
    "GEO-01-ENT-SAL": "entity_semantic",
    "GEO-03-ENT-CON": "entity_semantic",
    "GEO-04-TOP-AUTH": "entity_semantic",
    "GEO-05-CIT-FRQ": "citations_trust",
    "GEO-07-RAG-INC": "citations_trust",
    "GEO-11-FRS-REC": "content_technical",
    "GEO-17-CRW-ACC": "content_technical",
    "GEO-13-SNT-POL": "reputation_sentiment",
    "GEO-14-CMP-PST": "reputation_sentiment",
    "GEO-16-HAL-RSK": "reputation_sentiment",
}

CATEGORY_WEIGHTS = {
    "entity_semantic": 0.33,
    "citations_trust": 0.27,
    "content_technical": 0.12,
    "reputation_sentiment": 0.28,
}

CATEGORY_METRICS = {
    "entity_semantic": ["GEO-01-ENT-SAL", "GEO-03-ENT-CON", "GEO-04-TOP-AUTH"],
    "citations_trust": ["GEO-05-CIT-FRQ", "GEO-07-RAG-INC"],
    "content_technical": ["GEO-11-FRS-REC", "GEO-17-CRW-ACC"],
    "reputation_sentiment": ["GEO-13-SNT-POL", "GEO-14-CMP-PST", "GEO-16-HAL-RSK"],
}

AI_CRAWLERS = ["GPTBot", "ClaudeBot", "Bingbot", "Googlebot"]

SEVERITY_WEIGHTS = {"critical": 2.0, "major": 1.0, "minor": 0.5}


def safe_div(num: float, denom: float, default: float = 0.0) -> float:
    """Safe division returning default on zero denominator."""
    return num / denom if denom != 0 else default


def clamp(val: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Clamp value to [min_val, max_val] range."""
    return max(min_val, min(max_val, val))
