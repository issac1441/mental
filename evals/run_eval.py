#!/usr/bin/env python3
"""Learning-transfer eval runner (v2) for the mental plugin's explanation skills.

Per (case, arm): explain -> learn (full read + truncated-prefix reads, with
per-probe confidence) -> grade (ensemble of blind graders scoring probes,
prefix probes, planted-boundary coverage, false-certainty sampling,
paragraph-level extraneous accounting, quality rubric, citation checks, and
— when the case declares an audience — content-altitude fit).

A null_floor pseudo-arm answers the probes with no explanation at all,
estimating the prior-knowledge floor; report arm accuracies as lift over it.

All agent runs are pinned to one model + effort so the explanation is the
only variable. Output layout stays skill-creator compatible.
"""

from __future__ import annotations

import argparse
import json
import statistics
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

STAGE_TIMEOUTS = {"explain": 1500, "learn": 700, "grade": 1400}

DEFAULT_PERSONA = "你剛加入一個團隊，需要快速理解一個你完全沒看過的系統。"

FLOOR_ARM = "null_floor"


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
    for attempt in (1, 2, 3):
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
                    f"stderr={proc.stderr[-400:]!r} stdout={proc.stdout[-400:]!r}"
                )
            envelope = json.loads(proc.stdout)
            if envelope.get("is_error"):
                raise RuntimeError(f"claude reported error: {envelope}")
            return envelope
        except (subprocess.TimeoutExpired, RuntimeError, json.JSONDecodeError) as err:
            last_error = err
            if attempt < 3:
                time.sleep(10 * attempt)
    raise RuntimeError(f"claude call failed 3 times: {last_error}")


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
    return int(envelope.get("duration_ms") or envelope.get("duration_api_ms") or 0)


def build_mental_target(workspace: Path) -> Path:
    import shutil

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
                entry, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
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
        flags = probe.get("tier", "retention") + (", trap" if probe.get("trap") else "")
        parts.append(
            f"題 {probe['id']} ({flags}): {probe['question']}\n"
            f"標準答案: {probe['ground_truth']}"
        )
    return "\n\n".join(parts)


def persona_text(case: dict) -> str:
    name = case.get("persona")
    if not name:
        return DEFAULT_PERSONA
    return (EVALS_DIR / "prompts" / "personas" / f"{name}.md").read_text(
        encoding="utf-8"
    ).strip()


