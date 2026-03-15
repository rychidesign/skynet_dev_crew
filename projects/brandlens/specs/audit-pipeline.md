# Audit Pipeline

## References
- Related: specs/data-model.md — all audit_* tables
- Related: specs/metrics.md — metric formulas used by Agent 5
- Related: specs/security.md — plan enforcement before trigger
- Related: specs/billing.md — usage metering on audit trigger
- Source: pipeline-documentation.md (user-provided — detailed data flow reference)
- Source: data-contracts.schema.json (user-provided — JSON schemas for all contracts)

## Pipeline Overview

7 stages, total runtime 2–5 minutes per audit:

```
Trigger → Preprocess → Agent 1 (Query Gen) → Agent 2 (Response Collector)
  → Agent 3 (Mention Analyzer) ─┐
  → Agent 4 (Competitor Mapper) ─┤ PARALLEL
  → Agent 5 (Synthesizer) → Archive + Dashboard
```

Orchestrated by LangGraph StateGraph on Railway (FastAPI). No timeout limits.

## Status FSM

```
pending → preprocessing → generating → collecting → analyzing → synthesizing → completed
  │                                                                              │
  └─── failed ◄──────────────────────(any stage can fail)────────────────────────┘
  │
  └─── cancelled
```

Terminal states: completed, cancelled. Only `failed → pending` allows re-run.

## Stage Details

### Stage 0: Trigger
- Source: Frontend POST /api/audits → Backend POST /audits/run
- Contract: `AuditRequest` (see data-contracts.schema.json)
- Actions: validate plan limits, increment usage_tracking, create audits row (status=pending), publish ProgressUpdate to Redis, start LangGraph pipeline
- Idempotency: client-generated idempotency_key, reject duplicates within 5min

### Stage 1: Preprocessor
- Input: company domain
- Output: `audit_technical_checks` table
- Feeds: GEO-17 (Crawl Accessibility), GEO-11 (Freshness)
- Duration: 5–15s
- Actions: fetch robots.txt → parse crawler permissions, fetch sitemap.xml → validate + extract lastmod dates, sample 10 URLs for HTTP status
- Skip if domain is NULL (set GEO-17/GEO-11 scores to NULL)

### Stage 2: Agent 1 — Query Generator
- Input: company profile (name, industry, core_topics, competitors) + config.query_count
- Output: `audit_queries` table
- Duration: 10–30s
- Distribution: min 15% informational, 15% comparative, 10% recommendation, 10% authority, 10% factual. Every metric must have >= 3 targeted queries. Brand name in max 60% of queries.
- Idempotency: DELETE + re-INSERT for audit_id

### Stage 3: Agent 2 — Response Collector
- Input: audit_queries + config.platforms
- Output: `audit_responses` table
- Duration: 60–180s (dominant stage)
- Concurrency: per-platform semaphores (chatgpt:10, claude:5, perplexity:3, google_aio:5)
- Cache: check Upstash Redis by cache_key (sha256 of query+platform+model). TTL from config.cache_ttl_hours.
- Retry: max 3 retries, exponential backoff (2s, 4s, 8s). On 429: wait Retry-After header (max 60s).
- Idempotency: UNIQUE idempotency_key, ON CONFLICT DO NOTHING
- Cost logging: each call logs tokens + cost to audit_events

### Stage 4a: Agent 3 — Mention Analyzer (PARALLEL)
- Input: audit_responses
- Output: `audit_mentions` table
- Feeds: GEO-01, GEO-04, GEO-05, GEO-13
- Duration: 20–60s
- Extracts per response: entity mentions + position, sentiment, authority markers, NER attributes, disambiguation issues
- Each response must produce >= 1 mention (even if mention_type=absent)

### Stage 4b: Agent 4 — Competitor Mapper (PARALLEL)
- Input: audit_responses + companies.competitors
- Output: `audit_competitors` table
- Feeds: GEO-14
- Duration: 15–45s
- Filters responses with comparative/recommendation intent
- Per competitor: avg position, recommendation count, comparative language, per-platform breakdown
- Idempotency: UPSERT on (audit_id, competitor_name)

### Stage 5: Agent 5 — Synthesizer
- Input: all prior outputs + companies.facts (ground truth)
- Output: audit_metric_scores, audit_recommendations, audit_hallucinations, audits (final update)
- Duration: 30–90s
- Steps: (1) hallucination check vs facts, (2) compute all 10 metric scores, (3) weighted Global GEO Score, (4) generate recommendations per low-scoring metric, (5) UPDATE audits with final scores + status=completed
- DB trigger auto-populates metric_time_series on completion

### Stage 6: Post-Pipeline
- Archive: serialize full audit to JSON, upload to R2 (`/audits/{id}/...`)
- Redis cleanup: progress keys auto-expire (TTL 1h)
- Dashboard queries from: metric_time_series (trends), audit_metric_scores (detail), audit_recommendations (actions)

## Real-Time Progress (SSE)

- Backend writes `ProgressUpdate` to Redis key `audit:{id}:progress` after each stage transition.
- Frontend SSE endpoint reads Redis key, streams updates to browser.
- Contract: `ProgressUpdate` from data-contracts.schema.json
- Fields: status, progress (0.0–1.0), current_agent, message, queries_generated, responses_collected/total, mentions_analyzed

## Batch Write Optimization
- audit_responses: batch INSERT 50 rows per statement
- audit_mentions: batch INSERT after Agent 3 completes
- audit_events: async fire-and-forget writes
- Cost aggregation: single UPDATE on audits at pipeline end
