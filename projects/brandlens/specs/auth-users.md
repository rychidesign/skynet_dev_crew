# Auth and Users

## References
- Related: specs/security.md — RLS policies, role enforcement, JWT validation
- Related: specs/data-model.md — organizations, organization_members tables
- Related: specs/billing.md — plan assignment on org creation
- Related: SPECS.md — role definitions and plan overview

## Auth Provider
Supabase Auth with two methods:
- **Email + password** — standard signup/login with email confirmation
- **Google OAuth** — one-click sign in via Google

## Registration Flow

1. User signs up via email/password or Google OAuth.
2. Supabase creates entry in `auth.users`.
3. Post-signup hook (database trigger or Edge Function) creates:
   a. New `organizations` row with `plan='free'`, auto-generated slug from user email domain.
   b. New `organization_members` row with `role='owner'` linking user to org.
   c. New `subscriptions` row with `plan='free'`, `status='active'`.
   d. New `usage_tracking` row for current month with `audits_used=0`.
4. User lands on `/onboarding` — prompted to name their organization and add first company.

## Login Flow

1. User submits credentials or clicks Google sign-in.
2. Supabase returns JWT access token + refresh token.
3. Frontend stores tokens in Supabase client (automatic cookie/localStorage handling).
4. All subsequent API calls include `Authorization: Bearer <access_token>`.
5. Backend validates JWT and resolves user's organization and role.

## Session Management

| Property | Value |
|---|---|
| Access token lifetime | 1 hour (Supabase default) |
| Refresh token lifetime | 7 days |
| Token refresh | Automatic via `supabase.auth.onAuthStateChange()` |
| Logout | Clears tokens client-side, invalidates refresh token server-side |

## Organization and Team Management

### Invitation Flow
1. Admin/Owner enters email address on team management page.
2. Backend creates `organization_members` row with `role` set, `accepted_at=NULL`.
3. System sends invitation email (Supabase Auth invite or custom email).
4. Invitee clicks link → if no account, signs up first → then `accepted_at` is set.
5. Invitee now sees the organization's data.

### Role Management
- Owner can change any member's role (except demoting themselves unless transferring ownership).
- Admin can change roles of analyst and viewer members.
- Analyst and viewer cannot change roles.
- Removing a member: sets a soft-delete or hard-deletes the `organization_members` row.

### Multi-Org Support
A user can belong to multiple organizations. Frontend provides org switcher:
- Current org stored in client state (Zustand) and URL context.
- All API calls scoped to the selected organization.
- RLS automatically filters data by org membership.

## Role Permissions Matrix

| Action | Owner | Admin | Analyst | Viewer |
|---|---|---|---|---|
| View dashboards and reports | Yes | Yes | Yes | Yes |
| View audit details | Yes | Yes | Yes | Yes |
| Trigger new audit | Yes | Yes | Yes | No |
| Create/edit/delete companies | Yes | Yes | Yes | No |
| Manage team members | Yes | Yes | No | No |
| Change member roles | Yes | Yes (limited) | No | No |
| Access billing and plan | Yes | No | No | No |
| Delete organization | Yes | No | No | No |
| Export reports | Yes | Yes | Yes | No |

## Password Requirements
- Minimum 8 characters
- Supabase Auth handles password hashing (bcrypt)
- Password reset via email link (Supabase built-in)

## OAuth Scopes (Google)
- `email` — required for account identification
- `profile` — optional, for display name and avatar

## Frontend Auth Components
- `/login` — email/password form + Google OAuth button
- `/signup` — registration form + Google OAuth button
- `/forgot-password` — email input, triggers reset email
- `/reset-password` — new password form (accessed via email link)
- `/onboarding` — org name + first company setup (shown once after signup)
- `/settings/team` — member list, invite form, role dropdowns
