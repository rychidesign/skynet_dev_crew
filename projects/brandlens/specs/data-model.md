# Data Model

## References
- Related: SPECS.md — project overview, plan limits
- Related: specs/security.md — RLS policies
- Related: specs/billing.md — subscriptions table, plan enforcement
- Related: specs/audit-pipeline.md — which agent writes to which table
- Source SQL: `001_schema.sql` (provided by user — use as primary reference for exact column types)

## Extensions
- `uuid-ossp` — UUID generation
- `pgcrypto` — cryptographic functions
- Future: `vector` (pgvector) — for V2 embeddings

## Enum Types

| Enum | Values |
|------|--------|
| `audit_status` | pending, preprocessing, generating, collecting, analyzing, synthesizing, completed, failed, cancelled |
| `ai_platform` | chatgpt, claude, perplexity, google_aio, copilot |
| `metric_category` | entity_semantic, citations_trust, content_technical, reputation_sentiment |
| `event_severity` | debug, info, warning, error, critical |
| `query_intent` | informational, comparative, navigational, recommendation, authority, factual |
| `mention_type` | primary, secondary, citation, comparison, recommendation, absent |
| `org_role` | owner, admin, analyst, viewer |

## Tables

### organizations
Multi-tenant root entity.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | uuid_generate_v4() |
| name | TEXT NOT NULL | |
| slug | TEXT UNIQUE NOT NULL | URL-friendly identifier |
| plan | TEXT NOT NULL DEFAULT 'free' | CHECK: free, pro, enterprise |
| settings | JSONB DEFAULT '{}' | Org-level settings |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | auto-trigger |

### organization_members
Join table: Supabase Auth users ↔ organizations.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → organizations | CASCADE |
| user_id | UUID | Supabase auth.uid() |
| role | org_role DEFAULT 'viewer' | |
| invited_at | TIMESTAMPTZ | |
| accepted_at | TIMESTAMPTZ | NULL until accepted |
| UNIQUE | (organization_id, user_id) | |

### companies
Brands being audited. Belong to an organization.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → organizations | CASCADE |
| name | TEXT NOT NULL | Brand name |
| domain | TEXT | e.g. "example.com" |
| industry | TEXT | |
| description | TEXT | |
| facts | JSONB DEFAULT '{}' | Ground truth for hallucination detection (GEO-16) |
| competitors | TEXT[] DEFAULT '{}' | Tracked competitor names/domains |
| core_topics | TEXT[] DEFAULT '{}' | For topical authority queries |
| created_at, updated_at | TIMESTAMPTZ | |

### subscriptions (NEW — not in original schema)
Paddle-synced subscription state. See specs/billing.md for details.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → organizations | UNIQUE, CASCADE |
| paddle_subscription_id | TEXT UNIQUE | Paddle's subscription ID |
| paddle_customer_id | TEXT | |
| status | TEXT NOT NULL | active, past_due, cancelled, trialing, paused |
| plan | TEXT NOT NULL | free, pro, enterprise |
| current_period_start | TIMESTAMPTZ | |
| current_period_end | TIMESTAMPTZ | |
| cancel_at | TIMESTAMPTZ | NULL unless scheduled cancellation |
| created_at, updated_at | TIMESTAMPTZ | |

### usage_tracking (NEW)
Monthly usage counters for plan limit enforcement.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → organizations | CASCADE |
| period_start | DATE NOT NULL | 1st of month |
| audits_used | INTEGER DEFAULT 0 | Incremented per audit trigger |
| UNIQUE | (organization_id, period_start) | |

