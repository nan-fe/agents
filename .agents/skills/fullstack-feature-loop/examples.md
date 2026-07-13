# Traces

Illustrative outputs; commands come from the project overlay.

---

## A — New feature (API + UI)

**Ask:** Add CSV export on reports, like existing PDF export.

**Brief (excerpt):** Change type: new feature · Contract: additive · Layers: skip Data, run API+UI · Ref: pdf-export-handler, export-button.

**Plan:** API endpoint + tests → tier-1 · contract_regen → UI button + client → tier-1 · Final: `final.full` · Update feature doc.

---

## B — Refactor (breaking API + schema)

**Ask:** Split `users.profile` JSON blob into normalized columns; update profile API and settings page.

**Brief (excerpt):** Change type: refactor · Contract: breaking · Layers: Data+API+UI · Migration: backfill script, deprecate old field one release.

**Plan:**

1. **Data** — migration + backfill → tier-1
2. **API** — new DTO, compat shim or versioned route → tier-1
3. **UI** — contract_regen → settings form bound to new fields → tier-1
4. **Final** — `final.full` · doc + rollout notes

**Refactor checks:** compat window documented · old clients/tests updated · no silent data loss.

---

## C — Bugfix (UI only)

**Ask:** Dashboard chart stale after filter change.

**Brief:** Change type: bugfix · Contract: none · Layers: UI only.

**Plan:** fix hook deps + test → tier-1 · Final: `final.ui`.

---

## Matrix

| | New feature | Refactor (breaking) | Bugfix |
|--|-------------|---------------------|--------|
| Data | If schema | Usually | Rare |
| API | If contract | Usually | If server bug |
| UI | Usually | Usually | Often alone |
| contract_regen | If new API | If API changed | No |
