# Testing Rules

## Frontend (Vitest + React Testing Library)

### What to Test
- **Services**: all functions in `lib/services/` — mock Supabase client, verify query params and return types
- **Hooks**: custom hooks with side effects (useAuditProgress SSE, useOrgContext)
- **Utility functions**: `formatScore`, `getScoreColor`, `planLimits` — pure functions, easy to test
- **Key components**: PlanGate (locked vs unlocked rendering), ScoreGauge (color thresholds), MetricCard (locked state)

### What NOT to Test
- shadcn/ui base components (already tested upstream)
- Simple presentational components with no logic
- Next.js page layouts (tested via E2E if needed)

### Patterns
- One test file per source file: `MetricCard.test.tsx` next to `MetricCard.tsx`
- Use `describe` blocks grouped by behavior, not by method
- Mock Supabase with `vi.mock("@/lib/supabase/client")`
- Assertions: prefer `toBeInTheDocument`, `toHaveTextContent` over snapshot tests

## Backend (Pytest + httpx)

### What to Test
- **API endpoints**: all routes in `api/` — test request validation, auth, response shape
- **Services**: business logic in `services/` — plan enforcement, usage metering
- **Agent functions**: each agent as unit — mock LLM calls, verify state transformations
- **Score calculations**: metric formulas from specs/metrics.md — given known inputs, verify exact scores
- **Pydantic models**: validation edge cases (invalid metric_id format, out-of-range scores)

### What NOT to Test
- LangGraph framework internals
- Supabase client library
- Third-party API response formats (mock them)

### Patterns
- Use `pytest-asyncio` for async test functions
- Use `httpx.AsyncClient` with `app` for API integration tests
- Fixtures: `test_audit`, `test_company`, `test_organization` with realistic data
- Mock LLM calls with deterministic responses — never call real AI APIs in tests
- Score calculation tests: use exact expected values from metric formulas

## Test File Location
- Frontend: colocated with source (`components/shared/MetricCard.test.tsx`)
- Backend: separate `tests/` directory mirroring `apps/api/` structure

## Coverage Expectations
- Services and utilities: aim for 80%+ coverage
- Agent score calculations: 100% coverage (critical business logic)
- UI components: cover key interaction paths, skip pure layout
