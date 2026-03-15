# BrandLens — Overview

## What We're Building
BrandLens is a PWA that measures brand visibility across AI search engines (ChatGPT, Claude, Perplexity, Gemini, Copilot). A multi-agent pipeline generates queries, collects AI responses, analyzes mentions and competitors, and produces a scored report with actionable recommendations. Target: 50–200 users at soft launch.
**Language:** English (UI and all content)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15 (App Router), TypeScript, Vercel Pro |
| UI Library | Tailwind CSS + shadcn/ui |
| Charts | Recharts |
| PWA | Serwist |
| Backend | FastAPI (Python 3.12+), LangGraph, Railway |
| Database | Supabase PostgreSQL 15 (pgBouncer) |
| Auth | Supabase Auth (email/password + Google OAuth) |
| Cache / Realtime | Upstash Redis |
| File Storage | Cloudflare R2 |
| Billing | Paddle (webhooks → Supabase) |
| AI Providers | OpenAI, Anthropic, Perplexity, Google Gemini, Copilot |
| Monitoring | Sentry + PostHog + Structlog |
| Monorepo | Turborepo |
| Testing | Vitest (frontend), Pytest (backend) |

## Core Hierarchy

```
Organizations
├── Organization Members (user ↔ org, role)
├── Companies (brand being audited)
│   ├── facts, competitors[], core_topics[]
│   └── Audits
│       ├── Audit Queries → Audit Responses
│       │   ├── Audit Mentions
│       │   └── Audit Hallucinations
│       ├── Audit Competitors
│       ├── Audit Metric Scores (10 per audit)
│       ├── Audit Recommendations
│       ├── Audit Technical Checks
│       └── Audit Events
├── Metric Time Series (denormalized trend snapshots)
└── Subscriptions (Paddle-synced)
```

## User Roles

| Role | Access |
|------|--------|
| Owner | Everything + billing, org deletion, plan management |
| Admin | Member management, company CRUD, audit trigger |
| Analyst | Audit trigger, results viewing, company management |
| Viewer | Read-only: dashboards, reports |

## Plans

| | Free | Pro | Enterprise |
|---|---|---|---|
| Audits/month | 1 | 20 | 100 |
| Queries/audit | 10 | 50 | 200 |
| Platforms | 2 (ChatGPT, Perplexity) | 5 (all) | 5 (all) |
| Metrics | 4 (GEO-01, 13, 17 + Global) | All 10 | All 10 |
| Competitors | No | Max 5 | Unlimited |
| Trend history | Last 2 audits | 1 year | Unlimited |
| Team members | 1 | 5 | Unlimited |
| Recommendations | Score + rating only | Full P0–P3 | Full + export |

## Key Features (MVP)
- Audit Dashboard: overview, Global GEO Score, trend chart, running audit status
- New Audit Trigger: configure queries, platforms, cache TTL
- Real-time Audit Progress: SSE stream with live agent status
- Audit Detail Report: 10 metrics, category scores, per-platform breakdown, hallucinations
- Recommendations: prioritized P0–P3 action items per metric
- Competitor Analysis: competitive landscape, per-platform positioning
- Trend Analysis: historical metric evolution across audits
- Company Management: CRUD with facts (ground truth), competitors, topics
- Organization and Team: multi-tenant, invitations, roles
- Billing: Paddle checkout, plan enforcement, usage tracking

## Detailed Specs

| File | Covers |
|------|--------|
| specs/data-model.md | Full database schema — tables, columns, enums, indexes, RLS, triggers |
| specs/security.md | RLS policies, auth flow, JWT validation, plan enforcement |
| specs/auth-users.md | Auth methods, role permissions, invitation flow, session management |
| specs/billing.md | Paddle integration, plan limits, webhook handling, usage metering |
| specs/audit-pipeline.md | 7-stage pipeline: trigger → preprocess → 5 agents → archive |
| specs/metrics.md | 10 GEO metrics: formulas, weights, scoring model, thresholds |
| specs/dashboard-ui.md | Pages, navigation, components, data flow for frontend |

## Agent Workflow
1. Read this file (SPECS.md)
2. Read PROGRESS.md — find your current task (← CURRENT)
3. Read only relevant spec files listed in your task
4. Read relevant rules files
5. Do ONLY your assigned task
6. Run lint and tests (if configured)
7. End session — Supervisor handles PROGRESS.md updates
