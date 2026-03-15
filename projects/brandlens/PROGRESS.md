# Implementation Progress

> **Instructions for AI Agents:**
> 1. Read `SPECS.md` first (project overview)
> 2. Find your current task below (marked ← CURRENT)
> 3. Read the spec files listed under your task
> 4. Read relevant rules files
> 5. Do ONLY your assigned task — nothing more
> 6. Run lint and tests (if configured)
> 7. DO NOT modify PROGRESS.md — Supervisor handles this automatically
> 8. End session

---

## Phase 1: Project Setup and Foundation

- [x] **Task 1.1: Initialize monorepo and frontend scaffold**
  - Set up Turborepo with apps/web and packages/shared directories
  - Initialize Next.js 15 (App Router) with TypeScript in apps/web
  - Install and configure: Tailwind CSS, shadcn/ui (slate theme), Lucide React, Recharts
  - Configure path aliases (@/ for apps/web), ESLint, tsconfig strict mode
  - Create turbo.json with build/dev/lint pipelines
  - Spec: SPECS.md
  - Files: output/package.json, output/turbo.json, output/apps/web/package.json, output/apps/web/tsconfig.json, output/apps/web/tailwind.config.ts, output/apps/web/next.config.ts, output/apps/web/app/layout.tsx, output/apps/web/app/globals.css

- [x] **Task 1.2: Configure PWA and Vercel deployment**
  - Install and configure Serwist for PWA support
  - Create manifest.json with BrandLens branding (blue theme, no icons yet)
  - Create service worker configuration for offline caching
  - Add Vercel configuration (vercel.json if needed)
  - Spec: SPECS.md, specs/dashboard-ui.md
  - Files: output/apps/web/app/manifest.ts, output/apps/web/lib/serwist.ts, output/apps/web/next.config.ts (update)

- [x] **Task 1.3: Initialize backend scaffold**
  - Create apps/api directory with FastAPI project structure
  - Set up main.py with FastAPI app, CORS, health endpoint
  - Create core/config.py with Pydantic BaseSettings (all env vars)
  - Create Dockerfile for Railway deployment
  - Create requirements.txt with all dependencies
  - Spec: SPECS.md, specs/audit-pipeline.md
  - Files: output/apps/api/main.py, output/apps/api/core/config.py, output/apps/api/core/__init__.py, output/apps/api/Dockerfile, output/apps/api/requirements.txt, output/apps/api/.env.example

- [x] **Task 1.4: Database schema and migrations**
  - Create supabase directory with migration files
  - Migration 001: full schema from 001_schema.sql (enums, tables, indexes, RLS, triggers)
  - Migration 002: subscriptions + usage_tracking tables with RLS
  - Create seed.sql with test organization, company, and sample data
  - Spec: specs/data-model.md, specs/security.md, specs/billing.md
  - Files: output/supabase/migrations/001_schema.sql, output/supabase/migrations/002_subscriptions.sql, output/supabase/seed.sql, output/supabase/config.toml

- [x] **Task 1.5: Shared types and constants**
  - Create packages/shared with TypeScript types mirroring DB schema
  - Define plan limits constant map (PLAN_LIMITS) matching specs/billing.md
  - Define metric IDs, category weights, rating thresholds from specs/metrics.md
  - Define enum types matching database enums
  - Spec: specs/data-model.md, specs/billing.md, specs/metrics.md
  - Files: output/packages/shared/src/types/database.ts, output/packages/shared/src/constants/plans.ts, output/packages/shared/src/constants/metrics.ts, output/packages/shared/src/index.ts, output/packages/shared/package.json, output/packages/shared/tsconfig.json

- [x] **Task 1.6: Backend Pydantic models and shared contracts**
  - Create Pydantic models matching data-contracts.schema.json
  - Models: AuditRequest, AuditConfig, GeneratedQuery, PlatformResponse, MentionAnalysis, CompetitorMapping, MetricScore, AuditResult, ProgressUpdate, HallucinationFinding, TechnicalCheckResult
  - Create plan limits config dict matching packages/shared constants
  - Spec: specs/data-model.md, specs/billing.md, specs/audit-pipeline.md
  - Files: output/apps/api/models/audit.py, output/apps/api/models/metrics.py, output/apps/api/models/billing.py, output/apps/api/models/__init__.py, output/apps/api/core/plan_limits.py

