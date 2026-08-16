from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_NAMES = {
    "understand",
    "build",
    "sync",
    "doctor",
    "change",
    "review",
    "learn",
    "practice",
    "quiz",
}


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
        codex = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        claude = json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        for manifest in (codex, claude):
            self.assertEqual(manifest["name"], "mental")
            self.assertEqual(manifest["version"], "0.2.0")
            self.assertEqual(manifest["skills"], "./skills/")
            self.assertEqual(manifest["license"], "0BSD")
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
            self.assertNotIn("[TODO", text)

    def test_skill_ui_metadata_mentions_the_skill(self) -> None:
        for name in sorted(SKILL_NAMES):
            path = ROOT / "skills" / name / "agents" / "openai.yaml"
            text = path.read_text(encoding="utf-8")
            self.assertIn("display_name:", text)
            self.assertIn("short_description:", text)
            self.assertIn(f"${name}", text)

    def test_primary_and_advanced_skills_are_clear_in_ui_metadata(self) -> None:
        for name in ("understand", "change", "review", "learn", "practice", "quiz"):
            text = (ROOT / "skills" / name / "agents" / "openai.yaml").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("(Advanced)", text)
        for name in ("build", "sync", "doctor"):
            text = (ROOT / "skills" / name / "agents" / "openai.yaml").read_text(
                encoding="utf-8"
            )
            self.assertIn("(Advanced)", text)

    def test_every_referenced_support_file_exists(self) -> None:
        path_pattern = re.compile(
            r"\.\./\.\./(?:references|scripts|assets)/[A-Za-z0-9_./-]+"
        )
        for name in sorted(SKILL_NAMES):
            skill_dir = ROOT / "skills" / name
            text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            for relative in path_pattern.findall(text):
                target = (skill_dir / relative.rstrip(".,;:")).resolve()
                self.assertTrue(
                    target.exists(),
                    f"Missing support path referenced by {name}: {target}",
                )

    def test_behavior_cases_are_encoded_in_skills(self) -> None:
        cases = json.loads(
            (ROOT / "tests" / "behavior_cases.json").read_text(encoding="utf-8")
        )
        self.assertEqual({case["skill"] for case in cases}, SKILL_NAMES)
        for case in cases:
            text = (ROOT / "skills" / case["skill"] / "SKILL.md").read_text(
                encoding="utf-8"
            )
            for phrase in case["required_phrases"]:
                self.assertIn(
                    phrase, text, f"{case['name']} is missing contract phrase: {phrase}"
                )

    def test_read_only_skills_have_explicit_write_boundaries(self) -> None:
        understand = (ROOT / "skills" / "understand" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        review = (ROOT / "skills" / "review" / "SKILL.md").read_text(encoding="utf-8")
        doctor = (ROOT / "skills" / "doctor" / "SKILL.md").read_text(encoding="utf-8")
        change = (ROOT / "skills" / "change" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Never edit", understand)
        self.assertIn("Do not update artifacts", review)
        self.assertIn("Do not edit by default", doctor)
        self.assertIn("Remain read-only by default", change)

    def test_context_selection_contract_is_shared(self) -> None:
        for name in ("understand", "change", "review", "learn", "practice", "quiz"):
            text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("Lens", text)
            self.assertIn("Job", text)
            self.assertNotIn("detail=", text)
        understand = (ROOT / "skills" / "understand" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Infer Job and Lens from the request and session", understand)
        self.assertIn("advanced override", understand)
        self.assertIn("host memory", understand)
        self.assertIn("If no mental workspace exists", understand)

    def test_operational_contract_has_no_legacy_zoom(self) -> None:
        operational_paths = [ROOT / "README.md", ROOT / "README.zh-TW.md"]
        operational_paths.extend((ROOT / "references").glob("*.md"))
        operational_paths.extend((ROOT / "skills").glob("*/SKILL.md"))
        for path in operational_paths:
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"\b[Zz]oom\b", str(path))
            self.assertNotRegex(text, r"\bL[0-4]\b", str(path))

    def test_change_review_practice_and_quiz_have_distinct_contracts(self) -> None:
        change = (ROOT / "skills" / "change" / "SKILL.md").read_text(encoding="utf-8")
        review = (ROOT / "skills" / "review" / "SKILL.md").read_text(encoding="utf-8")
        practice = (ROOT / "skills" / "practice" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        quiz = (ROOT / "skills" / "quiz" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`intent`", change)
        self.assertIn("`decision`", change)
        self.assertIn("`plan-interpretation`", change)
        self.assertIn("record=<true|false>", change)
        self.assertIn("Actual Change Mental Model", review)
        self.assertIn("Before → After", review)
        self.assertIn("structurally equivalent new scenario", practice)
        self.assertIn("current change, current session", practice)
        self.assertIn("items=12", quiz)
        self.assertIn("feedback=end|after-each", quiz)
        self.assertIn("format=mixed|open|mcq", quiz)
        self.assertIn("Generate the complete exam before collecting answers", quiz)

    def test_all_skills_load_the_shared_writing_profile(self) -> None:
        for name in sorted(SKILL_NAMES):
            text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("../../references/writing-profile.md", text)

    def test_all_skills_load_the_shared_output_style(self) -> None:
        for name in sorted(SKILL_NAMES):
            text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("../../references/output-style.md", text)

    def test_all_skills_load_source_safety_and_define_inputs(self) -> None:
        for name in sorted(SKILL_NAMES):
            text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("../../references/source-safety.md", text)
            self.assertIn("## Input contract", text)

    def test_context_and_decision_defaults_are_unambiguous(self) -> None:
        methodology = (ROOT / "references" / "methodology.md").read_text(
            encoding="utf-8"
        )
        contract = (ROOT / "references" / "artifact-contract.md").read_text(
            encoding="utf-8"
        )
        practice = (ROOT / "skills" / "practice" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        change = (ROOT / "skills" / "change" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Manual `job=` input wins", methodology)
        self.assertIn(
            "Do not require a first-time user to choose Views or Detail", methodology
        )
        self.assertIn("independent explanation, transfer, and a boundary", practice)
        self.assertIn("`accepted` or `rejected`", change)
        self.assertIn(
            "Recognition or “looks good” is not conceptual verification", contract
        )
        self.assertIn("it cannot validate unsupported facts", contract)

    def test_documented_style_is_inspired_not_claimed_compliant(self) -> None:
        profile = (ROOT / "references" / "writing-profile.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("STE-inspired", profile)
        self.assertIn("Do not claim ASD-STE100 compliance", profile)
        self.assertIn("user's language", profile)

    def test_lens_artifact_contract_and_template_exist(self) -> None:
        contract = (ROOT / "references" / "artifact-contract.md").read_text(
            encoding="utf-8"
        )
        validator = (ROOT / "scripts" / "validate_workspace.py").read_text(
            encoding="utf-8"
        )
        template = (ROOT / "assets" / "templates" / "lens.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("`kind: lens`", contract)
        for field in ("assumes", "prioritizes", "vocabulary"):
            self.assertIn(field, contract)
            self.assertIn(field, template)
        self.assertNotIn("default_views", contract)
        self.assertNotIn("default_views", template)
        self.assertIn("authority: conceptual", template)
        self.assertIn('"lens"', validator)

    def test_authority_gates_conflicts_and_trust_are_first_class(self) -> None:
        methodology = (ROOT / "references" / "methodology.md").read_text(
            encoding="utf-8"
        )
        contract = (ROOT / "references" / "artifact-contract.md").read_text(
            encoding="utf-8"
        )
        repository = (ROOT / "references" / "repository-workflow.md").read_text(
            encoding="utf-8"
        )
        for authority in ("mechanical", "conceptual", "decision"):
            self.assertIn(f"**{authority}**", methodology)
        for heading in (
            "Mechanical refresh",
            "Conceptual activation",
            "Human decision",
        ):
            self.assertIn(heading, methodology)
        self.assertIn("mental/conflicts/", contract)
        self.assertIn("mental/decisions/", contract)
        self.assertIn("Decision Surprise Rate", contract)
        self.assertIn("Model × Harness × Task Class", methodology)
        self.assertIn("Do not use lines changed", repository)

    def test_quickstart_is_understand_first_and_build_is_optional(self) -> None:
        for path in (ROOT / "README.md", ROOT / "README.zh-TW.md"):
            text = path.read_text(encoding="utf-8")
            self.assertLess(text.find("/mental:understand"), text.find("/mental:build"))
            self.assertRegex(text.lower(), r"build.{0,160}(optional|選用|進階)")

    def test_local_document_links_resolve(self) -> None:
        link_pattern = re.compile(r"\[[^]]+]\(([^)]+)\)")
        paths = [ROOT / "README.md", ROOT / "README.zh-TW.md"]
        paths.extend((ROOT / "docs").glob("*.md"))
        paths.extend((ROOT / "references").glob("*.md"))
        for path in paths:
            for target in link_pattern.findall(path.read_text(encoding="utf-8")):
                target = target.strip().split("#", 1)[0].strip("<>")
                if not target or target.startswith(("http://", "https://", "mailto:")):
                    continue
                resolved = (path.parent / target).resolve()
                self.assertTrue(resolved.exists(), f"Broken link in {path}: {target}")


if __name__ == "__main__":
    unittest.main()
