# ASD-STE100 evaluation and writing policy

[繁體中文版](ste100-evaluation.zh-TW.md)

## Decision

Use a **STE-inspired clarity profile** for `mental`. Do not claim that the plugin or its output complies with ASD-STE100.

ASD-STE100 Issue 9 is a controlled form of English for technical documentation. It combines writing rules with a controlled dictionary. Its official FAQ says that it is not intended for general-purpose writing, while principles such as short sentences, one topic per sentence, and active voice can be useful elsewhere.

That distinction fits `mental`: procedural skill instructions benefit strongly from STE principles, but multilingual teaching and conceptual explanation require a broader language range.

## Fit by content type

| Content | Fit | Policy |
| --- | --- | --- |
| `SKILL.md` workflows | High | Use direct imperatives, explicit actors and objects, one action per step, and visible conditions. |
| Installation and validation instructions | High | Use short ordered steps, stable command names, and separate expected results. |
| Artifact templates | High | Use precise headings and prompts. Keep decisions, evidence, and actions separate. |
| Validator diagnostics | Medium | State the object, problem, and smallest repair. Avoid vague pronouns. |
| Methodology and design rationale | Medium | Use progressive structure and stable terms, but permit qualified argument and nuance. |
| Adaptive lessons | Selective | Keep one relationship per chunk, but preserve analogy, questions, examples, and natural learner language. |
| Traditional Chinese content | Principle only | Apply clarity and information-order principles. Do not apply English grammar, dictionary, or word-count rules. |

## Adopted principles

The operational profile adopts these ideas:

- Use one stable term for one concept within a scope.
- Use active voice when the actor is known.
- Write procedures as direct imperatives.
- Put a condition before the action when the reader must know it first.
- Keep one primary action in each numbered step.
- Keep one topic in a descriptive sentence or paragraph when practical.
- Give information gradually, from anchor to relationships to detail.
- Use a vertical list when prose would hide alternatives, conditions, or results.
- Do not omit words that identify the actor, object, evidence, or decision state.
- Prefer concrete behavior over abstract claims such as “works correctly.”

For English technical prose, the official limits of 20 words for procedural sentences and 25 words for descriptive sentences are useful review signals. `mental` does not enforce them as universal limits because links, code identifiers, evidence markers, and teaching context can make mechanical counts misleading.

## Deliberately excluded requirements

The project does not adopt:

- the full controlled English dictionary;
- restrictions on English verb forms or `-ing` forms;
- aerospace-specific safety-instruction rules;
- mechanical word-count validation;
- an ASD-STE100 compliance label.

Full compliance would require applying the complete current standard, including its dictionary, to applicable English technical text. A small subset cannot establish compliance. The official standard is copyrighted and is not vendored in this repository.

## Expected benefit

The profile should improve the agent's ability to parse instructions consistently and should make procedures easier for people to scan. Stable terminology also helps translation and reduces accidental concept aliases.

The profile can become harmful when it removes useful analogy, rhythm, uncertainty, or learner-specific phrasing. For that reason, conceptual and learning output uses it as a clarity constraint, not as a controlled vocabulary.

## Validation status

This is a design decision, not an empirical result. The repository verifies that all skills load the shared writing profile and that documentation does not claim compliance. Readability, task success, translation quality, and learning outcomes still require user studies or controlled comparisons.

## Official sources

- [ASD-STE100 official site](https://www.asd-ste100.org/) — current issue and scope.
- [Official FAQ](https://www.asd-ste100.org/STE_faq.html) — intended use, principles, restrictions, translation, and compliance cautions.
- [ASD-STE100 Issue 9](https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf) — official writing rules and dictionary. The PDF is linked, not redistributed.
