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

Ask one compact batch, then wait. Do not diagnose from writing style, identity, confidence, or protected traits.

## Mastery states

- `unknown`: no evidence yet.
- `exposed`: the concept was explained or recognized.
- `working`: the learner recalled or applied it with support.
- `verified`: the learner independently explained and transferred it, including a boundary or counterexample.

Move at most one state at a time unless the learner provides unusually strong evidence. A wrong answer is evidence about the model gap, not a judgment about the person. Store the state and a short evidence note in `.mental/mastery.json`.

## Teaching loop

1. State the lens, zoom, and one learning objective.
2. Give an anchor with at most five new relationships.
3. Walk through one representative scenario.
4. Show one boundary, failure, or misconception.
5. Ask the learner to predict or teach back.
6. Correct the smallest broken relationship.
7. Update private mastery only after the learner responds.

Keep personalized plans and answers private. Shared exercises may live in `mental/exercises/`; personal attempts belong in `.mental/sessions/`.

## Practice design

Prefer free recall, teach-back, transfer, debugging, comparison, and counterexamples. Avoid multiple-choice as the default because recognition can mask a missing model. Do not reveal the solution until the learner has attempted the task or explicitly asks.