---

## Phase 2: Authentication and Organization

- [x] **Task 2.1: Supabase auth client setup**
  - Create Supabase browser client and server client utilities
  - Set up auth middleware for Next.js (protect dashboard routes)
  - Create auth store (Zustand) for client-side session state
  - Spec: specs/auth-users.md, specs/security.md
  - Files: output/apps/web/lib/supabase/client.ts, output/apps/web/lib/supabase/server.ts, output/apps/web/lib/supabase/middleware.ts, output/apps/web/stores/authStore.ts, output/apps/web/middleware.ts

- [x] **Task 2.2: Auth pages (login, signup, forgot password)**
  - Create (auth) route group layout (centered, minimal)
  - Create /login page: email/password form + Google OAuth button
  - Create /signup page: registration form + Google OAuth button
  - Create /forgot-password page: email input for reset
  - Create /reset-password page: new password form
  - Spec: specs/auth-users.md, specs/dashboard-ui.md
  - Files: output/apps/web/app/(auth)/layout.tsx, output/apps/web/app/(auth)/login/page.tsx, output/apps/web/app/(auth)/signup/page.tsx, output/apps/web/app/(auth)/forgot-password/page.tsx, output/apps/web/app/(auth)/reset-password/page.tsx

- [x] **Task 2.3: Onboarding flow**
  - Create /onboarding page: org name input + first company form
  - On submit: create organization + company via Supabase
  - Auto-create subscription (free) and usage_tracking row
  - Redirect to dashboard on completion
  - Spec: specs/auth-users.md, specs/data-model.md
  - Files: output/apps/web/app/onboarding/page.tsx, output/apps/web/lib/services/organizationService.ts

- [x] **Task 2.4: Backend auth middleware**
  - Create FastAPI dependency for JWT validation (verify Supabase JWT)
  - Create dependency for extracting user_id and resolving org membership + role
  - Create role-checking dependency (require_role("analyst"))
  - Spec: specs/security.md, specs/auth-users.md
  - Files: output/apps/api/core/dependencies.py, output/apps/api/core/auth.py

---

## Phase 3: App Shell and Navigation

- [x] **Task 3.1: Dashboard layout and sidebar**
  - Create (dashboard) route group layout with app shell
  - Build Sidebar: collapsible, links to Dashboard, Audits, Companies, Settings
  - Build TopBar: logo, org switcher dropdown, user menu
  - Create org context store (Zustand) for selected organization
  - Spec: specs/dashboard-ui.md
  - Files: output/apps/web/app/(dashboard)/layout.tsx, output/apps/web/components/layout/Sidebar.tsx, output/apps/web/components/layout/TopBar.tsx, output/apps/web/components/layout/AppShell.tsx, output/apps/web/stores/orgStore.ts

- [x] **Task 3.2: Shared UI components (score and plan)**
  - Create ScoreGauge: circular gauge with color coding by threshold
  - Create MetricCard: score bar, label, locked state with blur overlay
  - Create PlanGate: wrapper component for plan-restricted features
  - Create score utility: getScoreColor, getRatingLabel
  - Spec: specs/dashboard-ui.md, specs/billing.md, specs/metrics.md
  - Files: output/apps/web/components/shared/ScoreGauge.tsx, output/apps/web/components/shared/MetricCard.tsx, output/apps/web/components/shared/PlanGate.tsx, output/apps/web/lib/utils/score.ts

