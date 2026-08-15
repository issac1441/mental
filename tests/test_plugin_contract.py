from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_NAMES = {"understand", "build", "sync", "doctor", "change", "review", "learn", "practice"}


def skill_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError(f"Missing frontmatter: {path}")
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


class PluginContractTests(unittest.TestCase):
    def test_manifests_describe_the_same_skills_only_plugin(self) -> None:
        codex = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        claude = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        for manifest in (codex, claude):
            self.assertEqual(manifest["name"], "mental")
            self.assertEqual(manifest["version"], "0.1.0")
            self.assertEqual(manifest["skills"], "./skills/")
            self.assertEqual(manifest["license"], "MIT")
            self.assertNotIn("mcpServers", manifest)
            self.assertNotIn("apps", manifest)
            self.assertNotIn("hooks", manifest)

    def test_exact_skill_set_and_frontmatter(self) -> None:
        actual = {path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md")}
        self.assertEqual(actual, SKILL_NAMES)
        for name in sorted(SKILL_NAMES):
            path = ROOT / "skills" / name / "SKILL.md"
            text = path.read_text(encoding="utf-8")
            fields = skill_frontmatter(path)
            self.assertEqual(fields.keys(), {"name", "description"})
            self.assertEqual(fields["name"], name)
            self.assertGreater(len(fields["description"]), 40)
            self.assertNotIn("TODO", text)

    def test_skill_ui_metadata_mentions_the_skill(self) -> None:
        for name in sorted(SKILL_NAMES):
            path = ROOT / "skills" / name / "agents" / "openai.yaml"
            text = path.read_text(encoding="utf-8")
            self.assertIn("display_name:", text)
            self.assertIn("short_description:", text)
            self.assertIn(f"${name}", text)

    def test_every_referenced_support_file_exists(self) -> None:
        path_pattern = re.compile(r"\.\./\.\./(?:references|scripts|assets)/[A-Za-z0-9_./-]+")
        for name in sorted(SKILL_NAMES):
            skill_dir = ROOT / "skills" / name
            text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            for relative in path_pattern.findall(text):
                target = (skill_dir / relative.rstrip(".,;:")).resolve()
                self.assertTrue(target.exists(), f"Missing support path referenced by {name}: {target}")

    def test_behavior_cases_are_encoded_in_skills(self) -> None:
        cases = json.loads((ROOT / "tests" / "behavior_cases.json").read_text(encoding="utf-8"))
        self.assertEqual({case["skill"] for case in cases}, SKILL_NAMES)
        for case in cases:
            text = (ROOT / "skills" / case["skill"] / "SKILL.md").read_text(encoding="utf-8")
            for phrase in case["required_phrases"]:
                self.assertIn(phrase, text, f"{case['name']} is missing contract phrase: {phrase}")

    def test_read_only_skills_have_explicit_write_boundaries(self) -> None:
        understand = (ROOT / "skills" / "understand" / "SKILL.md").read_text(encoding="utf-8")
        review = (ROOT / "skills" / "review" / "SKILL.md").read_text(encoding="utf-8")
        doctor = (ROOT / "skills" / "doctor" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Never edit", understand)
        self.assertIn("Do not update artifacts", review)
        self.assertIn("Do not edit by default", doctor)


if __name__ == "__main__":
    unittest.main()
