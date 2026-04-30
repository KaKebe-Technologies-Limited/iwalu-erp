# Frontend Development Context

**Role**: Frontend Developer (Next.js/React)  
**Focus**: UI components, pages, API integration, state management  
**Ignore**: Django models, database migrations, DRF serializers

## My Responsibilities
- Next.js pages and routing
- React components (Server & Client)
- TanStack Query hooks for API calls
- Zustand stores for state
- shadcn/ui component usage
- Tailwind styling
- Form validation with react-hook-form

## Not My Concern
- Django models
- Database schema
- DRF ViewSets
- Backend business logic
- Python code

## Quick Commands
```bash
# Run from /frontend directory
pnpm run dev
pnpm run lint
pnpm run type-check
```

## Standards
Refer to Frontend Standards (Next.js) in @../CLAUDE.md

---

# Phase 7a — Onboarding Flows (Frontend Work Required)

The backend has implemented a full email-based onboarding system. The frontend needs to build these flows.

---

## 1. Tenant Registration → Pending Verification Screen

**Current state**: `/auth/register` exists and submits to `POST /api/tenants/register/`.

**What needs to change**: After a successful 201 response, do NOT redirect to the dashboard. Instead:

1. Store the `domain` value from the response (e.g., `acmefuels.nexuserp.com`) in component state or sessionStorage.
2. Redirect to a new page: `/auth/verify-pending`
3. Show: "We've sent a verification email to {email}. Click the link in the email to activate your account."
4. The admin is **not** active yet — do not issue tokens or navigate to dashboard.

**Response shape** (`POST /api/tenants/register/` → 201):
```json
{
  "tenant": { "schema_name": "acmefuels", "name": "Acme Fuels Ltd", ... },
  "domain": "acmefuels.nexuserp.com",
  "admin_user": { "email": "...", "role": "admin", "is_active": false },
  "message": "..."
}
```

**New page to create**: `app/auth/verify-pending/page.tsx`
- Static informational screen, no API calls
- "Didn't receive it? Check your spam folder." copy
- Link back to `/auth/login`

---

## 2. Email Verification Handler

The backend sends a verification link pointing to:
```
https://nexuserp.com/api/tenants/verify-email/?token=<uuid>
```

This is a **backend URL**, not a frontend page. The backend verifies the token and returns JSON. The frontend needs an intermediary page that calls this and handles the redirect.

**Option A — Frontend intercept page (recommended)**

Configure the backend's verify URL in `.env` to point to a Next.js page instead:
```
VERIFY_EMAIL_FRONTEND_URL=https://nexuserp.com/auth/verify-email
```
Then the backend would send: `https://nexuserp.com/auth/verify-email?token=<uuid>`

Create `app/auth/verify-email/page.tsx`:
```typescript
'use client';
// 1. Read ?token= from URL searchParams
// 2. Call GET /api/tenants/verify-email/?token=<token>
// 3. On success: store { access, refresh } in Zustand auth store
//    then window.location.href = data.redirect_url  (crosses subdomain boundary)
// 4. On error: show error message with link back to /auth/register
```

**Response shape** (`GET /api/tenants/verify-email/?token=...` → 200):
```json
{
  "access": "eyJ...",
  "refresh": "eyJ...",
  "redirect_url": "https://acmefuels.nexuserp.com/dashboard",
  "tenant": { "schema_name": "acmefuels", "name": "Acme Fuels Ltd" },
  "message": "Email verified. Your account is now active."
}
```

**Important**: `redirect_url` crosses a subdomain boundary. Use `window.location.href` (hard navigation), not Next.js `router.push`. The tokens should be stored before the redirect so the target subdomain's auth store can hydrate from them.

> Coordinate with backend: the backend currently sends the verify link to `/api/tenants/verify-email/`. If the frontend intercept approach is adopted, update `VERIFY_EMAIL_FRONTEND_REDIRECT` in backend env and the backend will send the link to the frontend page instead. Otherwise the backend URL can return a redirect response to the frontend page.

**Option B — Backend redirects to frontend**

