# fullstack-feature-loop

Layered full-stack guide: **Explore → Plan → Act-Observe → Final Verify**.

## Install

Publish this directory, or `cp -r fullstack-feature-loop ~/.cursor/skills/`.

## App repo setup

```bash
cp overlay-template.md /path/to/your-app/docs/feature-loop.overlay.md
# fill layers, tier1, final, invariants
```

Skill `docs/` only has [adoption.md](docs/adoption.md). Overlay file lives in **your app**, not here.

## Package

| File | Role |
|------|------|
| [SKILL.md](SKILL.md) | Workflow |
| [reference.md](reference.md) | Skip tree, verify keys |
| [examples.md](examples.md) | New feature / refactor / bugfix traces |
| [overlay-template.md](overlay-template.md) | Copy to app repo |
