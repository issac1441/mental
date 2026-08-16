# Mental methodology

Use this reference to help a person acquire, test, and repair a useful model while an agent works.

## Purpose

Agent throughput can exceed a person's ability to reconstruct what changed, why it changed, and what will happen next. Optimize for prediction, decision quality, and correction rather than document volume or diff size.

The core loop is:

`orient → human prediction → evidence → model gap → decision or repair → transfer`

Do not let the agent perform the learner's prediction or treat recognition as understanding.

## Lens × Job

Use two primary controls. Infer them from the current session unless the user supplies them.

### Lens

A Lens is the role whose typical knowledge, vocabulary, concerns, and decisions should shape the explanation. It is a session-scoped explanation assumption, not a permanent identity or ability label.

Built-in lenses are:

- **general**: assume no specialist context; prioritize purpose, consequences, and minimum vocabulary.
- **engineer**: assume code navigation and basic software concepts; prioritize mechanisms, contracts, failures, and evidence.
- **architect**: assume system-design vocabulary; prioritize boundaries, ownership, invariants, and tradeoffs.
- **pm**: assume product and delivery concepts; prioritize user effects, options, constraints, dependencies, and tradeoffs.
- **operator**: assume operational procedures; prioritize runtime state, observability, recovery, and failure handling.
- **student**: assume only declared prerequisites; prioritize anchors, vocabulary, worked examples, and transfer.
- **researcher**: assume research-method vocabulary; prioritize constructs, evidence strength, boundary conditions, and alternative explanations.

Repository work defaults to `engineer`. General learning defaults to `student`. A project may define a custom `kind: lens` artifact with `assumes`, `concerns`, and `vocabulary` lists. Do not infer ability from grammar, response speed, identity, confidence, or protected traits.

### Job

Job describes what the person needs to do now:

- **orient**: establish purpose, boundary, minimum vocabulary, and the relationship map.
- **decide**: compare effects, tradeoffs, ownership, failure semantics, and reversibility.
- **predict**: trace a mechanism or state transition and commit to an expected outcome before seeing the answer.
- **verify**: compare a claim, implementation, or answer with contracts, evidence, and counterexamples.
- **repair**: find the first broken relationship, correct it minimally, and test transfer.

Infer Job from the request. Manual `job=` input wins. `understand` defaults to `orient`, `change` to `decide`, `review` and `quiz` to `verify`, and `practice` to `repair`.

Job decides the cognitive objective. Lens decides assumed knowledge, vocabulary,
and which concerns are most salient. When they appear to conflict, satisfy the
Job and express it through the Lens; `concerns` is a salience hint, not an
allowlist of topics the agent may discuss.

## Internal views and response density

Use these semantic slices internally:

- **anchor**: purpose, intuition, and minimum vocabulary;
- **map**: boundaries, prerequisites, parts, and relationships;
- **mechanism**: causal chain, state transition, or algorithm;
- **scenario**: walkthrough, transfer, failure, or counterexample;
- **evidence**: source text, code, tests, observations, uncertainty, and conflicts.

The agent selects only the slices needed by Lens, Job, and the current question. Do not require a first-time user to choose Views or Detail. Accept an explicit `views=` override as an advanced escape hatch when a user already knows the vocabulary.

Infer response density from natural language such as “briefly” or “go deep.” Do not turn density into a second content taxonomy. Do not print a repetitive Lens/Job/View header. Disclose the selection only when the user set it, the choice is uncertain or non-default, or knowing it makes the answer actionable.

## Selection precedence

Choose context in this order:

1. manual Lens, Job, or advanced View override;
2. the explicit goal in the current turn;
3. current-session evidence, including plans, TODOs, corrections, answers, and decisions;
4. relevant `.mental/profile.md` or `.mental/mastery.json` state;
5. host memory, only when exposed and only as a weak signal;
6. skill defaults.

Never persist an inferred preference unless the user explicitly asks.

## Evidence and artifact authority

Source files, code, tests, and runtime observations are material or implementation truth. Artifacts declare who may update them:

- **mechanical**: a representation that can be stably regenerated from registered evidence under a recorded source revision and refresh basis. The agent may refresh it without a human truth judgment.
- **conceptual**: a durable explanation, boundary, prerequisite structure, or teaching model. It may become active only with recorded verification evidence; fluency or user assent is not verification.
- **decision**: an intent, tradeoff, responsibility choice, or accepted change. Only a human with decision standing can accept or reject it.

Conflicts are first-class artifacts. Never hide a disagreement by rewriting either side. Resolve it with evidence or a recorded decision.

## Three gates

### Mechanical refresh

Refresh a mechanical artifact automatically only when its registered source IDs,
concrete source revisions, refresh basis, and Evidence section make the
regeneration reproducible. Record the new basis and mark it `current`. Mark it
`stale` and expose a delta when those conditions are missing or the source is
unavailable. Do not infer mechanical authority from prose or ask a human to
approve source-derived facts.

### Conceptual activation

Move a conceptual artifact from `draft` to `active` only when its verification section records:

1. source or implementation evidence;
2. a checked representative success and failure prediction;
3. known gaps and linked open conflicts;
4. one valid verification basis: source/test corroboration, domain-owner validation, or demonstrated prediction and transfer.

“Looks good” and recognition are not verification. `active` means “current working model with an explicit basis,” not infallible truth.

Record activation in frontmatter with `verification_basis`,
`checked_predictions`, `known_gaps`, and `conflicts`. Checked predictions must
include a representative success plus a failure or boundary. Empty lists are
valid for drafts; they are not sufficient for activation.

### Human decision

Ask the human to decide desired behavior, tradeoffs, ownership, reversibility, and risk. A human decision can become `accepted` or `rejected`; it cannot make an unsupported factual claim true.

## Trust unit

Treat trust as `Model × Harness × Task Class`:

- **Model**: the relevant boundaries, contracts, mechanisms, and known conflicts;
- **Harness**: tests, runtime probes, canaries, or evaluation tasks that can detect a wrong prediction;
- **Task Class**: the bounded kind of work for which the model and harness apply.

Do not assign global agent trust. State missing model coverage or harness evidence before expanding autonomy for a task class.

## Change workflow

Use this repository lifecycle:

1. Use `change` to expose intent, ask one useful human prediction when appropriate, and compare it with evidence.
2. Record consequential choices and obtain the human decision.
3. Use Plan Mode to turn the accepted delta into implementation steps.
4. Implement and verify with a task-class-relevant harness.
5. Use `review` to explain the actual delta and find Decision Surprises.
6. Use `quiz` when the operator wants a bounded assessment.
7. Use advanced `sync` only when durable artifacts need refresh or reconciliation.

`change` may also interpret an existing plan or TODO list. If an option is unclear, return from Plan Mode to `change`, decide, then revise the plan.

## Learning workflow

Teach through `diagnose → anchor → relationship → scenario → retrieval → transfer → correction`. Prefer one meaningful chunk over a lecture. Evidence of understanding is the ability to predict, explain, apply, or find a counterexample—not familiarity or confidence.

Use `practice` for adaptive repair and `quiz` for a fixed-coverage assessment. Integrate short prediction and teach-back moments into `change` and `review` so learning does not require a separate study session.

## Presentation

Read `output-style.md` and `writing-profile.md` for user-visible responses. Lead with the outcome, reveal only the model needed for the current Job, and preserve evidence, uncertainty, boundaries, decisions, and open conflicts.
