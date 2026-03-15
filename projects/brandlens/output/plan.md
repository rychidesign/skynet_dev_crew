Now I have all the information needed. Let me compile the detailed technical plan.

---

# Technical Plan: Task 5.8 — Synthesizer Agent (Agent 5) — Scoring

## Task Summary

Implement the scoring half of the Synthesizer agent (Agent 5 in the LangGraph pipeline). This agent is the **last computation stage**: it cross-references AI-generated mentions against `companies.facts` for hallucination detection, computes all 10 GEO metric scores using exact formulas from specs/metrics.md, applies category weights, computes the Global GEO Score, and persists results to `audit_hallucinations` and `audit_metric_scores`. The `audits` table final update happens in Task 5.9 (recommendations).

---

## Files to Create/Modify

### 1. `output/apps/api/agents/synthesizer.py`
**Purpose:** Main LangGraph node entry point. Orchestrates the two sub-steps: hallucination detection and score computation. Pure state transformer: `async def run(state: AuditState) -> AuditState`.

**Responsibilities:**
- Load required data from state (responses, mentions, competitors, technical checks, company facts)
- Call `hallucination_detector.detect(...)` → list of hallucination findings
- Batch-insert hallucinations into `audit_hallucinations`
- Call `score_calculator.compute_all_scores(...)` → dict of MetricScore objects
- Batch-insert metric scores into `audit_metric_scores`
- Compute Global GEO Score from metric scores
- Store `global_geo_score` and `score_breakdown` back into `state`
- Publish `ProgressUpdate` to Redis (stage: `synthesizing`, progress ~0.85)
- Log events to `audit_events`

**Max ~120 lines** (delegates to helper modules)

---

### 2. `output/apps/api/agents/score_calculator.py`
**Purpose:** Pure computation module — all 10 metric score formulas. No I/O, no DB calls. Takes structured data dicts as input, returns a dict of `MetricScore` objects.

**Responsibilities:**
- `compute_all_scores(data: ScoringData) -> dict[str, MetricScore]`
- One private function per metric: `_score_geo01`, `_score_geo03`, `_score_geo04`, `_score_geo05`, `_score_geo07`, `_score_geo11`, `_score_geo17`, `_score_geo13`, `_score_geo14`, `_score_geo16`
- `compute_global_geo_score(metric_scores: dict[str, MetricScore]) -> float`
- Category weight application using `CATEGORY_WEIGHTS` and `METRIC_WEIGHTS` constants

**Max ~180 lines** — split if needed.

---

### 3. `output/apps/api/agents/hallucination_detector.py`
**Purpose:** Standalone module for cross-referencing AI response mentions/claims against `companies.facts`.

**Responsibilities:**
- `detect(responses: list[dict], mentions: list[dict], facts: dict) -> list[HallucinationFinding]`
- Extract factual claims from response text (using LLM call or regex heuristics)
- Compare each extracted claim against corresponding `facts` field
- Assign severity: `critical` (key facts: founding_date, founder, HQ), `major` (products, revenue), `minor` (ancillary details)
- Apply severity weighting per spec: `critical x2`, `minor x0.5`
- Return list of `HallucinationFinding` dataclass instances

**Max ~150 lines**

---

### 4. `output/apps/api/agents/synthesizer_db.py`
**Purpose:** All DB write operations for the synthesizer. Keeps `synthesizer.py` thin.

**Responsibilities:**
- `insert_hallucinations(db: AsyncClient, audit_id: str, findings: list[HallucinationFinding]) -> None` — batch insert to `audit_hallucinations`
- `insert_metric_scores(db: AsyncClient, audit_id: str, scores: dict[str, MetricScore]) -> None` — batch insert to `audit_metric_scores`
- Uses `executemany`-style batch inserts (max 50 per statement per pipeline spec)
- Idempotent: `ON CONFLICT (audit_id, metric_id) DO UPDATE`

**Max ~80 lines**

---

## Data Structures / Interfaces (Python Dataclasses / Pydantic)

These are defined **within the files above** (or in `models/metrics.py` if already partially present from Task 1.6):

