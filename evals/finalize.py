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
import sys
from datetime import datetime, timezone
from pathlib import Path

import aggregate


def arm_rows_in(
    iteration_dir: Path, arm: str, allow_mixed_provenance: bool = False
) -> list[dict]:
    rows = aggregate.collect(iteration_dir)
    aggregate.validate_comparable_provenance(rows, allow_mixed_provenance)
    return [row for row in rows if row["arm"] == arm]


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
    if not deltas:
        raise ValueError("cannot bootstrap an empty paired sample")
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


def paired_metric_deltas(
    arm_a: list[dict[str, float]],
    arm_b: list[dict[str, float]],
    label: str,
) -> list[float]:
    if len(arm_a) != len(arm_b):
        raise ValueError(
            f"paired arms need equal repeat counts for {label}: "
            f"{len(arm_a)} != {len(arm_b)}"
        )
    deltas = []
    for index, (values_a, values_b) in enumerate(zip(arm_a, arm_b, strict=True), start=1):
        cases_a, cases_b = set(values_a), set(values_b)
        if cases_a != cases_b:
            missing_a = sorted(cases_b - cases_a)
            missing_b = sorted(cases_a - cases_b)
            raise ValueError(
                f"paired repeat {index} has different {label} case sets; "
                f"missing from first={missing_a}, missing from second={missing_b}"
            )
        deltas.extend(values_a[case] - values_b[case] for case in sorted(cases_a))
    return deltas


