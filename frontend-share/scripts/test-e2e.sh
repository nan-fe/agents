#!/usr/bin/env bash
# End-to-end test entrypoint: Postgres → migrate → build → Playwright.
set -euo pipefail

log() {
  printf '\n[test:e2e] %s\n' "$*"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT="$(cd "$FRONTEND_DIR/.." && pwd)"

E2E_POSTGRES_PORT="${E2E_POSTGRES_PORT:-5433}"

if [[ "${E2E_SKIP_POSTGRES:-}" == "1" && -n "${DATABASE_URL:-}" ]]; then
  E2E_DATABASE_URL="$DATABASE_URL"
elif [[ -z "${E2E_DATABASE_URL:-}" ]]; then
  E2E_DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:${E2E_POSTGRES_PORT}/xhs_auth"
fi

export AUTH_SECRET="${AUTH_SECRET:-e2e-auth-secret-minimum-32-characters}"
export DATABASE_URL="$E2E_DATABASE_URL"
export FORCE_COLOR="${FORCE_COLOR:-1}"

load_dotenv_database_url() {
  local env_file="$FRONTEND_DIR/.env"
  [[ -f "$env_file" ]] || return 1

  local line
  line="$(grep -E '^DATABASE_URL=' "$env_file" | tail -1 || true)"
  [[ -n "$line" ]] || return 1

  line="${line#DATABASE_URL=}"
  line="${line#\"}"
  line="${line%\"}"
  line="${line#\'}"
  line="${line%\'}"

  printf '%s' "$line"
}

prisma_db_ok() {
  pnpm exec prisma db execute --schema=prisma/schema.prisma --stdin <<<'SELECT 1' >/dev/null 2>&1
}

docker_daemon_running() {
  docker info >/dev/null 2>&1
}

try_docker_e2e_postgres() {
  E2E_DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:${E2E_POSTGRES_PORT}/xhs_auth"
  export DATABASE_URL="$E2E_DATABASE_URL"

  if prisma_db_ok; then
    log "Postgres ready via Docker e2e DSN (${E2E_DATABASE_URL})"
    return 0
  fi

  if ! docker_daemon_running; then
    return 1
  fi

  log "Starting e2e Postgres on port ${E2E_POSTGRES_PORT} (docker-compose.e2e.yml)..."
  if ! docker compose -f "$ROOT/docker-compose.e2e.yml" up postgres -d --wait; then
    return 1
  fi

  local attempt
  for attempt in $(seq 1 30); do
    if prisma_db_ok; then
      log "Postgres ready via Docker e2e DSN (${E2E_DATABASE_URL})"
      return 0
    fi
    if (( attempt == 1 || attempt % 5 == 0 )); then
      log "Waiting for Docker Postgres on 127.0.0.1:${E2E_POSTGRES_PORT}... (${attempt}/30)"
    fi
    sleep 2
  done

  return 1
}

try_local_env_postgres() {
  local env_url
  env_url="$(load_dotenv_database_url || true)"
  [[ -n "$env_url" ]] || return 1

  E2E_DATABASE_URL="$env_url"
  export DATABASE_URL="$E2E_DATABASE_URL"

  if ! prisma_db_ok; then
    return 1
  fi

  log "Postgres ready via frontend-share/.env (${E2E_DATABASE_URL})"
  return 0
}

ensure_postgres() {
  if [[ "${E2E_SKIP_POSTGRES:-}" == "1" ]]; then
    local attempt
    for attempt in $(seq 1 30); do
      if prisma_db_ok; then
        log "Postgres ready (${E2E_DATABASE_URL})"
        return 0
      fi
      if (( attempt == 1 || attempt % 5 == 0 )); then
        log "Waiting for CI Postgres... (${attempt}/30)"
      fi
      sleep 2
    done
    echo "[test:e2e] Cannot connect with DATABASE_URL=${E2E_DATABASE_URL} (E2E_SKIP_POSTGRES=1)." >&2
    exit 1
  fi

  if try_docker_e2e_postgres; then
    return 0
  fi

  if try_local_env_postgres; then
    log "Docker unavailable; using local Postgres from .env"
    return 0
  fi

  echo "[test:e2e] Could not connect to Postgres." >&2
  echo "Option A — start Docker Desktop, then rerun: pnpm test:e2e" >&2
  echo "Option B — ensure frontend-share/.env DATABASE_URL works and database xhs_auth exists:" >&2
  echo "  createdb xhs_auth   # if needed" >&2
  echo "  pnpm db:migrate:deploy" >&2
  exit 1
}

cd "$FRONTEND_DIR"

log "Step 1/4: ensure Postgres"
ensure_postgres
log "Using DATABASE_URL=${E2E_DATABASE_URL}"

log "Step 2/4: prisma migrate deploy"
pnpm exec prisma migrate deploy

log "Step 3/4: production build"
pnpm build

log "Step 4/4: Playwright (install browser if needed, then run tests)"
if [[ "${CI:-}" == "true" ]]; then
  pnpm exec playwright install chromium --with-deps
else
  pnpm exec playwright install chromium
fi

exec pnpm exec playwright test --reporter=list "$@"
