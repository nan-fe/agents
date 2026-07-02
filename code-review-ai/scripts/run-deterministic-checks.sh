#!/usr/bin/env bash
# Phase 0: run ruff, tsc, pytest, and optional OpenAPI check on changed paths.
# Emits a JSON array of issues to stdout (always exit 0 unless script error).
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

BASE="${BASE_REF:-}"
if [[ -z "$BASE" ]]; then
  BASE="$(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null || echo "")"
fi

collect_changed_files() {
  {
    if [[ -n "$BASE" ]]; then
      git diff --name-only "$BASE" 2>/dev/null || true
      git diff --cached --name-only "$BASE" 2>/dev/null || true
    else
      git diff --name-only 2>/dev/null || true
      git diff --cached --name-only 2>/dev/null || true
    fi
  } | sort -u
}

CHANGED="$(collect_changed_files)"
ISSUES="[]"

append_issue() {
  local file="$1" line="$2" message="$3" evidence="$4"
  # Escape for JSON (minimal)
  file="${file//\\/\\\\}"; file="${file//\"/\\\"}"
  message="${message//\\/\\\\}"; message="${message//\"/\\\"}"
  evidence="${evidence//\\/\\\\}"; evidence="${evidence//\"/\\\"}"
  ISSUES="$(python3 -c "
import json, sys
issues = json.loads(sys.argv[1])
issues.append({
    'agent': 'tooling',
    'file': sys.argv[2],
    'line': int(sys.argv[3]),
    'message': sys.argv[4],
    'confidence': 100,
    'rule_ref': 'deterministic-check',
    'evidence': sys.argv[5],
})
print(json.dumps(issues))
" "$ISSUES" "$file" "$line" "$message" "$evidence")"
}

has_prefix() {
  local prefix="$1"
  echo "$CHANGED" | grep -q "^${prefix}" || return 1
}

# --- ruff (backend / mcp-lark) ---
if has_prefix "backend/" || has_prefix "mcp-lark/"; then
  if command -v ruff >/dev/null 2>&1; then
    RUFF_OUT="$(mktemp)"
    if ! ruff check backend mcp-lark --output-format=json >"$RUFF_OUT" 2>/dev/null; then
      python3 -c "
import json, sys
issues = json.loads(sys.argv[1])
for v in json.load(open(sys.argv[2])):
    issues.append({
        'agent': 'tooling',
        'file': v.get('filename', 'backend/'),
        'line': v.get('location', {}).get('row', 1),
        'message': f\"ruff {v.get('code', 'E')}: {v.get('message', '')}\",
        'confidence': 100,
        'rule_ref': 'ruff',
        'evidence': v.get('code', ''),
    })
print(json.dumps(issues))
" "$ISSUES" "$RUFF_OUT" >"${RUFF_OUT}.json"
      ISSUES="$(cat "${RUFF_OUT}.json")"
    fi
    rm -f "$RUFF_OUT" "${RUFF_OUT}.json"
  fi
fi

# --- tsc (frontend-share) ---
if has_prefix "frontend-share/"; then
  if [[ -d "$ROOT/frontend-share/node_modules" ]]; then
    TSC_OUT="$(mktemp)"
    if ! (cd "$ROOT/frontend-share" && pnpm lint >"$TSC_OUT" 2>&1); then
      ISSUES="$(python3 -c "
import json, re, sys
issues = json.loads(sys.argv[1])
pat = re.compile(r'^(?P<path>[^(\s]+)\((?P<line>\d+),\d+\):\s+error\s+(?P<code>TS\d+):\s+(?P<msg>.+)$')
with open(sys.argv[2]) as f:
    for raw in f:
        m = pat.match(raw.rstrip())
        if not m:
            continue
        fpath = m.group('path')
        if not fpath.startswith('frontend-share/'):
            fpath = 'frontend-share/' + fpath
        issues.append({
            'agent': 'tooling',
            'file': fpath,
            'line': int(m.group('line')),
            'message': f\"tsc {m.group('code')}: {m.group('msg')}\",
            'confidence': 100,
            'rule_ref': 'tsc',
            'evidence': raw.rstrip(),
        })
print(json.dumps(issues))
" "$ISSUES" "$TSC_OUT")"
    fi
    rm -f "$TSC_OUT"
  fi
fi

# --- targeted pytest (backend) ---
if has_prefix "backend/"; then
  if command -v pytest >/dev/null 2>&1; then
    PYTEST_FILES=()
    while IFS= read -r f; do
      [[ -z "$f" ]] && continue
      base="$(basename "$f" .py)"
      candidate="backend/tests/test_${base}.py"
      if [[ -f "$candidate" ]]; then
        PYTEST_FILES+=("$candidate")
      fi
    done <<< "$(echo "$CHANGED" | grep '^backend/app/' || true)"

    if [[ ${#PYTEST_FILES[@]} -gt 0 ]]; then
      PYTEST_OUT="$(mktemp)"
      UNIQUE_TESTS=()
      while IFS= read -r t; do UNIQUE_TESTS+=("$t"); done < <(printf '%s\n' "${PYTEST_FILES[@]}" | sort -u)
      if ! (cd "$ROOT/backend" && pytest "${UNIQUE_TESTS[@]}" -m "not network" -q --tb=line >"$PYTEST_OUT" 2>&1); then
        fail_line="$(grep -E '^FAILED|^ERROR' "$PYTEST_OUT" | head -1 || echo "pytest failed")"
        append_issue "backend/" 1 "pytest failed for changed modules" "$fail_line"
      fi
      rm -f "$PYTEST_OUT"
    fi
  fi
fi

# --- OpenAPI contract (backend routes/models changed) ---
if echo "$CHANGED" | grep -qE '^backend/app/(routes|models|schemas|api)/'; then
  if [[ -x "$ROOT/scripts/check-openapi-contract.sh" ]]; then
    OAPI_OUT="$(mktemp)"
    if ! (cd "$ROOT" && bash scripts/check-openapi-contract.sh >"$OAPI_OUT" 2>&1); then
      snippet="$(tail -5 "$OAPI_OUT" | tr '\n' ' ')"
      append_issue "frontend-share/src/api/schema.d.ts" 1 "OpenAPI types out of sync with backend; run pnpm gen:api" "$snippet"
    fi
    rm -f "$OAPI_OUT"
  fi
fi

echo "$ISSUES"
