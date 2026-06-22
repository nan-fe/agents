# Project Agent Guidelines

## Pre-commit

Install once:

```bash
pip install -r requirements-dev.txt
pip install -r backend/requirements.txt
pip install -e mcp-lark
pre-commit install
```

Hooks run on commit:

- **ruff** / **ruff-format** on `backend/` and `mcp-lark/`
- **pytest** for changed Python files (`scripts/pre-commit-pytest.sh`)
- **frontend-share lint** (`tsc --noEmit`) when `frontend-share/` changes

## Frontend Code Style

- Prefer arrow functions for frontend TypeScript and React code, including components, helpers, callbacks, and framework exports when the framework allows it.
- Use Tailwind CSS utility classes for styling. Avoid adding custom CSS unless Tailwind cannot express the behavior clearly or the style is truly global.
- Keep frontend changes consistent with the existing TypeScript, React, and Next.js patterns in the repository.

## Next.js App (`frontend-share`)

The production frontend lives in `frontend-share/` (Next.js App Router). Follow the detailed rules in [`frontend-share/AGENTS.md`](frontend-share/AGENTS.md), including:

- Prefer `useActionState` for async interactions with pending state (avoid manual `useState` + `try/finally` in components).
- Run `pnpm lint` and `pnpm build` in `frontend-share/` before merging (CI runs both on every push/PR).

### OpenAPI as the API type source of truth

- Backend OpenAPI is the single source of truth for frontend API types (`frontend-share/src/api/schema.d.ts`).
- After changing backend routes, request/response models, or OpenAPI metadata, regenerate types:

  ```bash
  # backend running on :8000
  cd frontend-share && pnpm gen:api
  ```

- Commit the updated `schema.d.ts` in the same PR as the backend API change. CI runs `scripts/check-openapi-contract.sh` (starts backend → `pnpm gen:api` → diff).

## Backend Python (`backend/`)

- Follow FastAPI and Pydantic conventions in [`.agents/skills/fastapi/SKILL.md`](.agents/skills/fastapi/SKILL.md) (`Annotated` dependencies, lifespan patterns, etc.).
- **Ruff** config lives in root [`pyproject.toml`](pyproject.toml); run `ruff check backend mcp-lark` and `ruff format backend mcp-lark` before merging.
- **Mypy** config lives in root [`pyproject.toml`](pyproject.toml) (`[tool.mypy]`, scope: `backend/app`). Install via `requirements-dev.txt`, then run:

  ```bash
  pip install -r requirements-dev.txt
  pip install -e mcp-lark   # needed for lark_im imports
  bash scripts/mypy-backend.sh
  ```

  Or from repo root: `python3 -m mypy`. The codebase is not yet fully typed; fix reported issues incrementally when touching related modules.
- Run tests before merging:

  ```bash
  cd backend
  pytest tests/ -m "not network"
  ```

- Default pytest config excludes `@pytest.mark.network` tests (external DuckDuckGo). Do not remove that marker without good reason.
- CI has no `backend/.env`; required Settings fields are injected via GitHub Actions `env` and `backend/tests/conftest.py` (dummy SiliconFlow/BASE_MODEL placeholders).
- Local dev: copy `backend/.env.example` → `backend/.env` with real keys.
- `@pytest.mark.integration` tests may require Playwright/Chromium and real URLs; keep them marked and excluded from default CI when they also need network.
- `mcp-lark` is installed editable (`pip install -e ../mcp-lark`) for Lark integration in backend tests and runtime.

## MCP Lark (`mcp-lark/`)

```bash
cd mcp-lark
pytest tests/
```
