# code-review-ai

Cursor-native parallel code review for this repository: **deterministic tooling** (ruff, tsc, pytest, OpenAPI) plus **LLM review agents**. Results merge, dedupe, and filter to confidence ≥ 80.

## Trigger

In Cursor:

- `/code-review` or `运行 code review`
- `code review --comment` — also post to current PR
- `code review --plan "must: add DELETE endpoint"` — requirements traceability

Entry: [`.cursor/skills/code-review-ai/SKILL.md`](../.cursor/skills/code-review-ai/SKILL.md) → [`orchestrator/SKILL.md`](orchestrator/SKILL.md)

## Architecture

```
Phase 0: run-deterministic-checks.sh  → ruff / tsc / pytest / OpenAPI
    ↓
Parallel Task subagents:
  compliance-1 | cross-file-impact | obvious-errors | git-blame
  (+ requirements-traceability when PR/plan text exists)
    ↓
Merge → filter confidence ≥ 80 → terminal or gh pr comment
```

## Agents

| Phase / Agent | Skill | Focus |
|---------------|-------|-------|
| **Phase 0** | [`scripts/run-deterministic-checks.sh`](scripts/run-deterministic-checks.sh) | Runtime/type errors via ruff, tsc, pytest, OpenAPI sync |
| 1 | [`skills/compliance-reviewer/SKILL.md`](skills/compliance-reviewer/SKILL.md) | AGENTS.md + `.cursor/rules` |
| 2 | [`skills/cross-file-impact/SKILL.md`](skills/cross-file-impact/SKILL.md) | Stale imports, API renames, missing schema.d.ts |
| 3 | [`skills/obvious-errors/SKILL.md`](skills/obvious-errors/SKILL.md) | Logic bugs, edge cases, error paths |
| 4 | [`skills/git-blame-context/SKILL.md`](skills/git-blame-context/SKILL.md) | History-based regression risk |
| 5 (optional) | [`skills/requirements-traceability/SKILL.md`](skills/requirements-traceability/SKILL.md) | PR/plan vs diff — missing features |

## Diff modes

| Mode | When |
|------|------|
| `branch changes` (default) | Merge-base with `main` + staged/unstaged |
| `uncommitted changes` | Working tree only |
| `--base <branch>` | Custom base |

## Output

- Terminal Markdown table (default)
- `--comment` → [`scripts/post-pr-comment.sh`](scripts/post-pr-comment.sh)

## Complementary tools

| Tool | Use for |
|------|---------|
| **code-review-ai** | Project rules, tooling, cross-file, requirements, blame |
| **Bugbot** (`/review-bugbot`) | General bug scan |
| **Security Review** (`/review-security`) | Security-focused review |

## Schema

[`schemas/issue.schema.json`](schemas/issue.schema.json)
