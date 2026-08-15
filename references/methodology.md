# Mental methodology

Use this reference to choose an explanation shape and to preserve the distinction between evidence and an agreed model.

## Purpose

Implementation throughput can exceed a person's ability to rebuild a correct model of the system. Optimize for model acquisition, prediction, and correction rather than document volume or diff size.

## Lens × Zoom

Choose one lens and one zoom before explaining. State both when the choice matters.

### Repository lenses

- **Consumer**: What can I do and what should I expect?
- **Integrator**: How do I connect this to another system?
- **Architect**: What are the boundaries, responsibilities, and tradeoffs?
- **Maintainer**: What changes safely, and what invariants must hold?
- **Debugger**: What happens at runtime and where can it fail?

### Learning lenses

- **Novice**: What is the anchor idea and minimum vocabulary?
- **Practitioner**: How do I use it in realistic situations?
- **Solver**: How do mechanisms and constraints determine outcomes?
- **Explainer**: How do I reconstruct and teach the model?
- **Critic**: Where does the model stop working or become misleading?

### Zoom levels

- **L0 — Abstract**: one-sentence purpose and anchor metaphor.
- **L1 — System**: major parts and relationships.
- **L2 — Component**: responsibilities, contracts, prerequisites, and boundaries.
- **L3 — Runtime**: scenarios, state transitions, causal chains, and failures.
- **L4 — Evidence**: source text, code, tests, observations, and exact details.

Start at the lowest zoom that answers the question. Expand only when the learner asks or cannot predict the next step.

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

Use this order for repository work:

1. Orient to the current model and evidence.
2. Predict what should happen before reading or changing details.
3. Describe the proposed model delta.
4. Make decisions, contracts, invariants, and failures explicit.
5. Obtain the human decision.
6. Implement only the accepted change.
7. Verify predictions with tests or runtime evidence.
8. Update the model without hiding surprises.

Review the model delta rather than narrating every changed line.

## Learning workflow

Teach through a loop of diagnose → anchor → relationships → scenario → recall → transfer → correction. Prefer one meaningful chunk over a complete lecture. Evidence of understanding is the learner's ability to predict, explain, apply, or find a counterexample—not familiarity or confidence alone.
