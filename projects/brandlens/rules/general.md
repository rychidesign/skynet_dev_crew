# General Coding Conventions

## Tech Stack
- Frontend: Next.js 15 (App Router), TypeScript, Tailwind CSS, shadcn/ui, Recharts
- Backend: FastAPI (Python 3.12+), LangGraph, Pydantic
- Database: Supabase PostgreSQL 15
- Cache: Upstash Redis
- Monorepo: Turborepo (apps/web, apps/api, packages/shared)

## TypeScript (Frontend)
- Strict mode enabled, no `any` types — use `unknown` + type guards
- Database columns: snake_case. TypeScript: camelCase. Convert at service layer.
- All function signatures must have explicit return types
- Use `type` for data shapes, `interface` for contracts that may be extended

## Python (Backend)
- Type hints on all function signatures and return types
- Pydantic models for all request/response validation
- Follow PEP 8, enforced by Ruff linter
- Use `async def` for all endpoint handlers and DB operations

## Naming

### Frontend (TypeScript)
- Components: PascalCase (`MetricCard.tsx`, `AuditProgress.tsx`)
- Hooks: camelCase with `use` prefix (`useAuditProgress.ts`)
- Services: camelCase (`auditService.ts`)
- Utilities: kebab-case (`format-date.ts`, `plan-limits.ts`)
- Constants: UPPER_SNAKE_CASE (`MAX_QUERIES`, `PLAN_LIMITS`)
- Types/interfaces: PascalCase (`AuditResult`, `MetricScore`)

### Backend (Python)
- Modules: snake_case (`query_generator.py`, `rate_limiter.py`)
- Classes: PascalCase (`AuditState`, `ResponseCollector`)
- Functions/variables: snake_case (`get_audit_by_id`, `total_cost`)
- Constants: UPPER_SNAKE_CASE (`PLATFORM_LIMITS`, `PLAN_LIMITS`)

## Imports

### Frontend
- Absolute paths via `@/` alias (maps to `apps/web/`)
- Group order: (1) React/Next.js, (2) external libs, (3) `@/components`, (4) `@/lib`, (5) `@/types`, (6) relative imports
- No barrel exports (index.ts re-exports) — import directly from source file

### Backend
- Group order: (1) stdlib, (2) third-party, (3) local modules
- Use explicit relative imports within packages

## File Size (CRITICAL)

### Limits
- **Frontend: max 150 lines per file**
- **Backend: max 200 lines per file**

### Enforcement
- Use `file_size_check` tool BEFORE submitting code
- Reviewer will REJECT files exceeding limits
- Files exceeding limits MUST be split before proceeding

### How to Split Large Files
1. **Extract helpers** — Move utility functions to separate files
2. **Extract subcomponents** — Split UI components into smaller pieces
3. **Extract services** — Move business logic to service files
4. **Extract types** — Move type definitions to separate files
5. **Use modules** — Organize related functions into module directories

### Example Split
```
# Before (300 lines in one file):
agents/response_collector.py

# After (split into focused files):
agents/response_collector.py          # Main orchestration (~100 lines)
agents/response_collector/cache.py    # Cache logic (~50 lines)
agents/response_collector/api.py      # API calls (~80 lines)
agents/response_collector/db.py       # Database operations (~60 lines)
```

## DRY
- Search existing code before creating new functions or components
- Shared types between frontend and backend go in `packages/shared/`
- Reusable UI patterns → extract to `components/ui/` or `components/shared/`
