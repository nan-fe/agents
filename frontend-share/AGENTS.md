# frontend-share Agent Guidelines

Next.js App Router app for share pages, auth, and the studio UI. React 19 with React Compiler enabled (`reactCompiler: true` in `next.config.mjs`).

## App Router layout

- Routes live under `src/app/` (`page.tsx`, `layout.tsx`, Route Handlers in `route.ts`).
- Prefer Server Components by default; add `'use client'` only when the component needs hooks, browser APIs, or event handlers.
- Server Actions live in `'use server'` modules (e.g. `src/lib/actions/register-action.ts`); keep them thin and delegate to `src/lib/*` services.
- API rewrites proxy most backend paths; **do not** add rewrites for SSE or long-running proxies — use dedicated Route Handlers (`app/dialog/generate/route.ts`, `app/product_info/[...path]/route.ts`) to avoid buffering/timeouts.

## Async UI: `useActionState`

- Prefer `useActionState` for form submits and other user-triggered async work with pending/error state.
- Pair with `startTransition` when dispatching from non-form handlers (see `product-pool.tsx`, `result-display.tsx`).
- Server Actions return a serializable state object; client wrappers may add navigation or `signIn` after success (`register-form.tsx`).

```tsx
const [state, formAction, isPending] = useActionState(registerAction, initialState);
```

Avoid manual `useState` + `try/finally` for the same pending/submit flow unless React Compiler or Server Actions cannot apply.

## SSE streaming

- Parse streams with `parseSSEStream` (`src/lib/sse/sse-parser.ts`); ingest/dedupe via `sse-stream-ingest.ts` and track `Last-Event-ID` with `sse-event-id.ts`.
- Client connection lifecycle: `useSSEClient` (`src/app/studio/hooks/use-sse-client.ts`) — retries, reconnect with `lastEventId`, optional fallback.
- Resume failures: handle `RESUME_FAILED` / `RESUME_FAILED_CODE` from `src/lib/sse/sse-resume.ts` in the UI.
- Browser-facing dialog SSE goes through `src/services/api.ts`; server-side proxies use `fetchWithReport` where appropriate.

## Prisma

- Schema: `prisma/schema.prisma`. Migrations under `prisma/migrations/`.
- Singleton client: `src/lib/prisma.ts` (dev hot-reload safe via `globalThis`).
- Local DB: set `DATABASE_URL` in `.env` (see `.env.example`). Commands: `pnpm db:migrate`, `pnpm db:migrate:deploy`, `pnpm db:generate`.
- `pnpm build` runs `prisma generate` before `next build`; run migrations separately in deploy (Docker entrypoint / ops).

## Sentry (Better Stack compatible)

- Shared init options: `src/lib/sentry.ts` (`getSentryInitOptions`, `isSentryEnabled`).
- Wired in `instrumentation.ts`, `instrumentation-client.ts`, `sentry.server.config.ts`, `sentry.edge.config.ts`.
- **Server/route fetch errors**: use `fetchWithReport` (`src/lib/fetch-with-report.ts`) — reports network failures and non-2xx (configurable via `ignoreStatuses`, `ignoreClientErrors`, `skipReport`).
- **Client API helpers**: `reportError` in `src/services/api.ts` for caught errors in the browser.
- **React error boundaries**: `global-error.tsx` and route `error.tsx` call `Sentry.captureException`.
- Do not send PII; `sendDefaultPii: false`. Tag operations with `tags: { operation, source }` for filtering.

## OpenAPI types

- Generated types: `src/api/schema.d.ts` via `pnpm gen:api` (backend must be running on `:8000`).
- Import component types from `src/api/schema.d.ts` in `src/services/api.ts`; keep hand-written fetch logic there, not in generated file.

## CI checklist

Before opening a PR touching this package:

```bash
pnpm lint       # tsc --noEmit
pnpm test       # Vitest: sse-parser, middleware
pnpm build
pnpm test:e2e   # Playwright smoke (auto: Postgres, migrate, build)
```

If backend API changed, also run `pnpm gen:api` and commit `src/api/schema.d.ts`, or locally verify with `bash scripts/check-openapi-contract.sh` from repo root.

## Testing

- **Vitest** (`src/**/*.test.ts`): pure utilities and middleware with mocks — e.g. `src/lib/sse/sse-parser.test.ts`, `src/middleware.test.ts`.
- **Playwright** (`e2e/`): register/login → `/studio` smoke. `pnpm test:e2e` prefers **Docker Postgres on `:5433`** (`docker-compose.e2e.yml`); if Docker is not running, it falls back to `DATABASE_URL` in `frontend-share/.env` (your local `:5432`). Set `E2E_SKIP_POSTGRES=1` when Postgres is already provided (CI).