def release_criteria(
    arms_summary: dict,
    refs_summary: dict,
    paired: dict | None,
    noninferiority_margin: float,
) -> list[dict]:
    if not paired or "with_skill" not in arms_summary or "without_skill" not in arms_summary:
        return []
    if paired.get("arms") != ["with_skill", "without_skill"]:
        return [
            {
                "criterion": "paired comparison is with_skill minus without_skill",
                "ok": False,
                "detail": f"paired arms were {paired.get('arms')}",
            }
        ]
    w = arms_summary["with_skill"]["metrics"]
    wo = arms_summary["without_skill"]["metrics"]
    criteria = []

    def add(name: str, ok: bool, detail: str) -> None:
        criteria.append({"criterion": name, "ok": bool(ok), "detail": detail})

    delta = paired.get("probe_accuracy_delta")
    transfer_ok = bool(delta) and delta["ci95"][0] >= noninferiority_margin
    add(
        f"transfer noninferiority (lower CI >= {noninferiority_margin:+.3f})",
        transfer_ok,
        (
            f"probe delta {delta['mean']:+.3f}, 95% CI {delta['ci95']}"
            if delta
            else "probe delta unavailable"
        ),
    )

    prefix = paired.get("prefix25_delta")
    prefix_ok = bool(prefix) and prefix["ci95"][0] > 0
    add(
        "anytime validity better than bare (lower paired CI > 0)",
        prefix_ok,
        (
            f"prefix25 delta {prefix['mean']:+.3f}, 95% CI {prefix['ci95']}"
            if prefix
            else "prefix25 delta unavailable"
        ),
    )

    w_brier, wo_brier = w.get("brier"), wo.get("brier")
    brier_ok = bool(w_brier and wo_brier) and (
        w_brier["mean"] <= wo_brier["mean"] + 0.01
    )
    add(
        "reader calibration present and not worse (Brier)",
        brier_ok,
        (
            f"Brier {w_brier['mean']} vs {wo_brier['mean']}"
            if w_brier and wo_brier
            else "Brier unavailable"
        ),
    )

    false_certainty = w.get("false_certainty_total")
    false_certainty_values = (
        false_certainty.get("values", []) if false_certainty else []
    )
    false_certainty_ok = bool(false_certainty_values) and all(
        value == 0 for value in false_certainty_values
    )
    add(
        "calibration sample present with zero fabricated flat assertions",
        false_certainty_ok,
        (
            f"false-certainty per repeat: {false_certainty_values}"
            if false_certainty
            else "false-certainty sampling unavailable"
        ),
    )

    altitude = w.get("altitude_implementation_share")
    add(
        "pm-case altitude measured and within cap (<=0.10 mean)",
        bool(altitude) and altitude["mean"] <= 0.10,
        f"implementation share {altitude['mean'] if altitude else 'unavailable'}",
    )

    coverage = w.get("boundary_coverage")
    add(
        "boundary coverage measured and stays complete",
        bool(coverage) and coverage["mean"] >= 0.9,
        f"boundary coverage {coverage['mean'] if coverage else 'unavailable'}",
    )

    old = refs_summary.get("old_skill")
    if old is not None:
        old_extraneous = old.get("extraneous_ratio")
        current_extraneous = w.get("extraneous_ratio")
        add(
            "leaner than the pre-tune skill (extraneous)",
            bool(current_extraneous)
            and isinstance(old_extraneous, (int, float))
            and current_extraneous["mean"] < old_extraneous,
            (
                f"extraneous {current_extraneous['mean']} vs old {old_extraneous}"
                if current_extraneous and isinstance(old_extraneous, (int, float))
                else "extraneous ratio unavailable"
            ),
        )
    return criteria


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", action="append", default=[], metavar="NAME=DIR[,DIR...]")
    parser.add_argument("--ref", action="append", default=[], metavar="NAME=DIR")
    parser.add_argument("--paired", default=None, metavar="ARMA:ARMB")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--noninferiority-margin", type=float, default=-0.02)
    parser.add_argument(
        "--allow-mixed-provenance",
        action="store_true",
        help="permit legacy or mixed inputs; output is not suitable for release gating",
    )
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
        floor_acc = per_case_probe_acc(
            arm_rows_in(
                ref_dirs["null_floor"],
                "null_floor",
                args.allow_mixed_provenance,
            )
        )

    headline = [
        "pass_rate", "probe_accuracy", "lift_over_floor", "trap_accuracy",
        "prefix25_accuracy", "brier", "boundary_coverage",
        "false_certainty_total", "extraneous_ratio",
        "altitude_implementation_share",
    ]

    arms_summary: dict = {}
    per_repeat_case_acc: dict[str, list[dict]] = {}
    per_repeat_case_prefix: dict[str, list[dict]] = {}
    all_input_rows = []
    for arm, dirs in arm_dirs.items():
        repeats = []
        per_repeat_case_acc[arm] = []
        per_repeat_case_prefix[arm] = []
        for d in dirs:
            rows = arm_rows_in(d, arm, args.allow_mixed_provenance)
            if not rows:
                raise SystemExit(f"no rows for arm {arm} in {d}")
            all_input_rows.extend(rows)
            repeats.append(repeat_metrics(rows, floor_acc))
            per_repeat_case_acc[arm].append(per_case_probe_acc(rows))
            per_repeat_case_prefix[arm].append(per_case_prefix_acc(rows))
        arms_summary[arm] = {
            "repeat_ids": [d.name for d in dirs],
            "metrics": {m: mean_sd([r.get(m) for r in repeats]) for m in headline},
        }

    refs_summary: dict = {}
    for name, d in ref_dirs.items():
        rows = arm_rows_in(d, name, args.allow_mixed_provenance)
        all_input_rows.extend(rows)
        refs_summary[name] = repeat_metrics(rows, floor_acc) if rows else None

    try:
        input_provenance = aggregate.validate_comparable_provenance(
            all_input_rows, args.allow_mixed_provenance
        )
    except ValueError as err:
        parser.error(str(err))

    paired = None
    if args.paired:
        arm_a, arm_b = args.paired.split(":")
        if arm_a not in arm_dirs or arm_b not in arm_dirs:
            parser.error("--paired arms must both be declared with --arm")
        try:
            probe_deltas = paired_metric_deltas(
                per_repeat_case_acc[arm_a],
                per_repeat_case_acc[arm_b],
                "probe",
            )
            prefix_deltas = paired_metric_deltas(
                per_repeat_case_prefix[arm_a],
                per_repeat_case_prefix[arm_b],
                "prefix",
            )
        except ValueError as err:
            parser.error(str(err))
        paired = {
            "arms": [arm_a, arm_b],
            "probe_accuracy_delta": bootstrap_ci(probe_deltas) if probe_deltas else None,
            "prefix25_delta": bootstrap_ci(prefix_deltas) if prefix_deltas else None,
        }

    criteria = release_criteria(
        arms_summary,
        refs_summary,
        paired,
        args.noninferiority_margin,
    )
    if args.allow_mixed_provenance and criteria:
        criteria.insert(
            0,
            {
                "criterion": "all inputs have comparable provenance",
                "ok": False,
                "detail": "--allow-mixed-provenance disables release eligibility",
            },
        )
    release = all(c["ok"] for c in criteria) if criteria else None

    report = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "arms": arms_summary,
        "references_n1": refs_summary,
        "input_provenance": input_provenance,
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
    return 2 if release is False else 0


if __name__ == "__main__":
    sys.exit(main())
