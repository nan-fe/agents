---
name: code-review-ai
description: Use when the user asks for /code-review, PR review, or pre-merge audit of branch changes against AGENTS.md, tooling, and requirements.
---

# Code Review AI

Use when the user asks to run `/code-review`, `code review`, review a PR/branch, or audit changes before merge.

## Steps

1. **Read and follow** [`code-review-ai/orchestrator/SKILL.md`](../../../code-review-ai/orchestrator/SKILL.md).

2. **Parse flags**: `--comment`, `--pr N`, `uncommitted changes`, `--base branch`, `--plan "..."` or requirements in user message.

3. **Execute phases in order**:
   - **Phase 0**: `bash code-review-ai/scripts/run-deterministic-checks.sh`
   - **Phase 1**: diff + guidelines + PR/requirements text
   - **Phase 2**: launch 4 Task subagents in parallel (compliance-1, cross-file-impact, obvious-errors, git-blame); add requirements-traceability if PR/plan text exists
   - **Phase 3–5**: merge with tooling issues, filter ≥80, report; `--comment` if requested

## Do not

- Skip Phase 0 tooling
- Auto-fix unless asked
- Replace `/review-security` for deep security audits

## Related

- [`code-review-ai/README.md`](../../../code-review-ai/README.md)
- Skills: [`code-review-ai/skills/`](../../../code-review-ai/skills/)
