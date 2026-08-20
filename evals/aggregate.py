#!/usr/bin/env python3
"""Aggregate learning-transfer eval results into benchmark.json / benchmark.md.

Reads an iteration directory produced by run_eval.py:

    iteration-N/<case>/<arm>/{grading.json, timing.json, outputs/}

and writes benchmark.json (skill-creator viewer schema) plus a Markdown
summary next to it. Arms are treated as "configurations".
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

ARM_ORDER = ["with_skill", "old_skill", "without_skill"]


def stats(values: list[float]) -> dict:
    if not values:
        return {"mean": 0, "stddev": 0, "min": 0, "max": 0}
    return {
        "mean": round(statistics.mean(values), 3),
        "stddev": round(statistics.stdev(values), 3) if len(values) > 1 else 0.0,
        "min": round(min(values), 3),
        "max": round(max(values), 3),
    }


def collect(iteration_dir: Path) -> tuple[list[dict], dict]:
    runs: list[dict] = []
    extras: dict[str, list[dict]] = {}
    for case_dir in sorted(p for p in iteration_dir.iterdir() if p.is_dir()):
        meta_path = case_dir / "eval_metadata.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        for arm_dir in sorted(p for p in case_dir.iterdir() if p.is_dir()):
            grading_path = arm_dir / "grading.json"
            timing_path = arm_dir / "timing.json"
            if not grading_path.exists():
                continue
            grading = json.loads(grading_path.read_text(encoding="utf-8"))
            timing = (
                json.loads(timing_path.read_text(encoding="utf-8"))
                if timing_path.exists()
                else {}
            )
            summary = grading.get("summary", {})
            runs.append(
                {
                    "eval_id": meta.get("eval_id"),
                    "eval_name": meta.get("eval_name", case_dir.name),
                    "configuration": arm_dir.name,
                    "run_number": 1,
                    "result": {
                        "pass_rate": summary.get("pass_rate", 0),
                        "passed": summary.get("passed", 0),
                        "failed": summary.get("failed", 0),
                        "total": summary.get("total", 0),
                        "time_seconds": timing.get("total_duration_seconds", 0),
                        "tokens": timing.get("total_tokens", 0),
                        "tool_calls": 0,
                        "errors": 0,
                    },
                    "expectations": grading.get("expectations", []),
                    "notes": [],
                }
            )
            extras.setdefault(arm_dir.name, []).append(
                {
                    "case": meta.get("eval_name", case_dir.name),
                    "probe_correct": grading.get("probe_summary", {}).get("correct"),
                    "probe_total": grading.get("probe_summary", {}).get("total"),
                    "scores": grading.get("scores", {}),
                    "explanation_chars": timing.get("explanation_chars"),
                    "time_seconds": timing.get("total_duration_seconds"),
                }
            )
    return runs, extras


def summarize(runs: list[dict], extras: dict) -> tuple[dict, list[str]]:
    run_summary: dict = {}
    for arm in ARM_ORDER:
        arm_runs = [r for r in runs if r["configuration"] == arm]
        if not arm_runs:
            continue
        run_summary[arm] = {
            "pass_rate": stats([r["result"]["pass_rate"] for r in arm_runs]),
            "time_seconds": stats([r["result"]["time_seconds"] for r in arm_runs]),
            "tokens": stats([r["result"]["tokens"] for r in arm_runs]),
        }

    if "with_skill" in run_summary and "without_skill" in run_summary:
        run_summary["delta"] = {
            "pass_rate": f"{run_summary['with_skill']['pass_rate']['mean'] - run_summary['without_skill']['pass_rate']['mean']:+.3f}",
            "time_seconds": f"{run_summary['with_skill']['time_seconds']['mean'] - run_summary['without_skill']['time_seconds']['mean']:+.1f}",
            "tokens": f"{run_summary['with_skill']['tokens']['mean'] - run_summary['without_skill']['tokens']['mean']:+.0f}",
        }

    notes: list[str] = []
    for arm in ARM_ORDER:
        rows = extras.get(arm, [])
        if not rows:
            continue
        probe_rates = [
            r["probe_correct"] / r["probe_total"]
            for r in rows
            if r.get("probe_total")
        ]
        chars = [r["explanation_chars"] for r in rows if r.get("explanation_chars")]
        rubric_keys = ("gist", "coherence", "overhead", "concreteness")
        rubric_means = {
            key: round(
                statistics.mean(
                    [r["scores"].get(key, 0) for r in rows if r.get("scores")]
                ),
                2,
            )
            for key in rubric_keys
            if any(r.get("scores") for r in rows)
        }
        notes.append(
            f"{arm}: transfer(probe) accuracy {statistics.mean(probe_rates):.0%}"
            + (f", avg explanation {statistics.mean(chars):,.0f} chars" if chars else "")
            + (f", rubric {rubric_means}" if rubric_means else "")
        )
    return run_summary, notes


def to_markdown(benchmark: dict) -> str:
    lines = [
        "# Learning-transfer benchmark",
        "",
        f"Generated: {benchmark['metadata']['timestamp']}",
        "",
        "| configuration | pass rate (mean) | time s (mean) | tokens (mean) |",
        "| --- | --- | --- | --- |",
    ]
    for arm in ARM_ORDER:
        summary = benchmark["run_summary"].get(arm)
        if not summary:
            continue
        lines.append(
            f"| {arm} | {summary['pass_rate']['mean']:.3f} "
            f"| {summary['time_seconds']['mean']:.1f} "
            f"| {summary['tokens']['mean']:,.0f} |"
        )
    lines += ["", "## Per-run", ""]
    lines.append("| eval | configuration | passed/total | time s |")
    lines.append("| --- | --- | --- | --- |")
    for run in benchmark["runs"]:
        result = run["result"]
        lines.append(
            f"| {run['eval_name']} | {run['configuration']} "
            f"| {result['passed']}/{result['total']} | {result['time_seconds']} |"
        )
    lines += ["", "## Notes", ""]
    lines += [f"- {note}" for note in benchmark["notes"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iteration_dir", type=Path)
    parser.add_argument("--skill-name", default="understand")
    args = parser.parse_args()

    runs, extras = collect(args.iteration_dir)
    if not runs:
        print("no graded runs found")
        return 1
    run_summary, notes = summarize(runs, extras)

    benchmark = {
        "metadata": {
            "skill_name": args.skill_name,
            "skill_path": "skills/understand",
            "executor_model": "claude-opus-4-8 (effort=max)",
            "analyzer_model": "deterministic aggregate.py",
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "evals_run": sorted({r["eval_name"] for r in runs}),
            "runs_per_configuration": 1,
        },
        "runs": runs,
        "run_summary": run_summary,
        "notes": notes,
    }

    out_json = args.iteration_dir / "benchmark.json"
    out_json.write_text(
        json.dumps(benchmark, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    out_md = args.iteration_dir / "benchmark.md"
    out_md.write_text(to_markdown(benchmark), encoding="utf-8")
    print(f"wrote {out_json}\nwrote {out_md}")
    return 0


if __name__ == "__main__":
    main()