def run_learner(
    case: dict,
    explanation: str,
    model: str,
    effort: str,
) -> list:
    prompt = render(
        load_prompt("learner"),
        PERSONA=persona_text(case),
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
    return extract_json(envelope.get("result", ""), "[", "]")


def merge_gradings(gradings: list[dict]) -> dict:
    """Conservative merge: an expectation/probe passes only if every grader
    passed it. Scores and ratios are averaged. Disagreements are recorded."""
    if len(gradings) == 1:
        merged = dict(gradings[0])
    else:
        first = gradings[0]
        merged = {"expectations": []}
        disagreements = 0
        for idx, exp in enumerate(first.get("expectations", [])):
            verdicts = []
            for grading in gradings:
                exps = grading.get("expectations", [])
                verdicts.append(bool(exps[idx].get("passed")) if idx < len(exps) else False)
            agreed = all(v == verdicts[0] for v in verdicts)
            if not agreed:
                disagreements += 1
            merged["expectations"].append(
                {
                    "text": exp.get("text", f"expectation {idx}"),
                    "passed": all(verdicts),
                    "evidence": exp.get("evidence", "")
                    + ("" if agreed else " [graders disagreed]"),
                }
            )

        def probe_and(key: str) -> list:
            by_id: dict = {}
            for grading in gradings:
                for row in grading.get(key, []) or []:
                    pid = row.get("id")
                    by_id.setdefault(pid, []).append(bool(row.get("correct")))
            return [{"id": pid, "correct": all(vs)} for pid, vs in sorted(by_id.items())]

        merged["probe_results"] = probe_and("probe_results")
        prefix_merged: dict = {}
        fractions = set()
        for grading in gradings:
            fractions.update((grading.get("prefix_results") or {}).keys())
        for fraction in fractions:
            by_id: dict = {}
            for grading in gradings:
                for row in (grading.get("prefix_results") or {}).get(fraction, []):
                    by_id.setdefault(row.get("id"), []).append(bool(row.get("correct")))
            prefix_merged[fraction] = [
                {"id": pid, "correct": all(vs)} for pid, vs in sorted(by_id.items())
            ]
        merged["prefix_results"] = prefix_merged

        def mean_of(key: str):
            values = [g.get(key) for g in gradings if isinstance(g.get(key), (int, float))]
            return round(statistics.mean(values), 3) if values else None

        merged["scores"] = {
            k: round(
                statistics.mean(
                    [g.get("scores", {}).get(k, 0) for g in gradings if g.get("scores")]
                ),
                2,
            )
            for k in ("gist", "coherence", "overhead", "concreteness")
        }
        merged["boundary_coverage"] = gradings[0].get("boundary_coverage", {})
        merged["false_certainty"] = {
            "sampled": max(
                (g.get("false_certainty", {}).get("sampled", 0) for g in gradings),
                default=0,
            ),
            "wrong_flat": max(
                (g.get("false_certainty", {}).get("wrong_flat", 0) for g in gradings),
                default=0,
            ),
        }
        merged["extraneous_ratio"] = mean_of("extraneous_ratio")
        altitudes = [
            g.get("altitude", {}).get("implementation_share")
            for g in gradings
            if isinstance(g.get("altitude"), dict)
        ]
        altitudes = [a for a in altitudes if isinstance(a, (int, float))]
        if altitudes:
            merged["altitude"] = {
                "implementation_share": round(statistics.mean(altitudes), 3)
            }
        total = len(merged["expectations"])
        merged["grader_agreement"] = (
            round((total - disagreements) / total, 3) if total else 1.0
        )

    expectations = merged.get("expectations", [])
    passed = sum(1 for e in expectations if e.get("passed"))
    merged["summary"] = {
        "passed": passed,
        "failed": len(expectations) - passed,
        "total": len(expectations),
        "pass_rate": round(passed / len(expectations), 3) if expectations else 0,
    }
    merged["graders"] = len(gradings)
    return merged


def run_combo(
    case: dict,
    arm: str,
    skill_path: Path | None,
    workspace: Path,
    iteration_dir: Path,
    model: str,
    effort: str,
    graders: int,
    force: bool,
) -> str:
    run_dir = iteration_dir / case["name"] / arm
    outputs = run_dir / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    target = target_path(case, workspace)
    log = lambda msg: print(f"[{case['name']}/{arm}] {msg}", flush=True)

    # ---------------- floor pseudo-arm: probes with no explanation ----------
    if arm == FLOOR_ARM:
        answers_file = outputs / "learner_answers.json"
        if answers_file.exists() and not force:
            answers = json.loads(answers_file.read_text(encoding="utf-8"))
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
            answers = extract_json(envelope.get("result", ""), "[", "]")
            answers_file.write_text(
                json.dumps(answers, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        grading_file = run_dir / "grading.json"
        if not grading_file.exists() or force:
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
            grading = extract_json(envelope.get("result", ""), "{", "}")
            grading = merge_gradings([grading])
            grading_file.write_text(
                json.dumps(grading, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            log(f"floor grade: done ({grading['summary']['passed']}/{grading['summary']['total']})")
        return f"{case['name']}/{arm}"

    # ---------------- stage 1: explain -------------------------------------
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

    # ---------------- stage 2: learn (full + prefixes) ----------------------
    answers_file = outputs / "learner_answers.json"
    if answers_file.exists() and not force:
        log("learn: cached")
        answers = json.loads(answers_file.read_text(encoding="utf-8"))
    else:
        log("learn(full): running")
        answers = run_learner(case, explanation, model, effort)
        answers_file.write_text(
            json.dumps(answers, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log("learn(full): done")

    prefix_answers: dict[str, list] = {}
    for fraction in case.get("prefixes", []):
        key = str(fraction)
        prefix_file = outputs / f"learner_answers_prefix_{key}.json"
        if prefix_file.exists() and not force:
            prefix_answers[key] = json.loads(prefix_file.read_text(encoding="utf-8"))
            continue
        log(f"learn(prefix {key}): running")
        truncated = explanation[: max(200, int(len(explanation) * fraction))]
        truncated += "\n\n（說明文件到此被截斷。）"
        prefix_answers[key] = run_learner(case, truncated, model, effort)
        prefix_file.write_text(
            json.dumps(prefix_answers[key], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log(f"learn(prefix {key}): done")

    # ---------------- stage 3: grade (ensemble, blind) ----------------------
    grading_file = run_dir / "grading.json"
    if grading_file.exists() and not force:
        log("grade: cached")
    else:
        boundaries = "\n".join(f"{i+1}. {b}" for i, b in enumerate(case.get("boundaries", [])))
        altitude_task = ""
        altitude_field = ""
        if case.get("altitude_max_implementation") is not None:
            altitude_task = (
                "\n### 8. 內容高度（altitude）\n"
                "這份說明的目標讀者是不懂程式的角色。把說明逐段標高度 "
                "{purpose|functional|operational|implementation}，回報 implementation "
                "段落比例（0-1）。程式碼路徑僅作為文末引用或括號證據時，不算 implementation 段。"
            )
            altitude_field = ',\n  "altitude": {"implementation_share": 0.05}'
        prompt = render(
            load_prompt("grader"),
            QUESTION=case["question"],
            BOUNDARIES=boundaries or "（本案未宣告埋藏邊界，第 3 項回報空清單即可）",
            PROBES_WITH_GT=probes_with_gt(case),
            LEARNER_ANSWERS=json.dumps(answers, ensure_ascii=False, indent=2),
            PREFIX_ANSWERS=json.dumps(prefix_answers, ensure_ascii=False, indent=2)
            or "{}",
            EXPLANATION=explanation,
            ALTITUDE_TASK=altitude_task,
            ALTITUDE_FIELD=altitude_field,
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
            grading = extract_json(envelope.get("result", ""), "{", "}")
            g_file.write_text(
                json.dumps(grading, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            gradings.append(grading)
        merged = merge_gradings(gradings)
        grading_file.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log(
            f"grade: done ({merged['summary']['passed']}/{merged['summary']['total']}"
            f", agreement={merged.get('grader_agreement', 1.0)})"
        )

    return f"{case['name']}/{arm}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--iteration", type=int, default=2)
    parser.add_argument(
        "--arms", default="with_skill,old_skill,without_skill",
        help="comma list of with_skill,old_skill,without_skill",
    )
    parser.add_argument("--old-skill-path", type=Path, default=None)
    parser.add_argument("--cases", default="", help="comma list of case names; default all")
    parser.add_argument("--model", default="claude-opus-4-8")
    parser.add_argument("--effort", default="max")
    parser.add_argument("--graders", type=int, default=2)
    parser.add_argument("--no-floor", action="store_true", help="skip the null_floor arm")
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
    if not args.no_floor:
        arm_skills[FLOOR_ARM] = None

    workspace = args.workspace
    iteration_dir = workspace / f"iteration-{args.iteration}"
    iteration_dir.mkdir(parents=True, exist_ok=True)

    for case in cases:
        case_dir = iteration_dir / case["name"]
        case_dir.mkdir(parents=True, exist_ok=True)
        assertions = [
            f"probe {p['id']} ({p.get('tier', 'retention')}"
            + (", trap" if p.get("trap") else "")
            + f"): {p['question']}"
            for p in case["probes"]
        ]
        assertions += [
            "gist / coherence / overhead / concreteness (各 >=4/5)",
            "boundaries: 主動揭露 >=2/3 埋藏邊界",
            "calibration: 抽查肯定斷言 0 錯誤",
            "citations: 引用存在且支持主張",
        ]
        if case.get("altitude_max_implementation") is not None:
            assertions.append(
                f"altitude: implementation 段落 <= {case['altitude_max_implementation']:.0%}"
            )
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
                args.graders,
                args.force,
            ): (case["name"], arm)
            for case, arm in combos
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                future.result()
                print(f"DONE {name[0]}/{name[1]}", flush=True)
            except Exception as err:
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
