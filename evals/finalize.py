#!/usr/bin/env python3
"""Cross-repeat finalization for the learning-transfer eval.

Aggregates multiple iteration directories as independent repeats of the same
battery, reports mean ± sd per arm, computes per-(case, repeat) paired deltas
between two arms with a bootstrap 95% CI, and evaluates release criteria.

Usage:
  python3 evals/finalize.py \
    --arm with_skill=/ws/iteration-4,/ws/iteration-5,/ws/iteration-6 \
    --arm without_skill=/ws/iteration-2,/ws/iteration-5,/ws/iteration-6 \
    --ref old_skill=/ws/iteration-2 \
    --ref null_floor=/ws/iteration-2 \
    --paired with_skill:without_skill \
    --out /ws/final

Repeats are paired positionally: the i-th directory of each paired arm is
treated as the same repeat context.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from datetime import datetime, timezone
from pathlib import Path

import aggregate


def arm_rows_in(iteration_dir: Path, arm: str) -> list[dict]:
    return [r for r in aggregate.collect(iteration_dir) if r["arm"] == arm]


def per_case_probe_acc(rows: list[dict]) -> dict[str, float]:
    result = {}
    for row in rows:
        acc = aggregate.probe_accuracy(row["grading"].get("probe_results", []))
        if acc is not None:
            result[row["case"]] = acc
    return result


def per_case_prefix_acc(rows: list[dict]) -> dict[str, float]:
    result = {}
    for row in rows:
        hits = []
        for res_list in (row["grading"].get("prefix_results") or {}).values():
            hits.extend(bool(r.get("correct")) for r in res_list)
        if hits:
            result[row["case"]] = sum(hits) / len(hits)
    return result


def repeat_metrics(rows: list[dict], floor_acc: dict) -> dict:
    metrics = aggregate.v2_metrics_for_arm(rows, floor_acc)
    pass_rates = [r["grading"].get("summary", {}).get("pass_rate", 0) for r in rows]
    metrics["pass_rate"] = round(statistics.mean(pass_rates), 3) if pass_rates else None
    return metrics


def mean_sd(values: list[float | None]) -> dict | None:
    values = [v for v in values if isinstance(v, (int, float))]
    if not values:
        return None
    return {
        "mean": round(statistics.mean(values), 3),
        "sd": round(statistics.stdev(values), 3) if len(values) > 1 else 0.0,
        "n": len(values),
        "values": [round(v, 3) for v in values],
    }


def bootstrap_ci(deltas: list[float], iterations: int = 10_000, seed: int = 20260820) -> dict:
    rng = random.Random(seed)
    means = []
    for _ in range(iterations):
        sample = [rng.choice(deltas) for _ in deltas]
        means.append(statistics.mean(sample))
    means.sort()
    return {
        "mean": round(statistics.mean(deltas), 3),
        "ci95": [
            round(means[int(0.025 * iterations)], 3),
            round(means[int(0.975 * iterations)], 3),
        ],
        "n_pairs": len(deltas),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", action="append", default=[], metavar="NAME=DIR[,DIR...]")
    parser.add_argument("--ref", action="append", default=[], metavar="NAME=DIR")
    parser.add_argument("--paired", default=None, metavar="ARMA:ARMB")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    arm_dirs: dict[str, list[Path]] = {}
    for spec in args.arm:
        name, dirs = spec.split("=", 1)
        arm_dirs[name] = [Path(d) for d in dirs.split(",")]
    ref_dirs: dict[str, Path] = {}
    for spec in args.ref:
        name, d = spec.split("=", 1)
        ref_dirs[name] = Path(d)

    floor_acc: dict[str, float] = {}
    if "null_floor" in ref_dirs:
        floor_acc = per_case_probe_acc(arm_rows_in(ref_dirs["null_floor"], "null_floor"))

    headline = [
        "pass_rate", "probe_accuracy", "lift_over_floor", "trap_accuracy",
        "prefix25_accuracy", "brier", "boundary_coverage",
        "false_certainty_total", "extraneous_ratio",
        "altitude_implementation_share",
    ]

    arms_summary: dict = {}
    per_repeat_case_acc: dict[str, list[dict]] = {}
    per_repeat_case_prefix: dict[str, list[dict]] = {}
    for arm, dirs in arm_dirs.items():
        repeats = []
        per_repeat_case_acc[arm] = []
        per_repeat_case_prefix[arm] = []
        for d in dirs:
            rows = arm_rows_in(d, arm)
            if not rows:
                raise SystemExit(f"no rows for arm {arm} in {d}")
            repeats.append(repeat_metrics(rows, floor_acc))
            per_repeat_case_acc[arm].append(per_case_probe_acc(rows))
            per_repeat_case_prefix[arm].append(per_case_prefix_acc(rows))
        arms_summary[arm] = {
            "repeat_dirs": [str(d) for d in dirs],
            "metrics": {m: mean_sd([r.get(m) for r in repeats]) for m in headline},
        }

    refs_summary: dict = {}
    for name, d in ref_dirs.items():
        rows = arm_rows_in(d, name)
        refs_summary[name] = repeat_metrics(rows, floor_acc) if rows else None

    paired = None
    if args.paired:
        arm_a, arm_b = args.paired.split(":")
        probe_deltas, prefix_deltas = [], []
        n_repeats = min(len(arm_dirs[arm_a]), len(arm_dirs[arm_b]))
        for i in range(n_repeats):
            acc_a, acc_b = per_repeat_case_acc[arm_a][i], per_repeat_case_acc[arm_b][i]
            for case in sorted(set(acc_a) & set(acc_b)):
                probe_deltas.append(acc_a[case] - acc_b[case])
            pre_a, pre_b = per_repeat_case_prefix[arm_a][i], per_repeat_case_prefix[arm_b][i]
            for case in sorted(set(pre_a) & set(pre_b)):
                prefix_deltas.append(pre_a[case] - pre_b[case])
        paired = {
            "arms": [arm_a, arm_b],
            "probe_accuracy_delta": bootstrap_ci(probe_deltas) if probe_deltas else None,
            "prefix25_delta": bootstrap_ci(prefix_deltas) if prefix_deltas else None,
        }

    # Release criteria for finalizing the tuned skill.
    criteria = []
    if paired and "with_skill" in arm_dirs and "without_skill" in arm_dirs:
        w = {m: arms_summary["with_skill"]["metrics"].get(m) for m in headline}
        wo = {m: arms_summary["without_skill"]["metrics"].get(m) for m in headline}

        def add(name: str, ok: bool, detail: str):
            criteria.append({"criterion": name, "ok": bool(ok), "detail": detail})

        delta = paired["probe_accuracy_delta"]
        add(
            "transfer not worse than bare (paired CI overlaps or exceeds 0)",
            delta["ci95"][1] >= 0,
            f"probe delta {delta['mean']:+.3f}, 95% CI {delta['ci95']}",
        )
        pre = paired["prefix25_delta"]
        add(
            "anytime validity better than bare (prefix25 delta > 0)",
            pre["mean"] > 0,
            f"prefix25 delta {pre['mean']:+.3f}, 95% CI {pre['ci95']}",
        )
        add(
            "reader calibration not worse (Brier)",
            w["brier"]["mean"] <= wo["brier"]["mean"] + 0.01,
            f"Brier {w['brier']['mean']} vs {wo['brier']['mean']}",
        )
        add(
            "zero fabricated flat assertions across repeats",
            w["false_certainty_total"]["mean"] == 0,
            f"false-certainty per repeat: {w['false_certainty_total']['values']}",
        )
        alt = w["altitude_implementation_share"]
        add(
            "pm-case altitude within cap (<=0.10 mean)",
            alt is None or alt["mean"] <= 0.10,
            f"implementation share {alt['mean'] if alt else 'n/a'}",
        )
        add(
            "boundary coverage stays complete",
            w["boundary_coverage"]["mean"] >= 0.9,
            f"boundary coverage {w['boundary_coverage']['mean']}",
        )
        old = refs_summary.get("old_skill")
        if old:
            add(
                "leaner than the pre-tune skill (extraneous)",
                w["extraneous_ratio"]["mean"] < (old.get("extraneous_ratio") or 1),
                f"extraneous {w['extraneous_ratio']['mean']} vs old {old.get('extraneous_ratio')}",
            )
    release = all(c["ok"] for c in criteria) if criteria else None

    report = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "arms": arms_summary,
        "references_n1": refs_summary,
        "paired": paired,
        "release_criteria": criteria,
        "release_ok": release,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "benchmark-final.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# Final benchmark — repeats aggregate",
        "",
        f"Generated: {report['generated']}",
        "",
        "| metric | " + " | ".join(arm_dirs) + " |",
        "| --- |" + " --- |" * len(arm_dirs),
    ]
    for metric in headline:
        cells = []
        for arm in arm_dirs:
            entry = arms_summary[arm]["metrics"].get(metric)
            cells.append(f"{entry['mean']} ± {entry['sd']}" if entry else "—")
        lines.append(f"| {metric} | " + " | ".join(cells) + " |")
    if paired:
        lines += [
            "",
            f"## Paired deltas ({paired['arms'][0]} − {paired['arms'][1]})",
            "",
            f"- probe accuracy: {paired['probe_accuracy_delta']['mean']:+.3f} "
            f"(95% CI {paired['probe_accuracy_delta']['ci95']}, "
            f"n={paired['probe_accuracy_delta']['n_pairs']} case×repeat pairs)",
            f"- prefix25: {paired['prefix25_delta']['mean']:+.3f} "
            f"(95% CI {paired['prefix25_delta']['ci95']})",
        ]
    if criteria:
        lines += ["", "## Release criteria", ""]
        for c in criteria:
            lines.append(f"- {'✅' if c['ok'] else '❌'} {c['criterion']} — {c['detail']}")
        lines += ["", f"**Release: {'PASS' if release else 'BLOCKED'}**"]
    (args.out / "benchmark-final.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.out}/benchmark-final.json and .md")
    print(f"release_ok = {release}")
    return 0


if __name__ == "__main__":
    main()