### audits
Top-level audit run record.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| organization_id | UUID FK → organizations | CASCADE |
| company_id | UUID FK → companies | CASCADE |
| triggered_by | UUID | auth.uid() |
| status | audit_status DEFAULT 'pending' | FSM — see pipeline spec |
| config | JSONB DEFAULT '{}' | {query_count, platforms[], cache_ttl_hours} |
| started_at, completed_at | TIMESTAMPTZ | |
| duration_ms | INTEGER | |
| total_input_tokens | INTEGER DEFAULT 0 | |
| total_output_tokens | INTEGER DEFAULT 0 | |
| total_cost_usd | NUMERIC(10,6) DEFAULT 0 | |
| global_geo_score | NUMERIC(5,2) | Populated by Agent 5 |
| score_breakdown | JSONB | Full AuditResult object |
| error_message | TEXT | |
| created_at, updated_at | TIMESTAMPTZ | |

### audit_queries (Agent 1 output)

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| audit_id | UUID FK → audits | CASCADE |
| query_text | TEXT NOT NULL | |
| intent | query_intent | |
| target_metrics | TEXT[] DEFAULT '{}' | e.g. ["GEO-01-ENT-SAL"] |
| query_index | SMALLINT NOT NULL | Sequential ordering |
| created_at | TIMESTAMPTZ | |
| UNIQUE | (audit_id, query_index) | |

### audit_responses (Agent 2 output)

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| audit_id | UUID FK → audits | CASCADE |
| query_id | UUID FK → audit_queries | CASCADE |
| platform | ai_platform | |
| model_id | TEXT | e.g. "gpt-4o" |
| response_text | TEXT NOT NULL | |
| citations | JSONB DEFAULT '[]' | [{url, domain, title, type, is_brand_citation}] |
| rag_sources | JSONB DEFAULT '[]' | [{url, domain, title, snippet, is_brand_source}] |
| input_tokens, output_tokens | INTEGER | |
| cost_usd | NUMERIC(10,6) | |
| latency_ms | INTEGER | |
| served_from_cache | BOOLEAN DEFAULT FALSE | |
| cache_key | TEXT | |
| idempotency_key | TEXT UNIQUE NOT NULL | sha256(audit_id+query_id+platform+model_id) |
| created_at | TIMESTAMPTZ | |

### audit_mentions (Agent 3 output)

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| audit_id | UUID FK → audits | CASCADE |
| response_id | UUID FK → audit_responses | CASCADE |
| entity_name | TEXT NOT NULL | |
| mention_type | mention_type | |
| position_rank | SMALLINT | 1 = first mentioned |
| sentiment_score | NUMERIC(4,3) | Range: -1.0 to 1.0 |
| sentiment_label | TEXT | positive, negative, neutral |
| authority_markers | TEXT[] DEFAULT '{}' | ["leading", "expert", "trusted"] |
| is_authority_cite | BOOLEAN DEFAULT FALSE | |
| extracted_attributes | JSONB DEFAULT '{}' | NER output |
| is_confused | BOOLEAN DEFAULT FALSE | Disambiguation issue |
| confusion_note | TEXT | |
| created_at | TIMESTAMPTZ | |

### audit_competitors (Agent 4 output)

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| audit_id | UUID FK → audits | CASCADE |
| competitor_name | TEXT NOT NULL | |
| competitor_domain | TEXT | |
| avg_mention_position | NUMERIC(4,2) | |
| recommendation_count | INTEGER DEFAULT 0 | |
| total_appearances | INTEGER DEFAULT 0 | |
| positive/negative/neutral_comparisons | INTEGER DEFAULT 0 | |
| platform_breakdown | JSONB DEFAULT '{}' | Per-platform stats |
| created_at | TIMESTAMPTZ | |

### audit_metric_scores (Agent 5 output)

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| audit_id | UUID FK → audits | CASCADE |
| metric_id | TEXT NOT NULL | e.g. "GEO-01-ENT-SAL" |
| metric_category | metric_category | |
| score | NUMERIC(5,2) | 0–100 |
| components | JSONB DEFAULT '{}' | Sub-component breakdown |
| weight | NUMERIC(4,3) | |
| weighted_contribution | NUMERIC(5,2) | |
| platform_scores | JSONB DEFAULT '{}' | Per-platform breakdown |
| evidence_summary | TEXT | |
| created_at | TIMESTAMPTZ | |
| UNIQUE | (audit_id, metric_id) | |

