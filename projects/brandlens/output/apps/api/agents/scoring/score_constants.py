"""Constants for GEO metric scoring and category weighting."""

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

CATEGORY_WEIGHTS = {
    "entity_semantic": 0.33,
    "citations_trust": 0.27,
    "content_technical": 0.12,
    "reputation_sentiment": 0.28,
}

METRIC_TO_CATEGORY = {
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
