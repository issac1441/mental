from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD = ROOT / "scripts" / "scaffold_workspace.py"
VALIDATE = ROOT / "scripts" / "validate_workspace.py"
FIXTURES = ROOT / "tests" / "fixtures"


def run(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, check=check, text=True, capture_output=True)


class WorkspaceScriptTests(unittest.TestCase):
    def test_hybrid_scaffold_is_valid_and_non_destructive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run("python3", str(SCAFFOLD), str(workspace), "--mode", "hybrid", "--language", "zh-TW", "--date", "2026-08-15")
            index = workspace / "mental" / "index.md"
            original = index.read_text(encoding="utf-8")
            self.assertIn("mode: hybrid", original)
            self.assertTrue((workspace / "mental" / "contracts").is_dir())
            self.assertTrue((workspace / "mental" / "learning" / "path.md").is_file())

            run("python3", str(SCAFFOLD), str(workspace), "--mode", "hybrid", "--language", "en", "--date", "2030-01-01")
            self.assertEqual(index.read_text(encoding="utf-8"), original)

            result = run("python3", str(VALIDATE), str(workspace), "--json")
            report = json.loads(result.stdout)
            self.assertTrue(report["ok"], report)
            self.assertEqual(report["errors"], [])

    def test_private_state_is_ignored_by_git(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run("git", "init", "-q", cwd=workspace)
            run("python3", str(SCAFFOLD), str(workspace), "--mode", "learning", "--date", "2026-08-15")
            ignored = run("git", "check-ignore", ".mental/profile.md", ".mental/mastery.json", cwd=workspace)
            self.assertIn(".mental/profile.md", ignored.stdout)
            self.assertIn(".mental/mastery.json", ignored.stdout)
            status = run("git", "status", "--short", cwd=workspace).stdout
            self.assertNotIn("profile.md", status)
            self.assertNotIn("mastery.json", status)

    def test_repository_and_learning_fixtures_validate(self) -> None:
        for fixture_name in ("repository", "learning"):
            result = run("python3", str(VALIDATE), str(FIXTURES / fixture_name), "--json")
            report = json.loads(result.stdout)
            self.assertTrue(report["ok"], f"{fixture_name}: {report}")
            self.assertEqual(report["errors"], [])

    def test_missing_required_field_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "repository"
            shutil.copytree(FIXTURES / "repository", workspace)
            map_path = workspace / "mental" / "model" / "map.md"
            map_path.write_text(map_path.read_text(encoding="utf-8").replace("status: canonical\n", "", 1), encoding="utf-8")
            result = run("python3", str(VALIDATE), str(workspace), "--json", check=False)
            self.assertNotEqual(result.returncode, 0)
            report = json.loads(result.stdout)
            self.assertTrue(any("missing required field 'status'" in error for error in report["errors"]))

    def test_broken_link_and_unknown_source_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "learning"
            shutil.copytree(FIXTURES / "learning", workspace)
            map_path = workspace / "mental" / "model" / "map.md"
            content = map_path.read_text(encoding="utf-8")
            content = content.replace("source-event-loop", "source-missing", 1)
            content += "\n[missing](../concepts/not-there.md)\n"
            map_path.write_text(content, encoding="utf-8")
            result = run("python3", str(VALIDATE), str(workspace), "--json", check=False)
            self.assertNotEqual(result.returncode, 0)
            report = json.loads(result.stdout)
            self.assertTrue(any("unknown source id" in error for error in report["errors"]))
            self.assertTrue(any("broken local link" in error for error in report["errors"]))

    def test_invalid_mastery_state_fails_without_exposing_private_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run("python3", str(SCAFFOLD), str(workspace), "--mode", "learning", "--date", "2026-08-15")
            mastery_path = workspace / ".mental" / "mastery.json"
            mastery = json.loads(mastery_path.read_text(encoding="utf-8"))
            mastery["concepts"]["event-loop"] = {
                "state": "92-percent",
                "evidence": ["self-reported confidence"],
                "updated_at": "2026-08-15",
            }
            mastery_path.write_text(json.dumps(mastery), encoding="utf-8")
            result = run("python3", str(VALIDATE), str(workspace), "--json", check=False)
            self.assertNotEqual(result.returncode, 0)
            report = json.loads(result.stdout)
            self.assertTrue(any("invalid mastery state" in error for error in report["errors"]))
            self.assertNotIn("self-reported confidence", result.stdout)


if __name__ == "__main__":
    unittest.main()
