# Security

## References
- Related: specs/data-model.md — table definitions, enum types
- Related: specs/auth-users.md — auth methods, session management
- Related: specs/billing.md — plan limits that security must enforce
- Related: SPECS.md — role definitions

## Architecture

Security operates at 3 layers:
1. **Supabase RLS** — database-level access control (source of truth)
2. **Backend middleware** — FastAPI JWT validation, plan enforcement, rate limiting
3. **Frontend guards** — route protection and UI element visibility (UX only, never trust)

## Row Level Security (RLS)

All tables have RLS enabled. Two helper functions handle access checks:

### user_in_org(org_id UUID) → BOOLEAN
Returns true if `auth.uid()` is a member of the given organization. Used by top-level tables (organizations, companies, audits).

### audit_org_check(audit_id UUID) → BOOLEAN
Joins through audits → organization_members to check access. Used by all audit child tables (queries, responses, mentions, competitors, scores, recommendations, hallucinations, technical_checks, events).

### Policy Pattern

| Table Group | Policy | USING Clause |
|---|---|---|
| organizations | org_access | `user_in_org(id)` |
| organization_members | org_access | `user_in_org(organization_id)` |
| companies | org_access | `user_in_org(organization_id)` |
| audits | org_access | `user_in_org(organization_id)` |
| All audit_* child tables | audit_access | `audit_org_check(audit_id)` |
| metric_time_series | timeseries_access | Join companies → org_members |
| subscriptions | org_access | `user_in_org(organization_id)` |
| usage_tracking | org_access | `user_in_org(organization_id)` |

All policies use `FOR ALL` — same check for SELECT, INSERT, UPDATE, DELETE. RLS does not differentiate by role; role-based restrictions are enforced in the application layer.

### Service Role Key
The backend (Railway) uses `SUPABASE_SERVICE_ROLE_KEY` to bypass RLS for pipeline writes. This key must NEVER be exposed to the frontend or stored in client-accessible environment variables.

## Backend Security (FastAPI)

### JWT Validation
1. Frontend sends Supabase JWT in `Authorization: Bearer <token>` header.
2. Backend middleware validates JWT signature using Supabase JWT secret.
3. Extracts `user_id` (sub claim) and attaches to request context.
4. All endpoints require valid JWT except: health check, Paddle webhooks.

### Role Enforcement (Application Layer)
Backend checks role from `organization_members` before executing actions:

| Action | Minimum Role |
|---|---|
| View dashboards, reports | viewer |
| Trigger audit | analyst |
| Create/edit companies | analyst |
| Manage team members | admin |
| Change org settings | admin |
| Billing, plan changes | owner |
| Delete organization | owner |

### Plan Enforcement
Before triggering an audit, backend checks:
1. `usage_tracking.audits_used` < plan limit for current period.
2. Requested `config.query_count` ≤ plan max queries.
3. Requested `config.platforms` ⊆ plan allowed platforms.
4. If competitor analysis requested, plan must include it.
Rejection returns HTTP 403 with `plan_limit_exceeded` error code and upgrade prompt data.

### Rate Limiting
- Per-user: max 10 API requests/second (HTTP 429 on exceed).
- Per-org audit trigger: max 1 concurrent audit (queue or reject).
- Per-platform AI calls: asyncio.Semaphore (chatgpt:10, claude:5, perplexity:3, google_aio:5).

## Frontend Security

### Route Protection
- Unauthenticated users → redirect to `/login`.
- Authenticated users without org → redirect to `/onboarding`.
- Role-based route guards: billing pages require owner role.
- Plan-based UI gates: locked metrics show upgrade CTA, not raw data.

### Data Exposure Rules
- Frontend uses Supabase `anon` key only — all queries go through RLS.
- Never expose: service role key, AI API keys, Paddle API key, internal user IDs of other orgs.
- Locked metrics: backend omits data from response (not just hidden in UI).

## Paddle Webhook Security
- Verify webhook signature using Paddle's public key.
- Dedicated endpoint: `POST /webhooks/paddle` — no JWT required.
- Idempotent processing: use Paddle event ID to deduplicate.
- Only process events: `subscription.created`, `subscription.updated`, `subscription.cancelled`, `subscription.past_due`.

## Environment Variable Segregation

| Variable | Available In | Never In |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Frontend | — |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Frontend | — |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend only | Frontend |
| `OPENAI_API_KEY` | Backend only | Frontend |
| `ANTHROPIC_API_KEY` | Backend only | Frontend |
| `PERPLEXITY_API_KEY` | Backend only | Frontend |
| `PADDLE_API_KEY` | Backend only | Frontend |
| `PADDLE_WEBHOOK_SECRET` | Backend only | Frontend |
