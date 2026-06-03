# Project Agent Guidelines

## Frontend Code Style

- Prefer arrow functions for frontend TypeScript and React code, including components, helpers, callbacks, and framework exports when the framework allows it.
- Use Tailwind CSS utility classes for styling. Avoid adding custom CSS unless Tailwind cannot express the behavior clearly or the style is truly global.
- Keep frontend changes consistent with the existing TypeScript, React, and Next.js patterns in the repository.

## React 19 & React Compiler (`frontend-ts`)

The Vite app in `frontend-ts/` uses React 19 with React Compiler enabled. Follow the detailed rules in [`frontend-ts/AGENTS.md`](frontend-ts/AGENTS.md), including:

- Prefer `useActionState` for async interactions with pending state (avoid manual `useState` + `try/finally` in components).
- Run `pnpm lint:react` in `frontend-ts/` before merging; `react-hooks/todo` and `react-hooks/unsupported-syntax` must be zero errors.
