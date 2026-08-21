---
name: learn
description: Teach a source-bound goal adaptively through diagnosis, explanation, prediction, and transfer. Use for guided learning, onboarding, prerequisite diagnosis, or difficult material; it can start directly from supplied sources without requiring a prebuilt mental workspace and persists personal progress only with explicit session consent.
---

# Learn

Help the learner construct and use a model rather than recognize a fluent summary.

## Input contract

`<learning-goal-or-scope> [lens=<built-in-or-custom-id>]`

Infer response density from natural language. Accept advanced `views=` only when explicitly supplied.

## Workflow

1. Read `../../references/methodology.md`, `../../references/output-style.md`, `../../references/artifact-contract.md`, `../../references/learning-workflow.md`, `../../references/source-safety.md`, and `../../references/writing-profile.md` relative to this skill.
2. Read the current session and the smallest relevant supplied or registered sources. Use current mechanical artifacts, active conceptual artifacts, custom lenses, private profile, or mastery state when present and relevant.
3. If no mental workspace exists, continue from supplied sources. Do not require `$build`. Offer persistence only after the lesson demonstrates reusable value.
4. Establish one observable goal: what the learner should predict, explain, compare, build, or debug.
5. Select the session Lens; infer `orient` or `repair` Job from the goal. Do not infer ability from identity, confidence, grammar, or speed.
6. Ask one compact batch of 2–5 high-information diagnostic prompts, then stop for answers.
7. After the response, identify the smallest missing relationship. Teach one chunk with an anchor, relationship, mechanism, scenario, and boundary only as needed.
8. End with a prediction or teach-back prompt. Keep the answer hidden until the learner attempts it or asks.
9. Persist `.mental/` profile, mastery, or session evidence only after a response and explicit persistence consent for the active learning session. Before any private write, run `python3 ../../scripts/ensure_private_state.py <workspace> --language <language>` with absolute paths resolved from this skill directory. If the helper refuses an unsafe path or ignore rule, stop the write and report it; never fall back to `mental/`.
10. Recommend the next prerequisite from observed gaps. Use `$practice` for adaptive repair, `$quiz` for fixed coverage, and optional advanced `$build` to preserve reusable source-bound material.

Shared reusable material belongs in `mental/`; personal answers, diagnostics, goals, and progress belong in `.mental/`.
