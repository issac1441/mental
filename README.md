# mental

`mental` is an agent-native plugin that closes the gap between agent execution and human understanding. It helps people orient, predict, decide, review, learn, and repair a model from inside Claude Code or Codex.

It is not a standalone CLI, hosted service, or replacement for source material. It has no backend, account, telemetry, MCP server, or external LLM API. The interface is nine skills; bundled Python scripts are internal deterministic helpers.

[繁體中文指南](README.zh-TW.md)

Design notes: [background and research framing](docs/design-background.md) · [STE100 evaluation](docs/ste100-evaluation.md)

## Quickstart

### 1. Load `mental`

For Claude Code development:

```sh
git clone https://github.com/issac1441/mental.git /absolute/path/to/mental
cd /path/to/the-repository-you-want-to-understand
claude --plugin-dir /absolute/path/to/mental
```

For Codex, install `mental` from a configured plugin marketplace as described in [Install and validate](#install-and-validate), then open the target repository:

```sh
codex -C /path/to/the-repository-you-want-to-understand
```

### 2. Ask first—no setup required

```text
/mental:understand How does a request move through this repository?
$mental:understand How does a request move through this repository?
```

`understand` reads the current session and the smallest relevant repository or supplied-source evidence. It works before `mental/` exists and never writes files. If the model will be useful again, it may offer `build`; persistence is optional, not an entrance fee.

### 3. Predict and decide a change

```text
/mental:change Add request timeouts without changing failure semantics.
/mental:change Tell me the actual effect of option A in the current plan.
```

When a prediction can expose a consequential model gap, `change` asks the human first, waits for an answer or `skip`, then compares it with evidence. A direct-answer request stays direct. Human approval applies to desired behavior and tradeoffs—not unsupported factual claims.

### 4. Review what actually happened

```text
/mental:review Review the current diff.
/mental:quiz current-change items=12 feedback=end format=mixed
```

`review` reconstructs Before → After, exposes choices discovered only after approval as Decision Surprises, and checks the bounded `Model × Harness × Task Class` trust unit.

### 5. Persist only after value appears

```text
/mental:build Save the reusable model we just established.
```

`build` is an advanced persistence skill. It stores regenerable mechanical artifacts, conceptual drafts with verification requirements, decision history, and first-class conflicts. It does not create a wiki for coverage's sake.

## Interaction model

`mental` uses **Lens × Job**:

- **Lens** is the session role whose knowledge, vocabulary, concerns, and decisions should shape the explanation: `general`, `engineer`, `architect`, `pm`, `operator`, `student`, `researcher`, or a custom lens.
- **Job** is what the person needs now: `orient`, `decide`, `predict`, `verify`, or `repair`.

The agent infers both from the current goal and session. Manual `lens=` and `job=` values win. Semantic Views—anchor, map, mechanism, scenario, and evidence—remain internal selection vocabulary. Experienced users may supply `views=` as an advanced override, but first-time users are not expected to know it.

`mental` does not print repetitive context headers. It discloses Lens, Job, or Views only when user-selected, non-default, uncertain, or actionable.

## Skills

### Primary skills

| Skill | Use it when | Writes by default |
| --- | --- | --- |
| `understand` | You need an immediate explanation or orientation | No |
| `change` | You need to predict, compare, or decide before implementation | No; records only when asked |
| `review` | The agent finished and you need the actual change model | No |
| `learn` | You want diagnosis and adaptive source-bound teaching | Private state only with evidence and explicit persistence consent |
| `practice` | You want answer-adaptive repair and transfer | Private state only with evidence and explicit persistence consent |
| `quiz` | You want a complete fixed-coverage assessment | Private results only with explicit persistence consent |

### Advanced persistence and maintenance

| Skill | Use it when |
| --- | --- |
| `build` | A useful model, lens, decision, or conflict should persist |
| `sync` | Registered sources changed and durable artifacts need refresh |
| `doctor` | A durable workspace's authority, evidence, decisions, conflicts, links, or privacy may be invalid |

Every skill has its own authoritative Input contract. Host interfaces may show descriptions or default prompts, but enumerated argument autocomplete is not guaranteed across Claude Code and Codex.

## Artifact authority

Artifacts say who may update them:

| Authority | Meaning | States |
| --- | --- | --- |
| `mechanical` | Regenerable from registered evidence | `current`, `stale` |
| `conceptual` | Durable working explanation with a verification basis | `draft`, `active`, `stale` |
| `decision` | Human intent, tradeoff, or accepted change | `pending`, `accepted`, `rejected`, `superseded` |

`active` means “current working model with recorded verification,” not infallible truth. Recognition or “looks good” is not verification. Mechanical artifacts refresh without a human truth judgment; human decisions cannot make unsupported facts true.

Conflicts live under `mental/conflicts/` with stable IDs, `open|resolved` status, both claims and evidence, owner, and resolution history. Consequential choices live in an append-preserving decision ledger under `mental/decisions/`.

Shared artifacts live in `mental/`. Private goals, answers, progress, and sessions live in gitignored `.mental/`.

## Representative journeys

**Vibe coding:** `understand → change → human prediction/decision → Plan Mode → implementation → review → optional quiz → advanced sync`

**Quick question:** `understand`, with no artifact setup.

**Product decision:** `understand lens=pm → change job=decide → human decision → Plan Mode → review`

**Learning:** `learn supplied source → practice → quiz → optional build`

**Durable model:** `understand → proven reuse value → build → later sync/doctor`

## Install and validate

### Claude Code

```sh
claude --plugin-dir /absolute/path/to/mental
claude plugin validate /absolute/path/to/mental
```

For persistent distribution, add the repository to a Claude Code marketplace and install `mental` from it.

### Codex

Install `mental` from a configured plugin marketplace, then use `/skills` or type `$` to select a skill. For a non-default local marketplace:

```sh
codex plugin marketplace add /absolute/path/to/marketplace
codex plugin add mental@marketplace-name
```

The package uses `.codex-plugin/plugin.json` plus `skills/*/SKILL.md`. Claude and Codex share the same skill semantics.

### OpenCode compatibility

OpenCode support is currently documentation-only and does not promise native namespace parity. Copy or link `skills/`, `references/`, `scripts/`, and `assets/` under one `.agents/` directory while preserving relative paths. Skills appear by unscoped names such as `understand` and `change`.

## Development

The repository has no runtime dependencies:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/scaffold_workspace.py /tmp/mental-demo --mode hybrid --language en
python3 scripts/validate_workspace.py /tmp/mental-demo
```

The Python helpers are internal skill implementation details, not a supported end-user CLI.

## License

[0BSD](LICENSE). Use, copy, modify, and distribute it freely. Redistribution does not require attribution or preservation of a copyright notice.
