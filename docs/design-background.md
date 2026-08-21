# Design background and research framing

[繁體中文版](design-background.zh-TW.md)

## Abstract

`mental` addresses a coordination problem: an agent can act faster than a person can build a reliable model of what happened. The product therefore aims to shorten the gap between agent execution and human model acquisition. It supports both agentic software work and source-bound learning.

The current method emphasizes immediate explanation before artifact setup, human-first prediction, decision accountability, adaptive repair, three artifact authorities, and first-class conflicts. This document records the original research framing, later design corrections, and claims that still require empirical evaluation.

## 1. Problem statement

A large code change can be locally correct while leaving the operator unable to answer:

- What changed in the system model?
- Which boundary, contract, or invariant now matters?
- What should happen at runtime?
- Which consequential choice did the agent make on the operator's behalf?
- Where does this explanation stop predicting correctly?

Learning has the same gap. A learner can read a fluent summary yet fail to reconstruct a mechanism, predict an outcome, or transfer the idea. Content delivery and artifact generation are not model acquisition.

The central question is:

> How can an agent help a person construct and repair a small, source-linked model without performing the person's prediction or decision for them?

## 2. Design hypotheses

These are product hypotheses, not established properties.

### H1 — Relationships beat inventory

A small map of boundaries, prerequisites, causal links, contracts, and failures will support useful predictions better than an exhaustive inventory.

### H2 — Lens × Job reduces irrelevant explanation

A session role (Lens) plus the current cognitive task (Job) should select a more useful explanation than either a generic answer or a large set of controls the user must configure in advance.

### H3 — Human-first prediction exposes model gaps

When it is consequential, asking the person to predict before revealing evidence should expose missing relationships more reliably than asking whether an explanation feels clear. The interaction must allow a direct answer or `skip`; compulsory Socratic friction can reduce utility.

### H4 — Transfer and counterexamples beat recognition

Independent explanation, application to a structurally related case, and a boundary or counterexample provide stronger evidence of understanding than recognition or assent.

### H5 — The gate must match human standing

People can legitimately decide desired behavior, tradeoffs, ownership, and risk. A newcomer cannot validate unfamiliar implementation facts merely by approving a fluent draft. Mechanical refresh, conceptual activation, and human decision therefore require different gates.

### H6 — Learning in the work loop has higher reach

Short prediction and repair moments inside `change` and `review` may reach operators who will not start a separate study session. Deliberate `learn`, `practice`, and `quiz` remain useful for explicit learning goals.

## 3. Connections to cognitive science

These studies motivate design choices; they do not validate the plugin as a whole.

### Mental models

Johnson-Laird describes mental models as representations used in cognition and reasoning. `mental` borrows the practical criterion that a useful representation supports inference. Markdown artifacts are external coordination objects, not claims about a person's internal representation.

### Cognitive load and schema acquisition

Sweller's 1988 work argues that means-ends problem solving can consume capacity otherwise available for schema acquisition. Progressive disclosure, small relationship sets, worked scenarios, and explicit prerequisites respond to this concern. `mental` does not measure cognitive load and must not claim that it reduces it.

### Self-explanation and generation

Chi and colleagues found that successful learners generated more self-explanations and connected steps to principles. This motivates teach-back, human prediction, and repair of the first broken relationship. An agent-authored prediction would defeat this purpose.

### Retrieval and transfer

Karpicke and Blunt found retrieval practice stronger than elaborative concept mapping in their science-text experiments. A map is therefore insufficient: learners must reconstruct and transfer. Retrieval can also reinforce a wrong model, so source evidence, counterexamples, and open conflicts must remain visible.

## 4. Method evolution

### From Lens × Zoom to Lens × Views × Detail

The first design used Lens × Zoom. Later work separated semantic slices—anchor, map, mechanism, scenario, and evidence—from response density because evidence is not simply a deeper version of system structure.

That correction still exposed too many controls at the input surface. Default Lens-to-View mappings encoded little additional information, and Detail partially repeated View selection.

### From Lens × Views × Detail to Lens × Job

The current interface keeps:

- **Lens** as a low-frequency session assumption about role knowledge, vocabulary, concerns, and decisions;
- **Job** as the per-task need: orient, decide, predict, verify, or repair.

Views remain internal audit vocabulary. The agent chooses them and reports them only when user-selected, non-default, uncertain, or actionable. Experienced users may override Views, but first-time users do not need to understand the taxonomy.

