# Dashboard UI

## References
- Related: specs/metrics.md — metric definitions for score cards and charts
- Related: specs/billing.md — plan gate component, upgrade CTAs
- Related: specs/auth-users.md — auth pages, role-based visibility
- Related: specs/audit-pipeline.md — real-time progress SSE

## Design Principles
- Light theme, minimalist, generous whitespace
- Line art aesthetic: thin borders, outline icons (Lucide), subtle shadows
- Blue + gray palette: primary #2563EB, text #1E293B, muted #64748B, border #E2E8F0, background #F8FAFC
- No emoji anywhere in the UI
- Typography: Inter (sans-serif), monospace for metric IDs and scores
- shadcn/ui components as base, customized to match style

## App Shell

```
┌─────────────────────────────────────────────────┐
│ TopBar: Logo | Org Switcher | Search | User Menu │
├──────────┬──────────────────────────────────────┤
│ Sidebar  │ Main Content Area                     │
│          │                                       │
│ Dashboard│                                       │
│ Audits   │                                       │
│ Companies│                                       │
│ Settings │                                       │
│          │                                       │
└──────────┴──────────────────────────────────────┘
```

Sidebar: collapsible, icons + labels. Active item highlighted with blue left border.

## Pages

### / (Dashboard)
- Company selector dropdown (if multiple companies)
- Global GEO Score: large circular gauge with rating label
- Trend chart: Recharts line chart, score over time (metric_time_series)
- Category breakdown: 4 cards with category scores
- Recent audits: table with date, score, status, duration
- Quick action: "Run New Audit" button

### /audits (Audit List)
- Filterable table: company, status, date range, score range
- Columns: company name, date, status badge, global score, duration, cost
- Click row → audit detail

### /audits/new (New Audit)
- Step form: (1) Select company, (2) Configure: query count slider, platform checkboxes, cache TTL, competitor toggle, (3) Confirm and start
- Plan limits shown inline (e.g. "10/10 queries" on free)
- Disabled options show lock icon + plan name required

### /audits/[id] (Audit Detail)
- Header: company name, date, status, duration, cost
- If running: real-time progress bar with SSE, current agent label, counters
- If completed:
  - Global Score gauge + rating
  - 10 metric cards in 4 category groups. Each card: metric name, score bar, mini sparkline (if history exists). Locked metrics: blurred with upgrade CTA overlay.
  - Per-platform comparison: horizontal bar chart (score per platform per metric)
  - Recommendations tab: P0–P3 cards with title, description, action items, effort badge
  - Competitors tab: table with competitor name, avg position, appearances, recommendation count, sentiment. Locked on free.
  - Hallucinations tab: table with claim, expected vs actual, severity badge, platform
  - Raw data tab (collapsible): query list, response previews

### /companies (Company List)
- Card grid or table: name, domain, industry, last audit date, last score
- "Add Company" button

### /companies/[id] (Company Detail)
- Edit form: name, domain, industry, description
- Facts editor: key-value JSON editor for ground truth data
- Competitors: editable list (add/remove names)
- Core topics: tag input
- Audit history: table of past audits for this company
- Trend chart: score evolution over time

### /settings (Settings)
Tabbed layout:
- **General**: organization name, slug
- **Team**: member list with roles, invite form (admin+ only)
- **Billing**: current plan, usage stats, upgrade/downgrade, cancel (owner only)
- **Account**: profile name, email, password change, delete account

### /login, /signup, /forgot-password, /reset-password, /onboarding
See specs/auth-users.md for details.

## Key Components

### ScoreGauge
Circular gauge displaying 0–100 score with color coding:
- 0–24: red (#EF4444), 25–49: orange (#F97316), 50–74: yellow (#EAB308), 75–89: blue (#2563EB), 90–100: green (#22C55E)

### MetricCard
- Props: metricId, score, label, category, isLocked, trend (sparkline data)
- Locked state: blurred score + "Upgrade to Pro" overlay

### PlanGate
- Wraps any plan-restricted feature
- Props: requiredPlan, featureName
- Renders children if plan sufficient, otherwise lock overlay with upgrade CTA

### AuditProgress
- SSE-connected component showing live pipeline status
- Progress bar (0–100%), current agent name, counters (queries generated, responses collected)
- Status transitions animate smoothly

### TrendChart
- Recharts LineChart with date x-axis, score y-axis
- Multiple lines for different metrics or single global score
- Responsive, tooltips on hover

## Data Flow

| Page | Data Source | Query Pattern |
|---|---|---|
| Dashboard | metric_time_series | Latest N snapshots for selected company |
| Audit List | audits | Paginated, filtered by org, ordered by created_at DESC |
| Audit Detail | audits + audit_metric_scores + audit_recommendations + audit_competitors + audit_hallucinations | Single audit with all children |
| Audit Progress | Upstash Redis via SSE | Real-time polling of audit:{id}:progress |
| Company Detail | companies + metric_time_series | Company + trend data |
| Settings/Team | organization_members | Members for current org |
| Settings/Billing | subscriptions + usage_tracking | Current plan + usage |

## Responsive Behavior
- Desktop: sidebar + main content (min-width: 1024px)
- Tablet: collapsed sidebar, hamburger toggle (768–1023px)
- Mobile: bottom tab bar replacing sidebar, stacked layouts (< 768px)
- PWA: installable, offline shows cached last dashboard state
