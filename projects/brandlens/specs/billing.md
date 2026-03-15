# Billing

## References
- Related: specs/data-model.md — subscriptions, usage_tracking tables
- Related: specs/security.md — plan enforcement, webhook security
- Related: specs/auth-users.md — org creation assigns free plan
- Related: SPECS.md — plan comparison table

## Provider
Paddle (merchant of record). Paddle handles tax, invoicing, and payment processing. BrandLens stores subscription state locally for fast plan enforcement.

## Plan Definitions

| Limit | Free | Pro | Enterprise |
|---|---|---|---|
| `max_audits_per_month` | 1 | 20 | 100 |
| `max_queries_per_audit` | 10 | 50 | 200 |
| `allowed_platforms` | ["chatgpt","perplexity"] | all 5 | all 5 |
| `metrics_available` | ["GEO-01-ENT-SAL","GEO-13-SNT-POL","GEO-17-CRW-ACC"] + global | all 10 | all 10 |
| `competitor_analysis` | false | true | true |
| `max_competitors` | 0 | 5 | unlimited (999) |
| `trend_history_months` | 0 (last 2 audits only) | 12 | unlimited (999) |
| `max_team_members` | 1 | 5 | unlimited (999) |
| `recommendations_level` | "score_only" | "full" | "full_export" |

These limits are stored as a constant map in backend code (`PLAN_LIMITS`), not in the database. Plan name in `subscriptions.plan` is the lookup key.

## Paddle Integration

### Products and Prices
Create in Paddle dashboard:
- Product: "BrandLens Pro" → monthly and yearly price IDs
- Product: "BrandLens Enterprise" → monthly and yearly price IDs
- Free plan has no Paddle product (default state)

### Checkout Flow
1. User clicks "Upgrade" on billing page.
2. Frontend opens Paddle Checkout overlay using `Paddle.Checkout.open({ items: [{ priceId }] })`.
3. Paddle handles payment, creates subscription.
4. Paddle sends `subscription.created` webhook to backend.
5. Backend updates `subscriptions` and `organizations.plan`.

### Webhook Endpoint
`POST /webhooks/paddle` — no JWT auth, verified by Paddle signature.

### Webhook Events to Handle

| Event | Action |
|---|---|
| `subscription.created` | UPSERT subscriptions row, UPDATE organizations.plan |
| `subscription.updated` | UPDATE subscriptions (plan change, renewal) |
| `subscription.cancelled` | UPDATE subscriptions.status='cancelled', schedule plan downgrade |
| `subscription.past_due` | UPDATE subscriptions.status='past_due', send warning email |
| `subscription.paused` | UPDATE subscriptions.status='paused' |

### Downgrade Logic
When subscription cancelled or expired:
- Set `organizations.plan = 'free'` at `current_period_end`.
- Existing audit data remains accessible (read-only).
- New audits subject to free plan limits.
- Team members beyond limit: all retain read access, but only owner can trigger audits.

## Usage Metering

### Audit Counter
- `usage_tracking` table: one row per org per month.
- On audit trigger: `UPDATE usage_tracking SET audits_used = audits_used + 1 WHERE organization_id = $1 AND period_start = date_trunc('month', now())`.
- If no row exists for current month, INSERT with `audits_used = 1`.
- Check before audit: if `audits_used >= plan.max_audits_per_month` → reject.

### Period Reset
Monthly counter resets naturally — each month gets a new row. No cron job needed.

## Frontend Billing Pages

### /settings/billing (Owner only)
- Current plan display with usage stats (audits used / limit).
- Upgrade/downgrade buttons opening Paddle checkout.
- Billing history (fetched from Paddle API or stored locally).
- Cancel subscription button with confirmation dialog.

### Plan Gate Component
Reusable component wrapping any plan-restricted feature:
- Props: `requiredPlan`, `featureName`
- If user's plan insufficient: renders lock icon + "Upgrade to Pro" CTA instead of children.
- Used on: locked metrics, competitor analysis, recommendations, export buttons.

### Upgrade Prompts
Contextual upgrade CTAs shown when user hits a limit:
- "You've used 1/1 audits this month. Upgrade to Pro for 20 audits/month."
- "Competitor Analysis requires Pro plan."
- Metric cards for locked metrics show blurred preview + upgrade button.
