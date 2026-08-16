from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD = ROOT / "scripts" / "scaffold_workspace.py"
VALIDATE = ROOT / "scripts" / "validate_workspace.py"
FIXTURES = ROOT / "tests" / "fixtures"


def run(
    *args: str,
    cwd: Path | None = None,
    check: bool = True,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=check,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


class WorkspaceScriptTests(unittest.TestCase):
    def test_hybrid_scaffold_is_valid_and_non_destructive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run(
                "python3",
                str(SCAFFOLD),
                str(workspace),
                "--mode",
                "hybrid",
                "--language",
                "zh-TW",
                "--date",
                "2026-08-15",
            )
            index = workspace / "mental" / "index.md"
            original = index.read_text(encoding="utf-8")
            self.assertIn("mode: hybrid", original)
            self.assertTrue((workspace / "mental" / "contracts").is_dir())
            self.assertTrue((workspace / "mental" / "conflicts").is_dir())
            self.assertTrue((workspace / "mental" / "decisions").is_dir())
            self.assertTrue((workspace / "mental" / "learning" / "path.md").is_file())

            run(
                "python3",
                str(SCAFFOLD),
                str(workspace),
                "--mode",
                "hybrid",
                "--language",
                "en",
                "--date",
                "2030-01-01",
            )
            self.assertEqual(index.read_text(encoding="utf-8"), original)

            result = run("python3", str(VALIDATE), str(workspace), "--json")
            report = json.loads(result.stdout)
            self.assertTrue(report["ok"], report)
            self.assertEqual(report["errors"], [])

    def test_private_state_is_ignored_by_git(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run("git", "init", "-q", cwd=workspace)
            run(
                "python3",
                str(SCAFFOLD),
                str(workspace),
                "--mode",
                "learning",
                "--date",
                "2026-08-15",
            )
            ignored = run(
                "git",
                "check-ignore",
                ".mental/profile.md",
                ".mental/mastery.json",
                cwd=workspace,
            )
            self.assertIn(".mental/profile.md", ignored.stdout)
            self.assertIn(".mental/mastery.json", ignored.stdout)
            status = run("git", "status", "--short", cwd=workspace).stdout
            self.assertNotIn("profile.md", status)
            self.assertNotIn("mastery.json", status)

    def test_scaffold_modes_create_only_their_required_seed_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for mode in ("repository", "learning", "hybrid"):
                workspace = root / mode
                run(
                    "python3",
                    str(SCAFFOLD),
                    str(workspace),
                    "--mode",
                    mode,
                    "--date",
                    "2026-08-15",
                )
                self.assertEqual(
                    (workspace / "mental" / "architecture.md").exists(), False
                )
                self.assertEqual(
                    (workspace / "mental" / "contracts").is_dir(),
                    mode in {"repository", "hybrid"},
                )
                self.assertTrue((workspace / "mental" / "conflicts").is_dir())
                self.assertEqual(
                    (workspace / "mental" / "decisions").is_dir(),
                    mode in {"repository", "hybrid"},
                )
                self.assertEqual(
                    (workspace / "mental" / "learning" / "path.md").is_file(),
                    mode in {"learning", "hybrid"},
                )

    def test_scaffold_rejects_frontmatter_injection_and_invalid_date(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            injected = run(
                "python3",
                str(SCAFFOLD),
                str(root / "injected"),
                "--language",
                "zh-TW\nstatus: canonical",
                check=False,
            )
            self.assertEqual(injected.returncode, 2)
            self.assertIn("language must be", injected.stderr)
            self.assertFalse((root / "injected" / "mental" / "index.md").exists())

            invalid_date = run(
                "python3",
                str(SCAFFOLD),
                str(root / "invalid-date"),
                "--date",
                "next-week",
                check=False,
            )
            self.assertEqual(invalid_date.returncode, 2)
            self.assertIn("date must use ISO", invalid_date.stderr)

    def test_scaffold_refuses_dangling_symlink_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            mental = workspace / "mental"
            mental.mkdir(parents=True)
            outside = root / "outside.md"
            (mental / "index.md").symlink_to(outside)

            result = run("python3", str(SCAFFOLD), str(workspace), check=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn("refusing to follow symlink", result.stderr)
            self.assertFalse(outside.exists())

    def test_validator_rejects_artifact_and_private_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            run(
                "python3",
                str(SCAFFOLD),
                str(workspace),
                "--mode",
                "learning",
                "--date",
                "2026-08-15",
            )
            (workspace / "mental" / "concepts" / "outside").symlink_to(
                root, target_is_directory=True
            )
            (workspace / ".mental" / "sessions" / "outside").symlink_to(
                root, target_is_directory=True
            )

            result = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            report = json.loads(result.stdout)
            self.assertFalse(report["ok"])
            self.assertTrue(
                any(
                    "artifact paths must not be symlinks" in error
                    for error in report["errors"]
                )
            )
            self.assertTrue(
                any(
                    "private-state paths must not be symlinks" in error
                    for error in report["errors"]
                )
            )

    def test_validator_rejects_tracked_private_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run("git", "init", "-q", cwd=workspace)
            run(
                "python3",
                str(SCAFFOLD),
                str(workspace),
                "--mode",
                "learning",
                "--date",
                "2026-08-15",
            )
            run("git", "add", ".", cwd=workspace)
            run(
                "git",
                "add",
                "-f",
                ".mental/profile.md",
                ".mental/mastery.json",
                cwd=workspace,
            )

            result = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            self.assertEqual(result.returncode, 1)
            report = json.loads(result.stdout)
            self.assertTrue(
                any(
                    "private files are tracked by Git" in error
                    for error in report["errors"]
                )
            )
            self.assertNotIn("Learning preferences", result.stdout)

    def test_validator_rejects_weakened_private_ignore_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run("git", "init", "-q", cwd=workspace)
            run(
                "python3",
                str(SCAFFOLD),
                str(workspace),
                "--mode",
                "learning",
                "--date",
                "2026-08-15",
            )
            (workspace / ".mental" / ".gitignore").write_text(
                "!.gitignore\n", encoding="utf-8"
            )

            result = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            report = json.loads(result.stdout)
            self.assertFalse(report["ok"])
            self.assertTrue(
                any("must contain '*'" in error for error in report["errors"])
            )
            self.assertTrue(
                any("Git does not ignore" in error for error in report["errors"])
            )

    def test_validator_rejects_reversed_private_ignore_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run("git", "init", "-q", cwd=workspace)
            run(
                "python3",
                str(SCAFFOLD),
                str(workspace),
                "--mode",
                "learning",
                "--date",
                "2026-08-15",
            )
            (workspace / ".mental" / ".gitignore").write_text(
                "!.gitignore\n*\n", encoding="utf-8"
            )

            result = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            report = json.loads(result.stdout)
            self.assertFalse(report["ok"])
            self.assertTrue(
                any("followed by '!.gitignore'" in error for error in report["errors"])
            )
            self.assertTrue(
                any(
                    "ignores '.mental/.gitignore' itself" in error
                    for error in report["errors"]
                )
            )

    def test_validator_rejects_extra_private_unignore_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run("git", "init", "-q", cwd=workspace)
            run(
                "python3",
                str(SCAFFOLD),
                str(workspace),
                "--mode",
                "learning",
                "--date",
                "2026-08-15",
            )
            (workspace / ".mental" / ".gitignore").write_text(
                "*\n!.gitignore\n!private-export.md\n", encoding="utf-8"
            )
            (workspace / ".mental" / "private-export.md").write_text(
                "private", encoding="utf-8"
            )

            result = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            report = json.loads(result.stdout)
            self.assertFalse(report["ok"])
            self.assertTrue(
                any("must contain '*'" in error for error in report["errors"])
            )
            self.assertTrue(
                any("private-export.md" in error for error in report["errors"])
            )

    def test_repository_and_learning_fixtures_validate(self) -> None:
        for fixture_name in ("repository", "learning"):
            result = run(
                "python3", str(VALIDATE), str(FIXTURES / fixture_name), "--json"
            )
            report = json.loads(result.stdout)
            self.assertTrue(report["ok"], f"{fixture_name}: {report}")
            self.assertEqual(report["errors"], [])

    def test_missing_required_field_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "repository"
            shutil.copytree(FIXTURES / "repository", workspace)
            map_path = workspace / "mental" / "model" / "map.md"
            map_path.write_text(
                map_path.read_text(encoding="utf-8").replace(
                    "authority: mechanical\n", "", 1
                ),
                encoding="utf-8",
            )
            result = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            self.assertNotEqual(result.returncode, 0)
            report = json.loads(result.stdout)
            self.assertTrue(
                any(
                    "missing required field 'authority'" in error
                    for error in report["errors"]
                )
            )

    def test_duplicate_frontmatter_key_and_invalid_metadata_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "repository"
            shutil.copytree(FIXTURES / "repository", workspace)
            index = workspace / "mental" / "index.md"
            content = index.read_text(encoding="utf-8")
            content = content.replace(
                "status: active\n", "status: active\nstatus: draft\n", 1
            )
            content = content.replace(
                "updated_at: 2026-08-15", "updated_at: sometime-last-week", 1
            )
            content = content.replace("mode: repository", "mode: banana", 1)
            index.write_text(content, encoding="utf-8")

            result = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            report = json.loads(result.stdout)
            self.assertTrue(
                any(
                    "duplicate frontmatter field 'status'" in error
                    for error in report["errors"]
                )
            )
            self.assertTrue(
                any("'updated_at' must use ISO" in error for error in report["errors"])
            )
            self.assertTrue(
                any("unsupported mode 'banana'" in error for error in report["errors"])
            )

    def test_validator_reports_unreadable_artifact_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run(
                "python3",
                str(SCAFFOLD),
                str(workspace),
                "--mode",
                "learning",
                "--date",
                "2026-08-15",
            )
            bad = workspace / "mental" / "concepts" / "bad.md"
            bad.write_bytes(b"\xff\xfe\x00")

            result = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            self.assertEqual(result.returncode, 1)
            report = json.loads(result.stdout)
            self.assertFalse(report["ok"])
            self.assertTrue(
                any("cannot read artifact" in error for error in report["errors"])
            )

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO files are not supported")
    def test_validator_rejects_fifo_artifact_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run(
                "python3",
                str(SCAFFOLD),
                str(workspace),
                "--mode",
                "learning",
                "--date",
                "2026-08-15",
            )
            fifo = workspace / "mental" / "concepts" / "blocking.md"
            os.mkfifo(fifo)

            result = run(
                "python3",
                str(VALIDATE),
                str(workspace),
                "--json",
                check=False,
                timeout=5,
            )
            report = json.loads(result.stdout)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("validator_error", report)
            self.assertTrue(
                any(
                    "Markdown artifacts must be regular files" in error
                    for error in report["errors"]
                )
            )

    def test_validator_reports_non_utf8_mastery_as_data_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run(
                "python3",
                str(SCAFFOLD),
                str(workspace),
                "--mode",
                "learning",
                "--date",
                "2026-08-15",
            )
            (workspace / ".mental" / "mastery.json").write_bytes(b"\xff\xfe")

            result = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            report = json.loads(result.stdout)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("validator_error", report)
            self.assertTrue(
                any("UTF-8 valid JSON" in error for error in report["errors"])
            )

    def test_broken_link_and_unknown_source_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "learning"
            shutil.copytree(FIXTURES / "learning", workspace)
            map_path = workspace / "mental" / "model" / "map.md"
            content = map_path.read_text(encoding="utf-8")
            content = content.replace("source-event-loop", "source-missing", 1)
            content += "\n[missing](../concepts/not-there.md)\n"
            map_path.write_text(content, encoding="utf-8")
            result = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            self.assertNotEqual(result.returncode, 0)
            report = json.loads(result.stdout)
            self.assertTrue(
                any("unknown source id" in error for error in report["errors"])
            )
            self.assertTrue(
                any("broken local link" in error for error in report["errors"])
            )

    def test_links_cannot_escape_workspace_and_angle_links_allow_spaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "learning"
            shutil.copytree(FIXTURES / "learning", workspace)
            concept = workspace / "mental" / "concepts" / "event-loop.md"
            spaced = workspace / "mental" / "concepts" / "worked example.md"
            spaced.write_text(
                concept.read_text(encoding="utf-8").replace(
                    "id: event-loop", "id: worked-example", 1
                ),
                encoding="utf-8",
            )
            map_path = workspace / "mental" / "model" / "map.md"
            map_path.write_text(
                map_path.read_text(encoding="utf-8")
                + "\n[valid](<../concepts/worked example.md>)\n[escape](/etc/hosts)\n",
                encoding="utf-8",
            )

            result = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            report = json.loads(result.stdout)
            self.assertTrue(
                any(
                    "local link must be relative" in error for error in report["errors"]
                )
            )
            self.assertFalse(
                any("worked example.md" in error for error in report["errors"])
            )

    def test_localized_source_heading_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "learning"
            shutil.copytree(FIXTURES / "learning", workspace)
            sources = workspace / "mental" / "sources.md"
            sources.write_text(
                sources.read_text(encoding="utf-8").replace(
                    "## source-event-loop", "## source-event-loop — Event loop 教材"
                ),
                encoding="utf-8",
            )
            result = run("python3", str(VALIDATE), str(workspace), "--json")
            self.assertTrue(json.loads(result.stdout)["ok"], result.stdout)

    def test_source_catalog_path_and_source_ids_are_unique(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "learning"
            shutil.copytree(FIXTURES / "learning", workspace)
            sources = workspace / "mental" / "sources.md"
            sources.write_text(
                sources.read_text(encoding="utf-8")
                + "\n## source-event-loop — duplicate\n\n- duplicate\n",
                encoding="utf-8",
            )
            shadow = workspace / "mental" / "concepts" / "shadow-sources.md"
            shadow.write_text(
                """---
id: shadow-sources
kind: sources
authority: mechanical
status: current
sources: []
prerequisites: []
updated_at: 2026-08-16
---

# Shadow catalog
""",
                encoding="utf-8",
            )

            result = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            report = json.loads(result.stdout)
            self.assertFalse(report["ok"])
            self.assertTrue(
                any(
                    "duplicate source id 'source-event-loop'" in error
                    for error in report["errors"]
                )
            )
            self.assertTrue(
                any(
                    "only allowed at mental/sources.md" in error
                    for error in report["errors"]
                )
            )

    def test_duplicate_ids_unsupported_kinds_and_misplaced_lenses_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "repository"
            shutil.copytree(FIXTURES / "repository", workspace)
            original = workspace / "mental" / "concepts" / "request-routing.md"
            duplicate = workspace / "mental" / "concepts" / "duplicate.md"
            duplicate.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")
            misplaced = workspace / "mental" / "concepts" / "operator-lens.md"
            misplaced.write_text(
                original.read_text(encoding="utf-8")
                .replace("id: request-routing", "id: operator-lens", 1)
                .replace("kind: concept", "kind: lens", 1),
                encoding="utf-8",
            )
            map_path = workspace / "mental" / "model" / "map.md"
            map_path.write_text(
                map_path.read_text(encoding="utf-8").replace(
                    "kind: map", "kind: telescope", 1
                ),
                encoding="utf-8",
            )

            result = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            report = json.loads(result.stdout)
            self.assertTrue(any("duplicate id" in error for error in report["errors"]))
            self.assertTrue(
                any(
                    "unsupported kind 'telescope'" in error
                    for error in report["errors"]
                )
            )
            self.assertTrue(
                any("kind 'lens' must live" in error for error in report["errors"])
            )

    def test_orphan_detection_does_not_match_id_substrings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "repository"
            shutil.copytree(FIXTURES / "repository", workspace)
            concept = workspace / "mental" / "concepts" / "request-routing.md"
            orphan = workspace / "mental" / "concepts" / "log.md"
            orphan.write_text(
                concept.read_text(encoding="utf-8").replace(
                    "id: request-routing", "id: log", 1
                ),
                encoding="utf-8",
            )
            glossary = workspace / "mental" / "glossary.md"
            glossary.write_text(
                glossary.read_text(encoding="utf-8") + "\nLogging is observable.\n",
                encoding="utf-8",
            )

            result = run("python3", str(VALIDATE), str(workspace), "--json")
            report = json.loads(result.stdout)
            self.assertTrue(
                any(
                    "concept 'log' is not referenced" in warning
                    for warning in report["warnings"]
                )
            )

    def test_invalid_mastery_state_fails_without_exposing_private_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run(
                "python3",
                str(SCAFFOLD),
                str(workspace),
                "--mode",
                "learning",
                "--date",
                "2026-08-15",
            )
            mastery_path = workspace / ".mental" / "mastery.json"
            mastery = json.loads(mastery_path.read_text(encoding="utf-8"))
            mastery["concepts"]["event-loop"] = {
                "state": "92-percent",
                "evidence": ["self-reported confidence"],
                "updated_at": "2026-08-15",
            }
            mastery_path.write_text(json.dumps(mastery), encoding="utf-8")
            result = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            self.assertNotEqual(result.returncode, 0)
            report = json.loads(result.stdout)
            self.assertTrue(
                any("invalid mastery state" in error for error in report["errors"])
            )
            self.assertNotIn("self-reported confidence", result.stdout)

    def test_custom_lens_validates_and_rejects_wrong_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "repository"
            shutil.copytree(FIXTURES / "repository", workspace)
            lens_dir = workspace / "mental" / "lenses"
            lens_dir.mkdir()
            lens_path = lens_dir / "incident-commander.md"
            lens_path.write_text(
                """---
id: incident-commander
kind: lens
authority: conceptual
status: draft
sources:
  - source-repo
prerequisites: []
updated_at: 2026-08-16
assumes:
  - basic service operations
concerns:
  - containment and recovery
vocabulary:
  - incident
---

# Incident commander

Explain runtime effects and recovery decisions first.

""",
                encoding="utf-8",
            )
            valid = run("python3", str(VALIDATE), str(workspace), "--json")
            self.assertTrue(json.loads(valid.stdout)["ok"], valid.stdout)

            lens_path.write_text(
                lens_path.read_text(encoding="utf-8").replace(
                    "authority: conceptual\n", "authority: mechanical\n"
                ),
                encoding="utf-8",
            )
            invalid = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            self.assertNotEqual(invalid.returncode, 0)
            report = json.loads(invalid.stdout)
            self.assertTrue(
                any(
                    "kind 'lens' allows authority: conceptual" in error
                    for error in report["errors"]
                )
            )

    def test_authority_status_state_machines_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "repository"
            shutil.copytree(FIXTURES / "repository", workspace)
            map_path = workspace / "mental" / "model" / "map.md"
            map_path.write_text(
                map_path.read_text(encoding="utf-8").replace(
                    "status: current", "status: accepted", 1
                ),
                encoding="utf-8",
            )
            result = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            report = json.loads(result.stdout)
            self.assertTrue(
                any(
                    "status 'accepted' is invalid for authority 'mechanical'" in error
                    for error in report["errors"]
                )
            )

    def test_kind_authority_matrix_and_scalar_types_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "repository"
            shutil.copytree(FIXTURES / "repository", workspace)
            map_path = workspace / "mental" / "model" / "map.md"
            map_path.write_text(
                map_path.read_text(encoding="utf-8")
                .replace("id: model-map", "id: [model-map]", 1)
                .replace("kind: map", "kind: [map]", 1)
                .replace("authority: mechanical", "authority: [conceptual]", 1),
                encoding="utf-8",
            )

            result = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            report = json.loads(result.stdout)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("validator_error", report)
            self.assertTrue(
                any("'id' must be a scalar" in error for error in report["errors"])
            )
            self.assertTrue(
                any("unsupported kind" in error for error in report["errors"])
            )
            self.assertTrue(
                any("unsupported authority" in error for error in report["errors"])
            )

    def test_current_mechanical_artifact_requires_rebuild_proof(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "repository"
            shutil.copytree(FIXTURES / "repository", workspace)
            map_path = workspace / "mental" / "model" / "map.md"
            content = map_path.read_text(encoding="utf-8")
            content = content.replace(
                "refresh_basis:\n  - source-repo@2026-08-15\n", "refresh_basis: []\n", 1
            )
            content = content.replace("## Evidence", "## Support", 1)
            map_path.write_text(content, encoding="utf-8")

            result = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            report = json.loads(result.stdout)
            self.assertTrue(
                any("has no refresh basis" in error for error in report["errors"])
            )
            self.assertTrue(
                any(
                    "requires an Evidence section" in error
                    for error in report["errors"]
                )
            )

    def test_active_conceptual_artifact_requires_activation_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "repository"
            shutil.copytree(FIXTURES / "repository", workspace)
            index = workspace / "mental" / "index.md"
            content = index.read_text(encoding="utf-8")
            content = content.replace(
                "verification_basis:\n  - source-repo and model-map cover the complete router fixture\n",
                "verification_basis:\n  - looks good\n",
                1,
            )
            content = content.replace(
                '  - "failure: /healthy returns the not-found response pair"\n', "", 1
            )
            content = content.replace("known_gaps: []\n", "known_gaps: pending\n", 1)
            index.write_text(content, encoding="utf-8")

            result = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            report = json.loads(result.stdout)
            self.assertTrue(
                any(
                    "non-placeholder verification basis" in error
                    for error in report["errors"]
                )
            )
            self.assertTrue(
                any(
                    "failure or boundary prediction" in error
                    for error in report["errors"]
                )
            )
            self.assertTrue(
                any(
                    "conceptual field 'known_gaps' must be a YAML list" in error
                    for error in report["errors"]
                )
            )

    def test_valid_draft_workspace_is_structurally_valid_but_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run(
                "python3",
                str(SCAFFOLD),
                str(workspace),
                "--mode",
                "learning",
                "--date",
                "2026-08-15",
            )
            result = run("python3", str(VALIDATE), str(workspace), "--json")
            report = json.loads(result.stdout)
            self.assertTrue(report["ok"], report)
            self.assertEqual(report["readiness"]["state"], "incomplete")
            self.assertIn("mental-index", report["readiness"]["draft_artifacts"])

    def test_decision_and_change_history_are_append_preserving(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "repository"
            shutil.copytree(FIXTURES / "repository", workspace)
            decision = workspace / "mental" / "decisions" / "route-contract.md"
            decision.write_text(
                decision.read_text(encoding="utf-8")
                .replace("status: accepted", "status: superseded", 1)
                .replace("superseded_by: []", "superseded_by: []", 1),
                encoding="utf-8",
            )
            change = workspace / "mental" / "changes" / "add-timeout.md"
            change.write_text(
                change.read_text(encoding="utf-8").replace(
                    "prediction_status: skipped", "prediction_status: always", 1
                ),
                encoding="utf-8",
            )

            result = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            report = json.loads(result.stdout)
            self.assertTrue(
                any(
                    "latest status history entry must match" in error
                    for error in report["errors"]
                )
            )
            self.assertTrue(
                any(
                    "superseded artifact requires 'superseded_by'" in error
                    for error in report["errors"]
                )
            )
            self.assertTrue(
                any(
                    "change field 'prediction_status'" in error
                    for error in report["errors"]
                )
            )

    def test_decision_history_transitions_and_replacement_links_are_validated(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "repository"
            shutil.copytree(FIXTURES / "repository", workspace)
            decision = workspace / "mental" / "decisions" / "route-contract.md"
            content = decision.read_text(encoding="utf-8")
            content = content.replace("status: accepted", "status: pending", 1)
            content = content.replace(
                "  - 2026-08-15:accepted\n",
                "  - 2026-08-15:accepted\n  - 2026-08-16:pending\n",
                1,
            )
            content = content.replace(
                "superseded_by: []", "superseded_by:\n  - replacement-decision", 1
            )
            decision.write_text(content, encoding="utf-8")
            replacement = workspace / "mental" / "decisions" / "replacement.md"
            replacement.write_text(
                """---
id: replacement-decision
kind: decision
authority: decision
status: accepted
sources:
  - source-repo
prerequisites: []
updated_at: 2026-08-16
decision_owner: human
surfaced: pre-approval
consequential: true
reversibility: costly
supersedes: []
superseded_by: []
status_history:
  - 2026-08-16:pending
  - 2026-08-16:accepted
---

# Replacement
""",
                encoding="utf-8",
            )

            result = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            report = json.loads(result.stdout)
            self.assertTrue(
                any(
                    "invalid status transition 'accepted' to 'pending'" in error
                    for error in report["errors"]
                )
            )
            self.assertTrue(
                any(
                    "does not link back through supersedes" in error
                    for error in report["errors"]
                )
            )

    def test_historical_private_state_is_advisory_not_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            run("git", "init", "-q", cwd=workspace)
            run("git", "config", "user.email", "mental@example.invalid", cwd=workspace)
            run("git", "config", "user.name", "mental fixture", cwd=workspace)
            run(
                "python3",
                str(SCAFFOLD),
                str(workspace),
                "--mode",
                "learning",
                "--date",
                "2026-08-15",
            )
            run("git", "add", "mental", ".mental/.gitignore", cwd=workspace)
            run("git", "add", "-f", ".mental/profile.md", cwd=workspace)
            run(
                "git",
                "commit",
                "-qm",
                "accidentally track private state",
                cwd=workspace,
            )
            run("git", "rm", "--cached", ".mental/profile.md", cwd=workspace)
            run("git", "commit", "-qm", "stop tracking private state", cwd=workspace)

            result = run("python3", str(VALIDATE), str(workspace), "--json")
            report = json.loads(result.stdout)
            self.assertTrue(report["ok"], report)
            self.assertTrue(
                any(
                    "Git history contains private-state paths" in warning
                    for warning in report["warnings"]
                )
            )

    def test_conflict_and_decision_metadata_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "repository"
            shutil.copytree(FIXTURES / "repository", workspace)
            conflict = workspace / "mental" / "conflicts" / "timeout-owner.md"
            conflict.write_text(
                conflict.read_text(encoding="utf-8")
                .replace("status: open", "status: resolved", 1)
                .replace("owner: unassigned\n", "", 1),
                encoding="utf-8",
            )
            decision = workspace / "mental" / "decisions" / "route-contract.md"
            decision.write_text(
                decision.read_text(encoding="utf-8").replace(
                    "surfaced: pre-approval", "surfaced: eventually", 1
                ),
                encoding="utf-8",
            )
            result = run(
                "python3", str(VALIDATE), str(workspace), "--json", check=False
            )
            report = json.loads(result.stdout)
            self.assertTrue(
                any("conflict field 'owner'" in error for error in report["errors"])
            )
            self.assertTrue(
                any(
                    "resolved conflict requires ISO 'resolved_at'" in error
                    for error in report["errors"]
                )
            )
            self.assertTrue(
                any("decision field 'surfaced'" in error for error in report["errors"])
            )


if __name__ == "__main__":
    unittest.main()
