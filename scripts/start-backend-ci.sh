#!/usr/bin/env bash
# Start backend for CI / OpenAPI contract checks.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="${BACKEND_CI_LOG:-$ROOT/backend-ci.log}"
PID_FILE="${BACKEND_CI_PID:-$ROOT/backend.pid}"
HOST="${BACKEND_CI_HOST:-127.0.0.1}"
PORT="${BACKEND_CI_PORT:-8000}"
HEALTH_URL="${BACKEND_CI_HEALTH_URL:-http://${HOST}:${PORT}/health}"
MAX_WAIT_SECONDS="${BACKEND_CI_MAX_WAIT_SECONDS:-180}"
POLL_SECONDS="${BACKEND_CI_POLL_SECONDS:-2}"

export API_KEY="${API_KEY:-test-api-key}"
export BASE_MODEL="${BASE_MODEL:-deepseek-v4-flash}"
export MODEL_BASE_URL="${MODEL_BASE_URL:-https://example.com/v1}"
export COPYWRITE_MODEL="${COPYWRITE_MODEL:-test-copywrite-model}"
export EMBEDING_MODEL="${EMBEDING_MODEL:-BAAI/bge-large-zh-v1.5}"
export GENARATION_MODEL="${GENARATION_MODEL:-test-generation-model}"
export PLAN_MODEL="${PLAN_MODEL:-test-plan-model}"
export INTENT_MODEL="${INTENT_MODEL:-test-intent-model}"
export SILICONFLOW_API_KEY="${SILICONFLOW_API_KEY:-test-siliconflow-key}"
export SILICONFLOW_BASE_URL="${SILICONFLOW_BASE_URL:-https://api.siliconflow.cn/v1}"
export IMAGE_MODEL="${IMAGE_MODEL:-Kwai-Kolors/Kolors}"
export LANGCHAIN_API_KEY="${LANGCHAIN_API_KEY:-test-langsmith-key}"
export LANGCHAIN_PROJECT="${LANGCHAIN_PROJECT:-xhs-ci}"
export LANGCHAIN_TRACING_V2="${LANGCHAIN_TRACING_V2:-false}"
export CHROMA_DB_PATH="${CHROMA_DB_PATH:-/tmp/xhs-chroma-ci}"

PYTHON_BIN="$(command -v python || command -v python3)"

rm -f "$LOG" "$PID_FILE"

cd "$ROOT/backend"
"$PYTHON_BIN" -m uvicorn app.main:app --host "$HOST" --port "$PORT" >"$LOG" 2>&1 &
echo $! >"$PID_FILE"

deadline=$((SECONDS + MAX_WAIT_SECONDS))
while ((SECONDS < deadline)); do
  if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Backend process exited during startup. Log:" >&2
    cat "$LOG" >&2
    exit 1
  fi
  if curl -sf "$HEALTH_URL" >/dev/null; then
    echo "Ready: $HEALTH_URL"
    exit 0
  fi
  sleep "$POLL_SECONDS"
done

echo "Timed out waiting for $HEALTH_URL (${MAX_WAIT_SECONDS}s). Log:" >&2
tail -n 80 "$LOG" >&2 || true
exit 1
