# mental

`mental` is an agent-native plugin for building, explaining, and maintaining verifiable mental models. It helps people understand repositories and source-bound learning material from inside Claude Code or Codex.

It is not a standalone CLI, hosted service, or replacement for source material. The interface is a set of skills; the bundled Python scripts are private implementation helpers invoked by those skills.

[繁體中文指南](README.zh-TW.md)

## Why mental

Agents can produce implementation faster than people can rebuild a trustworthy model of it. `mental` changes the review unit from a large diff or document dump to a small set of relationships, scenarios, decisions, contracts, and evidence.

The core rules are:

- choose a Lens and Zoom instead of explaining everything;
- separate observed, inferred, human-agreed, and conflicting claims;
- create drafts before canonical artifacts;
- use source/code/test/runtime evidence as material truth and the canonical model as agreed conceptual truth;
- never silently reconcile the two when they disagree;
- keep shared models in `mental/` and personal learning state in gitignored `.mental/`.

## Skills

| Skill | Purpose | Writes by default |
| --- | --- | --- |
| `understand` | Explain a question through the smallest useful model | No |
| `build` | Build draft artifacts from supplied sources | Drafts only |
| `sync` | Propose source-to-model deltas | Draft delta only |
| `doctor` | Audit structure, evidence, drift, and privacy | No |
| `change` | Design a repository change before implementation | Draft brief only |
| `review` | Review implementation against the agreed model | No |
| `learn` | Diagnose gaps and teach adaptively | Private state only after learner evidence |
| `practice` | Test recall, transfer, and boundaries | Private state only after learner evidence |

Claude Code exposes plugin skills as `/mental:<skill>`. Codex exposes installed skills through `/skills` and `$` mentions. For example:

```text
/mental:understand How does a request move through this repository?
/mental:build Use docs/protocol.md as the learning source
/mental:learn I want to debug this protocol confidently
```

```text
$mental:understand How does a request move through this repository?
$mental:build Build a learning model from docs/protocol.md
```

## Install and validate

### Claude Code

Load a checkout for one development session:

```sh
claude --plugin-dir /absolute/path/to/mental
```

Validate the package:

```sh
claude plugin validate /absolute/path/to/mental
```

For persistent distribution, add the repository to a Claude Code marketplace and install `mental` from that marketplace.

### Codex

Install `mental` from its configured plugin marketplace, then use `/skills` or type `$` to select a skill. During local development, place this checkout behind a local marketplace entry and use:

```sh
codex plugin marketplace add /absolute/path/to/marketplace
codex plugin add mental@marketplace-name
```

The plugin manifest follows the official skills-only layout: `.codex-plugin/plugin.json` plus `skills/*/SKILL.md`.

### OpenCode compatibility

OpenCode is documentation-only in v1 and does not receive native namespace parity. Copy or link `skills/`, `references/`, `scripts/`, and `assets/` under one `.agents/` directory so the `../../` support paths remain intact. Skills appear by their unscoped names such as `understand` and `build`.

## Artifact lifecycle

`build` creates `status: draft` artifacts under `mental/`. A human promotion gate reviews boundaries, inferred causal claims, invariants, representative success/failure scenarios, and known gaps. Only accepted artifacts become `canonical`.

Important claims use these markers:

- `[observed]` — directly supported by a supplied source;
- `[inferred]` — agent synthesis awaiting confirmation;
- `[agreed]` — explicitly accepted conceptual truth;
- `[conflict]` — canonical and source/implementation truth disagree.

See [the artifact contract](references/artifact-contract.md) for the stable Markdown schema.

## Development

The repository has no runtime dependencies. Run all checks with Python 3:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/scaffold_workspace.py /tmp/mental-demo --mode hybrid --language en
python3 scripts/validate_workspace.py /tmp/mental-demo
```

The helper scripts are an internal skill implementation detail, not a supported end-user command surface.

## License

MIT
