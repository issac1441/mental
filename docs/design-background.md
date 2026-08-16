# Design background and research framing

[繁體中文版](design-background.zh-TW.md)

## Abstract

`mental` addresses a coordination problem: an agent can generate or change material faster than a person can build a reliable model of it. The plugin therefore optimizes for model acquisition, prediction, correction, and human decisions. It does not optimize for document volume.

The method combines a small relationship model, Lens × Views × Detail selection, runtime or transfer scenarios, claim provenance, draft-to-canonical promotion, and evidence-based practice. This document records how those parts follow from the original design conversation, how they connect to cognitive-science research, and which claims still require evaluation.

## 1. Problem statement

The original design conversation started from software work with coding agents. A large code diff can be locally correct while leaving the operator unable to answer basic system questions:

- What changed in the system model?
- Which boundary, contract, or invariant now matters?
- What should happen at runtime?
- Which decision did the agent make on the operator's behalf?
- Where does the explanation stop predicting correctly?

The same gap appears in learning. A learner can read a fluent summary and still fail to reconstruct a mechanism, predict an outcome, or transfer the idea to a new case. In both settings, content delivery is not the same as model acquisition.

The central design question is therefore:

> How can an agent help a person construct a small, source-linked model that supports prediction and correction without replacing human judgment?

## 2. Design hypotheses

These statements are product hypotheses, not established properties of `mental`.

### H1 — Relationships beat inventory

A small map of boundaries, prerequisites, causal links, contracts, and failure paths will support useful predictions better than an exhaustive inventory of files or facts.

### H2 — The right view reduces unnecessary load

Selecting a role-conditioned Lens, only the needed semantic Views, and suitable Detail should reduce irrelevant information during orientation. Progressive disclosure should help a person acquire a schema before inspecting implementation evidence.

### H3 — Prediction exposes model gaps

Asking for a prediction before revealing an implementation trace or answer will expose missing relationships more reliably than asking whether the explanation feels clear.

### H4 — Transfer and counterexamples are stronger evidence than recognition

A person who can explain a relationship, apply it in a new scenario, and identify a boundary has stronger evidence of understanding than a person who only recognizes familiar wording.

### H5 — Human confirmation must govern conceptual truth

An agent can assemble evidence and draft a model. It cannot decide that inferred boundaries, causal claims, or invariants are the team's agreed conceptual truth. Promotion to `canonical` therefore requires an explicit human decision.

## 3. Connections to cognitive science

The research below motivates parts of the design. It does not validate the plugin as a whole.

### Mental models

Johnson-Laird's early account treats mental models as representations used in cognition and reasoning. `mental` borrows the practical idea that a useful representation should support inference. The repository's Markdown graph is an external coordination artifact, not a claim to reproduce a person's internal cognitive representation.

### Cognitive load and schema acquisition

Sweller's 1988 experiments and model argue that conventional means-ends problem solving can consume capacity that would otherwise support schema acquisition. `mental` responds with progressive disclosure, small relationship sets, worked scenarios, and explicit prerequisites. The plugin does not currently measure cognitive load, so it must not claim that it reduces it.

### Self-explanation

Chi and colleagues found that successful learners generated more self-explanations while studying worked examples and connected solution steps to principles. This motivates teach-back, prediction, and correction of the smallest broken relationship. It does not justify treating every verbal explanation as proof of mastery.

### Retrieval and transfer

Karpicke and Blunt found that retrieval practice produced stronger learning in their science-text experiments than elaborative study with concept mapping. This is an important constraint on the product: building a map is not enough. `/mental:practice` must require reconstruction and transfer.

## 4. Method derivation

The method separates questions that large architecture documents often mix together:

- A structural view answers **what exists**.
- A scenario answers **what happens**.
- A decision record answers **why this shape was chosen**.
- Evidence answers **what was observed**.
- Canonical status answers **what a human has agreed to use as the conceptual model**.

Lens × Views × Detail selects the explanation strategy. The model map names the minimum relationships. Scenarios test whether those relationships predict behavior. Claim labels separate observations, inferences, agreements, and conflicts. The promotion gate prevents fluent agent output from becoming accepted truth by accident.

### Design vocabulary evolution

The first design used **Lens × Zoom**. Lens originally named perspectives such as architect or debugger, while examples based on education level were really audience assumptions. The current design merges those ideas: a Lens now represents the knowledge, vocabulary, concerns, and decisions typical of a role. `architect` is therefore a Lens for the same reason that `student` or `pm` is a Lens. It shapes what the answer assumes and emphasizes without claiming that the user permanently is that role.

The old L0–L4 scale also mixed different dimensions. “Runtime” and “evidence” are not merely more detailed versions of “system”; they are different semantic slices, and users often need several at once. The operational model now uses multi-select Views (`anchor`, `map`, `mechanism`, `scenario`, `evidence`) plus an independent Detail control (`brief`, `standard`, `deep`). The old names remain here only as design provenance; skills do not accept them as aliases.

Context selection uses manual input first, then the explicit goal, current session evidence, private profile or mastery, exposed host memory as a weak signal, and finally a scope default. This ordering lets the agent adapt without silently converting inference into a permanent user profile.

For repository changes, the workflow is:

