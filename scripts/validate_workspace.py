#!/usr/bin/env python3
"""Internal, dependency-free validator used by mental:doctor and mental:sync."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote


REQUIRED_FIELDS = {"id", "kind", "status", "sources", "prerequisites", "updated_at"}
ALLOWED_KINDS = {
    "index",
    "sources",
    "glossary",
    "lens",
    "map",
    "concept",
    "scenario",
    "architecture",
    "contract",
    "decision",
    "change",
    "learning-path",
    "misconception",
    "exercise",
}
ALLOWED_STATUSES = {"draft", "canonical", "stale"}
ALLOWED_MASTERY_STATES = {"unknown", "exposed", "working", "verified"}
ALLOWED_VIEWS = {"anchor", "map", "mechanism", "scenario", "evidence"}
ID_RE = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^]]*]\(([^)]+)\)")


@dataclass
class Artifact:
    path: Path
    fields: dict[str, object]
    body: str


def scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_inline_list(value: str) -> list[str] | None:
    value = value.strip()
    if value == "[]":
        return []
    if value.startswith("[") and value.endswith("]"):
        return [scalar(item) for item in value[1:-1].split(",") if item.strip()]
    return None


def parse_frontmatter(path: Path) -> tuple[Artifact | None, list[str]]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, [f"{path}: missing opening frontmatter delimiter"]
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None, [f"{path}: missing closing frontmatter delimiter"]

    fields: dict[str, object] = {}
    current_list: str | None = None
    for line_number, line in enumerate(lines[1:end], start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")):
            match = re.match(r"^\s*-\s+(.+?)\s*$", line)
            if match and current_list:
                value = fields.setdefault(current_list, [])
                if isinstance(value, list):
                    value.append(scalar(match.group(1)))
                continue
            errors.append(f"{path}:{line_number}: unsupported nested frontmatter")
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*?)\s*$", line)
        if not match:
            errors.append(f"{path}:{line_number}: invalid frontmatter field")
            current_list = None
            continue
        key, raw = match.groups()
        current_list = None
        inline = parse_inline_list(raw)
        if inline is not None:
            fields[key] = inline
        elif raw:
            fields[key] = scalar(raw)
        else:
            fields[key] = []
            current_list = key
    body = "\n".join(lines[end + 1 :])
    return Artifact(path=path, fields=fields, body=body), errors


def list_field(artifact: Artifact, key: str) -> list[str]:
    value = artifact.fields.get(key, [])
    return value if isinstance(value, list) else []


def validate(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    if workspace.name == "mental" and (workspace / "index.md").exists():
        mental_root = workspace
        private_root = workspace.parent / ".mental"
    else:
        mental_root = workspace / "mental"
        private_root = workspace / ".mental"

    errors: list[str] = []
    warnings: list[str] = []
    artifacts: list[Artifact] = []
    if not mental_root.is_dir():
        return {"ok": False, "files": 0, "errors": [f"{mental_root}: not found"], "warnings": []}

    for path in sorted(mental_root.rglob("*.md")):
        artifact, parse_errors = parse_frontmatter(path)
        errors.extend(parse_errors)
        if artifact:
            artifacts.append(artifact)

    ids: dict[str, Path] = {}
    for artifact in artifacts:
        missing = REQUIRED_FIELDS - artifact.fields.keys()
        for field in sorted(missing):
            errors.append(f"{artifact.path}: missing required field '{field}'")
        artifact_id = artifact.fields.get("id")
        if isinstance(artifact_id, str):
            if not ID_RE.match(artifact_id):
                errors.append(f"{artifact.path}: invalid id '{artifact_id}'")
            elif artifact_id in ids:
                errors.append(f"{artifact.path}: duplicate id '{artifact_id}' also in {ids[artifact_id]}")
            else:
                ids[artifact_id] = artifact.path
        kind = artifact.fields.get("kind")
        if kind not in ALLOWED_KINDS:
            errors.append(f"{artifact.path}: unsupported kind '{kind}'")
        relative_parts = artifact.path.relative_to(mental_root).parts
        if kind == "lens" and (not relative_parts or relative_parts[0] != "lenses"):
            errors.append(f"{artifact.path}: kind 'lens' must live under mental/lenses/")
        if relative_parts and relative_parts[0] == "lenses" and kind != "lens":
            errors.append(f"{artifact.path}: artifacts under mental/lenses/ must use kind 'lens'")
        status = artifact.fields.get("status")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{artifact.path}: unsupported status '{status}'")
        for key in ("sources", "prerequisites"):
            if not isinstance(artifact.fields.get(key), list):
                errors.append(f"{artifact.path}: '{key}' must be a YAML list")
        if kind == "lens":
            for key in ("assumes", "prioritizes", "vocabulary", "default_views"):
                if not isinstance(artifact.fields.get(key), list):
                    errors.append(f"{artifact.path}: lens field '{key}' must be a YAML list")
            default_views = artifact.fields.get("default_views", [])
            if isinstance(default_views, list):
                for view in default_views:
                    if view not in ALLOWED_VIEWS:
                        errors.append(f"{artifact.path}: unsupported default view '{view}'")
        if status == "canonical" and kind not in {"index", "sources"} and not list_field(artifact, "sources"):
            errors.append(f"{artifact.path}: canonical artifact has no sources")

    source_catalog = next((a for a in artifacts if a.fields.get("kind") == "sources"), None)
    source_ids = set(re.findall(r"^##\s+([a-z0-9]+(?:[.-][a-z0-9]+)*)\s*$", source_catalog.body, re.MULTILINE)) if source_catalog else set()
    if not source_catalog:
        errors.append(f"{mental_root}: missing a kind=sources artifact")

    all_ids = set(ids)
    for artifact in artifacts:
        for source_id in list_field(artifact, "sources"):
            if source_id not in source_ids:
                errors.append(f"{artifact.path}: unknown source id '{source_id}'")
        for prerequisite in list_field(artifact, "prerequisites"):
            if prerequisite not in all_ids:
                errors.append(f"{artifact.path}: unknown prerequisite id '{prerequisite}'")
        for target in LINK_RE.findall(artifact.body):
            target = target.strip().split(maxsplit=1)[0].strip("<>\"")
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            target_path = unquote(target.split("#", 1)[0])
            if target_path and not (artifact.path.parent / target_path).resolve().exists():
                errors.append(f"{artifact.path}: broken local link '{target}'")

    combined = "\n".join(a.body for a in artifacts)
    for artifact in artifacts:
        if artifact.fields.get("kind") != "concept":
            continue
        artifact_id = str(artifact.fields.get("id", ""))
        other_content = combined.replace(artifact.body, "", 1)
        if artifact_id and artifact_id not in other_content:
            warnings.append(f"{artifact.path}: concept '{artifact_id}' is not referenced by another artifact")

    ignore_file = private_root / ".gitignore"
    if not ignore_file.exists():
        errors.append(f"{ignore_file}: private-state ignore file is missing")
    else:
        ignore_lines = {line.strip() for line in ignore_file.read_text(encoding="utf-8").splitlines() if line.strip()}
        if "*" not in ignore_lines or "!.gitignore" not in ignore_lines:
            errors.append(f"{ignore_file}: must ignore everything except .gitignore")

    mastery_file = private_root / "mastery.json"
    if mastery_file.exists():
        try:
            mastery = json.loads(mastery_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            errors.append(f"{mastery_file}: must contain valid JSON")
        else:
            if not isinstance(mastery, dict):
                errors.append(f"{mastery_file}: root must be an object")
            else:
                if mastery.get("version") != 1:
                    errors.append(f"{mastery_file}: version must be 1")
                concepts = mastery.get("concepts")
                if not isinstance(concepts, dict):
                    errors.append(f"{mastery_file}: concepts must be an object")
                else:
                    for concept_id, entry in concepts.items():
                        if not isinstance(concept_id, str) or not ID_RE.match(concept_id):
                            errors.append(f"{mastery_file}: invalid concept id '{concept_id}'")
                            continue
                        if not isinstance(entry, dict):
                            errors.append(f"{mastery_file}: mastery entry '{concept_id}' must be an object")
                            continue
                        if entry.get("state") not in ALLOWED_MASTERY_STATES:
                            errors.append(f"{mastery_file}: invalid mastery state for '{concept_id}'")
                        evidence = entry.get("evidence")
                        if not isinstance(evidence, list) or not all(isinstance(item, str) for item in evidence):
                            errors.append(f"{mastery_file}: evidence for '{concept_id}' must be a string array")
                        if not isinstance(entry.get("updated_at"), str):
                            errors.append(f"{mastery_file}: updated_at for '{concept_id}' must be a string")

    return {"ok": not errors, "files": len(artifacts), "errors": errors, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate mental workspace artifacts")
    parser.add_argument("workspace", nargs="?", default=".")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    result = validate(Path(args.workspace))
    if args.as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Checked {result['files']} artifact(s).")
        for warning in result["warnings"]:
            print(f"warning: {warning}")
        for error in result["errors"]:
            print(f"error: {error}")
        print("OK" if result["ok"] else "FAILED")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
