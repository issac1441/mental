---
name: learn
description: Teach a goal adaptively from supplied, evidence-linked mental-model artifacts. Use when a learner wants a guided lesson, onboarding path, prerequisite diagnosis, or help understanding difficult material. Begin with 2–5 diagnostic prompts, teach in small Lens × Zoom chunks, and keep personal goals and mastery in `.mental/`.
---

# Learn

Help the learner reconstruct and use the model rather than consume a long summary.

## Workflow

1. Read `../../references/methodology.md`, `../../references/artifact-contract.md`, and `../../references/learning-workflow.md` relative to this skill.
2. Read `mental/index.md`, the concept map, relevant canonical artifacts, and `.mental/profile.md` or `.mental/mastery.json` when present.
3. If no canonical learning model exists, do not invent a curriculum from general knowledge. Ask the user to provide sources and invoke `$build`, or obtain explicit permission to teach from clearly labeled draft artifacts.
4. Establish one observable goal: what the learner should predict, explain, build, compare, or debug.
5. Ask one compact batch of 2–5 high-information diagnostic prompts, then stop for answers. Do not infer ability from identity, confidence, grammar, or speed.
6. After the learner responds, identify the smallest broken or missing relationship. Teach one chunk using Anchor → Relationships → Scenario → Boundary, in the user's language and at the lowest useful zoom.
7. End with a prediction or teach-back prompt. Do not reveal its answer until the learner attempts it or asks.
8. Update `.mental/profile.md`, `.mental/mastery.json`, and a private session note only after response evidence exists. Use only `unknown`, `exposed`, `working`, and `verified`, following the transition rules in the learning reference.
9. Recommend the next concept based on prerequisites and observed gaps, not a fixed chapter order.

Shared models and reusable exercises belong in `mental/`; personal answers, diagnostics, goals, and progress belong in `.mental/`.
