# Architecture Rules

## Monorepo Structure

```
brandlens/
├── apps/
│   ├── web/                          # Next.js frontend (Vercel)
│   │   ├── app/                      # App Router pages
│   │   │   ├── (auth)/               # Auth group: login, signup, forgot-password
│   │   │   ├── (dashboard)/          # Authenticated group: dashboard, audits, companies, settings
│   │   │   ├── onboarding/
│   │   │   ├── layout.tsx
│   │   │   └── globals.css
│   │   ├── components/
│   │   │   ├── ui/                   # shadcn/ui base components
│   │   │   ├── shared/               # Reusable: ScoreGauge, MetricCard, PlanGate, TrendChart
│   │   │   ├── audit/                # Audit-specific: AuditProgress, AuditDetailTabs
│   │   │   ├── company/              # Company-specific: CompanyForm, FactsEditor
│   │   │   └── layout/               # AppShell, Sidebar, TopBar
│   │   ├── lib/
│   │   │   ├── supabase/             # Supabase client (browser + server)
│   │   │   ├── services/             # Data fetching: auditService, companyService
│   │   │   ├── hooks/                # Custom hooks: useAuditProgress, useOrgContext
│   │   │   └── utils/                # Helpers: formatScore, planLimits
│   │   ├── stores/                   # Zustand stores: authStore, orgStore
│   │   ├── types/                    # TypeScript types mirroring DB schema
│   │   └── package.json
│   │
│   └── api/                          # FastAPI backend (Railway)
│       ├── agents/                   # LangGraph agent implementations
│       │   ├── preprocessor.py
│       │   ├── query_generator.py
│       │   ├── response_collector.py
│       │   ├── mention_analyzer.py
│       │   ├── competitor_mapper.py
│       │   └── synthesizer.py
│       ├── core/                     # Shared backend utilities
│       │   ├── state.py              # AuditState (LangGraph state definition)
│       │   ├── graph.py              # LangGraph StateGraph assembly
│       │   ├── rate_limiter.py
│       │   ├── cost_tracker.py
│       │   ├── config.py             # Settings, plan limits
│       │   └── dependencies.py       # FastAPI dependency injection
│       ├── api/                      # FastAPI route handlers
│       │   ├── audits.py
│       │   ├── companies.py
│       │   ├── organizations.py
│       │   └── webhooks.py           # Paddle webhooks
│       ├── services/                 # Business logic layer
│       │   ├── audit_service.py
│       │   ├── billing_service.py
│       │   └── plan_enforcement.py
│       ├── models/                   # Pydantic models (request/response)
│       ├── main.py                   # FastAPI app entry point
│       ├── Dockerfile
│       └── requirements.txt
│
├── packages/
│   └── shared/                       # Shared constants and types
│       ├── contracts/                # JSON schemas (data-contracts.schema.json)
│       └── constants/                # Plan limits, metric IDs, enums
│
├── supabase/
│   ├── migrations/                   # SQL migrations (001_schema.sql, 002_subscriptions.sql)
│   └── seed.sql
│
├── turbo.json
└── package.json
```

## Separation of Concerns

### Frontend
- **Pages (app/)**: layout and data loading only. No business logic.
- **Components**: UI rendering only. No direct DB queries. Receive data via props or hooks.
- **Services (lib/services/)**: all Supabase queries and backend API calls. Return typed data.
- **Hooks (lib/hooks/)**: stateful logic, SSE connections, subscriptions. Call services.
- **Stores (stores/)**: global client state (current org, auth). Thin — most state is server state.
- **Types (types/)**: mirror DB schema in TypeScript. Single source of truth for frontend types.

### Backend
- **Routes (api/)**: HTTP handling only. Parse request, call service, return response.
- **Services (services/)**: business logic, plan enforcement, orchestration decisions.
- **Agents (agents/)**: LangGraph node implementations. Each agent is a pure function: input state → output state.
- **Core (core/)**: shared infrastructure — state definition, graph assembly, rate limiting.
- **Models (models/)**: Pydantic request/response models. Validate at API boundary.

## Key Rules
- Frontend NEVER imports from `apps/api/`. Communication is HTTP only.
- Backend NEVER imports from `apps/web/`. Shared types go in `packages/shared/`.
- Each agent file exports a single function matching LangGraph node signature.
- Route handlers are thin — max 20 lines. Delegate to services.
