from __future__ import annotations

import json
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EVALS_DIR = REPO_ROOT / "evals"
sys.path.insert(0, str(EVALS_DIR))

import aggregate  # noqa: E402
import finalize  # noqa: E402
import run_eval  # noqa: E402


def provenance(**overrides) -> dict:
    value = {
        "schema_version": 1,
        "protocol": "single-turn",
        "model": "model-a",
        "effort": "high",
        "graders": 2,
        "plugin_version": "0.4.1",
        "plugin_git_head": "a" * 40,
        "case": "a",
        "arm": "with_skill",
        "case_sha256": "1" * 64,
        "target_sha256": "2" * 64,
        "prompt_tree_sha256": "3" * 64,
        "runner_sha256": "4" * 64,
        "shared_runner_sha256": "5" * 64,
        "skill_sha256": "6" * 64,
    }
    value.update(overrides)
    return value


def metric(mean: float, values: list[float] | None = None) -> dict:
    return {
        "mean": mean,
        "sd": 0.0,
        "n": len(values or [mean]),
        "values": values or [mean],
    }


class TargetMaterializationTests(unittest.TestCase):
    def test_parallel_mental_target_is_complete_and_shared(self) -> None:
        with tempfile.TemporaryDirectory() as source_tmp, tempfile.TemporaryDirectory() as work_tmp:
            source = Path(source_tmp)
            for index in range(40):
                path = source / "nested" / f"file-{index}.txt"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"value {index}\n", encoding="utf-8")
            original_root = run_eval.REPO_ROOT
            run_eval.REPO_ROOT = source
            try:
                with ThreadPoolExecutor(max_workers=16) as pool:
                    targets = list(
                        pool.map(
                            lambda _: run_eval.build_mental_target(Path(work_tmp)),
                            range(32),
                        )
                    )
            finally:
                run_eval.REPO_ROOT = original_root

            self.assertEqual(len(set(targets)), 1)
            copied = list((targets[0] / "nested").glob("*.txt"))
            self.assertEqual(len(copied), 40)
            self.assertFalse(any(Path(work_tmp).glob(".target-mental-*")))


class CacheProvenanceTests(unittest.TestCase):
    def test_cache_without_provenance_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "case" / "arm"
            (run_dir / "outputs").mkdir(parents=True)
            (run_dir / "outputs" / "explanation.md").write_text(
                "stale", encoding="utf-8"
            )
            with self.assertRaises(run_eval.ProvenanceError):
                run_eval.ensure_run_provenance(run_dir, provenance(), force=False)

    def test_mismatch_requires_force_and_force_clears_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "case" / "arm"
            first = provenance(model="model-a")
            second = provenance(model="model-b")
            run_eval.ensure_run_provenance(run_dir, first, force=False)
            marker = run_dir / "outputs" / "explanation.md"
            marker.parent.mkdir()
            marker.write_text("cached", encoding="utf-8")

            with self.assertRaises(run_eval.ProvenanceError):
                run_eval.ensure_run_provenance(run_dir, second, force=False)
            run_eval.ensure_run_provenance(run_dir, second, force=True)

            self.assertFalse(marker.exists())
            self.assertEqual(
                second,
                json.loads((run_dir / "provenance.json").read_text(encoding="utf-8")),
            )


class GraderCompletenessTests(unittest.TestCase):
    def grading(self, ids: list[int]) -> dict:
        return {
            "expectations": [],
            "probe_results": [{"id": probe_id, "correct": True} for probe_id in ids],
        }

    def test_missing_probe_from_one_grader_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "probe IDs"):
            run_eval.merge_gradings(
                [self.grading([1, 2]), self.grading([1])],
                expected_probe_ids=[1, 2],
            )

    def test_duplicate_or_unknown_probe_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate"):
            run_eval.merge_gradings(
                [self.grading([1, 1])], expected_probe_ids=[1, 2]
            )
        with self.assertRaisesRegex(ValueError, "probe IDs"):
            run_eval.merge_gradings(
                [self.grading([1, 3])], expected_probe_ids=[1, 2]
            )

    def test_complete_graders_merge_conservatively(self) -> None:
        first = self.grading([1, 2])
        second = self.grading([1, 2])
        second["probe_results"][1]["correct"] = False
        merged = run_eval.merge_gradings(
            [first, second], expected_probe_ids=[1, 2]
        )
        self.assertEqual(
            merged["probe_results"],
            [{"id": 1, "correct": True}, {"id": 2, "correct": False}],
        )

    def test_wrong_boolean_types_or_missing_expectations_fail(self) -> None:
        grading = self.grading([1])
        grading["probe_results"][0]["correct"] = "false"
        with self.assertRaisesRegex(ValueError, "booleans"):
            run_eval.merge_gradings([grading], expected_probe_ids=[1])

        with self.assertRaisesRegex(ValueError, "exactly 1"):
            run_eval.merge_gradings(
                [self.grading([1])],
                expected_probe_ids=[1],
                expected_expectations=1,
            )


