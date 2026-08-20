# Writing profile

Use this reference for user-visible responses and generated artifacts. The profile is STE-inspired. It is not an ASD-STE100 compliance specification.

## Select the profile

- **Procedure:** Apply all procedure rules to workflows, installation steps, change gates, and repair instructions.
- **Technical description:** Apply the description rules to model artifacts, reviews, and diagnostics.
- **Learning:** Apply the learning rules to lessons, diagnostics, practice, and quizzes.
- **Non-English:** Apply the semantic principles in the user's language. Do not impose English grammar, dictionary, or word-count rules.

## Rules for all profiles

- Use one stable term for one concept in the current scope. Record aliases in the glossary.
- Name the actor, object, evidence, and decision state when they matter.
- Prefer concrete behavior to abstract claims such as “works correctly.”
- Put prerequisite information before dependent detail.
- Preserve uncertainty and the `[observed]`, `[inferred]`, `[agreed]`, and `[conflict]` labels.
- Do not simplify away a boundary, condition, failure, or conflict.

## Procedure profile

- Write direct instructions in the imperative form.
- Keep one primary action in each numbered step.
- Put a condition first when the reader must know it before the action.
- Use active voice when the actor is known.
- Use a vertical list when prose hides alternatives, conditions, or results.
- Separate the action, expected result, and human decision.

## Technical-description profile

- Open with the direct answer; put supporting detail after it.
- Give information gradually: purpose and intuition, then relationships, then mechanism, then exact evidence — as a flow, not as labeled sections.
- Organize by the subject's own structure; never use framework or process vocabulary as headings.
- Define a term at first use or choose a plainer one; never make the reader decode labels invented mid-answer.
- Keep one main topic in each sentence or paragraph when practical.
- Keep English sentences short. Treat 25 words as a review signal, not a hard validator rule.
- Link related sentences with stable key terms instead of unnecessary synonyms.

## Learning profile

- Teach one missing relationship at a time.
- Use the learner's language and preserve useful analogy, examples, and questions.
- Mark where an analogy stops working.
- End a teaching chunk with retrieval, prediction, teach-back, or transfer.
- Do not mistake simpler wording for simpler subject matter or lower learner ability.

## Compliance boundary

Do not claim ASD-STE100 compliance. `mental` does not enforce the full controlled dictionary, English grammar restrictions, aerospace safety rules, or all sentence limits. Refer to `../docs/ste100-evaluation.md` for the decision record and official sources.
