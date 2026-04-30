# Frontend Development - Gemini CLI Standards

**Focus**: UI/UX, Pages, API Integration, State Management
**Location**: `/frontend`

## Tech Stack
- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS + shadcn/ui
- **State**: TanStack Query (Server), Zustand (Client)
- **Forms**: react-hook-form + Zod

## Development Workflow
1. **Types**: Define TypeScript interfaces for backend models.
2. **Hooks**: Create/Update TanStack Query hooks in `lib/hooks/`.
3. **Components**: Build reusable UI in `components/`.
4. **Pages**: Implement routes in `src/app/`.

## Common Commands (Run from /frontend)
```bash
pnpm run dev
pnpm run lint
pnpm run type-check
```

## Components
- **Server Components**: Use for data fetching and static layouts.
- **Client Components**: Use `'use client'` for interactivity (forms, buttons, state).
- **Icons**: Use `lucide-react`.

---

Refer to root `GEMINI.md` for overall project standards.
