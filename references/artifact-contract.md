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
refresh_basis:
  - source-id@revision
prerequisites: []
updated_at: 2026-08-15
---
```

Required fields:

- `id`: stable lowercase identifier.
- `kind`: `index`, `sources`, `glossary`, `lens`, `map`, `concept`, `scenario`, `architecture`, `contract`, `decision`, `conflict`, `change`, `learning-path`, `misconception`, or `exercise`.
- `authority`: `mechanical`, `conceptual`, or `decision`.
- `status`: a state allowed by the artifact authority or kind.
- `sources`: IDs from `mental/sources.md`; use `[]` only for the source catalog or a draft human-authored index. An active index must cite a registered source.
- `prerequisites`: artifact IDs required first.
- `updated_at`: ISO date of the last material update.

`mental/sources.md` is the single source catalog. No other artifact may use
`kind: sources`, and every source ID heading in the catalog must be unique.

Kinds allow these authorities:

| Kind | Allowed authority |
| --- | --- |
| `index`, `lens`, `learning-path`, `misconception`, `exercise` | `conceptual` |
| `sources`, `map` | `mechanical` |
| `glossary`, `concept`, `scenario`, `architecture`, `contract` | `mechanical` or `conceptual` |
| `decision`, `conflict`, `change` | `decision` |

For a dual-authority kind, classify the artifact by its update contract, not by
how factual its prose sounds:

- Use `mechanical` only when a deterministic agent pass can stably regenerate
  the representation from registered evidence without choosing desired behavior
  or resolving competing interpretations.
- Use `conceptual` when the representation depends on a useful abstraction,
  boundary choice, prerequisite structure, or teaching interpretation.
- Use `decision` only for intended behavior, tradeoffs, ownership, or accepted
  change.

Every non-catalog mechanical artifact declares `refresh_basis` entries in the
form `<source-id>@<revision>`. A `current` mechanical artifact needs at least one
concrete basis, lists each basis source in `sources`, and contains a real
second-level `Evidence` section with non-placeholder content that cites at least
one listed source ID. If any of those are unavailable, keep it `stale`; do not
infer a safe refresh from the body alone. Use `build` to establish or rebuild a
missing regeneration basis before a later `sync` can refresh it.

Allowed state machines:

| Authority or kind | Status values | Update rule |
| --- | --- | --- |
| `mechanical` | `current`, `stale` | Agent refreshes from registered evidence |
| `conceptual` | `draft`, `active`, `stale` | Activation requires recorded verification, not assent |
| `decision` | `pending`, `accepted`, `rejected`, `superseded` | Human decides; preserve decision history |
| `kind: conflict` | `open`, `resolved` | Resolve with evidence or a recorded decision |

`index.md` may also declare `mode: repository|learning|hybrid` and `language`. Additional fields are allowed when stable and useful.

A `kind: lens` artifact lives under `mental/lenses/`, uses conceptual authority, and defines YAML lists named `assumes`, `concerns`, and `vocabulary`. It describes role needs, not identity, protected traits, or permanent ability.

## Evidence and interpretation

Do not require repetitive inline `[observed]`, `[inferred]`, or `[agreed]` labels. Use artifact structure instead:

- `Evidence` contains exact source, code, test, or runtime support.
- `Model` or domain-specific sections contain the current representation.
- `Inferences and gaps` contains synthesis that evidence does not directly establish.
- `Conflicts` links first-class conflict artifacts.

Keep source IDs beside material claims or in the nearest Evidence section. An `active` conceptual artifact remains a working model with a verification basis, not guaranteed truth.

Every conceptual artifact declares these YAML lists:

```yaml
verification_basis: []
checked_predictions: []
known_gaps: []
conflicts: []
```

Draft and stale artifacts may leave them empty. Before changing a conceptual
artifact to `active`, record a non-placeholder verification basis plus at least
one checked `success:` prediction and one checked `failure:` or `boundary:`
prediction. `conflicts` contains artifact IDs for first-class conflict records;
use an empty list only when the check found none. Recognition and assent are not
activation evidence.

Verification basis entries use one of these stable forms:

- `source:<source-id>` for a listed catalog source;
- `artifact:<artifact-id>` for corroboration by another shared artifact;
- `owner:<evidence>` for a named domain-owner validation;
- `runtime:<evidence>` for an observed runtime result;
- `transfer:<artifact-id>` for a recorded transfer demonstration.

The type stays in English; the evidence text can follow the user's language.
Checked predictions use `success:`, `failure:`, or `boundary:` (ASCII or
full-width colon) followed by a meaningful, non-placeholder claim.

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
supersedes: []
superseded_by: []
status_history:
  - 2026-08-15:pending
```

Allowed values:

- `decision_owner`: `human`, `agent`, `shared`, or `unassigned`;
- `surfaced`: `pre-approval` or `post-approval`;
- `consequential`: `true` or `false`;
- `reversibility`: `easy`, `costly`, `irreversible`, or `unknown`.

Preserve prior options, rejected alternatives, and status history. Do not rewrite an accepted decision as if the replacement had always been chosen.
The last `status_history` entry must match the current status. A superseded
decision names its replacement in `superseded_by`; the replacement names prior
records in `supersedes`, and both records link back to each other. History starts
at `pending`; it may move to `accepted`, `rejected`, or `superseded`.
`accepted` and `rejected` may later move only to `superseded`, which is terminal.
An artifact cannot supersede itself. During `doctor`, compare current history and
replacement links with the Git baseline when available. Prior entries must stay
in order and remain a prefix of the current record. This check detects working
tree rewrites; it is not tamper-proof after Git history itself is rewritten.

A `kind: change` also records `prediction_status` as `attempted`, `skipped`, or
`not-applicable`, `supersedes` and `superseded_by` lists, plus append-preserving
`status_history`. Do not store the person's prediction answer unless they
explicitly ask to record it.

Decision Surprise Rate for one reviewed change is:

`consequential post-approval decisions ÷ all consequential decisions discovered by that review`

Report `N/A` when the denominator is zero or review coverage is incomplete. Do not turn it into a global trust score.

## Three gates

- **Mechanical refresh:** registered evidence and the recorded refresh basis are sufficient for stable regeneration; no human truth approval.
- **Conceptual activation:** requires source/test support, checked success and failure predictions, known gaps/conflicts, and a recorded verification basis.
- **Human decision:** accepts desired behavior or tradeoffs; it cannot validate unsupported facts.

Recognition or “looks good” is not conceptual verification. A learner's understanding is tracked separately through prediction, explanation, transfer, and boundary evidence.

## Source catalog

Use only sources supplied or placed in scope. The current repository counts as supplied. A provided URL may be fetched with host capabilities; do not expand research scope without permission.

Each `mental/sources.md` entry starts with a unique `## <source-id>`. A localized title may follow an em dash, for example `## source-runtime — 執行期證據`.

## Validation semantics

`doctor` separates structure from readiness. A workspace made entirely of valid
drafts can report `Structure: valid` and `Readiness: incomplete`. Drafts, stale
artifacts, pending decisions, and open conflicts are legitimate work states, not
schema failures; they must remain visible in the readiness report.

The validator reports whether Git tracking and history privacy checks were
verified, unavailable, or failed. A non-Git workspace may still be structurally
valid, but `doctor` must not describe its private-state isolation or decision
history as verified.

## Language

Write titles and explanatory content in the user's language. Keep paths, IDs, enum values, and frontmatter keys in English.