- [x] **Task 3.3: TrendChart and platform chart components**
  - Create TrendChart: Recharts line chart for score over time
  - Create PlatformBarChart: horizontal bars comparing platforms per metric
  - Create CategoryBreakdown: 4 cards with category scores
  - All charts: responsive, tooltips, loading skeletons
  - Spec: specs/dashboard-ui.md, specs/metrics.md
  - Files: output/apps/web/components/shared/TrendChart.tsx, output/apps/web/components/shared/PlatformBarChart.tsx, output/apps/web/components/shared/CategoryBreakdown.tsx, output/apps/web/components/shared/ChartSkeleton.tsx

---

## Phase 4: Company Management

- [x] **Task 4.1: Company list and creation**
  - Create /companies page: card grid with name, domain, last audit score
  - Create "Add Company" dialog: name, domain, industry, description fields
  - Create companyService: list, create, update, delete operations
  - Spec: specs/dashboard-ui.md, specs/data-model.md
  - Files: output/apps/web/app/(dashboard)/companies/page.tsx, output/apps/web/components/company/CompanyCard.tsx, output/apps/web/components/company/CreateCompanyDialog.tsx, output/apps/web/lib/services/companyService.ts

- [x] **Task 4.2: Company detail and facts editor**
  - Create /companies/[id] page: edit form + facts + competitors + topics
  - Build FactsEditor: key-value editor for ground truth JSON
  - Build competitor list: add/remove with text input
  - Build core topics: tag input component
  - Show audit history table for this company
  - Spec: specs/dashboard-ui.md, specs/data-model.md
  - Files: output/apps/web/app/(dashboard)/companies/[id]/page.tsx, output/apps/web/components/company/CompanyForm.tsx, output/apps/web/components/company/FactsEditor.tsx, output/apps/web/components/company/CompetitorList.tsx, output/apps/web/components/company/TopicTags.tsx

