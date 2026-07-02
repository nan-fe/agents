---
name: code-review-orchestrator
description: Use when the user triggers /code-review or asks to review branch/PR changes before merge in this repository.
---

# Code Review Orchestrator

Orchestrate **Phase 0 tooling** plus **4–5 parallel Task subagents** for xhs-multi-agent-creator. Follow this skill exactly for `/code-review`, `code review`, or similar.

## User flags

| Flag | Effect |
|------|--------|
| (default) | `DIFF_MODE=branch changes`, terminal output |
| `uncommitted changes` / `dirty` | Working tree only |
| `--base <branch>` | Override merge-base branch |
| `--comment` | Post report via `code-review-ai/scripts/post-pr-comment.sh` |
| `--pr <N>` | PR number for `--comment` |
| `--plan <text>` or requirements in message | Feed `requirements-traceability` agent |

Default base: `main` (or repo default remote HEAD).

---

## Phase 0 — Deterministic checks (run first, always)

From `REPO_ROOT`:

```bash
export BASE_REF="$(git merge-base HEAD main 2>/dev/null || true)"
bash code-review-ai/scripts/run-deterministic-checks.sh
```

Parse stdout as JSON array → `TOOLING_ISSUES`. Each item has `agent: "tooling"`, `confidence: 100`.

**Do not skip Phase 0** even if diff is empty — tooling may still matter for staged files.

If a tool is missing (no ruff, no node_modules), note in report **Warnings** but continue.

Optional deep security scan: remind user `/review-security` is complementary.

---

## Phase 1 — Collect context

### Diff collection

**branch changes** (default):

```bash
BASE=$(git merge-base HEAD "${BASE_BRANCH:-main}")
git diff "$BASE" --unified=3
git diff --cached "$BASE" --unified=3
git diff --stat "$BASE"
```

**uncommitted changes**:

```bash
git diff --unified=3
git diff --cached --unified=3
git diff --stat
```

If diff is empty **and** `TOOLING_ISSUES` is empty → print `Code review found no issues (confidence ≥ 80).` and stop.

### Changed files

```bash
git diff --name-only "$BASE" 2>/dev/null; git diff --cached --name-only "$BASE" 2>/dev/null
```

Dedupe → `CHANGED_FILES`.

### Guidelines (for compliance agent)

Read: `AGENTS.md`, `frontend-share/AGENTS.md`, `.cursor/rules/*.mdc`, `.cursor/skills/*/SKILL.md`

### Requirements text (for optional agent 5)

Try in order:

1. User `--plan` or requirements in message
2. `gh pr view --json body,title` (if `gh` available)
3. Else `REQUIREMENTS_SOURCE=none`

### Reviewer skills to embed in Task prompts

- `code-review-ai/skills/compliance-reviewer/SKILL.md`
- `code-review-ai/skills/cross-file-impact/SKILL.md`
- `code-review-ai/skills/obvious-errors/SKILL.md`
- `code-review-ai/skills/git-blame-context/SKILL.md`
- `code-review-ai/skills/requirements-traceability/SKILL.md`

---

## Phase 2 — Launch parallel Task subagents

**Mandatory (one message, all concurrent):**

| Task | description | Skill | readonly |
|------|-------------|-------|----------|
| A | `CR compliance-1` | compliance-reviewer | true |
| B | `CR cross-file-impact` | cross-file-impact | true |
| C | `CR obvious-errors` | obvious-errors | true |
| D | `CR git-blame` | git-blame-context | true |

- `subagent_type`: `generalPurpose`
- `run_in_background`: `false`

**Optional Task E — requirements-traceability**

Launch **in the same parallel batch** when `REQUIREMENTS_TEXT` is non-empty:

- `description`: `CR requirements`
- Include `REQUIREMENTS_TEXT`, `REQUIREMENTS_SOURCE`, DIFF, CHANGED_FILES

If no requirements, skip Task E (do not launch empty).

### Prompt skeleton

```text
REPO_ROOT: <abs path>
DIFF_MODE: branch changes
BASE_REF: <sha>
CHANGED_FILES: [...]
TOOLING_ISSUES: <JSON from Phase 0>   # obvious-errors only
REQUIREMENTS_TEXT: ...                 # requirements agent only

DIFF:
<unified diff>

--- SKILL ---
<full skill markdown>

Return ONLY a JSON array. No markdown fences.
```

---

## Phase 3 — Parse responses

1. Start with `TOOLING_ISSUES` (already JSON)
2. Parse each subagent JSON array; strip accidental markdown fences
3. Retry failed parse **once** per agent
4. Note failures in **Warnings**

---

## Phase 4 — Filter, dedupe, sort

### Filter

Drop `confidence < 80`. **Never filter tooling** (`confidence: 100`).

### Dedupe

Key: `file + ":" + line + ":" + normalize(message)` (lowercase, collapse whitespace)

Keep higher confidence; merge agent names if tie.

Dedupe across agents (same location + similar message).

### Sort

1. tooling first (confidence 100)
2. then confidence descending
3. file, line ascending

---

## Phase 5 — Format output

```markdown
## Code Review Report

**Diff mode:** <mode>
**Base:** <BASE_REF>
**Issues (confidence ≥ 80):** <n>
**Requirements review:** included | skipped (no PR/plan text)

### Tooling (Phase 0)
| Confidence | Agent | Location | Issue |
...

### Review agents
| Confidence | Agent | Location | Issue |
...

### Details
- **file:line** (agent, score): rule_ref — evidence
```

Empty after filter: `Code review found no issues (confidence ≥ 80).`

### `--comment`

Write markdown to temp file → `bash code-review-ai/scripts/post-pr-comment.sh [--pr N] <file>`

---

## Phase 6 — Do not auto-fix

Report only unless user asks to fix.

---

## Failure modes

| Situation | Action |
|-----------|--------|
| Diff too large (>500 files) | Sample critical paths; warn in report |
| OpenAPI check needs backend | Note skip if `check-openapi-contract.sh` fails to start server |
| No requirements | Skip agent 5; state in report |
| Subagent JSON invalid twice | Warn; use other agents + tooling |

Schema: `code-review-ai/schemas/issue.schema.json`
