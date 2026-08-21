# Artifact contract

All shared artifacts live under `mental/`. Private learner state lives under `.mental/` and must be ignored by Git.

## Shared layout

```text
mental/
├── index.md
├── sources.md
├── glossary.md
├── lenses/                # reusable role-conditioned explanation lenses, on demand
├── model/
│   └── map.md
├── concepts/
├── scenarios/
├── architecture.md       # repository mode, on demand
├── contracts/            # repository mode, on demand
├── decisions/            # repository mode, on demand
├── changes/              # repository mode, on demand
├── learning/
│   └── path.md           # learning mode, on demand
├── misconceptions/       # learning mode, on demand
└── exercises/            # learning mode, on demand
```

Do not create optional artifacts without source-backed content.

## Private layout

```text
.mental/
├── .gitignore
├── profile.md
├── mastery.json
└── sessions/
```

`.mental/.gitignore` must ignore everything except itself. Never put personal answers, inferred ability, or session history under `mental/`.

Do not persist an agent-inferred Lens, View, Detail, or learning preference automatically. Add it to `profile.md` only when the user explicitly asks to remember it. Treat host memory as an optional weak signal, not as a replacement for this consent boundary.

`mastery.json` uses this private, non-scoring shape:

```json
{
  "version": 1,
  "updated_at": "2026-08-15",
  "concepts": {
    "concept-id": {
      "state": "working",
      "evidence": ["2026-08-15: predicted the base scenario with one prompt"],
      "updated_at": "2026-08-15"
    }
  }
}
```

`state` must be `unknown`, `exposed`, `working`, or `verified`. Evidence is a short factual note, not a transcript, personality judgment, or numeric score.

## Markdown frontmatter

Every Markdown artifact under `mental/` must begin with:

```yaml
---
id: stable-kebab-id
kind: concept
status: draft
sources:
  - source-id
prerequisites: []
updated_at: 2026-08-15
---
```

Required fields:

- `id`: stable lowercase identifier; do not encode a translated title in it.
- `kind`: `index`, `sources`, `glossary`, `lens`, `map`, `concept`, `scenario`, `architecture`, `contract`, `decision`, `change`, `learning-path`, `misconception`, or `exercise`.
- `status`: `draft`, `canonical`, or `stale`.
- `sources`: source IDs from `mental/sources.md`; use `[]` only for the source catalog itself or a human-authored index.
- `prerequisites`: artifact IDs required first; use `[]` when none.
- `updated_at`: ISO date of the last material update.

`index.md` may also declare `mode: repository|learning|hybrid` and `language`. Additional fields are allowed when they remain stable and useful.

A `kind: lens` artifact lives under `mental/lenses/`. In addition to the required fields, it defines `assumes`, `prioritizes`, `vocabulary`, and `default_views`. These fields are YAML lists. `default_views` may contain only `anchor`, `map`, `mechanism`, `scenario`, and `evidence`. A lens describes a role-conditioned explanation strategy; it must not encode a person's identity, protected traits, or a permanent ability judgment.

## Claim provenance

Prefix important claims with one of these labels:

- `[observed]` — directly supported by a cited source.
- `[inferred]` — agent synthesis awaiting confirmation.
- `[agreed]` — explicitly confirmed conceptual truth.
- `[conflict]` — source/implementation truth and canonical truth disagree.

Put source IDs beside the claim or in the nearest Evidence section. A canonical artifact may contain observations and agreed claims; unresolved inference must remain visibly inferred. Never remove a conflict merely to make validation pass.

## Draft promotion gate

Before changing `status: draft` to `status: canonical`, present the human with:

1. proposed boundaries and relationships;
2. inferred causal claims or invariants;
3. representative success and failure scenarios;
4. known gaps or conflicting evidence.

Promote only the explicitly accepted artifacts. Record the accepted conceptual claims as `[agreed]`; do not label every sentence agreed.

## Source policy

Use only sources the user supplied or explicitly placed in scope. The current repository counts as supplied when the skill is invoked from that repository. A provided URL may be fetched with host capabilities. Do not discover unrelated web sources without explicit permission.

`mental/sources.md` assigns stable source IDs and records type, location, scope, and retrieval/revision information. Preserve inaccessible or changed sources as gaps instead of replacing them silently.

## Language

Write titles and explanatory content in the user's language. Keep paths, IDs, enum values, and frontmatter keys in English.
