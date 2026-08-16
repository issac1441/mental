# Mental methodology

Use this reference to select the explanation shape and preserve the distinction between evidence and an agreed model.

## Purpose

Implementation throughput can exceed a person's ability to rebuild a correct model of a system or subject. Optimize for model acquisition, prediction, and correction rather than document volume or diff size.

## Lens × Views × Detail

Every explanation has three independent controls. State the selected values and a short basis when they affect the answer.

### Lens

A Lens is the role whose typical knowledge, vocabulary, concerns, and decisions should shape the answer. It combines audience and perspective. It is a session-scoped working assumption, not a permanent identity or an ability label.

Built-in lenses are starting points:

- **general**: assumes no specialist context; prioritizes purpose, consequences, and minimum vocabulary; defaults to `anchor,map,scenario`.
- **engineer**: assumes code navigation and basic software concepts; prioritizes mechanisms, contracts, failures, and evidence; defaults to `map,mechanism,scenario,evidence`.
- **architect**: assumes system-design vocabulary; prioritizes boundaries, ownership, invariants, and tradeoffs; defaults to `map,mechanism,scenario`.
- **pm**: assumes product and delivery concepts; prioritizes user effects, options, constraints, dependencies, and decision tradeoffs; defaults to `anchor,map,scenario`.
- **operator**: assumes operational procedures; prioritizes runtime state, observability, recovery, and failure handling; defaults to `mechanism,scenario,evidence`.
- **student**: assumes only declared prerequisites; prioritizes anchors, vocabulary, prerequisite gaps, worked examples, and transfer; defaults to `anchor,map,scenario`.
- **researcher**: assumes research-method vocabulary; prioritizes constructs, mechanism, evidence strength, boundary conditions, and alternative explanations; defaults to `map,mechanism,evidence`.

The repository context defaults to `engineer`. General learning defaults to `student`. Prefer a more specific goal-supported Lens when the evidence warrants it.

Projects may define reusable lenses as `kind: lens` artifacts under `mental/lenses/`. Each lens should declare:

- `assumes`: knowledge that the explanation may use without first teaching it;
- `prioritizes`: questions, risks, or decisions to emphasize;
- `vocabulary`: terms to prefer, define, or avoid;
- `default_views`: an ordered subset of the fixed View values.

Use a custom lens by artifact ID or path. Do not infer a person's ability from grammar, response speed, identity, confidence, or protected traits.

### Views

Views are fixed semantic slices and may be combined. Preserve this vocabulary so a request has the same meaning across domains:

- **anchor**: purpose, intuition, and the minimum vocabulary needed to start;
- **map**: parts or concepts, boundaries, prerequisites, and relationships;
- **mechanism**: causal chain, state transition, algorithm, or why an outcome occurs;
- **scenario**: a concrete walkthrough, transfer case, failure, or counterexample;
- **evidence**: exact source text, code, tests, observations, uncertainty, and conflicts.

Choose only the Views needed to answer the current question. Manual input accepts a comma-separated multi-selection such as `views=map,scenario,evidence`.

### Detail

Detail controls density inside the selected Views:

- **brief**: an orientation or decision summary;
- **standard**: enough relationships and examples to make a useful prediction;
- **deep**: mechanisms, alternatives, boundary conditions, and exact evidence.

Detail does not imply expertise. A `student` lens may request `deep`; an `architect` lens may request `brief`.

### Selection precedence

Choose context in this order:

1. manual `lens=`, `views=`, or `detail=` overrides;
2. the user's explicit goal or request in the current turn;
3. evidence from the current session, including active plans, TODOs, corrections, and demonstrated questions;
4. `.mental/profile.md` and `.mental/mastery.json`, when present and relevant;
5. host memory, only when the host exposes it and only as a weak signal;
6. the scope defaults above.

Use each signal only for the control it supports. Explain the basis briefly, including uncertainty. Never persist an inferred preference unless the user explicitly asks.

## Three kinds of truth

- **Observed**: directly supported by a supplied source, code, test, or runtime evidence.
- **Inferred**: synthesized by the agent from observations; plausible but not yet agreed.
- **Agreed**: explicitly accepted by a human as the canonical conceptual model.

Do not silently turn an inference into an agreement. When implementation truth and conceptual truth differ, preserve both and label the mismatch as a conflict.

## Core model

A useful model contains only what improves prediction:

- an anchor and a small relationship map;
- concepts or components with clear boundaries;
- representative scenarios, including one failure or counterexample;
- contracts, invariants, prerequisites, and decisions when applicable;
- evidence links and known gaps.

C4-style structure answers **what exists**. Runtime scenarios answer **what happens**. Decision records answer **why this shape was chosen**. Do not collapse these into a single large document.

## Change workflow

The recommended repository lifecycle is:

1. Use `change` to expose the proposed model delta or explain options.
2. Obtain the human decision.
3. Use the host's Plan Mode to turn the accepted delta into implementation steps.
4. Implement and verify the accepted plan.
5. Use `review` to explain the actual delta and audit it.
6. Use `quiz` when the operator wants a bounded assessment of the change.
7. Use `sync` to reconcile accepted model updates.

`change` may also interpret an existing plan or TODO list. If an option remains unclear, return from Plan Mode to `change`, explain its actual effects and tradeoffs, decide, then revise the plan.

## Learning workflow

Teach through a loop of diagnose → anchor → relationships → scenario → recall → transfer → correction. Prefer one meaningful chunk over a complete lecture. Evidence of understanding is the learner's ability to predict, explain, apply, or find a counterexample—not familiarity or confidence alone.

Use `practice` for adaptive coaching and `quiz` for a complete bounded assessment. Practice changes the next task after each response. Quiz prepares a fixed exam first and normally evaluates it after submission.

## Presentation

Apply `writing-profile.md` to user-visible responses and generated artifacts. Use the procedure profile for actions and approval gates, the technical-description profile for models and reviews, and the learning profile for lessons, practice, and quizzes. Follow the user's language. Do not trade away uncertainty, evidence, or boundary conditions to make text shorter.
