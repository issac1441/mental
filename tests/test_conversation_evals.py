from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import run_conversation_evals as evals

ROOT = Path(__file__).resolve().parents[1]


class ConversationEvalTests(unittest.TestCase):
    def test_cases_cover_the_conditional_behavior_contracts(self) -> None:
        cases = evals.load_cases(ROOT / "evals" / "cases.json")
        self.assertEqual(
            {case["id"] for case in cases},
            {
                "understand-without-workspace",
                "change-pauses-for-prediction",
                "change-direct-answer",
                "change-skip-is-local",
                "build-assent-does-not-activate",
                "sync-preserves-conceptual-and-decision-authority",
                "review-dsr-is-na-without-denominator",
            },
        )
        self.assertTrue(all(case["rubric"] for case in cases))
        self.assertTrue(all("{mental}" in case["turns"][0] for case in cases))

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
            (mental / "index.md").write_text(
                (mental / "index.md")
                .read_text(encoding="utf-8")
                .replace("status: draft", "status: active", 1),
                encoding="utf-8",
            )
            after = evals.snapshot(workspace)
            checks = evals.deterministic_checks(
                {
                    "deterministic": {
                        "no_writes": True,
                        "protected_globs": ["mental/*"],
                        "forbid_conceptual_active": True,
                    }
                },
                workspace,
                before,
                after,
            )
            self.assertEqual(len(checks), 3)
            self.assertTrue(all(not check["pass"] for check in checks))

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

    def test_judge_schema_requires_behavioral_score(self) -> None:
        schema = json.loads(
            (ROOT / "evals" / "judge-schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            set(schema["required"]), {"pass", "score", "reason", "criteria"}
        )
        self.assertTrue(evals.rubric_passed({"pass": True, "score": 3}))
        self.assertFalse(evals.rubric_passed({"pass": True, "score": 2}))
        self.assertFalse(evals.rubric_passed({"pass": False, "score": 4}))


if __name__ == "__main__":
    unittest.main()
