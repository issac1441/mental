#!/usr/bin/env python3
"""Aggregate learning-transfer eval results (v2) into benchmark.json / .md.

Reads iteration-N/<case>/<arm>/{grading.json, timing.json, outputs/} produced
by run_eval.py and emits:
- benchmark.json — skill-creator viewer schema (runs / run_summary / notes)
  plus a `v2_metrics` block per arm (tier accuracy, trap accuracy, Brier,
  prefix accuracy, boundary coverage, false-certainty, extraneous ratio,
  altitude, lift over the null_floor arm, grader agreement)
- benchmark.md — human-readable summary
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
ARM_ORDER = ["with_skill", "old_skill", "without_skill", "null_floor"]


def stats(values: list[float]) -> dict:
    if not values:
        return {"mean": 0, "stddev": 0, "min": 0, "max": 0}
    return {
        "mean": round(statistics.mean(values), 3),
        "stddev": round(statistics.stdev(values), 3) if len(values) > 1 else 0.0,
        "min": round(min(values), 3),
        "max": round(max(values), 3),
    }


def load_case_meta() -> dict:
    meta = {}
    for path in sorted((EVALS_DIR / "cases").glob("*.json")) + sorted(
        (EVALS_DIR / "cases" / "dialogue").glob("*.json")
    ):
        case = json.loads(path.read_text(encoding="utf-8"))
        meta[case["name"]] = {
            "probes": {p["id"]: p for p in case["probes"]},
            "boundaries": case.get("boundaries", []),
        }
    return meta


def probe_accuracy(rows: list[dict]) -> float | None:
    if not rows:
        return None
    return sum(1 for r in rows if r.get("correct")) / len(rows)


def collect(iteration_dir: Path) -> list[dict]:
    case_meta = load_case_meta()
    rows = []
    for case_dir in sorted(p for p in iteration_dir.iterdir() if p.is_dir()):
        meta_path = case_dir / "eval_metadata.json"
        if not meta_path.exists():
            continue
        eval_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        for arm_dir in sorted(p for p in case_dir.iterdir() if p.is_dir()):
            grading_path = arm_dir / "grading.json"
            if not grading_path.exists():
                continue
            grading = json.loads(grading_path.read_text(encoding="utf-8"))
            timing_path = arm_dir / "timing.json"
            timing = (
                json.loads(timing_path.read_text(encoding="utf-8"))
                if timing_path.exists()
                else {}
            )
            answers_path = arm_dir / "outputs" / "learner_answers.json"
            answers = (
                json.loads(answers_path.read_text(encoding="utf-8"))
                if answers_path.exists()
                else []
            )
            rows.append(
                {
                    "case": eval_meta.get("eval_name", case_dir.name),
                    "eval_id": eval_meta.get("eval_id"),
                    "prompt": eval_meta.get("prompt", ""),
                    "arm": arm_dir.name,
                    "grading": grading,
                    "timing": timing,
                    "answers": {a.get("id"): a for a in answers},
                    "probe_meta": case_meta.get(case_dir.name, {}).get("probes", {}),
                }
            )
    return rows


def v2_metrics_for_arm(arm_rows: list[dict], floor_acc: dict) -> dict:
    tier_hits: dict[str, list[bool]] = {}
    trap_hits: list[bool] = []
    brier_terms: list[float] = []
    prefix_hits: list[bool] = []
    full_acc_by_case: dict[str, float] = {}
    boundary_cov: list[float] = []
    false_cert: list[int] = []
    extraneous: list[float] = []
    altitude: list[float] = []
    agreement: list[float] = []

    for row in arm_rows:
        grading = row["grading"]
        probe_rows = grading.get("probe_results", [])
        acc = probe_accuracy(probe_rows)
        if acc is not None:
            full_acc_by_case[row["case"]] = acc
        for res in probe_rows:
            pid = res.get("id")
            correct = bool(res.get("correct"))
            meta = row["probe_meta"].get(pid, {})
            tier_hits.setdefault(meta.get("tier", "retention"), []).append(correct)
            if meta.get("trap"):
                trap_hits.append(correct)
            answer = row["answers"].get(pid)
            if answer is not None and isinstance(answer.get("confidence"), (int, float)):
                conf = max(0.0, min(100.0, float(answer["confidence"]))) / 100.0
                brier_terms.append((conf - (1.0 if correct else 0.0)) ** 2)
        for res_list in (grading.get("prefix_results") or {}).values():
            prefix_hits.extend(bool(r.get("correct")) for r in res_list)
        cov = grading.get("boundary_coverage")
        if isinstance(cov, dict) and (cov.get("covered") or cov.get("missed")):
            covered, missed = len(cov.get("covered", [])), len(cov.get("missed", []))
            if covered + missed:
                boundary_cov.append(covered / (covered + missed))
        fc = grading.get("false_certainty")
        if isinstance(fc, dict) and fc.get("sampled"):
            false_cert.append(int(fc.get("wrong_flat", 0)))
        if isinstance(grading.get("extraneous_ratio"), (int, float)):
            extraneous.append(float(grading["extraneous_ratio"]))
        alt = grading.get("altitude", {})
        if isinstance(alt, dict) and isinstance(
            alt.get("implementation_share"), (int, float)
        ):
            altitude.append(float(alt["implementation_share"]))
        if isinstance(grading.get("grader_agreement"), (int, float)):
            agreement.append(float(grading["grader_agreement"]))

    lifts = [
        full_acc_by_case[case] - floor_acc[case]
        for case in full_acc_by_case
        if case in floor_acc
    ]
    all_hits = [h for hits in tier_hits.values() for h in hits]

    def pct(values: list[bool]) -> float | None:
        return round(sum(values) / len(values), 3) if values else None

    return {
        "probe_accuracy": pct(all_hits),
        "tier_accuracy": {tier: pct(hits) for tier, hits in sorted(tier_hits.items())},
        "trap_accuracy": pct(trap_hits),
        "brier": round(statistics.mean(brier_terms), 3) if brier_terms else None,
        "prefix25_accuracy": pct(prefix_hits),
        "boundary_coverage": round(statistics.mean(boundary_cov), 3)
        if boundary_cov
        else None,
        "false_certainty_total": sum(false_cert) if false_cert else 0,
        "extraneous_ratio": round(statistics.mean(extraneous), 3)
        if extraneous
        else None,
        "altitude_implementation_share": round(statistics.mean(altitude), 3)
        if altitude
        else None,
        "lift_over_floor": round(statistics.mean(lifts), 3) if lifts else None,
        "grader_agreement": round(statistics.mean(agreement), 3) if agreement else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iteration_dir", type=Path)
    parser.add_argument("--skill-name", default="understand")
    args = parser.parse_args()

    rows = collect(args.iteration_dir)
    if not rows:
        print("no graded runs found")
        return 1

    floor_acc = {
        row["case"]: probe_accuracy(row["grading"].get("probe_results", []))
        for row in rows
        if row["arm"] == "null_floor"
    }
    floor_acc = {k: v for k, v in floor_acc.items() if v is not None}

    runs = []
    for row in rows:
        summary = row["grading"].get("summary", {})
        runs.append(
            {
                "eval_id": row["eval_id"],
                "eval_name": row["case"],
                "configuration": row["arm"],
                "run_number": 1,
                "result": {
                    "pass_rate": summary.get("pass_rate", 0),
                    "passed": summary.get("passed", 0),
                    "failed": summary.get("failed", 0),
                    "total": summary.get("total", 0),
                    "time_seconds": row["timing"].get("total_duration_seconds", 0),
                    "tokens": row["timing"].get("total_tokens", 0),
                    "tool_calls": 0,
                    "errors": 0,
                },
                "expectations": row["grading"].get("expectations", []),
                "notes": [],
            }
        )

    run_summary: dict = {}
    v2_metrics: dict = {}
    for arm in ARM_ORDER:
        arm_rows = [r for r in rows if r["arm"] == arm]
        if not arm_rows:
            continue
        run_summary[arm] = {
            "pass_rate": stats(
                [r["grading"].get("summary", {}).get("pass_rate", 0) for r in arm_rows]
            ),
            "time_seconds": stats(
                [r["timing"].get("total_duration_seconds", 0) for r in arm_rows]
            ),
            "tokens": stats([r["timing"].get("total_tokens", 0) for r in arm_rows]),
        }
        v2_metrics[arm] = v2_metrics_for_arm(arm_rows, floor_acc)

    if "with_skill" in run_summary and "without_skill" in run_summary:
        run_summary["delta"] = {
            "pass_rate": f"{run_summary['with_skill']['pass_rate']['mean'] - run_summary['without_skill']['pass_rate']['mean']:+.3f}",
            "time_seconds": f"{run_summary['with_skill']['time_seconds']['mean'] - run_summary['without_skill']['time_seconds']['mean']:+.1f}",
            "tokens": f"{run_summary['with_skill']['tokens']['mean'] - run_summary['without_skill']['tokens']['mean']:+.0f}",
        }

    notes = []
    for arm, metrics in v2_metrics.items():
        if arm == "null_floor":
            notes.append(
                f"null_floor: probe accuracy {metrics['probe_accuracy']} "
                "(prior-knowledge floor; lower = harder to guess)"
            )
            continue
        parts = [f"{arm}: probes {metrics['probe_accuracy']}"]
        if metrics["lift_over_floor"] is not None:
            parts.append(f"lift over floor {metrics['lift_over_floor']:+.3f}")
        if metrics["trap_accuracy"] is not None:
            parts.append(f"traps {metrics['trap_accuracy']}")
        if metrics["prefix25_accuracy"] is not None:
            parts.append(f"prefix25 {metrics['prefix25_accuracy']}")
        if metrics["brier"] is not None:
            parts.append(f"Brier {metrics['brier']}")
        if metrics["boundary_coverage"] is not None:
            parts.append(f"boundaries {metrics['boundary_coverage']}")
        parts.append(f"false-certainty {metrics['false_certainty_total']}")
        if metrics["extraneous_ratio"] is not None:
            parts.append(f"extraneous {metrics['extraneous_ratio']}")
        if metrics["altitude_implementation_share"] is not None:
            parts.append(f"impl-share {metrics['altitude_implementation_share']}")
        notes.append(", ".join(parts))

    benchmark = {
        "metadata": {
            "skill_name": args.skill_name,
            "skill_path": "skills/understand",
            "executor_model": "claude-opus-4-8 (effort=max)",
            "analyzer_model": "deterministic aggregate.py v2",
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "evals_run": sorted({r["case"] for r in rows}),
            "runs_per_configuration": 1,
        },
        "runs": runs,
        "run_summary": run_summary,
        "v2_metrics": v2_metrics,
        "notes": notes,
    }

    out_json = args.iteration_dir / "benchmark.json"
    out_json.write_text(
        json.dumps(benchmark, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# Learning-transfer benchmark (v2)",
        "",
        f"Generated: {benchmark['metadata']['timestamp']}",
        "",
        "| configuration | pass rate | probes | lift/floor | traps | prefix25 | Brier | boundaries | false-cert | extraneous | time s |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for arm in ARM_ORDER:
        if arm not in v2_metrics:
            continue
        m = v2_metrics[arm]
        s = run_summary.get(arm, {})

        def fmt(value, pattern="{:.3f}"):
            return pattern.format(value) if isinstance(value, (int, float)) else "—"

        lines.append(
            f"| {arm} | {fmt(s.get('pass_rate', {}).get('mean'))} "
            f"| {fmt(m['probe_accuracy'])} | {fmt(m['lift_over_floor'], '{:+.3f}')} "
            f"| {fmt(m['trap_accuracy'])} | {fmt(m['prefix25_accuracy'])} "
            f"| {fmt(m['brier'])} | {fmt(m['boundary_coverage'])} "
            f"| {m['false_certainty_total']} | {fmt(m['extraneous_ratio'])} "
            f"| {fmt(s.get('time_seconds', {}).get('mean'), '{:.1f}')} |"
        )
    lines += ["", "## Tier accuracy", ""]
    tiers = sorted(
        {t for m in v2_metrics.values() for t in (m.get("tier_accuracy") or {})}
    )
    lines.append("| configuration | " + " | ".join(tiers) + " |")
    lines.append("| --- |" + " --- |" * len(tiers))
    for arm in ARM_ORDER:
        if arm not in v2_metrics:
            continue
        ta = v2_metrics[arm].get("tier_accuracy") or {}
        cells = [
            ("{:.2f}".format(ta[t]) if isinstance(ta.get(t), (int, float)) else "—")
            for t in tiers
        ]
        lines.append(f"| {arm} | " + " | ".join(cells) + " |")
    lines += ["", "## Notes", ""]
    lines += [f"- {note}" for note in notes]
    out_md = args.iteration_dir / "benchmark.md"
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_json}\nwrote {out_md}")
    return 0


if __name__ == "__main__":
    main()
