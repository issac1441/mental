#!/usr/bin/env python3
"""Learning-transfer eval runner for the mental plugin's explanation skills.

Measures whether skill-mediated explanations help a fresh reader build a
predictive mental model faster than a plain-model baseline. Three stages per
(case, arm):

  1. explain — an agent answers the case question inside the target repo
     (with the skill under test, with the old skill snapshot, or bare).
  2. learn   — a fresh agent with NO repo access reads only the explanation
     and answers probe questions.
  3. grade   — a grader with repo access scores probe answers against ground
     truth, rates explanation quality (gist / coherence / overhead /
     concreteness), and spot-checks citations.

All agent runs are pinned to one model + effort so the only variable is the
explanation. Results are written in skill-creator's workspace layout
(grading.json / timing.json / outputs/) so its aggregator and viewer work.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVALS_DIR.parent

READ_ONLY_TOOLS = "Read Glob Grep"
LEARNER_BLOCKED_TOOLS = (
    "Read Glob Grep Bash Write Edit WebFetch WebSearch Task NotebookEdit TodoWrite"
)

STAGE_TIMEOUTS = {"explain": 1500, "learn": 700, "grade": 1100}


def load_prompt(name: str) -> str:
    return (EVALS_DIR / "prompts" / f"{name}.md").read_text(encoding="utf-8")


def render(template: str, **values: str) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def run_claude(
    prompt: str,
    cwd: Path,
    model: str,
    effort: str,
    timeout: int,
    allowed_tools: str | None = None,
    disallowed_tools: str | None = None,
    add_dirs: list[Path] | None = None,
    max_turns: int | None = None,
) -> dict:
    """Run one non-interactive claude call; return the parsed JSON envelope."""
    cmd = [
        "claude",
        "-p",
        "--model",
        model,
        "--effort",
        effort,
        "--output-format",
        "json",
        "--disable-slash-commands",
    ]
    if allowed_tools:
        cmd += ["--allowedTools", allowed_tools]
    if disallowed_tools:
        cmd += ["--disallowedTools", disallowed_tools]
    for extra in add_dirs or []:
        cmd += ["--add-dir", str(extra)]
    if max_turns is not None:
        cmd += ["--max-turns", str(max_turns)]

    last_error: Exception | None = None
    for attempt in (1, 2):
        try:
            proc = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                cwd=str(cwd),
                timeout=timeout,
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    f"claude exited {proc.returncode}: "
                    f"stderr={proc.stderr[-500:]!r} stdout={proc.stdout[-500:]!r}"
                )
            envelope = json.loads(proc.stdout)
            if envelope.get("is_error"):
                raise RuntimeError(f"claude reported error: {envelope}")
            return envelope
        except (subprocess.TimeoutExpired, RuntimeError, json.JSONDecodeError) as err:
            last_error = err
            if attempt == 1:
                time.sleep(5)
    raise RuntimeError(f"claude call failed twice: {last_error}")


def extract_json(text: str, opener: str, closer: str):
    start = text.find(opener)
    end = text.rfind(closer)
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"no JSON found in output: {text[:200]}...")
    return json.loads(text[start : end + 1])


def envelope_tokens(envelope: dict) -> int:
    usage = envelope.get("usage") or {}
    return sum(
        int(usage.get(key, 0) or 0)
        for key in (
            "input_tokens",
            "output_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
        )
    )


def envelope_duration_ms(envelope: dict) -> int:
    return int(
        envelope.get("duration_ms")
        or envelope.get("duration_api_ms")
        or 0
    )


def build_mental_target(workspace: Path) -> Path:
    """Copy this repository (minus evals/, VCS and private state) so the
    explainer sees the plugin as a plain target codebase."""
    target = workspace / "target-mental"
    if target.exists():
        return target
    exclude = {".git", "evals", ".mental", "__pycache__", ".claude"}
    target.mkdir(parents=True)
    for entry in REPO_ROOT.iterdir():
        if entry.name in exclude:
            continue
        dest = target / entry.name
        if entry.is_dir():
            shutil.copytree(
                entry,
                dest,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        else:
            shutil.copy2(entry, dest)
    return target


def target_path(case: dict, workspace: Path) -> Path:
    if case["target"] == "orderflow":
        return EVALS_DIR / "fixtures" / "orderflow"
    if case["target"] == "mental":
        return build_mental_target(workspace)
    raise ValueError(f"unknown target {case['target']}")


def probes_block(case: dict) -> str:
    return "\n".join(f"{p['id']}. {p['question']}" for p in case["probes"])


def probes_with_gt(case: dict) -> str:
    parts = []
    for probe in case["probes"]:
        parts.append(
            f"題 {probe['id']}: {probe['question']}\n標準答案: {probe['ground_truth']}"
        )
    return "\n\n".join(parts)


def run_combo(
    case: dict,
    arm: str,
    skill_path: Path | None,
    workspace: Path,
    iteration_dir: Path,
    model: str,
    effort: str,
    force: bool,
) -> str:
    run_dir = iteration_dir / case["name"] / arm
    outputs = run_dir / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    target = target_path(case, workspace)
    log = lambda msg: print(f"[{case['name']}/{arm}] {msg}", flush=True)

    # Stage 1: explain
    explanation_file = outputs / "explanation.md"
    if explanation_file.exists() and not force:
        log("explain: cached")
        explanation = explanation_file.read_text(encoding="utf-8")
    else:
        log("explain: running")
        if skill_path is None:
            prompt = render(load_prompt("explainer-baseline"), QUESTION=case["question"])
            add_dirs = None
        else:
            prompt = render(
                load_prompt("explainer-with-skill"),
                QUESTION=case["question"],
                SKILL_PATH=str(skill_path),
            )
            # allow reads of the skill and its ../../references
            add_dirs = [skill_path.parents[2]]
        envelope = run_claude(
            prompt,
            cwd=target,
            model=model,
            effort=effort,
            timeout=STAGE_TIMEOUTS["explain"],
            allowed_tools=READ_ONLY_TOOLS,
            add_dirs=add_dirs,
        )
        explanation = envelope.get("result", "")
        if not explanation.strip():
            raise RuntimeError("empty explanation")
        explanation_file.write_text(explanation, encoding="utf-8")
        (run_dir / "explain_envelope.json").write_text(
            json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        duration_ms = envelope_duration_ms(envelope)
        (run_dir / "timing.json").write_text(
            json.dumps(
                {
                    "total_tokens": envelope_tokens(envelope),
                    "duration_ms": duration_ms,
                    "total_duration_seconds": round(duration_ms / 1000, 1),
                    "explanation_chars": len(explanation),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        log(f"explain: done ({len(explanation)} chars)")

    # Stage 2: learn (no repo access)
    answers_file = outputs / "learner_answers.json"
    if answers_file.exists() and not force:
        log("learn: cached")
        answers = json.loads(answers_file.read_text(encoding="utf-8"))
    else:
        log("learn: running")
        prompt = render(
            load_prompt("learner"),
            EXPLANATION=explanation,
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
        answers = extract_json(envelope.get("result", ""), "[", "]")
        answers_file.write_text(
            json.dumps(answers, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log("learn: done")

    # Stage 3: grade (repo access, blind to arm)
    grading_file = run_dir / "grading.json"
    if grading_file.exists() and not force:
        log("grade: cached")
    else:
        log("grade: running")
        prompt = render(
            load_prompt("grader"),
            QUESTION=case["question"],
            PROBES_WITH_GT=probes_with_gt(case),
            LEARNER_ANSWERS=json.dumps(answers, ensure_ascii=False, indent=2),
            EXPLANATION=explanation,
        )
        envelope = run_claude(
            prompt,
            cwd=target,
            model=model,
            effort=effort,
            timeout=STAGE_TIMEOUTS["grade"],
            allowed_tools=READ_ONLY_TOOLS,
        )
        grading = extract_json(envelope.get("result", ""), "{", "}")
        expectations = grading.get("expectations", [])
        passed = sum(1 for e in expectations if e.get("passed"))
        grading["summary"] = {
            "passed": passed,
            "failed": len(expectations) - passed,
            "total": len(expectations),
            "pass_rate": round(passed / len(expectations), 3) if expectations else 0,
        }
        grading_file.write_text(
            json.dumps(grading, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log(f"grade: done ({passed}/{len(expectations)})")

    return f"{case['name']}/{arm}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--iteration", type=int, default=1)
    parser.add_argument(
        "--arms",
        default="with_skill,old_skill,without_skill",
        help="comma list of with_skill,old_skill,without_skill",
    )
    parser.add_argument(
        "--old-skill-path",
        type=Path,
        default=None,
        help="path to the snapshot skills/understand/SKILL.md (required for old_skill arm)",
    )
    parser.add_argument("--cases", default="", help="comma list of case names; default all")
    parser.add_argument("--model", default="claude-opus-4-8")
    parser.add_argument("--effort", default="max")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    cases = []
    for path in sorted((EVALS_DIR / "cases").glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        if not args.cases or case["name"] in args.cases.split(","):
            cases.append(case)
    if not cases:
        print("no cases matched", file=sys.stderr)
        return 1

    arm_skills: dict[str, Path | None] = {}
    for arm in args.arms.split(","):
        arm = arm.strip()
        if arm == "with_skill":
            arm_skills[arm] = REPO_ROOT / "skills" / "understand" / "SKILL.md"
        elif arm == "old_skill":
            if not args.old_skill_path:
                print("--old-skill-path required for old_skill arm", file=sys.stderr)
                return 1
            arm_skills[arm] = args.old_skill_path
        elif arm == "without_skill":
            arm_skills[arm] = None
        else:
            print(f"unknown arm {arm}", file=sys.stderr)
            return 1

    workspace = args.workspace
    iteration_dir = workspace / f"iteration-{args.iteration}"
    iteration_dir.mkdir(parents=True, exist_ok=True)

    # per-case metadata for the viewer
    for case in cases:
        case_dir = iteration_dir / case["name"]
        case_dir.mkdir(parents=True, exist_ok=True)
        assertions = [f"probe {p['id']}: {p['question']}" for p in case["probes"]]
        assertions += [
            "gist: 開頭即給出可獨立成立的正確答案",
            "coherence: 敘事連貫、組織服務主題 (>=4/5)",
            "overhead: 內容之前無元資訊/框架負擔 (>=4/5)",
            "concreteness: 主張連結到具體證據 (>=4/5)",
            "citations: 抽查的檔案引用存在且支持主張",
        ]
        (case_dir / "eval_metadata.json").write_text(
            json.dumps(
                {
                    "eval_id": case["id"],
                    "eval_name": case["name"],
                    "prompt": case["question"],
                    "assertions": assertions,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    combos = [(case, arm) for case in cases for arm in arm_skills]
    failures = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        futures = {
            pool.submit(
                run_combo,
                case,
                arm,
                arm_skills[arm],
                workspace,
                iteration_dir,
                args.model,
                args.effort,
                args.force,
            ): (case["name"], arm)
            for case, arm in combos
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                future.result()
                print(f"DONE {name[0]}/{name[1]}", flush=True)
            except Exception as err:  # keep going; report at the end
                failures.append((name, str(err)))
                print(f"FAIL {name[0]}/{name[1]}: {err}", flush=True)

    if failures:
        print(f"\n{len(failures)} combo(s) failed:", file=sys.stderr)
        for name, err in failures:
            print(f"  {name[0]}/{name[1]}: {err[:300]}", file=sys.stderr)
        return 2
    print("\nall combos complete", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
