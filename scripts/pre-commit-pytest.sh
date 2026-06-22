#!/usr/bin/env bash
# Run pytest for changed Python files in backend/ and mcp-lark/.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

declare -A backend_tests=()
declare -A mcp_tests=()
backend_run_all=false
mcp_run_all=false

add_backend_test() {
  local path="$1"
  [[ -f "$path" ]] && backend_tests["$path"]=1
}

add_mcp_test() {
  local path="$1"
  [[ -f "$path" ]] && mcp_tests["$path"]=1
}

map_backend_source_to_tests() {
  local file="$1"
  local base
  base="$(basename "$file" .py)"
  local candidate="backend/tests/test_${base}.py"

  if [[ -f "$candidate" ]]; then
    add_backend_test "$candidate"
    return
  fi

  local matches=0
  local match
  shopt -s nullglob
  for match in backend/tests/test_"${base}"*.py backend/tests/test_*"${base}"*.py; do
    add_backend_test "$match"
    matches=1
  done
  shopt -u nullglob

  if [[ "$matches" -eq 0 ]]; then
    backend_run_all=true
  fi
}

map_mcp_source_to_tests() {
  local file="$1"
  local base
  base="$(basename "$file" .py)"
  local candidate="mcp-lark/tests/test_${base}.py"

  if [[ -f "$candidate" ]]; then
    add_mcp_test "$candidate"
    return
  fi

  mcp_run_all=true
}

for file in "$@"; do
  [[ "$file" == *.py ]] || continue

  case "$file" in
    backend/tests/*)
      add_backend_test "$file"
      ;;
    backend/*)
      map_backend_source_to_tests "$file"
      ;;
    mcp-lark/tests/*)
      add_mcp_test "$file"
      ;;
    mcp-lark/*)
      map_mcp_source_to_tests "$file"
      ;;
  esac
done

if [[ ${#backend_tests[@]} -eq 0 && "$backend_run_all" == false && ${#mcp_tests[@]} -eq 0 && "$mcp_run_all" == false ]]; then
  exit 0
fi

run_backend_pytest() {
  local tests=()
  if [[ ${#backend_tests[@]} -gt 0 && "$backend_run_all" == false ]]; then
    for path in "${!backend_tests[@]}"; do
      tests+=("${path#backend/}")
    done
    (
      cd backend
      pytest -m "not network" --tb=short -q "${tests[@]}"
    )
    return
  fi

  (
    cd backend
    pytest tests/ -m "not network" --tb=short -q
  )
}

run_mcp_pytest() {
  local tests=()
  if [[ ${#mcp_tests[@]} -gt 0 && "$mcp_run_all" == false ]]; then
    for path in "${!mcp_tests[@]}"; do
      tests+=("${path#mcp-lark/}")
    done
    (
      cd mcp-lark
      pytest --tb=short -q "${tests[@]}"
    )
    return
  fi

  (
    cd mcp-lark
    pytest tests/ --tb=short -q
  )
}

if [[ ${#backend_tests[@]} -gt 0 || "$backend_run_all" == true ]]; then
  run_backend_pytest
fi

if [[ ${#mcp_tests[@]} -gt 0 || "$mcp_run_all" == true ]]; then
  run_mcp_pytest
fi