### `ScoringData` (input to score_calculator)
```python
@dataclass
class ScoringData:
    audit_id: str
    # From audit_mentions
    mentions: list[dict]          # rows from audit_mentions
    # From audit_responses  
    responses: list[dict]         # rows from audit_responses (with citations, rag_sources)
    # From audit_competitors
    competitors: list[dict]       # rows from audit_competitors
    # From audit_technical_checks
    technical_checks: dict        # single row from audit_technical_checks
    # From companies
    facts: dict                   # companies.facts JSONB
    # Derived
    total_queries: int
    comparison_queries: int       # count of responses with comparative intent
```

### `MetricScore` (output of score_calculator, input to DB writer)
```python
@dataclass
class MetricScore:
    metric_id: str                # e.g. "GEO-01-ENT-SAL"
    metric_category: str          # e.g. "entity_semantic"
    score: float                  # 0.0–100.0
    components: dict              # sub-component breakdown (TopMentionRate, etc.)
    weight: float                 # raw metric weight (e.g. 0.15)
    weighted_contribution: float  # category-normalized weight × score
    platform_scores: dict         # per-platform breakdown {platform: score}
    evidence_summary: str         # human-readable summary
```

### `HallucinationFinding` (output of hallucination_detector, input to DB writer)
```python
@dataclass
class HallucinationFinding:
    response_id: str
    claim_text: str
    fact_field: str               # e.g. "founding_date"
    expected_value: str
    actual_value: str
    severity: str                 # critical | major | minor
    platform: str                 # ai_platform enum value
```

---

## Metric Formulas Reference (for score_calculator.py)

### GEO-01-ENT-SAL (Entity Salience, weight=0.15)
```
Score = (0.4 × TopMentionRate + 0.35 × EntityRankPosition + 0.25 × DisambiguationClarity) × 100
TopMentionRate        = count(mentions where position_rank=1 AND entity_name=brand) / total_queries
EntityRankPosition    = 1 - (avg(position_rank where entity=brand) - 1) / max_rank
DisambiguationClarity = 1 - (count(is_confused=true) / count(total brand mentions))
```
- Sources: `audit_mentions` table
- `max_rank` = 10 (constant)

### GEO-03-ENT-CON (Entity Consistency, weight=0.08)
```
Score = (1 - InconsistencyRate) × 100
InconsistencyRate = conflicting_attributes / total_attributes_checked
```
- Attributes: name, founding_date, category, key_products, leadership, location
- Sources: cross-platform comparison of `extracted_attributes` in `audit_mentions`

### GEO-04-TOP-AUTH (Topical Authority, weight=0.10)
```
Score = (0.35 × AuthorityCiteRate + 0.35 × ExpertLanguageRate + 0.3 × ExclusiveInsightRate) × 100
AuthorityCiteRate       = count(is_authority_cite=true for brand) / total_brand_topic_mentions
ExpertLanguageRate      = count(authority_markers non-empty for brand) / total_brand_mentions
ExclusiveInsightRate    = unique_claims_attributed_only_to_brand / total_claims
```
- Sources: `audit_mentions.is_authority_cite`, `authority_markers`, `extracted_attributes`

### GEO-05-CIT-FRQ (Citation Frequency, weight=0.15)
```
Score = min(100, (TotalCitations / BenchmarkCitations) × 100)
TotalCitations = direct_urls + domain_mentions + author_attributions (from citations JSONB where is_brand_citation=true)
BenchmarkCitations = avg citations of top 3 competitors
```
- Sources: `audit_responses.citations`, `audit_mentions`
- Normalized per 100 queries

### GEO-07-RAG-INC (RAG Inclusion Rate, weight=0.12)
```
Score = (BrandRAGHits / TotalRAGResults) × 100 × RelevancyMultiplier
BrandRAGHits = count(rag_sources where is_brand_source=true)
TotalRAGResults = count(all rag_sources)
RelevancyMultiplier = avg(relevancy_score) clamped to (0, 1.2]
```
- Sources: `audit_responses.rag_sources` — only Perplexity responses (platform='perplexity')
- If no RAG data: score = NULL (or 0 with flag)