- [x] **Task 4.3: Backend company endpoints**
  - Create FastAPI router for companies: GET list, GET detail, POST create, PUT update, DELETE
  - Apply auth + role checks (analyst+ for write, viewer+ for read)
  - Apply org scoping (filter by user's organization)
  - Spec: specs/security.md, specs/data-model.md
  - Files: output/apps/api/api/companies.py, output/apps/api/services/company_service.py, output/apps/api/models/company.py

---

## Phase 5: Audit Pipeline (Backend)

- [x] **Task 5.1: LangGraph state and graph assembly**
  - Define AuditState dataclass for LangGraph StateGraph
  - Assemble the graph: preprocessor → query_gen → response_collector → (mention_analyzer || competitor_mapper) → synthesizer
  - Create graph entry point function that creates audit, starts pipeline
  - Spec: specs/audit-pipeline.md, specs/data-model.md
  - Files: output/apps/api/core/state.py, output/apps/api/core/graph.py

- [x] **Task 5.2: Rate limiter and cost tracker**
  - Create rate limiter with per-platform asyncio.Semaphore
  - Create Redis-backed RPM counter per platform
  - Create cost tracker: log tokens and cost per API call to audit_events
  - Create cost calculation utility (model → price per token)
  - Spec: specs/audit-pipeline.md, specs/security.md
  - Files: output/apps/api/core/rate_limiter.py, output/apps/api/core/cost_tracker.py, output/apps/api/core/redis_client.py

- [x] **Task 5.3: Preprocessor agent (GEO-17, GEO-11)**
  - Fetch and parse robots.txt for AI crawler permissions
  - Fetch and validate sitemap.xml, extract lastmod dates
  - Sample 10 URLs for HTTP status checks
  - Calculate freshness metrics, write to audit_technical_checks
  - Spec: specs/audit-pipeline.md, specs/metrics.md
  - Files: output/apps/api/agents/preprocessor.py, output/apps/api/core/utils/robots_parser.py, output/apps/api/core/utils/sitemap_parser.py, output/apps/api/core/utils/http_checker.py

- [x] **Task 5.4: Query Generator agent (Agent 1)**
  - Generate N queries based on company profile and metric requirements
  - Tag each query with intent and target_metrics
  - Enforce distribution rules (15% informational, 15% comparative, etc.)
  - Batch insert into audit_queries
  - Spec: specs/audit-pipeline.md, specs/metrics.md
  - Files: output/apps/api/agents/query_generator.py, output/apps/api/agents/query_models.py, output/apps/api/agents/query_prompts.py, output/apps/api/agents/query_constants.py, output/apps/api/agents/query_distribution_logic.py, output/apps/api/agents/query_validation_repair_logic.py, output/apps/api/agents/query_io_operations.py

- [x] **Task 5.5: Response Collector agent (Agent 2)**
  - For each (query, platform) pair: check cache → call API → extract citations/RAG sources
  - Implement OpenAI, Anthropic, Perplexity adapters
  - Apply rate limiting semaphores and retry logic (tenacity)
  - Batch insert into audit_responses, update cache
  - Spec: specs/audit-pipeline.md, specs/data-model.md
  - Files: output/apps/api/agents/response_collector.py, output/apps/api/agents/platform_adapters/__init__.py, output/apps/api/agents/platform_adapters/openai_adapter.py, output/apps/api/agents/platform_adapters/anthropic_adapter.py, output/apps/api/agents/platform_adapters/perplexity_adapter.py, output/apps/api/agents/platform_adapters/citation_utils.py

- [x] **Task 5.6: Mention Analyzer agent (Agent 3)**
  - For each response: extract entity mentions, position, sentiment, authority markers
  - Run NER for brand attributes extraction
  - Detect disambiguation issues
  - Batch insert into audit_mentions
  - Spec: specs/audit-pipeline.md, specs/metrics.md
  - Files: output/apps/api/agents/mention_analyzer.py

- [x] **Task 5.7: Competitor Mapper agent (Agent 4)**
  - Filter comparative/recommendation responses
  - For each competitor: calculate avg position, recommendation count, comparative language
  - Build per-platform breakdown
  - Upsert into audit_competitors
  - Spec: specs/audit-pipeline.md, specs/metrics.md
  - Files: output/apps/api/agents/competitor_mapper.py

- [ ] **Task 5.8: Synthesizer agent (Agent 5) — scoring** ← CURRENT
  - Cross-reference mentions vs companies.facts for hallucination detection
  - Compute all 10 metric scores using formulas from specs/metrics.md
  - Apply category weights, compute Global GEO Score
  - Insert into audit_metric_scores and audit_hallucinations
  - Spec: specs/metrics.md, specs/audit-pipeline.md
  - Files: output/apps/api/agents/synthesizer.py, output/apps/api/agents/score_calculator.py

- [ ] **Task 5.9: Synthesizer agent (Agent 5) — recommendations**
  - For each metric below threshold, generate prioritized recommendations
  - Map recommendations to action items from remediation playbook
  - Insert into audit_recommendations
  - Update audits with final scores, status=completed
  - Spec: specs/metrics.md, specs/audit-pipeline.md
  - Files: output/apps/api/agents/recommendation_generator.py

---

## Phase 6: Audit Trigger and Real-Time Progress

- [ ] **Task 6.1: Backend audit trigger endpoint**
  - POST /audits/run: validate request, enforce plan limits, increment usage, create audit row
  - Start LangGraph pipeline in background task
  - Publish initial ProgressUpdate to Redis
  - GET /audits: list audits for org (paginated, filtered)
  - GET /audits/{id}: audit detail with all child data
  - Spec: specs/audit-pipeline.md, specs/billing.md, specs/security.md
  - Files: output/apps/api/api/audits.py, output/apps/api/services/audit_service.py, output/apps/api/services/plan_enforcement.py

- [ ] **Task 6.2: SSE progress endpoint**
  - Backend: write ProgressUpdate to Redis key audit:{id}:progress at each stage
  - Frontend API route: GET /api/audits/[id]/progress — SSE endpoint reading from Upstash Redis
  - Create useAuditProgress hook: connects to SSE, returns live status
  - Spec: specs/audit-pipeline.md
  - Files: output/apps/api/services/progress_service.py, output/apps/web/app/api/audits/[id]/progress/route.ts, output/apps/web/lib/hooks/useAuditProgress.ts

- [ ] **Task 6.3: New Audit page (frontend)**
  - Create /audits/new: step form (select company → configure → confirm)
  - Query count slider respecting plan limits
  - Platform checkboxes (disabled platforms show lock)
  - Competitor toggle (locked on free)
  - Submit triggers API call, redirects to audit detail with live progress
  - Spec: specs/dashboard-ui.md, specs/billing.md
  - Files: output/apps/web/app/(dashboard)/audits/new/page.tsx, output/apps/web/components/audit/AuditConfigForm.tsx, output/apps/web/lib/services/auditService.ts

---

## Phase 7: Audit Results and Dashboard

- [ ] **Task 7.1: Audit list page**
  - Create /audits page: filterable table (company, status, date, score)
  - Status badge component with color coding
  - Click row navigates to audit detail
  - Spec: specs/dashboard-ui.md
  - Files: output/apps/web/app/(dashboard)/audits/page.tsx, output/apps/web/components/audit/AuditTable.tsx, output/apps/web/components/audit/StatusBadge.tsx

- [ ] **Task 7.2: Audit detail — scores and progress**
  - Create /audits/[id] page with header (company, date, status, cost)
  - Running state: AuditProgress component with live SSE bar
  - Completed state: Global Score gauge + 10 metric cards in 4 category groups
  - Locked metrics: blurred with PlanGate overlay
  - Spec: specs/dashboard-ui.md, specs/metrics.md, specs/billing.md
  - Files: output/apps/web/app/(dashboard)/audits/[id]/page.tsx, output/apps/web/components/audit/AuditProgress.tsx, output/apps/web/components/audit/AuditScorePanel.tsx

- [ ] **Task 7.3: Audit detail — tabs (recommendations, competitors, hallucinations)**
  - Recommendations tab: P0–P3 cards with title, description, action items, effort badge
  - Competitors tab: table with position, appearances, sentiment (locked on free)
  - Hallucinations tab: table with claim, expected vs actual, severity, platform
  - Raw data tab: collapsible query list with response previews
  - Spec: specs/dashboard-ui.md, specs/metrics.md
  - Files: output/apps/web/components/audit/RecommendationsTab.tsx, output/apps/web/components/audit/CompetitorsTab.tsx, output/apps/web/components/audit/HallucinationsTab.tsx, output/apps/web/components/audit/RawDataTab.tsx, output/apps/web/components/audit/AuditDetailTabs.tsx

- [ ] **Task 7.4: Dashboard home page**
  - Create / (dashboard) page: company selector, Global Score gauge, trend chart
  - Category breakdown cards (4 categories)
  - Recent audits table (last 5)
  - "Run New Audit" quick action button
  - Spec: specs/dashboard-ui.md, specs/metrics.md
  - Files: output/apps/web/app/(dashboard)/page.tsx, output/apps/web/components/dashboard/DashboardOverview.tsx, output/apps/web/components/dashboard/RecentAudits.tsx

---

## Phase 8: Settings, Billing, and Team

- [ ] **Task 8.1: Settings layout and general tab**
  - Create /settings with tabbed layout (General, Team, Billing, Account)
  - General tab: edit org name and slug
  - Account tab: profile name, email display, password change, delete account
  - Spec: specs/dashboard-ui.md, specs/auth-users.md
  - Files: output/apps/web/app/(dashboard)/settings/page.tsx, output/apps/web/app/(dashboard)/settings/layout.tsx, output/apps/web/components/settings/GeneralSettings.tsx, output/apps/web/components/settings/AccountSettings.tsx

- [ ] **Task 8.2: Team management**
  - Team tab: member list with role badges, invite form (email + role picker)
  - Role change dropdown (admin+ only), remove member button
  - Backend endpoints: GET members, POST invite, PUT change role, DELETE remove
  - Spec: specs/auth-users.md, specs/security.md
  - Files: output/apps/web/components/settings/TeamSettings.tsx, output/apps/web/components/settings/InviteMemberForm.tsx, output/apps/web/lib/services/teamService.ts, output/apps/api/api/organizations.py, output/apps/api/services/organization_service.py

- [ ] **Task 8.3: Paddle billing integration (backend)**
  - Create webhook endpoint: POST /webhooks/paddle with signature verification
  - Handle events: subscription.created, updated, cancelled, past_due
  - Sync subscription state to subscriptions table, update organizations.plan
  - Create billing service: get current plan, get usage stats
  - Spec: specs/billing.md, specs/security.md
  - Files: output/apps/api/api/webhooks.py, output/apps/api/services/billing_service.py, output/apps/api/models/billing.py

- [ ] **Task 8.4: Billing page (frontend)**
  - Billing tab (owner only): current plan card, usage stats (audits used/limit)
  - Upgrade button: opens Paddle checkout overlay
  - Plan comparison display with feature highlights
  - Cancel subscription with confirmation dialog
  - Install Paddle.js, configure with environment variables
  - Spec: specs/billing.md, specs/dashboard-ui.md
  - Files: output/apps/web/components/settings/BillingSettings.tsx, output/apps/web/components/settings/PlanCard.tsx, output/apps/web/components/settings/UsageStats.tsx, output/apps/web/lib/paddle.ts

---

## Phase 9: Polish and Production

- [ ] **Task 9.1: R2 archival and cleanup**
  - Create R2 upload service in backend (async, non-blocking)
  - Archive full audit data to R2 on completion (JSON structure per specs)
  - Add Cloudflare R2 credentials to config
  - Spec: specs/audit-pipeline.md
  - Files: output/apps/api/services/archive_service.py, output/apps/api/core/r2_client.py

- [ ] **Task 9.2: Error handling and monitoring**
  - Install and configure Sentry for frontend (Next.js) and backend (FastAPI)
  - Install and configure PostHog for frontend analytics
  - Add structlog configuration for backend JSON logging
  - Create error boundary component for frontend
  - Spec: SPECS.md
  - Files: output/apps/web/lib/sentry.ts, output/apps/web/lib/posthog.ts, output/apps/web/components/shared/ErrorBoundary.tsx, output/apps/api/core/logging.py, output/apps/api/core/sentry.py

- [ ] **Task 9.3: Frontend tests**
  - Configure Vitest + React Testing Library in apps/web
  - Test ScoreGauge: color thresholds, score rendering
  - Test MetricCard: locked vs unlocked state
  - Test PlanGate: plan checking logic
  - Test score utilities: getScoreColor, getRatingLabel
  - Spec: rules/testing.md
  - Files: output/apps/web/vitest.config.ts, output/apps/web/components/shared/ScoreGauge.test.tsx, output/apps/web/components/shared/MetricCard.test.tsx, output/apps/web/components/shared/PlanGate.test.tsx, output/apps/web/lib/utils/score.test.ts

- [ ] **Task 9.4: Backend tests**
  - Configure Pytest + httpx in apps/api
  - Test score calculation: all 10 metric formulas with known inputs
  - Test plan enforcement: limits for each plan tier
  - Test audit API endpoints: trigger, list, detail (with mocked pipeline)
  - Test webhook signature verification
  - Spec: rules/testing.md, specs/metrics.md
  - Files: output/apps/api/tests/conftest.py, output/apps/api/tests/test_score_calculator.py, output/apps/api/tests/test_plan_enforcement.py, output/apps/api/tests/test_audits_api.py, output/apps/api/tests/test_webhooks.py

- [ ] **Task 9.5: Responsive layout and PWA finalization**
  - Ensure all pages work on tablet (collapsed sidebar) and mobile (bottom tab bar)
  - Add loading skeletons for all data-dependent pages
  - Test PWA install flow, offline caching of last dashboard state
  - Final Lighthouse audit: performance, accessibility, PWA score
  - Spec: specs/dashboard-ui.md
  - Files: output/apps/web/components/layout/MobileTabBar.tsx, output/apps/web/components/layout/Sidebar.tsx (update), output/apps/web/components/shared/PageSkeleton.tsx
