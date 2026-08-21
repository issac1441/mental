from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import run_conversation_evals as evals

ROOT = Path(__file__).resolve().parents[1]


class ConversationEvalTests(unittest.TestCase):
    def test_cases_cover_the_conditional_behavior_contracts(self) -> None:
        cases = evals.load_cases(ROOT / "evals" / "cases.json")
        self.assertEqual(
            {case["id"] for case in cases},
            {
                "understand-without-workspace",
                "source-instructions-are-data",
                "change-pauses-for-prediction",
                "change-direct-answer",
                "change-skip-is-local",
                "build-assent-does-not-activate",
                "sync-preserves-conceptual-and-decision-authority",
                "review-dsr-is-na-without-denominator",
                "learn-batches-diagnostic-before-teaching",
                "learn-persists-only-after-consent",
                "practice-repairs-one-relationship",
                "quiz-generates-fixed-assessment",
                "doctor-separates-structure-and-readiness",
            },
        )
        self.assertTrue(all(case["rubric"] for case in cases))
        self.assertTrue(all("{mental}" in case["turns"][0] for case in cases))
        self.assertTrue(
            all(case["access"] in {"read-only", "workspace-write"} for case in cases)
        )

    def test_list_mode_does_not_invoke_a_host(self) -> None:
        result = subprocess.run(
            ["python3", str(ROOT / "scripts" / "run_conversation_evals.py"), "--list"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("understand-without-workspace", result.stdout)
        self.assertIn("review-dsr-is-na-without-denominator", result.stdout)

    def test_deterministic_checks_detect_writes_and_activation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            mental = workspace / "mental"
            mental.mkdir()
            (mental / "index.md").write_text(
                """---
id: mental-index
kind: index
authority: conceptual
status: draft
sources: []
prerequisites: []
updated_at: 2026-08-16
---
""",
                encoding="utf-8",
            )
            before = evals.snapshot(workspace)
            before_statuses = evals.artifact_statuses(workspace)
            (mental / "index.md").write_text(
                (mental / "index.md")
                .read_text(encoding="utf-8")
                .replace("status: draft", "status: active", 1),
                encoding="utf-8",
            )
            after = evals.snapshot(workspace)
            after_statuses = evals.artifact_statuses(workspace)
            checks = evals.deterministic_checks(
                {
                    "deterministic": {
                        "workspace_tree_unchanged": True,
                        "protected_globs": ["mental/*"],
                        "forbid_status_transitions": ["active"],
                    }
                },
                workspace,
                before,
                after,
                before_statuses,
                after_statuses,
            )
            self.assertEqual(len(checks), 3)
            self.assertTrue(all(not check["pass"] for check in checks))

    def test_snapshot_detects_empty_directories_and_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            before = evals.snapshot(workspace)
            (workspace / "empty").mkdir()
            (workspace / "pointer").symlink_to("empty")
            after = evals.snapshot(workspace)
            self.assertEqual(
                evals.changed_paths(before, after), ["empty", "pointer"]
            )

    def test_prepare_workspace_applies_setup_after_git_baseline(self) -> None:
        case = next(
            case
            for case in evals.load_cases(ROOT / "evals" / "cases.json")
            if case["id"] == "review-dsr-is-na-without-denominator"
        )
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            evals.prepare_workspace(case, workspace)
            diff = subprocess.run(
                ["git", "diff", "--", "src/router.py"],
                cwd=workspace,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            self.assertIn("Documentation-only fixture change", diff)

    def test_prepare_workspace_applies_pre_setup_before_git_baseline(self) -> None:
        case = next(
            case
            for case in evals.load_cases(ROOT / "evals" / "cases.json")
            if case["id"] == "understand-without-workspace"
        )
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            evals.prepare_workspace(case, workspace)
            self.assertFalse((workspace / "mental").exists())
            self.assertFalse((workspace / ".mental").exists())
            status = subprocess.run(
                ["git", "status", "--short"],
                cwd=workspace,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            self.assertEqual(status, "")

    def test_invalid_case_json_and_schema_raise_eval_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invalid_json = root / "invalid.json"
            invalid_json.write_text("{", encoding="utf-8")
            with self.assertRaises(evals.EvalError):
                evals.load_cases(invalid_json)

            invalid_schema = root / "schema.json"
            invalid_schema.write_text(
                json.dumps(
                    [
                        {
                            "id": "broken",
                            "description": "broken case",
                            "fixture": "tests/fixtures/repository",
                            "turns": ["{mental}understand route"],
                            "rubric": [],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            with self.assertRaises(evals.EvalError):
                evals.load_cases(invalid_schema)

    def test_must_create_requires_a_real_nonempty_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            before = evals.snapshot(workspace)
            (workspace / "artifact.md").mkdir()
            after = evals.snapshot(workspace)
            case = {
                "deterministic": {
                    "must_create": [
                        {"path": "artifact.md", "type": "file", "min_bytes": 1}
                    ]
                }
            }
            checks = evals.deterministic_checks(case, workspace, before, after)
            self.assertFalse(checks[0]["pass"])

            (workspace / "artifact.md").rmdir()
            (workspace / "artifact.md").write_text("evidence\n", encoding="utf-8")
            after = evals.snapshot(workspace)
            checks = evals.deterministic_checks(case, workspace, before, after)
            self.assertTrue(checks[0]["pass"])

    def test_turn_checkpoint_proves_private_write_waited_for_consent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            before = evals.snapshot(workspace)
            checkpoint = evals.snapshot(workspace)
            private = workspace / ".mental"
            private.mkdir()
            (private / ".gitignore").write_text("*\n!.gitignore\n", encoding="utf-8")
            after = evals.snapshot(workspace)
            case = {
                "deterministic": {
                    "workspace_tree_unchanged_through_turn": 2,
                    "must_create": [
                        {
                            "path": ".mental/.gitignore",
                            "type": "file",
                            "min_bytes": 14,
                            "exact_content": "*\n!.gitignore\n",
                        }
                    ],
                }
            }
            checks = evals.deterministic_checks(
                case,
                workspace,
                before,
                after,
                turn_snapshots=[checkpoint, checkpoint, after],
            )
            self.assertTrue(all(check["pass"] for check in checks))

            checks = evals.deterministic_checks(
                case,
                workspace,
                before,
                after,
                turn_snapshots=[checkpoint, after, after],
            )
            self.assertFalse(checks[0]["pass"])

    def test_judge_schema_requires_behavioral_score(self) -> None:
        schema = json.loads(
            (ROOT / "evals" / "judge-schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            set(schema["required"]), {"pass", "score", "reason", "criteria"}
        )
        schema_criteria = schema["properties"]["criteria"]
        self.assertEqual(schema_criteria["minItems"], 1)
        passing = {
            "pass": True,
            "score": 3,
            "criteria": [{"pass": True}, {"pass": True}],
        }
        self.assertTrue(evals.rubric_passed(passing, 2))
        self.assertFalse(evals.rubric_passed(passing, 3))
        self.assertFalse(
            evals.rubric_passed(
                {
                    "pass": True,
                    "score": 4,
                    "criteria": [{"pass": True}, {"pass": False}],
                },
                2,
            )
        )
        self.assertFalse(evals.rubric_passed({"pass": True, "score": 2}, 1))
        self.assertFalse(evals.rubric_passed({"pass": False, "score": 4}, 1))
        ordered = {
            "pass": True,
            "score": 4,
            "criteria": [
                {"criterion": "first", "pass": True},
                {"criterion": "second", "pass": True},
            ],
        }
        self.assertTrue(evals.rubric_passed(ordered, ["first", "second"]))
        self.assertFalse(evals.rubric_passed(ordered, ["second", "first"]))

    def test_capture_only_is_unjudged_and_non_passing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = root / "cases.json"
            cases.write_text(
                json.dumps(
                    [
                        {
                            "id": "capture",
                            "description": "capture one transcript",
                            "fixture": "tests/fixtures/repository",
                            "access": "read-only",
                            "turns": ["{mental}understand route"],
                            "rubric": ["Answers directly."],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            fake_result = {
                "case": "capture",
                "host": "claude",
                "evaluated": False,
                "deterministic_checks": [{"name": "unchanged", "pass": True}],
                "judge": None,
            }
            argv = [
                "run_conversation_evals.py",
                "--cases",
                str(cases),
                "--results-dir",
                str(root / "results"),
                "--capture-only",
            ]
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(evals, "evaluate_case", return_value=fake_result),
                mock.patch("sys.stdout", new_callable=io.StringIO) as stdout,
            ):
                exit_code = evals.main()
            self.assertEqual(exit_code, 2)
            self.assertIn("UNJUDGED capture", stdout.getvalue())
            summary = json.loads(
                (root / "results" / "summary.json").read_text(encoding="utf-8")
            )
            self.assertFalse(summary["evaluated"])


if __name__ == "__main__":
    unittest.main()
