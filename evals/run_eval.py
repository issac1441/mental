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
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
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

PROVENANCE_SCHEMA_VERSION = 1
_MATERIALIZE_LOCK = threading.Lock()
_TARGET_EXCLUDES = {".git", "evals", ".mental", "__pycache__", ".claude"}


class ProvenanceError(RuntimeError):
    """Raised when cached eval artifacts cannot be attributed to this run."""


def sha256_json(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sha256_path(path: Path, exclude_names: set[str] | None = None) -> str:
    """Hash a file or directory tree, including names and symlink targets."""
    path = path.resolve()
    excluded = exclude_names or set()
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes())
        return digest.hexdigest()
    if not path.is_dir():
        raise FileNotFoundError(path)

    for root, dirs, files in os.walk(path, topdown=True, followlinks=False):
        dirs[:] = sorted(name for name in dirs if name not in excluded)
        for name in sorted(files):
            if name in excluded or name.endswith(".pyc"):
                continue
            item = Path(root) / name
            relative = item.relative_to(path).as_posix()
            digest.update(relative.encode("utf-8") + b"\0")
            if item.is_symlink():
                digest.update(b"link\0" + os.readlink(item).encode("utf-8"))
            else:
                digest.update(b"file\0")
                with item.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
    return digest.hexdigest()


def git_head(root: Path) -> str | None:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def plugin_version(root: Path) -> str:
    manifest = root / ".claude-plugin" / "plugin.json"
    try:
        value = json.loads(manifest.read_text(encoding="utf-8")).get("version")
    except (OSError, json.JSONDecodeError):
        value = None
    return str(value) if value else "unknown"


