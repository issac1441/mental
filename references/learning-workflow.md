# Adaptive learning workflow

## Source-bound learning model

Build learning content only from supplied material. A learning model normally contains:

- an anchor and concept relationship map;
- prerequisite edges;
- mechanisms or causal chains;
- representative examples and transfer scenarios;
- common misconceptions and boundary cases;
- exercises that test reconstruction, not recognition;
- evidence links and unresolved gaps.

## Diagnostic

Before teaching, ask for the learner's goal and use 2–5 high-information prompts. Prefer prompts that distinguish prerequisite gaps:

- predict what happens in a small scenario;
- explain a relationship in their own words;
- choose and justify an approach;
- identify why a plausible counterexample fails.

Ask one compact batch, then wait. Do not diagnose from writing style, identity, confidence, speed, or protected traits. Select Lens, Views, and Detail with the precedence in `methodology.md`.

## Mastery states

- `unknown`: no evidence yet.
- `exposed`: the concept was explained or recognized.
- `working`: the learner recalled or applied it with support.
- `verified`: the learner independently explained and transferred it, including a boundary or counterexample.

Move at most one state at a time unless the learner provides unusually strong evidence. A wrong answer is evidence about the model gap, not a judgment about the person. Store the state and a short evidence note in `.mental/mastery.json`.

## Teaching loop

1. State the Lens, Views, Detail, selection basis, and one learning objective.
2. Give an anchor with at most five new relationships.
3. Walk through one representative scenario.
4. Show one boundary, failure, or misconception.
5. Ask the learner to predict or teach back.
6. Correct the smallest broken relationship.
7. Update private mastery only after the learner responds.

Keep personalized plans and answers private. Shared exercises may live in `mental/exercises/`; personal attempts belong in `.mental/sessions/`.

## Practice design

Practice is adaptive coaching. Ask one focused task, inspect the response, find the first broken relationship, provide the smallest correction or hint, then ask a structurally equivalent scenario rather than rewording the same question. Continue with a transfer and a boundary check. Finish when the target relationship is demonstrated or when the remaining gap is clear.

Prefer free recall, teach-back, prediction, transfer, debugging, comparison, and counterexamples. Use multiple-choice only when the user requests it, it materially improves the task, or accessibility requires it. Do not reveal the solution until the learner has attempted the task or explicitly asks. End with a concrete statement of what the learner demonstrated, not generic praise.

## Quiz design

Quiz is a bounded assessment, not an adaptive loop. Resolve a scope, generate the complete exam before collecting answers, keep solutions hidden, then evaluate according to `feedback=end|after-each`. A default quiz has 12 mixed items; accept 10–20 items. Objective scores such as `9/12` are allowed. Do not convert a score into a mastery percentage, IQ-like label, or permanent ability claim.
