#!/usr/bin/env bash
# Type-check backend/app using repo-root pyproject.toml ([tool.mypy]).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 -m mypy