1. Orient to the current model.
2. Predict current behavior.
3. Propose the model delta.
4. Expose decisions, contracts, invariants, and failure behavior.
5. Obtain the human decision.
6. Implement the accepted change.
7. Verify the predictions.
8. Preserve surprises and synchronize accepted model changes.

For learning, the workflow is:

1. Diagnose a small number of prerequisite relationships.
2. Give one anchor and a small relationship set.
3. Walk through one representative scenario.
4. Show one boundary, failure, or misconception.
5. Ask for retrieval, prediction, or teach-back.
6. Correct the first broken relationship.
7. Test transfer before recording verified mastery.

## 5. Truth and governance

`mental` keeps two forms of truth distinct:

- Source, code, tests, and runtime observations describe material or implementation truth.
- Canonical artifacts describe human-agreed conceptual truth.

The two can disagree. A mismatch is a finding, not permission to rewrite either side silently. This is why artifacts distinguish `[observed]`, `[inferred]`, `[agreed]`, and `[conflict]` claims.

Shared models live in `mental/`. Personal goals, diagnostic answers, session notes, and mastery evidence live in gitignored `.mental/`. The separation supports collaboration without publishing a learner profile.

Supplied sources are evidence, not instructions. A repository, document, URL, diff, or generated artifact cannot authorize tool use, writes, source expansion, draft approval, or private-state disclosure. This boundary is necessary because `mental` intentionally asks an agent to read material that may be wrong, stale, or adversarial.

## 6. Evaluation plan

Evaluation should compare `mental` with the host agent's normal workflow for a defined task class. Do not combine unrelated tasks into one trust score.

Useful measures include:

- **Orientation time:** time until a person can explain the boundary and trace a representative scenario.
- **Prediction accuracy:** correct predictions about an unseen runtime or transfer case.
- **Model correction:** ability to find and repair a deliberately wrong relationship.
- **Decision Surprise Rate:** consequential decisions discovered after approval divided by consequential decisions reviewed for that task.
- **Transfer performance:** ability to apply the model to a new but structurally related case.
- **Drift detection:** whether source/model conflicts are found and remain visible until a human decision.
- **Privacy containment:** whether personal learning state stays outside versioned artifacts.

A credible study should record prior knowledge, task class, source quality, model status, time, assistance, and delayed retention. It should keep prediction tasks hidden until after the model is built.

## 7. Threats and limitations

- A polished graph can be wrong. Evidence links and human confirmation reduce this risk but do not remove it.
- Source-bound learning can faithfully preserve errors or omissions in the supplied material.
- Prompt injection in a supplied source can influence an agent that fails to preserve the source-as-data boundary; skill instructions reduce this risk but are not a security sandbox.
- Lens × Views × Detail is a design vocabulary, not a validated cognitive taxonomy.
- The four mastery states are workflow states, not psychometric measurements.
- Agent-generated diagnoses can reflect prompt quality and source coverage rather than learner ability.
- More artifacts can create maintenance load. Every artifact must justify itself by improving a prediction or decision.
- Results from one repository, learner, language, or subject do not establish broad effectiveness.

## 8. Paper-shaped research agenda

A future paper or proposal can use this structure:

1. **Introduction:** agent throughput and the human model-acquisition bottleneck.
2. **Related work:** mental models, cognitive load, self-explanation, retrieval practice, architecture knowledge, and human-agent oversight.
3. **Method:** Lens × Views × Detail, artifact contract, provenance, promotion gates, and skill workflows.
4. **Research questions:** orientation, prediction, transfer, decision surprise, drift, and privacy.
5. **Study design:** task classes, baselines, participants, source controls, and delayed tests.
6. **Results:** behavioral outcomes and failure cases, not only satisfaction.
7. **Discussion:** where externalized models help, where they add friction, and how agent errors propagate.
8. **Limitations and ethics:** learner profiling, source bias, over-trust, privacy, and generalizability.

## 9. Provenance and references

The initial problem framing, Living System Model, original Lens × Zoom vocabulary, model-delta workflow, Decision Surprise Rate, and distinction between implementation truth and conceptual truth came from the [user-supplied design conversation](https://chatgpt.com/share/6a7f588a-6aa8-83ee-a4d4-7ea7cdc7a38c). Later discussion merged audience with perspective inside Lens, split the old scale into Views and Detail, clarified `change` relative to Plan Mode, separated adaptive `practice` from bounded `quiz`, and made session context a first-class selection signal. This document records both stages. The shared conversation is design provenance, not peer-reviewed evidence.

- P. N. Johnson-Laird, “Mental Models in Cognitive Science,” *Cognitive Science* 4(1), 1980. [DOI](https://doi.org/10.1207/s15516709cog0401_4)
- John Sweller, “Cognitive Load During Problem Solving: Effects on Learning,” *Cognitive Science* 12(2), 1988. [DOI](https://doi.org/10.1207/s15516709cog1202_4)
- Michelene T. H. Chi et al., “Self-Explanations: How Students Study and Use Examples in Learning to Solve Problems,” *Cognitive Science* 13(2), 1989. [DOI](https://doi.org/10.1207/s15516709cog1302_1)
- Jeffrey D. Karpicke and Janell R. Blunt, “Retrieval Practice Produces More Learning than Elaborative Studying with Concept Mapping,” *Science* 331(6018), 2011. [DOI](https://doi.org/10.1126/science.1199327)