class AggregateProvenanceTests(unittest.TestCase):
    def row(self, case: str, arm: str, value: dict | None) -> dict:
        if value is not None:
            value = {**value, "case": case, "arm": arm}
            if arm in {"without_skill", "null_floor"}:
                value["skill_sha256"] = None
        return {"case": case, "arm": arm, "provenance": value}

    def test_missing_or_mixed_provenance_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing provenance"):
            aggregate.validate_comparable_provenance(
                [self.row("a", "with_skill", None)]
            )
        with self.assertRaisesRegex(ValueError, "mixed eval provenance"):
            aggregate.validate_comparable_provenance(
                [
                    self.row("a", "with_skill", provenance()),
                    self.row(
                        "a", "without_skill", provenance(model="different")
                    ),
                ]
            )
        with self.assertRaisesRegex(ValueError, "skill_sha256"):
            aggregate.validate_comparable_provenance(
                [
                    self.row("a", "with_skill", provenance(skill_sha256="7" * 64)),
                    self.row("b", "with_skill", provenance(skill_sha256="8" * 64)),
                ]
            )

    def test_explicit_mixed_override_is_marked(self) -> None:
        result = aggregate.validate_comparable_provenance(
            [
                self.row("a", "with_skill", provenance()),
                self.row("a", "without_skill", None),
            ],
            allow_mixed=True,
        )
        self.assertTrue(result["mixed"])
        legacy = aggregate.validate_comparable_provenance(
            [self.row("a", "with_skill", None)], allow_mixed=True
        )
        self.assertTrue(legacy["mixed"])
        self.assertTrue(legacy["legacy"])

    def test_case_protocols_may_differ_within_one_runner(self) -> None:
        result = aggregate.validate_comparable_provenance(
            [
                self.row("a", "with_skill", provenance(protocol="single-turn")),
                self.row("b", "with_skill", provenance(protocol="detection")),
            ]
        )
        self.assertFalse(result["mixed"])


class ReleaseGateTests(unittest.TestCase):
    def summaries(self) -> tuple[dict, dict, dict]:
        current = {
            "brier": metric(0.04),
            "false_certainty_total": metric(0.0, [0.0, 0.0, 0.0]),
            "altitude_implementation_share": metric(0.08),
            "boundary_coverage": metric(1.0),
            "extraneous_ratio": metric(0.18),
        }
        bare = {
            "brier": metric(0.06),
            "false_certainty_total": metric(1.0),
            "altitude_implementation_share": metric(0.07),
            "boundary_coverage": metric(0.95),
            "extraneous_ratio": metric(0.16),
        }
        arms = {
            "with_skill": {"metrics": current},
            "without_skill": {"metrics": bare},
        }
        refs = {"old_skill": {"extraneous_ratio": 0.25}}
        paired = {
            "arms": ["with_skill", "without_skill"],
            "probe_accuracy_delta": {"mean": 0.03, "ci95": [0.01, 0.05]},
            "prefix25_delta": {"mean": 0.04, "ci95": [0.01, 0.07]},
        }
        return arms, refs, paired

    def test_noninferiority_uses_lower_not_upper_ci(self) -> None:
        arms, refs, paired = self.summaries()
        paired["probe_accuracy_delta"] = {
            "mean": 0.01,
            "ci95": [-0.03, 0.05],
        }
        criteria = finalize.release_criteria(arms, refs, paired, -0.02)
        self.assertFalse(criteria[0]["ok"])

    def test_anytime_superiority_uses_lower_ci(self) -> None:
        arms, refs, paired = self.summaries()
        paired["prefix25_delta"] = {
            "mean": 0.02,
            "ci95": [-0.01, 0.05],
        }
        criteria = finalize.release_criteria(arms, refs, paired, -0.02)
        self.assertFalse(criteria[1]["ok"])

    def test_missing_calibration_altitude_or_coverage_blocks(self) -> None:
        for key, criterion_index in (
            ("brier", 2),
            ("false_certainty_total", 3),
            ("altitude_implementation_share", 4),
            ("boundary_coverage", 5),
        ):
            with self.subTest(metric=key):
                arms, refs, paired = self.summaries()
                arms["with_skill"]["metrics"][key] = None
                criteria = finalize.release_criteria(arms, refs, paired, -0.02)
                self.assertFalse(criteria[criterion_index]["ok"])

    def test_paired_inputs_require_equal_repeats_and_case_sets(self) -> None:
        with self.assertRaisesRegex(ValueError, "equal repeat counts"):
            finalize.paired_metric_deltas([{"a": 1.0}], [], "probe")
        with self.assertRaisesRegex(ValueError, "different probe case sets"):
            finalize.paired_metric_deltas(
                [{"a": 1.0}], [{"b": 1.0}], "probe"
            )


if __name__ == "__main__":
    unittest.main()
