#!/usr/bin/env python3
"""Multi-turn dialogue eval for learn/practice.

Protocol: a scripted learner (fixed per-case misconception script) talks to a
live tutor arm (skill-following or bare) over `claude -p --resume`. The
learner side is deterministic by design — what is being measured is the
tutor's behavior, not the learner's. After the dialogue:

1. an independent no-code learner reads only the transcript and answers the
   case probes (post-test: did the dialogue content transfer?);
2. graders with code access judge the dialogue-contract checks from the
   transcript and grade the post-test (same JSON shape as the single-turn
   battery, so aggregate.py works unchanged).

Cases live in evals/cases/dialogue/*.json — outside run_eval.py's glob.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EVALS_DIR))

from run_eval import (  # noqa: E402
    DEFAULT_PERSONA,
    FLOOR_ARM,
    LEARNER_BLOCKED_TOOLS,
    READ_ONLY_TOOLS,
    REPO_ROOT,
    STAGE_TIMEOUTS,
    envelope_duration_ms,
    envelope_tokens,
    ensure_run_provenance,
    extract_json,
    git_head,
    load_prompt,
    load_complete_grading,
    merge_gradings,
    plugin_version,
    probes_block,
    probes_with_gt,
    render,
    run_claude,
    run_provenance,
    sha256_path,
    target_path,
    write_invocation_metadata,
)


def transcript_markdown(turns: list[dict]) -> str:
    parts = []
    for i, turn in enumerate(turns, start=1):
        speaker = "導師" if turn["role"] == "tutor" else "學習者"
        parts.append(f"## 第 {i} 則（{speaker}）\n\n{turn['text']}")
    return "\n\n".join(parts)


def dialogue_checks_block(case: dict) -> str:
    return "\n".join(
        f"{i+1}. {c}" for i, c in enumerate(case.get("dialogue_checks", []))
    )


def run_arm(
    case: dict,
    arm: str,
    iteration_dir: Path,
    workspace: Path,
    model: str,
    effort: str,
    graders: int,
    force: bool,
) -> str:
    run_dir = iteration_dir / case["name"] / arm
    target = target_path(case, workspace)
    skill_ref = ("root", REPO_ROOT) if arm == "with_skill" else None
    provenance_case = {**case, "protocol": "dialogue"}
    provenance = run_provenance(
        provenance_case,
        arm,
        skill_ref,
        target,
        model,
        effort,
        graders,
        runner_path=Path(__file__),
    )
    ensure_run_provenance(run_dir, provenance, force)
    timing_file = run_dir / "timing.json"
    timing = (
        json.loads(timing_file.read_text(encoding="utf-8"))
        if timing_file.exists()
        else {}
    )

    def log(msg: str) -> None:
        print(f"[{case['name']}/{arm}] {msg}", flush=True)

    def save_timing(stage: str, envelope: dict) -> None:
        entry = timing.setdefault(stage, {"tokens": 0, "duration_ms": 0, "calls": 0})
        entry["tokens"] += envelope_tokens(envelope)
        entry["duration_ms"] += envelope_duration_ms(envelope)
        entry["calls"] += 1
        timing_file.write_text(
            json.dumps(timing, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ------------------------------------------------------------- floor arm
    if arm == FLOOR_ARM:
        answers_file = run_dir / "learner_answers.json"
        if answers_file.exists() and not force:
            answers = json.loads(answers_file.read_text(encoding="utf-8"))
            log("floor learner: cached")
        else:
            log("floor learner: running")
            prompt = render(load_prompt("learner-floor"), PROBES=probes_block(case))
            with tempfile.TemporaryDirectory(prefix="floor-") as empty:
                envelope = run_claude(
                    prompt,
                    cwd=Path(empty),
                    model=model,
                    effort=effort,
                    timeout=STAGE_TIMEOUTS["learn"],
                    disallowed_tools=LEARNER_BLOCKED_TOOLS,
                    max_turns=3,
                )
            save_timing("learn", envelope)
            answers = extract_json(envelope.get("result", ""), "[", "]")
            answers_file.write_text(
                json.dumps(answers, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        grading_file = run_dir / "grading.json"
        if grading_file.exists() and not force:
            load_complete_grading(
                grading_file,
                [probe["id"] for probe in case["probes"]],
                expected_expectations=len(case["probes"]),
            )
        else:
            log("floor grade: running")
            prompt = render(
                load_prompt("grader-floor"),
                PROBES_WITH_GT=probes_with_gt(case),
                LEARNER_ANSWERS=json.dumps(answers, ensure_ascii=False, indent=2),
            )
            envelope = run_claude(
                prompt,
                cwd=target,
                model=model,
                effort=effort,
                timeout=STAGE_TIMEOUTS["grade"],
                allowed_tools=READ_ONLY_TOOLS,
            )
            save_timing("grade", envelope)
            grading = merge_gradings(
                [extract_json(envelope.get("result", ""), "{", "}")],
                expected_probe_ids=[probe["id"] for probe in case["probes"]],
                expected_expectations=len(case["probes"]),
            )
            grading_file.write_text(
                json.dumps(grading, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return f"{case['name']}/{arm}"

    # -------------------------------------------------------- dialogue stage
    turns_file = run_dir / "turns.json"
    transcript_file = run_dir / "explanation.md"
    script: list[str] = case["script"]
    expected_turns = 2 * len(script) + 1

    turns: list[dict] = []
    session_id: str | None = None
    if turns_file.exists() and not force:
        saved = json.loads(turns_file.read_text(encoding="utf-8"))
        turns = saved.get("turns", [])
        session_id = saved.get("session_id")

    def save_turns() -> None:
        turns_file.write_text(
            json.dumps(
                {"session_id": session_id, "turns": turns},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        transcript_file.write_text(transcript_markdown(turns), encoding="utf-8")

    if len(turns) < expected_turns:
        if not turns:
            log("dialogue: opening turn")
            if arm == "with_skill":
                skill_path = REPO_ROOT / "skills" / case["skill"] / "SKILL.md"
                prompt = render(
                    load_prompt("tutor-with-skill"),
                    SKILL_NAME=case["skill"],
                    SKILL_PATH=str(skill_path),
                    CONTEXT_NOTE=case.get("context_note", ""),
                    OPENING=case["question"],
                )
                add_dirs = [REPO_ROOT]
            else:
                prompt = render(
                    load_prompt("tutor-baseline"),
                    CONTEXT_NOTE=case.get("context_note", ""),
                    OPENING=case["question"],
                )
                add_dirs = None
            envelope = run_claude(
                prompt,
                cwd=target,
                model=model,
                effort=effort,
                timeout=STAGE_TIMEOUTS["explain"],
                allowed_tools=case.get("allowed_tools", READ_ONLY_TOOLS),
                add_dirs=add_dirs,
            )
            save_timing("dialogue", envelope)
            session_id = envelope.get("session_id")
            if not session_id:
                raise RuntimeError("no session_id in envelope; cannot resume dialogue")
            turns.append({"role": "tutor", "text": envelope.get("result", "")})
            save_turns()
        while len(turns) < expected_turns:
            # turns looks like [T, L, T, L, T, ...]; next learner index:
            learner_index = (len(turns) - 1) // 2
            learner_msg = script[learner_index]
            if turns[-1]["role"] == "tutor":
                turns.append({"role": "learner", "text": learner_msg})
                save_turns()
            log(f"dialogue: tutor turn {2 + learner_index}/{len(script) + 1}")
            envelope = run_claude(
                turns[-1]["text"],
                cwd=target,
                model=model,
                effort=effort,
                timeout=STAGE_TIMEOUTS["explain"],
                allowed_tools=case.get("allowed_tools", READ_ONLY_TOOLS),
                add_dirs=[REPO_ROOT] if arm == "with_skill" else None,
                resume=session_id,
            )
            save_timing("dialogue", envelope)
            session_id = envelope.get("session_id") or session_id
            turns.append({"role": "tutor", "text": envelope.get("result", "")})
            save_turns()
        log(f"dialogue: done ({len(turns)} turns)")
    else:
        log("dialogue: cached")

    transcript = transcript_markdown(turns)

    # --------------------------------------------------- post-test learner
    answers_file = run_dir / "learner_answers.json"
    if answers_file.exists() and not force:
        answers = json.loads(answers_file.read_text(encoding="utf-8"))
        log("learn: cached")
    else:
        log("learn: running")
        explanation_doc = (
            "以下是一位導師與另一位學習者的完整教學對話逐字稿。把它當作你唯一的資料來源。\n\n"
            + transcript
        )
        prompt = render(
            load_prompt("learner"),
            PERSONA=DEFAULT_PERSONA,
            EXPLANATION=explanation_doc,
            PROBES=probes_block(case),
        )
        with tempfile.TemporaryDirectory(prefix="learner-") as empty:
            envelope = run_claude(
                prompt,
                cwd=Path(empty),
                model=model,
                effort=effort,
                timeout=STAGE_TIMEOUTS["learn"],
                disallowed_tools=LEARNER_BLOCKED_TOOLS,
                max_turns=3,
            )
        save_timing("learn", envelope)
        answers = extract_json(envelope.get("result", ""), "[", "]")
        answers_file.write_text(
            json.dumps(answers, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # -------------------------------------------------------------- graders
    grading_file = run_dir / "grading.json"
    if grading_file.exists() and not force:
        load_complete_grading(
            grading_file,
            [probe["id"] for probe in case["probes"]],
            expected_expectations=len(case.get("dialogue_checks", []))
            + len(case["probes"]),
        )
        log("grade: cached")
        return f"{case['name']}/{arm}"
    prompt = render(
        load_prompt("grader-dialogue"),
        DIALOGUE_CHECKS=dialogue_checks_block(case),
        PROBES_WITH_GT=probes_with_gt(case),
        LEARNER_ANSWERS=json.dumps(answers, ensure_ascii=False, indent=2),
        TRANSCRIPT=transcript,
    )
    gradings = []
    for g_index in range(1, graders + 1):
        g_file = run_dir / f"grading-{g_index}.json"
        if g_file.exists() and not force:
            gradings.append(json.loads(g_file.read_text(encoding="utf-8")))
            continue
        log(f"grade[{g_index}/{graders}]: running")
        envelope = run_claude(
            prompt,
            cwd=target,
            model=model,
            effort=effort,
            timeout=STAGE_TIMEOUTS["grade"],
            allowed_tools=READ_ONLY_TOOLS,
        )
        save_timing("grade", envelope)
        grading = extract_json(envelope.get("result", ""), "{", "}")
        g_file.write_text(
            json.dumps(grading, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        gradings.append(grading)
    merged = merge_gradings(
        gradings,
        expected_probe_ids=[probe["id"] for probe in case["probes"]],
        expected_expectations=len(case.get("dialogue_checks", []))
        + len(case["probes"]),
    )
    grading_file.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(f"grade: done ({merged['summary']['passed']}/{merged['summary']['total']})")
    return f"{case['name']}/{arm}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--iteration", type=int, required=True)
    parser.add_argument("--arms", default="with_skill,without_skill")
    parser.add_argument("--cases", default="", help="comma list; default all dialogue cases")
    parser.add_argument("--model", default="claude-opus-4-8")
    parser.add_argument("--effort", default="max")
    parser.add_argument("--graders", type=int, default=2)
    parser.add_argument("--no-floor", action="store_true")
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    cases = []
    for path in sorted((EVALS_DIR / "cases" / "dialogue").glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        if not args.cases or case["name"] in args.cases.split(","):
            cases.append(case)
    if not cases:
        print("no dialogue cases matched", file=sys.stderr)
        return 1

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    for arm in arms:
        if arm not in ("with_skill", "without_skill"):
            print(f"unknown arm {arm}", file=sys.stderr)
            return 1
    if not args.no_floor:
        arms.append(FLOOR_ARM)

    workspace = args.workspace.expanduser().resolve()
    iteration_dir = workspace / f"iteration-{args.iteration}"
    iteration_dir.mkdir(parents=True, exist_ok=True)

    write_invocation_metadata(
        iteration_dir,
        {
            "schema_version": 1,
            "runner": "run_dialogue_eval.py",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": args.model,
            "effort": args.effort,
            "graders": args.graders,
            "arms": arms,
            "cases": [case["name"] for case in cases],
            "plugin_version": plugin_version(REPO_ROOT),
            "plugin_git_head": git_head(REPO_ROOT),
            "runner_sha256": sha256_path(Path(__file__)),
            "prompt_tree_sha256": sha256_path(EVALS_DIR / "prompts"),
        },
    )

    for case in cases:
        case_dir = iteration_dir / case["name"]
        case_dir.mkdir(parents=True, exist_ok=True)
        assertions = [f"dialogue: {c}" for c in case.get("dialogue_checks", [])] + [
            f"probe {p['id']} ({p.get('tier', 'retention')}"
            + (", trap" if p.get("trap") else "")
            + f"): {p['question']}"
            for p in case["probes"]
        ]
        (case_dir / "eval_metadata.json").write_text(
            json.dumps(
                {
                    "eval_id": case["id"],
                    "eval_name": case["name"],
                    "prompt": case["question"],
                    "assertions": assertions,
                    "protocol": "dialogue",
                    "script_turns": len(case["script"]),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    combos = [(case, arm) for case in cases for arm in arms]
    failures = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        futures = {
            pool.submit(
                run_arm,
                case,
                arm,
                iteration_dir,
                workspace,
                args.model,
                args.effort,
                args.graders,
                args.force,
            ): (case["name"], arm)
            for case, arm in combos
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                print(f"DONE {future.result()}", flush=True)
            except Exception as err:  # noqa: BLE001
                failures.append((name, err))
                print(f"FAIL {name}: {err}", flush=True)

    if failures:
        print(f"{len(failures)} combo(s) failed", file=sys.stderr)
        return 1
    print("all combos complete", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
