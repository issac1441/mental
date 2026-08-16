# Artifact contract

Shared artifacts live under `mental/`. Private learner state lives under `.mental/` and must be ignored by Git.

## Shared layout

```text
mental/
├── index.md
├── sources.md
├── glossary.md
├── lenses/                # reusable role-conditioned lenses, on demand
├── model/
│   └── map.md             # regenerable mechanical map
├── concepts/              # mechanical or conceptual, on demand
├── scenarios/             # mechanical or conceptual, on demand
├── architecture.md        # repository mode, on demand
├── contracts/             # repository mode, on demand
├── decisions/             # append-preserving decision ledger
├── conflicts/             # first-class open/resolved conflicts
├── changes/               # recorded model deltas, on demand
├── learning/
│   └── path.md            # learning mode, on demand
├── misconceptions/       # learning mode, on demand
└── exercises/            # learning mode, on demand
```

Do not create optional artifacts without source-backed content. On-demand directories may be absent from a fresh clone. `understand` must work before this layout exists; persistence is earned after the interaction demonstrates value.

## Private layout

```text
.mental/
├── .gitignore
├── profile.md
├── mastery.json
└── sessions/
```

`.mental/.gitignore` must ignore everything except itself. Never put personal answers, inferred ability, or session history under `mental/`.

Persist a Lens, Job, learning preference, or response-density preference only when the user explicitly asks. Treat host memory as an optional weak signal, not consent to persist.

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

`state` is `unknown`, `exposed`, `working`, or `verified`. Evidence is a short factual note, not a transcript, personality judgment, or numeric mastery score.

## Markdown frontmatter

Every Markdown artifact under `mental/` begins with:

```yaml
---
id: stable-kebab-id
kind: concept
authority: mechanical
status: current
sources:
  - source-id
prerequisites: []
updated_at: 2026-08-15
---
```

Required fields:

- `id`: stable lowercase identifier.
- `kind`: `index`, `sources`, `glossary`, `lens`, `map`, `concept`, `scenario`, `architecture`, `contract`, `decision`, `conflict`, `change`, `learning-path`, `misconception`, or `exercise`.
- `authority`: `mechanical`, `conceptual`, or `decision`.
- `status`: a state allowed by the artifact authority or kind.
- `sources`: IDs from `mental/sources.md`; use `[]` only for the source catalog or a human-authored index.
- `prerequisites`: artifact IDs required first.
- `updated_at`: ISO date of the last material update.

Allowed state machines:

| Authority or kind | Status values | Update rule |
| --- | --- | --- |
| `mechanical` | `current`, `stale` | Agent refreshes from registered evidence |
| `conceptual` | `draft`, `active`, `stale` | Activation requires recorded verification, not assent |
| `decision` | `pending`, `accepted`, `rejected`, `superseded` | Human decides; preserve decision history |
| `kind: conflict` | `open`, `resolved` | Resolve with evidence or a recorded decision |

`index.md` may also declare `mode: repository|learning|hybrid` and `language`. Additional fields are allowed when stable and useful.

A `kind: lens` artifact lives under `mental/lenses/`, uses conceptual authority, and defines YAML lists named `assumes`, `prioritizes`, and `vocabulary`. It describes role needs, not identity, protected traits, or permanent ability.

## Evidence and interpretation

Do not require repetitive inline `[observed]`, `[inferred]`, or `[agreed]` labels. Use artifact structure instead:

- `Evidence` contains exact source, code, test, or runtime support.
- `Model` or domain-specific sections contain the current representation.
- `Inferences and gaps` contains synthesis that evidence does not directly establish.
- `Conflicts` links first-class conflict artifacts.

Keep source IDs beside material claims or in the nearest Evidence section. An `active` conceptual artifact remains a working model with a verification basis, not guaranteed truth.

## Conflict artifacts

A `kind: conflict` artifact lives under `mental/conflicts/` and records:

- both claims and their evidence;
- why the mismatch matters;
- `owner` and `opened_at` frontmatter;
- the decision or evidence needed to resolve it;
- `resolved_at` when status becomes `resolved`.

Never delete an open conflict to make validation pass. Never resolve it by silently rewriting one side.

## Decision ledger

A consequential choice gets a `kind: decision` entry under `mental/decisions/` when the user asks to record the change or durable accountability is already in scope. Required frontmatter is:

```yaml
decision_owner: human
surfaced: pre-approval
consequential: true
reversibility: costly
```

Allowed values:

- `decision_owner`: `human`, `agent`, `shared`, or `unassigned`;
- `surfaced`: `pre-approval` or `post-approval`;
- `consequential`: `true` or `false`;
- `reversibility`: `easy`, `costly`, `irreversible`, or `unknown`.

Preserve prior options, rejected alternatives, and status history. Do not rewrite an accepted decision as if the replacement had always been chosen.

Decision Surprise Rate for one reviewed change is:

`consequential post-approval decisions ÷ all consequential decisions discovered by that review`

Report `N/A` when the denominator is zero or review coverage is incomplete. Do not turn it into a global trust score.

## Three gates

- **Mechanical refresh:** registered evidence is sufficient; no human truth approval.
- **Conceptual activation:** requires source/test support, checked success and failure predictions, known gaps/conflicts, and a recorded verification basis.
- **Human decision:** accepts desired behavior or tradeoffs; it cannot validate unsupported facts.

Recognition or “looks good” is not conceptual verification. A learner's understanding is tracked separately through prediction, explanation, transfer, and boundary evidence.

## Source catalog

Use only sources supplied or placed in scope. The current repository counts as supplied. A provided URL may be fetched with host capabilities; do not expand research scope without permission.

Each `mental/sources.md` entry starts with `## <source-id>`. A localized title may follow an em dash, for example `## source-runtime — 執行期證據`.

## Language

Write titles and explanatory content in the user's language. Keep paths, IDs, enum values, and frontmatter keys in English.
