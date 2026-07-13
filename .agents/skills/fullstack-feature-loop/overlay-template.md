# Overlay Template

Copy into your **app repo**, fill, then use with [SKILL.md](SKILL.md). Not bundled — you create this file.

Suggested path: `docs/feature-loop.overlay.md` or `.agents/skills/<project>/overlay.md`

---

## layers

```yaml
layers:
  - id: data
    name: Data
    paths: [db/migrations/, prisma/]
  - id: api
    name: API
    paths: [src/server/, api/]
  - id: ui
    name: UI
    paths: [src/app/, src/components/]
```

## context

```yaml
context:
  index: docs/feature-index.md
  route_table:
    - { glob: "src/app/auth/**", doc: docs/features/auth.md }
  template: docs/features/_template.md
```

## invariants

```markdown
1. API schema is client type source of truth
2. Auth on all mutating routes
3. [add project-specific rules]
```

## conventions

| Layer | Pattern | Where |
|-------|---------|-------|
| UI | Centralized fetch + errors | `src/lib/api.ts` |
| API | Typed validation | `api/handlers/` |
| Tests | Exclude network by default | `tests/` |

## tier1

```yaml
tier1:
  data: npm run db:generate && npm test -- db/<module>
  api: npm run lint:api && npm test -- api/<module>
  ui: npm run lint && npm test
  ui_with_contract: npm run gen:api && npm run lint && npm test
```

## final

```yaml
final:
  data: npm test -- db/
  api: npm run lint:api && npm test -- api/
  ui: npm run lint && npm test && npm run build
  full: npm run lint && npm test && npm run build
```

## contract_regen (optional)

```yaml
contract_regen:
  command: npm run gen:api
  output: src/api/schema.d.ts
```

## layer_skip_answers

```
UI-only → ui | Same-contract bugfix → touched layers only
Same-contract refactor → touched layers + regression tests
Breaking refactor / new endpoint → all affected + contract_regen before ui
```