The backend `verify-email` endpoint already returns JSON. Alternatively it can be changed to return an HTTP 302 redirect to a frontend page with the tokens as query params (less secure). Option A is preferred.

---

## 3. Staff Invitation Accept Page

New page: `app/accept-invite/page.tsx` (or `app/auth/accept-invite/page.tsx`)

This page lives on the **tenant subdomain** (`acmefuels.nexuserp.com/accept-invite?token=<uuid>`).

```typescript
'use client';
// 1. Read ?token= from URL searchParams
// 2. Show form: First Name, Last Name, Username, Password, Confirm Password
// 3. On submit: POST /api/users/accept-invite/
//    { token, first_name, last_name, username, password }
// 4. On success: store JWT tokens, redirect to /dashboard
// 5. On error: show specific message (expired / already used / invalid)
```

**Response shape** (`POST /api/users/accept-invite/` → 201):
```json
{
  "user": { "id": 42, "email": "jane@acme.com", "role": "cashier", ... },
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

**Error responses to handle**:
- `"This invitation has expired."` → show "Ask your admin to resend the invitation."
- `"This invitation has already been used."` → show "This link has already been used. Try logging in."
- `"Invalid invitation token."` → show generic invalid link message.

---

## 4. Invite Staff UI (Admin Dashboard)

New component inside the existing Users/Employees page area.

### Hook: `lib/hooks/useInvitations.ts`

```typescript
// POST /api/users/invite/
export function useInviteUser() {
  return useMutation({
    mutationFn: (data: { email: string; role: string }) =>
      apiClient('/users/invite/', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['invitations'] }),
  });
}

// GET /api/users/invitations/
export function useInvitations() {
  return useQuery({
    queryKey: ['invitations'],
    queryFn: () => apiClient('/users/invitations/'),
  });
}
```

### UI components needed

1. **Invite button** on the Users page → opens a modal/sheet
2. **Invite modal**: email field + role dropdown (manager/cashier/attendant/accountant, no admin)
3. **Pending invitations list**: shows email, role, expiry, "Pending" / "Accepted" badge

---

## 5. TypeScript Types

```typescript
interface UserInvitation {
  id: number;
  email: string;
  role: 'manager' | 'cashier' | 'attendant' | 'accountant';
  is_pending: boolean;
  accepted_at: string | null;
  expires_at: string;
  created_at: string;
}

interface TenantRegistrationResponse {
  tenant: {
    id: number;
    schema_name: string;
    name: string;
    created_on: string;
  };
  domain: string;
  admin_user: {
    id: number;
    email: string;
    username: string;
    role: string;
    is_active: boolean;
  };
  message: string;
}

interface EmailVerificationResponse {
  access: string;
  refresh: string;
  redirect_url: string;
  tenant: { schema_name: string; name: string };
  message: string;
}
```

---

## 6. Summary of New Pages / Components

| Item | Path | Priority |
|------|------|----------|
| Verify-pending screen | `app/auth/verify-pending/page.tsx` | High |
| Email verification handler | `app/auth/verify-email/page.tsx` | High |
| Accept invite page | `app/accept-invite/page.tsx` | High |
| Invite modal component | `components/users/InviteUserModal.tsx` | High |
| Pending invitations list | `components/users/InvitationsList.tsx` | Medium |
| `useInvitations` hook | `lib/hooks/useInvitations.ts` | High |

---

## 7. Subdomain Architecture Note

All tenant dashboard pages must be served from `schema.nexuserp.com`. The API calls from those pages will hit `schema.nexuserp.com/api/...` which routes to the correct tenant schema.

When a user logs in at `schema.nexuserp.com/api/auth/login/`, the JWT token returned is scoped to that tenant context. Store it in Zustand + localStorage as normal. The `Authorization: Bearer <token>` header is what authenticates subsequent requests — the subdomain is what determines tenant schema routing.

The **accept-invite** page and all dashboard pages must run on the tenant subdomain. The **registration** and **verify-email** pages run on the main domain (`nexuserp.com`).