The built-in Lens names are role-shaped conveniences, not identity claims. A person may use `architect` for one explanation and `student` for another. Job sets the cognitive objective; Lens supplies assumed knowledge, vocabulary, and salient concerns. `concerns` is not a whitelist: a PM Lens can still trace a mechanism when the Job is prediction. When the controls appear to conflict, Job wins and Lens shapes its presentation. This distinction must be tested because role labels can still invite identity-based inference if agents apply them carelessly.

### From artifact-first to value-first

The first quickstart required `build`. This delayed value and asked newcomers to approve a model they were not yet equipped to judge. The current flow starts with read-only `understand` or source-bound `learn`. `build` becomes optional persistence after an interaction demonstrates reuse value.

### From agent prediction to human prediction

The shipped change workflow once instructed the agent to write a Prediction. That reproduced the cognitive outsourcing the product was meant to prevent. `change` now asks one high-information human prediction when it can affect a consequential decision, allows `skip`, then compares the response with evidence and repairs the smallest model gap. `skip` applies to one invocation and is not retained as a behavior profile. A recorded brief stores only whether a prediction was attempted, skipped, or not applicable; the answer remains in conversation unless the user asks to persist it.

### From one promotion gate to three gates

Human assent was previously treated as a path from draft to canonical. This confused recognition, decision authority, and factual verification. The current design separates:

- mechanical refresh from registered evidence;
- conceptual activation with a recorded verification basis;
- human acceptance of intent and tradeoffs.

`active` means current working model, not infallible truth.

## 5. Authority, conflicts, and decisions

Source files, code, tests, and runtime observations remain material or implementation truth. Shared artifacts declare maintenance authority:

- **mechanical** artifacts are regenerable caches and can refresh automatically only from a recorded source ID, concrete revision, refresh basis, and Evidence section;
- **conceptual** artifacts are durable explanations that require evidence and checked predictions before activation;
- **decision** artifacts preserve human or agent choices, rejected alternatives, timing, and reversibility.

Authority and volatility are separate axes. Authority decides who may update an artifact; volatility would decide how often an agent should inspect it. V1 does not add a `volatility` field because no decay policy has been validated yet. Registered source revisions plus `current|stale` provide the smaller operational mechanism; future evaluations should test whether a separate decay hint reduces scans without adding another ceremonial field.

Mechanical does not mean “contains no inference.” It means a bounded agent pass can
stably reconstruct the same representation from the registered evidence without
choosing desired behavior or resolving competing conceptual interpretations.
Kinds that can serve as either caches or explanations therefore allow both
mechanical and conceptual authority. Automatic refresh is safe only when the
artifact records how to reproduce the mechanical reading; otherwise it becomes
stale and produces a visible delta.

Conflicts are first-class `open|resolved` artifacts with stable IDs, owners, both sides of the mismatch, and resolution evidence. They are actionable interrupts rather than inline confidence labels.

Decision Surprise names a specifically agentic failure mode: a consequential choice becomes visible only after approval or implementation. The bounded Decision Surprise Rate is consequential post-approval decisions divided by all consequential decisions discovered by that review. It is `N/A` without a valid denominator and is never a global trust score.

Trust is scoped as `Model × Harness × Task Class`. A model without a task-relevant test or canary does not justify autonomy; a harness does not transfer trust beyond the task class it covers.

## 6. Skill and output-style layers

An opt-in skill alone cannot fix poor default explanations. `mental` therefore defines a shared output policy: outcome first, smallest predictive model, progressive evidence, actionable uncertainty, and no repetitive context header.

The portable plugin can guarantee that policy inside mental skills. Making it always-on outside skill invocations depends on host-level instruction mechanisms and should be evaluated separately rather than assumed portable.

Six primary skills preserve meaningful interaction and write boundaries: `understand`, `change`, `review`, `learn`, `practice`, and `quiz`. `build`, `sync`, and `doctor` remain advanced persistence and maintenance capabilities. This reduces cold-start complexity without merging read-only explanation, private learning writes, and artifact maintenance into ambiguous commands.

## 7. Evaluation plan

Compare `mental` with the host agent's normal workflow for a defined task class. Useful measures include:

