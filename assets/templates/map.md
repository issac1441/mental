---
id: model-map
kind: map
authority: mechanical
status: stale
sources:
  - {{SOURCE_ID}}
prerequisites: []
updated_at: {{TODAY}}
refresh_basis: []
---

# Model map

## Boundary

Describe the evidence-derived scope currently represented. Put interpretive boundaries in `Inferences and gaps`.

## Relationships

```mermaid
flowchart LR
    source["Supplied source"] --> model["Candidate mental model"]
```

## Representative scenario

Add the smallest source-backed scenario that tests whether the relationship map predicts an outcome.

## Counterexample or failure

Add one source-backed boundary case that prevents overgeneralization.

## Evidence

- `{{SOURCE_ID}}`: inspection pending

## Inferences and gaps

- Source inspection is incomplete.
- Link any open `mental/conflicts/` artifacts here.
