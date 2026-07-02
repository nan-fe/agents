#!/usr/bin/env bash
# Post a code-review report as a GitHub PR comment (no LLM — formatting only).
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: post-pr-comment.sh [--pr NUMBER] BODY_FILE

Post a markdown report to a GitHub pull request.

Options:
  --pr NUMBER   Pull request number (default: infer from current branch via gh)
  BODY_FILE     Path to markdown file to post as comment

Requires: gh CLI authenticated (gh auth status)
EOF
}

PR=""
BODY_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pr)
      PR="${2:?--pr requires a number}"
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      if [[ -z "$BODY_FILE" ]]; then
        BODY_FILE="$1"
        shift
      else
        echo "Unexpected argument: $1" >&2
        usage >&2
        exit 1
      fi
      ;;
  esac
done

if [[ -z "$BODY_FILE" || ! -f "$BODY_FILE" ]]; then
  echo "BODY_FILE is required and must exist." >&2
  usage >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found. Install GitHub CLI and run: gh auth login" >&2
  exit 1
fi

if [[ -z "$PR" ]]; then
  if ! PR="$(gh pr view --json number -q .number 2>/dev/null)"; then
    echo "Could not infer PR from current branch. Pass --pr NUMBER." >&2
    exit 1
  fi
fi

gh pr comment "$PR" --body-file "$BODY_FILE"
echo "Posted comment to PR #$PR"