def _atomic_materialize(target: Path, builder) -> Path:
    """Materialize one immutable target without exposing a partial directory."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with _MATERIALIZE_LOCK:
        if target.exists():
            return target
        staging_root = Path(
            tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent)
        )
        payload = staging_root / "payload"
        try:
            builder(payload)
            os.replace(payload, target)
        finally:
            shutil.rmtree(staging_root, ignore_errors=True)
    return target


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
    resume: str | None = None,
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
    if resume:
        cmd += ["--resume", resume]
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
    """Return the largest parseable JSON value delimited by opener/closer.

    Grader/learner prose can contain stray braces (rubric snippets, code),
    so a naive first-to-last slice breaks; walk balanced spans instead."""
    best = None
    start = text.find(opener)
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for idx in range(start, len(text)):
            char = text[idx]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    candidate = text[start : idx + 1]
                    try:
                        parsed = json.loads(candidate)
                        if best is None or len(candidate) > best[0]:
                            best = (len(candidate), parsed)
                    except json.JSONDecodeError:
                        pass
                    break
        start = text.find(opener, start + 1)
    if best is None:
        raise ValueError(f"no JSON found in output: {text[:200]}...")
    return best[1]


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
    source_sha = sha256_path(REPO_ROOT, _TARGET_EXCLUDES)
    target = workspace / f"target-mental-{source_sha[:16]}"

    def build(payload: Path) -> None:
        shutil.copytree(
            REPO_ROOT,
            payload,
            ignore=shutil.ignore_patterns(*_TARGET_EXCLUDES, "*.pyc"),
        )

    return _atomic_materialize(target, build)


def target_path(case: dict, workspace: Path) -> Path:
    base: Path
    if case["target"] == "orderflow":
        base = EVALS_DIR / "fixtures" / "orderflow"
    elif case["target"] == "doctor-workspace":
        base = EVALS_DIR / "fixtures" / "doctor-workspace"
    elif case["target"] == "sync-workspace":
        base = EVALS_DIR / "fixtures" / "sync-workspace"
    elif case["target"] == "mental":
        base = build_mental_target(workspace)
    else:
        raise ValueError(f"unknown target {case['target']}")

    setup = case.get("target_setup")
    if not setup:
        return base

    setup_material = {
        "case": case["name"],
        "base_sha256": sha256_path(base),
        "setup": setup,
    }
    if setup.get("brief"):
        setup_material["brief_sha256"] = sha256_path(REPO_ROOT / setup["brief"])
    if setup.get("overlay"):
        setup_material["overlay_sha256"] = sha256_path(
            REPO_ROOT / setup["overlay"]
        )
    setup_sha = sha256_json(setup_material)
    target = workspace / f"target-{case['name']}-{setup_sha[:16]}"

    def build(payload: Path) -> None:
        shutil.copytree(
            base,
            payload,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"),
        )
        if setup.get("brief"):
            shutil.copy2(REPO_ROOT / setup["brief"], payload / "CHANGE_BRIEF.md")
        if setup.get("git"):
            git = ["git", "-c", "user.email=eval@local", "-c", "user.name=eval"]
            subprocess.run(git + ["init", "-q"], cwd=payload, check=True)
            subprocess.run(git + ["add", "-A"], cwd=payload, check=True)
            subprocess.run(git + ["commit", "-qm", "base"], cwd=payload, check=True)
        if setup.get("overlay"):
            overlay = REPO_ROOT / setup["overlay"]
            for path in overlay.rglob("*"):
                if path.is_file():
                    dest = payload / path.relative_to(overlay)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, dest)

    return _atomic_materialize(target, build)


def run_provenance(
    case: dict,
    arm: str,
    skill_ref: tuple | None,
    target: Path,
    model: str,
    effort: str,
    graders: int,
    runner_path: Path | None = None,
) -> dict:
    runner = runner_path or Path(__file__)
    skill_root = skill_ref[1] if skill_ref is not None else None
    return {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "protocol": case.get("protocol", "single-turn"),
        "case": case["name"],
        "arm": arm,
        "model": model,
        "effort": effort,
        "graders": graders,
        "plugin_version": plugin_version(REPO_ROOT),
        "plugin_git_head": git_head(REPO_ROOT),
        "case_sha256": sha256_json(case),
        "target_sha256": sha256_path(target, {".git", "__pycache__"}),
        "prompt_tree_sha256": sha256_path(EVALS_DIR / "prompts"),
        "runner_sha256": sha256_path(runner),
        "shared_runner_sha256": sha256_path(Path(__file__)),
        "skill_sha256": sha256_path(skill_root, _TARGET_EXCLUDES)
        if skill_root is not None
        else None,
    }


def ensure_run_provenance(run_dir: Path, expected: dict, force: bool) -> None:
    """Allow cache reuse only when every material input matches exactly."""
    provenance_file = run_dir / "provenance.json"
    existing = None
    if provenance_file.exists():
        try:
            existing = json.loads(provenance_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as err:
            raise ProvenanceError(f"invalid cached provenance: {err}") from err

    payload_exists = run_dir.exists() and any(
        path.name != provenance_file.name for path in run_dir.iterdir()
    )
    if force and run_dir.exists():
        shutil.rmtree(run_dir)
        existing = None
        payload_exists = False
    elif payload_exists and existing is None:
        raise ProvenanceError(
            f"cached artifacts in {run_dir} have no provenance; use a new iteration "
            "or --force"
        )
    elif existing is not None and existing != expected:
        raise ProvenanceError(
            f"cached provenance mismatch in {run_dir}; use a new iteration or --force"
        )

    run_dir.mkdir(parents=True, exist_ok=True)
    if existing is None:
        provenance_file.write_text(
            json.dumps(expected, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def write_invocation_metadata(iteration_dir: Path, payload: dict) -> Path:
    invocations = iteration_dir / "invocations"
    invocations.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    path = invocations / f"{timestamp}-{os.getpid()}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def case_skill_name(case: dict) -> str:
    return case.get("skill", "understand")


def case_allowed_tools(case: dict) -> str:
    if case.get("allowed_tools"):
        return case["allowed_tools"]
    if case.get("target_setup", {}).get("git"):
        return READ_ONLY_TOOLS + " Bash(git *)"
    return READ_ONLY_TOOLS


def case_context_note(case: dict) -> str:
    if case.get("context_note") is not None:
        return case["context_note"]
    if case.get("target_setup", {}).get("git"):
        return "repo 目前有未提交的 diff——請直接執行不加額外旗標的 `git diff` 查看變更；核准的 change brief 在 CHANGE_BRIEF.md。目前 workspace 沒有 mental/ canonical model。"
    if case["target"] == "doctor-workspace":
        return ""
    return "目前 workspace 沒有 mental/ canonical model。"


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


def _validate_probe_rows(rows: object, expected_ids: list, label: str) -> None:
    if not isinstance(rows, list):
        raise ValueError(f"{label} must be a list")
    ids = [row.get("id") for row in rows if isinstance(row, dict)]
    if len(ids) != len(rows):
        raise ValueError(f"{label} contains a non-object row")
    if len(ids) != len(set(map(str, ids))):
        raise ValueError(f"{label} contains duplicate probe IDs")
    if [str(value) for value in ids] != [str(value) for value in expected_ids]:
        raise ValueError(
            f"{label} probe IDs must be exactly {expected_ids!r}, got {ids!r}"
        )
    if any(not isinstance(row.get("correct"), bool) for row in rows):
        raise ValueError(f"{label} correct values must be booleans")


def validate_grading_completeness(
    grading: dict,
    expected_probe_ids: list,
    expected_prefixes: list[str],
    expected_expectations: int | None = None,
) -> None:
    expectations = grading.get("expectations")
    if not isinstance(expectations, list):
        raise ValueError("expectations must be a list")
    if expected_expectations is not None and len(expectations) != expected_expectations:
        raise ValueError(
            f"expectations must contain exactly {expected_expectations} rows, "
            f"got {len(expectations)}"
        )
    if any(
        not isinstance(row, dict) or not isinstance(row.get("passed"), bool)
        for row in expectations
    ):
        raise ValueError("expectation passed values must be booleans")
    _validate_probe_rows(
        grading.get("probe_results", []), expected_probe_ids, "probe_results"
    )
    prefixes = grading.get("prefix_results", {}) or {}
    if not isinstance(prefixes, dict):
        raise ValueError("prefix_results must be an object")
    if set(prefixes) != set(expected_prefixes):
        raise ValueError(
            "prefix_results keys must be exactly "
            f"{expected_prefixes!r}, got {sorted(prefixes)!r}"
        )
    for prefix in expected_prefixes:
        _validate_probe_rows(
            prefixes[prefix], expected_probe_ids, f"prefix_results[{prefix!r}]"
        )


def load_complete_grading(
    path: Path,
    expected_probe_ids: list,
    expected_prefixes: list[str] | None = None,
    expected_expectations: int | None = None,
) -> dict:
    grading = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(grading, dict):
        raise ValueError(f"{path} must contain a JSON object")
    validate_grading_completeness(
        grading,
        expected_probe_ids,
        expected_prefixes or [],
        expected_expectations,
    )
    return grading


def merge_gradings(
    gradings: list[dict],
    expected_probe_ids: list | None = None,
    expected_prefixes: list[str] | None = None,
    expected_expectations: int | None = None,
) -> dict:
    """Conservative merge: an expectation/probe passes only if every grader
    passed it. Scores and ratios are averaged. Disagreements are recorded."""
    if not gradings:
        raise ValueError("at least one grading is required")
    probe_ids = expected_probe_ids or []
    prefixes = expected_prefixes or []
    for index, grading in enumerate(gradings, start=1):
        if not isinstance(grading, dict):
            raise ValueError(f"grading {index} must be an object")
        validate_grading_completeness(
            grading, probe_ids, prefixes, expected_expectations
        )

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
            return [
                {
                    "id": probe_id,
                    "correct": all(
                        bool(grading[key][index].get("correct"))
                        for grading in gradings
                    ),
                }
                for index, probe_id in enumerate(probe_ids)
            ]

        merged["probe_results"] = probe_and("probe_results")
        prefix_merged: dict = {}
        for fraction in prefixes:
            prefix_merged[fraction] = [
                {
                    "id": probe_id,
                    "correct": all(
                        bool(grading["prefix_results"][fraction][index].get("correct"))
                        for grading in gradings
                    ),
                }
                for index, probe_id in enumerate(probe_ids)
            ]
        merged["prefix_results"] = prefix_merged

        def mean_of(key: str):
            values = [g.get(key) for g in gradings if isinstance(g.get(key), (int, float))]
            return round(statistics.mean(values), 3) if values else None

        scored = [g for g in gradings if g.get("scores")]
        if scored:
            merged["scores"] = {
                k: round(
                    statistics.mean([g["scores"].get(k, 0) for g in scored]), 2
                )
                for k in ("gist", "coherence", "overhead", "concreteness")
            }
        if any("false_positives" in g for g in gradings):
            merged["false_positives"] = max(
                int(g.get("false_positives", 0) or 0) for g in gradings
            )
            merged["extra_findings"] = gradings[0].get("extra_findings", [])
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
    skill_ref: tuple | None,
    workspace: Path,
    iteration_dir: Path,
    model: str,
    effort: str,
    graders: int,
    force: bool,
) -> str:
    skill_path: Path | None = None
    if skill_ref is not None:
        skill_path = skill_ref[1] / "skills" / case_skill_name(case) / "SKILL.md"
        if not skill_path.exists():
            raise RuntimeError(f"skill file missing: {skill_path}")
    run_dir = iteration_dir / case["name"] / arm
    target = target_path(case, workspace)
    provenance = run_provenance(
        case, arm, skill_ref, target, model, effort, graders
    )
    ensure_run_provenance(run_dir, provenance, force)
    outputs = run_dir / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)

    def log(msg: str) -> None:
        print(f"[{case['name']}/{arm}] {msg}", flush=True)

    expected_probe_ids = [probe["id"] for probe in case.get("probes", [])]
    expected_prefixes = [str(value) for value in case.get("prefixes", [])]
    expected_detection_rows = len(case.get("boundaries", [])) + len(
        case.get("conformance_checks", [])
    )
    expected_standard_rows = len(expected_probe_ids) + 7

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
        if grading_file.exists() and not force:
            load_complete_grading(
                grading_file,
                expected_probe_ids,
                expected_expectations=len(expected_probe_ids),
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
            grading = extract_json(envelope.get("result", ""), "{", "}")
            grading = merge_gradings(
                [grading],
                expected_probe_ids=expected_probe_ids,
                expected_expectations=len(expected_probe_ids),
            )
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
            question = case["question"]
            note = case_context_note(case)
            if note:
                question = f"{question}\n\n（{note}）"
            prompt = render(load_prompt("explainer-baseline"), QUESTION=question)
            add_dirs = None
        else:
            prompt = render(
                load_prompt("explainer-with-skill"),
                SKILL_NAME=case_skill_name(case),
                QUESTION=case["question"],
                SKILL_PATH=str(skill_path),
                CONTEXT_NOTE=case_context_note(case),
            )
            add_dirs = [skill_path.parents[2]]
        envelope = run_claude(
            prompt,
            cwd=target,
            model=model,
            effort=effort,
            timeout=STAGE_TIMEOUTS["explain"],
            allowed_tools=case_allowed_tools(case),
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

    # ---------------- detection protocol: grade the report directly --------
    if case.get("protocol") == "detection":
        grading_file = run_dir / "grading.json"
        if grading_file.exists() and not force:
            load_complete_grading(
                grading_file, [], expected_expectations=expected_detection_rows
            )
            log("grade: cached")
            return f"{case['name']}/{arm}"
        inventory = "\n".join(
            f"{i+1}. {b}" for i, b in enumerate(case.get("boundaries", []))
        )
        conformance = "\n".join(
            f"{i+1}. {c}" for i, c in enumerate(case.get("conformance_checks", []))
        ) or "（無）"
        prompt = render(
            load_prompt("grader-detection"),
            INVENTORY=inventory,
            CONFORMANCE=conformance,
            REPORT=explanation,
        )
        gradings = []
        for g_index in range(1, graders + 1):
            g_file = run_dir / f"grading-{g_index}.json"
            if g_file.exists() and not force:
                gradings.append(json.loads(g_file.read_text(encoding="utf-8")))
                continue
            log(f"grade[{g_index}/{graders}]: running (detection)")
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
        merged = merge_gradings(
            gradings,
            expected_probe_ids=[],
            expected_expectations=expected_detection_rows,
        )
        grading_file.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log(
            f"grade: done ({merged['summary']['passed']}/{merged['summary']['total']})"
        )
        return f"{case['name']}/{arm}"

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
        load_complete_grading(
            grading_file,
            expected_probe_ids,
            expected_prefixes,
            expected_standard_rows,
        )
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
        merged = merge_gradings(
            gradings,
            expected_probe_ids=expected_probe_ids,
            expected_prefixes=expected_prefixes,
            expected_expectations=expected_standard_rows,
        )
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

    arm_skills: dict[str, tuple | None] = {}
    for arm in args.arms.split(","):
        arm = arm.strip()
        if arm == "with_skill":
            arm_skills[arm] = ("root", REPO_ROOT)
        elif arm == "old_skill":
            if not args.old_skill_path:
                print("--old-skill-path required for old_skill arm", file=sys.stderr)
                return 1
            # --old-skill-path points at <root>/skills/<name>/SKILL.md
            arm_skills[arm] = ("root", args.old_skill_path.parents[2])
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

    write_invocation_metadata(
        iteration_dir,
        {
            "schema_version": PROVENANCE_SCHEMA_VERSION,
            "runner": "run_eval.py",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": args.model,
            "effort": args.effort,
            "graders": args.graders,
            "arms": list(arm_skills),
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
        if case.get("protocol") == "detection":
            assertions = [f"detect: {b}" for b in case.get("boundaries", [])] + [
                f"conformance: {c}" for c in case.get("conformance_checks", [])
            ]
        else:
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

    combos = [
        (case, arm)
        for case in cases
        for arm in arm_skills
        if not (arm == FLOOR_ARM and not case.get("probes"))
    ]
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