- **Time to first value:** time from installation to a useful answer.
- **Orientation time:** time until a person can explain the boundary and trace a scenario.
- **Prediction accuracy:** correct predictions about an unseen runtime or transfer case.
- **Model correction:** ability to find and repair a deliberately wrong relationship.
- **Decision Surprise Rate:** bounded post-approval consequential choices divided by reviewed consequential choices.
- **Transfer performance:** application to a new structurally related case.
- **Maintenance cost:** human time spent reviewing mechanical versus conceptual drift.
- **Privacy containment:** whether personal learning state stays outside versioned artifacts.

A credible study should record prior knowledge, task class, source quality, artifact authority, time, assistance, harness coverage, and delayed retention. Prediction tasks must remain hidden until the person commits to an answer.

Implementation assurance uses two orthogonal layers. Deterministic tests validate
manifests, schemas, paths, privacy, and state transitions quickly in CI.
Conversation evaluations then run an actual Claude Code or Codex host, preserve
its real output and workspace delta, and ask a rubric judge to score conditional
behavior. A phrase-presence test is not a conversation evaluation. Host evals
remain slower and probabilistic, so they supplement rather than replace the
deterministic layer.

The deterministic workspace snapshot records regular-file content, directory
presence, symlink targets, and special-file types inside the fixture. It can
detect net changes at the end of a run, including empty directories and
symlinks. It cannot prove that a host never wrote and then removed a path, and
it does not observe writes outside the fixture. Read-only cases therefore also
use the host's read-only controls. Capture-only runs are explicitly unjudged and
cannot pass the evaluation gate.

## 8. Threats and limitations

- A polished model can be wrong, and practice can reinforce that error.
- Source-bound learning can preserve errors or omissions in supplied material.
- Human prediction adds useful effort only when the question has information value; overuse becomes ceremony.
- Lens × Job is design vocabulary, not a validated cognitive taxonomy.
- The mastery states are workflow states, not psychometric measurements.
- Agent diagnoses may reflect prompt and source quality rather than learner ability.
- Generated artifacts can become a maintenance burden; persistence must earn its cost.
- Skill instructions reduce prompt-injection risk but are not a security sandbox.
- Results from one repository, learner, language, or subject do not establish general effectiveness.

## 9. Paper-shaped research agenda

1. **Introduction:** agent throughput and human model-acquisition bottlenecks.
2. **Related work:** mental models, cognitive load, self-explanation, generation, retrieval, architecture knowledge, and human-agent oversight.
3. **Method:** Lens × Job, human-first prediction, authority-specific gates, decision ledger, conflicts, and adaptive repair.
4. **Research questions:** time to value, prediction, transfer, Decision Surprise, maintenance cost, and privacy.
5. **Study design:** task classes, baselines, participants, source controls, harnesses, and delayed tests.
6. **Results:** behavioral outcomes and failure cases, not only satisfaction.
7. **Discussion:** where externalized models help, where they add friction, and how agent errors propagate.
8. **Limitations and ethics:** learner profiling, source bias, over-trust, privacy, and generalizability.

## 10. Provenance and references

The initial problem framing, Living System Model, Lens × Zoom vocabulary, model-delta workflow, Decision Surprise Rate, truth layering, trust unit, and PREDICT interaction came from the [user-supplied design conversation](https://chatgpt.com/share/6a7f588a-6aa8-83ee-a4d4-7ea7cdc7a38c). Later conversations merged audience and perspective inside Lens, separated adaptive practice from fixed quiz, added session context, and then corrected artifact-first onboarding, agent-authored prediction, a single promotion gate, and overexposed Views/Detail controls. This document preserves that evolution rather than presenting the latest shape as inevitable.

- P. N. Johnson-Laird, “Mental Models in Cognitive Science,” *Cognitive Science* 4(1), 1980. [DOI](https://doi.org/10.1207/s15516709cog0401_4)
- John Sweller, “Cognitive Load During Problem Solving: Effects on Learning,” *Cognitive Science* 12(2), 1988. [DOI](https://doi.org/10.1207/s15516709cog1202_4)
- Michelene T. H. Chi et al., “Self-Explanations: How Students Study and Use Examples in Learning to Solve Problems,” *Cognitive Science* 13(2), 1989. [DOI](https://doi.org/10.1207/s15516709cog1302_1)
- Jeffrey D. Karpicke and Janell R. Blunt, “Retrieval Practice Produces More Learning than Elaborative Studying with Concept Mapping,” *Science* 331(6018), 2011. [DOI](https://doi.org/10.1126/science.1199327)
