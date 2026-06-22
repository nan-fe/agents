#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCHEMA="$ROOT/frontend-share/src/api/schema.d.ts"
BASELINE="$(mktemp)"
GENERATED="$(mktemp)"

restore_schema() {
  if [[ -f "$BASELINE" ]]; then
    mv "$BASELINE" "$SCHEMA"
  fi
}

cleanup() {
  rm -f "$GENERATED"
}

trap 'restore_schema; cleanup' EXIT

cp "$SCHEMA" "$BASELINE"

(
  cd "$ROOT/frontend-share"
  pnpm gen:api
)

cp "$SCHEMA" "$GENERATED"
restore_schema
trap - EXIT
cleanup

if diff -u "$SCHEMA" "$GENERATED"; then
  echo "OpenAPI types are in sync."
else
  echo "OpenAPI types drifted. Run: cd frontend-share && pnpm gen:api" >&2
  exit 1
fi
