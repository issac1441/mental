---
name: learn
description: Teach a goal adaptively from supplied, evidence-linked mental-model artifacts. Use when a learner wants a guided lesson, onboarding path, prerequisite diagnosis, or help understanding difficult material. Select a role-conditioned Lens, multiple semantic Views, and Detail from explicit input plus session evidence before teaching.
---

# Learn

Help the learner reconstruct and use the model rather than consume a long summary.

## Input contract

Use a natural-language learning goal, optionally followed by:

`lens=<built-in-or-artifact-id> views=<anchor,map,mechanism,scenario,evidence> detail=<brief|standard|deep>`

## Workflow

1. Read `../../references/methodology.md`, `../../references/artifact-contract.md`, `../../references/learning-workflow.md`, and `../../references/writing-profile.md` relative to this skill.
2. Read the current session, `mental/index.md`, the concept map, relevant canonical artifacts, relevant custom lenses, and `.mental/profile.md` or `.mental/mastery.json` when present. Treat host memory as a weak signal only when exposed.
3. If no canonical learning model exists, do not invent a curriculum from general knowledge. Ask the user to provide sources and invoke `$build`, or obtain explicit permission to teach from clearly labeled draft artifacts.
4. Establish one observable goal: what the learner should predict, explain, build, compare, or debug.
5. Select Lens, Views, and Detail using manual override → explicit goal → current session evidence → private profile or mastery → exposed host memory → `student` default. State the basis. Do not infer ability from identity, confidence, grammar, or speed, and do not persist inferred preferences.
6. Ask one compact batch of 2–5 high-information diagnostic prompts, then stop for answers.
7. After the learner responds, identify the smallest broken or missing relationship. Teach one chunk using only the selected Views and Detail. Prefer Anchor → Map → Mechanism → Scenario → Boundary when all are needed.
8. End with a prediction or teach-back prompt. Do not reveal its answer until the learner attempts it or asks.
9. Update `.mental/profile.md`, `.mental/mastery.json`, and a private session note only after response evidence exists and only when writing personal progress is in scope. Use `unknown`, `exposed`, `working`, and `verified` with the learning reference's transition rules.
10. Recommend the next concept based on prerequisites and observed gaps, not a fixed chapter order. Recommend `$practice` for adaptive coaching or `$quiz` for a bounded exam.

Shared models and reusable exercises belong in `mental/`; personal answers, diagnostics, goals, and progress belong in `.mental/`.