### GEO-11-FRS-REC (Freshness and Recency, weight=0.06)
```
Score = (0.4 × PublicationRecency + 0.3 × UpdateFrequency + 0.3 × TemporalRelevance) × 100
PublicationRecency   = avg(1 / avg_lastmod_days) normalized to [0,1]
UpdateFrequency      = update_frequency_monthly / benchmark_frequency (benchmark=4/month)
TemporalRelevance    = current_year_content_pct / 100
```
- Sources: `audit_technical_checks.avg_lastmod_days`, `update_frequency_monthly`, `current_year_content_pct`
- If technical_checks is NULL: score = NULL

### GEO-17-CRW-ACC (Crawl Accessibility, weight=0.06)
```
Score = (0.4 × CrawlPermission + 0.3 × SitemapPresence + 0.3 × BasicAccessibility) × 100
CrawlPermission    = allowed_crawlers / 4  (GPTBot, ClaudeBot, Bingbot, Googlebot)
SitemapPresence    = 1.0 if sitemap_valid, 0.5 if sitemap_present, 0.0 if neither
BasicAccessibility = count(sampled_pages where ok=true) / count(sampled_pages)
```
- Sources: `audit_technical_checks.crawler_permissions`, `sitemap_present`, `sitemap_valid`, `sampled_pages`

### GEO-13-SNT-POL (Sentiment Polarity, weight=0.10)
```
Score = ((AvgSentiment + 1) / 2) × 100
AvgSentiment = weighted_mean(sentiment_scores for brand mentions)
# Recent responses (last 20%) weighted 2×
```
- Sources: `audit_mentions.sentiment_score` where `entity_name=brand`

### GEO-14-CMP-PST (Competitive Position, weight=0.10)
```
Score = (0.4 × MentionOrder + 0.3 × RecommendationRate + 0.3 × ComparativeAdvantage) × 100
MentionOrder         = 1 - (avg_brand_position - 1) / num_competitors
RecommendationRate   = brand_recommendation_first / comparison_queries
ComparativeAdvantage = (positive_comparisons - negative_comparisons) / total_comparisons
```
- Sources: `audit_competitors` (brand row) + `audit_mentions`

### GEO-16-HAL-RSK (Hallucination Risk, weight=0.08)
```
Score = (1 - HallucinationRate) × 100
HallucinationRate = weighted_incorrect / total_claims
# Severity weights: critical=2, major=1, minor=0.5
```
- Sources: `HallucinationFinding` list from `hallucination_detector`

---

## Global GEO Score Computation

```python
CATEGORY_WEIGHTS = {
    "entity_semantic":       0.33,
    "citations_trust":       0.27,
    "content_technical":     0.12,
    "reputation_sentiment":  0.28,
}

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
```

**Global GEO Score formula (Python pseudocode):**
```python
def compute_global_geo_score(metric_scores: dict[str, MetricScore]) -> float:
    category_scores = defaultdict(list)
    for metric_id, ms in metric_scores.items():
        category = METRIC_TO_CATEGORY[metric_id]
        category_scores[category].append((ms.weight, ms.score))

    global_score = 0.0
    for category, weight_score_pairs in category_scores.items():
        total_weight = sum(w for w, _ in weight_score_pairs)
        normalized = sum((w / total_weight) * s for w, s in weight_score_pairs)
        global_score += CATEGORY_WEIGHTS[category] * normalized

    return round(global_score, 2)
```

---

## Dependencies Between Components

```
synthesizer.py
  ├── imports hallucination_detector.py  → detect()
  ├── imports score_calculator.py        → compute_all_scores(), compute_global_geo_score()
  ├── imports synthesizer_db.py          → insert_hallucinations(), insert_metric_scores()
  └── reads from AuditState (core/state.py)

score_calculator.py
  ├── imports constants from core/config.py or packages/shared (CATEGORY_WEIGHTS, METRIC_WEIGHTS)
  └── imports ScoringData, MetricScore dataclasses (defined inline or in models/metrics.py)

hallucination_detector.py
  ├── imports HallucinationFinding dataclass
  └── uses structlog

synthesizer_db.py
  ├── uses supabase AsyncClient (from core/dependencies.py)
  └── imports MetricScore, HallucinationFinding
```

**Upstream dependencies (already implemented by prior tasks):**
- `core/state.