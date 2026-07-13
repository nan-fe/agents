---
name: fullstack-feature-loop
description: >-
  Use when implementing full-stack features, refactoring requirements across
  persistence/API/UI, or cross-layer bugfixes; when the user changes behavior,
  contracts, or data shape across layers. Not for typos, comments-only, or
  trivial one-line edits.
---

# Full-Stack Feature Loop

**Explore → Plan → Act-Observe → Final Verify** for layered full-stack work.

Skip tree, observation format, overlay fields: [reference.md](reference.md). Traces: [examples.md](examples.md).

---

## Overlay (required)

No overlay ships here. Adopter copies [overlay-template.md](overlay-template.md) into the **target app repo** and fills it.

Search target repo (not this package): `.cursor/skills/*/feature-loop.overlay.md` → `.agents/skills/*/overlay.md` → `**/feature-loop.overlay.md`.

**Missing overlay:** follow [docs/adoption.md](docs/adoption.md), then continue.

---

## Flow

```
Explore → Plan → [per layer: implement → tier-1 → heal≤3] → Final Verify
```

Default layer order: **Data → API → UI** (from overlay `layers[]`). Skip layers per [reference.md](reference.md#layer-skip-question-tree).

---

## Explore — Context Brief (required before code)

1. Overlay `context.index` + `route_table` → Feature Context Doc
2. Overlay `conventions` + similar existing code
3. Classify **change type** and affected layers

```markdown
## Context Brief
- **Scope**: [one line + entry]
- **Change type**: new feature | bugfix | refactor
- **Contract impact**: none | additive | breaking (note migration/compat)
- **Layers**: [run / skip + why]
- **Data source**: [primary store or none]
- **Invariants**: [overlay checklist]
- **Reference files**: [2–5]
- **Planned tasks**: [ ] Data  [ ] API  [ ] UI
```

**Refactor:** note what stays compatible, what migrates, and whether UI can ship after API.

---

## Plan

Per running layer: small checklist + `tier-1: <overlay command>`.

- API contract change → `contract_regen` before UI tier-1 (if overlay defines it)
- Breaking refactor → order: data migration → API (compat if needed) → UI

---

## Act-Observe

After **each** layer: run tier-1 immediately. Fail → [observation format](reference.md#self-heal-observation-format) → fix → retry (max 3).

**Prohibited:** claim done without tier-1; skip tier-1 between layers.

Use **verification-before-completion**: fresh command output as evidence.

---

## Final Verify

Overlay `final.<scope>` for touched layers. Sync feature docs if routes, flows, or schema changed.

---

## Done when

- [ ] Context Brief + Plan written
- [ ] Each layer tier-1 passed
- [ ] Final Verify passed with evidence
- [ ] Contract regen + doc sync if applicable