### audit_recommendations (Agent 5 output)

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| audit_id | UUID FK → audits | CASCADE |
| priority | TEXT CHECK (P0–P3) | |
| target_metric | TEXT | e.g. "GEO-01-ENT-SAL" |
| title | TEXT NOT NULL | |
| description | TEXT NOT NULL | |
| action_items | JSONB DEFAULT '[]' | [{step, action, effort}] |
| estimated_impact | TEXT | |
| effort_level | TEXT | low, medium, high |
| created_at | TIMESTAMPTZ | |

### audit_hallucinations (Agent 5 output)

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| audit_id | UUID FK → audits | CASCADE |
| response_id | UUID FK → audit_responses | CASCADE |
| claim_text | TEXT NOT NULL | |
| fact_field | TEXT NOT NULL | e.g. "founding_date" |
| expected_value, actual_value | TEXT | |
| severity | TEXT CHECK (critical, major, minor) | |
| platform | ai_platform | |
| created_at | TIMESTAMPTZ | |

### audit_technical_checks (Preprocessor output)

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| audit_id | UUID FK → audits | UNIQUE, CASCADE |
| robots_txt_raw | TEXT | |
| crawler_permissions | JSONB DEFAULT '{}' | {GPTBot: "allowed", ...} |
| sitemap_present, sitemap_valid | BOOLEAN | |
| sitemap_url_count | INTEGER | |
| sampled_pages | JSONB DEFAULT '[]' | [{url, status, ok}] |
| avg_lastmod_days | NUMERIC(8,2) | |
| update_frequency_monthly | NUMERIC(6,2) | |
| current_year_content_pct | NUMERIC(5,2) | |
| sitemap_sample | JSONB DEFAULT '[]' | |
| created_at | TIMESTAMPTZ | |

### audit_events (Observability log)

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| audit_id | UUID FK → audits | CASCADE |
| agent | TEXT NOT NULL | preprocessor, query_generator, etc. |
| event_type | TEXT NOT NULL | started, progress, completed, error, etc. |
| severity | event_severity DEFAULT 'info' | |
| message | TEXT NOT NULL | |
| metadata | JSONB DEFAULT '{}' | {platform, tokens_in, cost_usd, ...} |
| progress | NUMERIC(4,3) | 0.0–1.0 |
| created_at | TIMESTAMPTZ | |

### metric_time_series (Denormalized trend snapshots)

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| company_id | UUID FK → companies | CASCADE |
| audit_id | UUID FK → audits | UNIQUE |
| snapshot_date | DATE | |
| global_geo_score | NUMERIC(5,2) | |
| ent_sal_score ... hal_rsk_score | NUMERIC(5,2) | 10 flat metric columns |
| category_entity_semantic ... | NUMERIC(5,2) | 4 category averages |
| platform_scores | JSONB DEFAULT '{}' | |
| created_at | TIMESTAMPTZ | |

## Key Indexes
- `idx_audits_company_created` — dashboard: latest audits per company
- `idx_timeseries_company_date` — trend charts
- `idx_metric_scores_trend` — metric evolution over time
- `idx_audit_events_audit_time` — event log queries
- `idx_audit_events_severity` — partial index for error/critical only
- `idx_audit_responses_cache` — cache lookups (where served_from_cache=FALSE)

## Triggers
- `update_updated_at()` — auto-set updated_at on organizations, companies, audits
- `populate_time_series()` — auto-insert into metric_time_series when audit status → completed

## Notes
- Full DDL in `001_schema.sql` — agents should reference it for exact types
- RLS policies defined in specs/security.md
- Subscriptions + usage_tracking are new tables not in original schema
