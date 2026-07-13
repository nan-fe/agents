# Adoption

1. Install skill (platform or copy to `~/.cursor/skills/`).
2. In **your app repo**: `cp overlay-template.md docs/feature-loop.overlay.md` (any path).
3. Fill `layers`, `context`, `invariants`, `conventions`, `tier1`, `final`.
4. Smoke test: UI-only change → UI layer only; API change → `contract_regen` before UI tier-1.

Update overlay when CI commands or invariants change.
