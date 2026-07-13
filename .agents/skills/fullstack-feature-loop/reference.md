# Reference

Read when skipping layers, picking verify commands, or healing failures. Commands live in the **project overlay**, not here.

---

## Layer Skip Question Tree

Document answers in Context Brief.

```
Request
├─ UI only (style/copy/layout; no API/schema)? → UI only
├─ Bugfix, same contract, no migration? → touched layer(s) only
├─ Refactor, same external contract & schema? → touched layer(s) only; extra regression tests
├─ Schema / migration change? → Data (+ API if DTO/storage access changes)
├─ API contract added/changed/breaking refactor? → affected layers; contract_regen before UI tier-1
├─ Data+API done, UI deferred? → note in Brief
├─ Streaming (SSE/WebSocket)? → API handler + UI client; check overlay streaming rules
└─ New feature, no feature doc? → default all layers; create doc after Final Verify
```

**One primary data store per feature.** Cross-store access must be explicit in Brief.

---

## Verify Commands (from overlay)

| When | Overlay key |
|------|-------------|
| After Data task | `tier1.data` |
| After API task | `tier1.api` |
| After UI task | `tier1.ui` |
| After UI + API contract changed | `tier1.ui_with_contract` |
| All layers done | `final.full` |
| Data / API / UI only | `final.data` / `final.api` / `final.ui` |

---

## Self-Heal Observation Format

```markdown
## Observation (attempt N/3)
**Command**: `...` · **Exit**: N
\`\`\`
<full stdout/stderr>
\`\`\`
**Hypothesis**: ... · **Fix**: ...
```

Stop after 3 failures; escalate to systematic debugging if root cause unclear.

---

## Overlay Fields

| Field | Purpose |
|-------|---------|
| `layers[]` | Data / API / UI paths |
| `context.*` | Index, route_table, template |
| `invariants[]` | Global rules for Brief |
| `conventions` | Per-layer patterns |
| `tier1.*` / `final.*` | Verify commands |
| `contract_regen` | Client types from API schema (optional) |

Template: [overlay-template.md](overlay-template.md) — copy into app repo.

---

## Feature Context Doc (optional)

Per-feature doc should cover: scope + entry, three layers (or N/A), pitfalls (2–4), real test paths.
