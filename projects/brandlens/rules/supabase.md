# Supabase Rules

## Client Setup
- Browser client: `createBrowserClient()` in `lib/supabase/client.ts` — uses anon key
- Server client: `createServerClient()` in `lib/supabase/server.ts` — uses anon key with cookie-based auth
- Service client (backend only): uses `SUPABASE_SERVICE_ROLE_KEY` — bypasses RLS

## Query Patterns
- All frontend queries go through service files in `lib/services/`
- Always destructure: `const { data, error } = await supabase.from(...)`
- Always handle errors — never ignore the `error` object
- Use `.select()` to specify columns — avoid `select("*")` on large tables
- Use database views for complex JOINed reads (create views in migrations)

### Example Service Pattern
```typescript
// lib/services/auditService.ts
export async function getAuditDetail(supabase: SupabaseClient, auditId: string) {
  const { data, error } = await supabase
    .from("audits")
    .select("*, audit_metric_scores(*), audit_recommendations(*)")
    .eq("id", auditId)
    .single();

  if (error) throw new Error(`Failed to fetch audit: ${error.message}`);
  return data;
}
```

## RLS
- RLS is the single source of truth for data access control
- UI hides elements for UX, but NEVER rely on UI for security
- All new tables MUST have RLS enabled + at least one policy
- Test RLS by querying as different users in Supabase dashboard

## Migrations
- One migration file per logical change: `001_schema.sql`, `002_subscriptions.sql`
- Use `supabase db push` for development, `supabase db diff` to generate migrations
- Never modify a deployed migration — create a new one
- Include RLS policies in the same migration as the table

## Auth
- Use `supabase.auth.getUser()` for server-side user resolution
- Use `supabase.auth.getSession()` for client-side session checks
- Listen to `onAuthStateChange` for reactive auth state in frontend
- JWT claims contain `sub` (user_id) — used by RLS via `auth.uid()`

## Realtime (future use)
- If adding Supabase Realtime subscriptions, use custom hooks
- Always call `channel.unsubscribe()` on component unmount
- Prefer Upstash Redis SSE for audit progress (lower latency)

## DO NOT
- DO NOT use `.rpc()` for simple CRUD — use query builder
- DO NOT store service role key in frontend environment variables
- DO NOT create tables without enabling RLS
- DO NOT bypass RLS for convenience — fix the policy instead
