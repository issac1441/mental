# mental

`mental` helps you understand repositories and supplied learning material from inside Claude Code or Codex. Use it to explain a system, evaluate a planned change, review completed work, learn a topic, or test your understanding.

[繁體中文指南](README.zh-TW.md)

## Quickstart

### 1. Load the plugin

With Claude Code:

```sh
git clone https://github.com/issac1441/mental.git /absolute/path/to/mental
cd /path/to/your-project
claude --plugin-dir /absolute/path/to/mental
```

With Codex, install `mental` from a configured plugin marketplace, then open your project:

```sh
codex -C /path/to/your-project
```

Claude Code uses `/mental:<skill>`. Codex uses `$mental:<skill>` or the skill selector.

### 2. Understand something

```text
/mental:understand How does a request move through this repository?
$mental:understand How does a request move through this repository?
```

You can use `understand` immediately. A `mental/` workspace is not required.

### 3. Examine a change before implementation

```text
/mental:change Add request timeouts without changing failure behavior.
/mental:change Tell me the actual effect of option A in the current plan.
```

Answer the prediction question, or enter `skip` when you only want the explanation. The skill remains read-only unless you add `record=true`.

### 4. Review completed work

```text
/mental:review Review the current diff.
/mental:quiz current-change items=12 feedback=end format=mixed
```

`review` explains the Before → After behavior and reports findings. `quiz` checks whether you can reconstruct the change.

### 5. Learn from supplied material

```text
/mental:learn Teach me the event loop from docs/event-loop.md.
/mental:practice event-loop
/mental:quiz event-loop items=15
```

`learn` starts with 2–5 short diagnostic questions. Use `practice` for adaptive follow-up and `quiz` for a complete assessment.

### 6. Save a reusable model (optional)

```text
/mental:build Save the reusable model from this session.
```

After artifacts exist, use:

```text
/mental:sync
/mental:doctor
```

## Skill reference

| Skill | Syntax | Use it for | Default writes |
| --- | --- | --- | --- |
| `understand` | `<question> [job=...] [lens=...]` | Explain a repository, document, session, or supplied topic | None |
| `change` | `<intent-or-question> [job=decide\|predict] [lens=...] [record=true\|false]` | Compare a proposed change, option, plan, or TODO list | None |
| `review` | `[diff-or-ref] [job=verify\|predict] [lens=...]` | Explain and audit completed work | None |
| `learn` | `<goal-or-scope> [lens=...]` | Diagnose prerequisites and teach from supplied sources | Private progress only with consent |
| `practice` | `[scope] [lens=...]` | Run an answer-adaptive practice loop | Private progress only with consent |
| `quiz` | `[scope] [items=12] [feedback=end\|after-each] [format=mixed\|open\|mcq] [lens=...]` | Run a fixed 10–20 item assessment | Private results only with consent |
| `build` | `[source-or-scope] [mode=repository\|learning\|hybrid] [language=...]` | Create or extend reusable artifacts | `mental/` and `.mental/` |
| `sync` | `[scope]` | Refresh existing artifacts after sources change | `mental/` |
| `doctor` | `[scope] [repair=true\|false]` | Check artifact structure, links, evidence, conflicts, and privacy | None unless `repair=true` |

## Common options

You normally do not need to specify these values. The skill infers them from your request and current session.

- `lens=` controls the assumed role and vocabulary: `general`, `engineer`, `architect`, `pm`, `operator`, `student`, `researcher`, or a custom lens ID.
- `job=` controls the current task: `orient`, `decide`, `predict`, `verify`, or `repair`.
- `views=` is an advanced override. Accepted values are `anchor`, `map`, `mechanism`, `scenario`, and `evidence`.

Examples:

```text
/mental:understand lens=pm job=orient Explain the checkout service.
/mental:understand lens=architect job=predict How does failover work?
/mental:change job=decide Compare options A and B.
```

## Typical workflows

- Repository orientation: `understand`
- Planned implementation: `understand → change → Plan Mode → implementation → review`
- Explain a completed diff: `review → optional quiz`
- Guided learning: `learn → practice → quiz`
- Reusable workspace: `understand → optional build → later sync or doctor`

## Files created by mental

- `mental/` contains shared, versionable models, sources, scenarios, changes, decisions, and conflicts.
- `.mental/` contains private profiles, answers, mastery state, and session records. The scaffold configures Git to ignore this directory.

`understand` and `review` never write files. Learning skills save private progress only after you consent during the active session.

## Installation and validation

### Claude Code

```sh
claude --plugin-dir /absolute/path/to/mental
claude plugin validate /absolute/path/to/mental
```

For persistent installation, add the repository to a Claude Code marketplace and install `mental` from it.

### Codex

Install `mental` from a configured plugin marketplace, then use `/skills` or type `$` to select a skill. For a non-default local marketplace:

```sh
codex plugin marketplace add /absolute/path/to/marketplace
codex plugin add mental@marketplace-name
```

### OpenCode

OpenCode support is documentation-only. Copy or link `skills/`, `references/`, `scripts/`, and `assets/` under one `.agents/` directory while preserving their relative paths. Skills appear with unscoped names such as `understand` and `change`.

## Development

```sh
python3 -m unittest discover -s tests -v
python3 scripts/scaffold_workspace.py /tmp/mental-demo --mode hybrid --language en
python3 scripts/validate_workspace.py /tmp/mental-demo
```

The Python scripts are internal skill helpers, not a public CLI.

## Additional documentation

- [Design background and research framing](docs/design-background.md)
- [ASD-STE100 evaluation](docs/ste100-evaluation.md)

## License

[0BSD](LICENSE). You may use, copy, modify, and distribute this project without an attribution requirement.
