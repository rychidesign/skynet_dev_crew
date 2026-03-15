# DO NOT Rules for AI Agents

## Universal
- DO NOT modify files outside the scope of your current task
- DO NOT duplicate code — search for existing utils first with search_content tool
- DO NOT use magic numbers or strings — use constants from config or shared package
- DO NOT edit PROGRESS.md — Supervisor handles this automatically
- DO NOT call file_writer with empty content
- DO NOT truncate file content — always write complete files
- DO NOT invent API endpoints not defined in specs — check specs/audit-pipeline.md and specs/billing.md

## File Size Limits (CRITICAL)
- DO NOT write backend files (.py, .go, .rs, .java, .rb, .php) longer than 200 lines
- DO NOT write frontend files (.tsx, .ts, .jsx, .js, .vue, .svelte, .css) longer than 150 lines
- DO NOT submit code without checking file size with file_size_check tool
- DO NOT ignore file size violations from Reviewer — split files immediately
- DO NOT use "rest of code" comments or truncation — write complete files

### How to handle large implementations:
1. Split into multiple files by responsibility
2. Extract helper functions into separate utility files
3. Create separate modules for different concerns
4. Use dependency injection to keep files small

## TypeScript (Frontend)
- DO NOT use `any` type — use `unknown` + type guards or proper types
- DO NOT use `@ts-ignore` or `@ts-expect-error`
- DO NOT import from `../../../` — use `@/` absolute paths
- DO NOT use `useEffect` for data fetching — use server components or React Query
- DO NOT put database logic in components — use services in `lib/services/`
- DO NOT use `localStorage` or `sessionStorage` for auth tokens — Supabase client handles this
- DO NOT hardcode plan limits in components — import from shared constants

## Python (Backend)
- DO NOT use `print()` for logging — use `structlog`
- DO NOT catch bare `Exception` — catch specific exceptions
- DO NOT use synchronous DB calls — use `async/await` everywhere
- DO NOT store secrets in code — use environment variables via `core/config.py`
- DO NOT bypass RLS by using service role key in frontend-facing queries
- DO NOT return raw database rows from API — use Pydantic response models

## UI
- DO NOT edit generated shadcn/ui files in `components/ui/`
- DO NOT use emoji anywhere in the UI — use Lucide icons instead
- DO NOT add color values outside Tailwind config — extend theme properly
- DO NOT show locked metric data to free users — backend must omit it
- DO NOT rely on frontend for access control — always enforce in backend + RLS

## Supabase
- DO NOT use `.rpc()` for simple CRUD — use query builder
- DO NOT expose `SUPABASE_SERVICE_ROLE_KEY` to frontend code
- DO NOT create tables without RLS policies
- DO NOT store computed aggregates in client state — use database triggers or views
