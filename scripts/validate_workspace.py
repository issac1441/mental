"""Internal, dependency-free validator used by mental:doctor and mental:sync."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

REQUIRED_FIELDS = {
    "id",
    "kind",
    "authority",
    "status",
    "sources",
    "prerequisites",
    "updated_at",
}
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
    "conflict",
    "change",
    "learning-path",
    "misconception",
    "exercise",
}
ALLOWED_AUTHORITIES = {"mechanical", "conceptual", "decision"}
AUTHORITY_STATUSES = {
    "mechanical": {"current", "stale"},
    "conceptual": {"draft", "active", "stale"},
    "decision": {"pending", "accepted", "rejected", "superseded"},
}
CONFLICT_STATUSES = {"open", "resolved"}
ALLOWED_MASTERY_STATES = {"unknown", "exposed", "working", "verified"}
ALLOWED_DECISION_OWNERS = {"human", "agent", "shared", "unassigned"}
ALLOWED_SURFACED_STATES = {"pre-approval", "post-approval"}
ALLOWED_REVERSIBILITY = {"easy", "costly", "irreversible", "unknown"}
ID_RE = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^]]*]\(([^)]+)\)")
SOURCE_HEADING_RE = re.compile(
    r"^##\s+([a-z0-9]+(?:[.-][a-z0-9]+)*)(?:\s+(?:—|-)\s+\S.*)?$",
    re.MULTILINE,
)
ID_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)*")


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
        if key in fields:
            errors.append(f"{path}:{line_number}: duplicate frontmatter field '{key}'")
            continue
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


def is_iso_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return dt.date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def markdown_destination(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("<"):
        closing = raw.find(">")
        return raw[1:closing] if closing != -1 else raw
    return raw.split(maxsplit=1)[0] if raw else ""


def inspect_git_privacy(
    workspace: Path, private_root: Path, errors: list[str], warnings: list[str]
) -> None:
    try:
        inside = subprocess.run(
            ["git", "-C", str(workspace), "rev-parse", "--is-inside-work-tree"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        warnings.append(
            f"{workspace}: Git is unavailable; private-state tracking was not checked"
        )
        return
    if inside.returncode != 0:
        warnings.append(
            f"{workspace}: not a Git worktree; private-state tracking was not checked"
        )
        return

    tracked_result = subprocess.run(
        ["git", "-C", str(workspace), "ls-files", "-z", "--", ".mental"],
        check=False,
        capture_output=True,
    )
    if tracked_result.returncode != 0:
        warnings.append(f"{workspace}: Git could not inspect tracked private state")
        return
    tracked = [
        item.decode("utf-8", errors="replace")
        for item in tracked_result.stdout.split(b"\0")
        if item
    ]
    leaked = sorted(path for path in tracked if path != ".mental/.gitignore")
    if leaked:
        errors.append(
            f"{private_root}: private files are tracked by Git: {', '.join(leaked)}"
        )

    probes = {
        ".mental/profile.md",
        ".mental/mastery.json",
        ".mental/sessions/privacy-probe.md",
    }
    if private_root.is_dir() and not private_root.is_symlink():
        for path in private_root.rglob("*"):
            if path.is_file() and path.name != ".gitignore" and not path.is_symlink():
                probes.add(path.relative_to(workspace).as_posix())
    for probe in sorted(probes):
        ignored = subprocess.run(
            [
                "git",
                "-C",
                str(workspace),
                "check-ignore",
                "--no-index",
                "--quiet",
                "--",
                probe,
            ],
            check=False,
            capture_output=True,
        )
        if ignored.returncode == 1:
            errors.append(f"{private_root}: Git does not ignore '{probe}'")
        elif ignored.returncode not in {0, 1}:
            warnings.append(
                f"{private_root}: Git could not verify ignore status for '{probe}'"
            )


def validate(workspace: Path) -> dict[str, object]:
    workspace = workspace.resolve()
    if workspace.name == "mental" and (workspace / "index.md").exists():
        mental_root = workspace
        private_root = workspace.parent / ".mental"
        workspace_root = workspace.parent
    else:
        mental_root = workspace / "mental"
        private_root = workspace / ".mental"
        workspace_root = workspace

    errors: list[str] = []
    warnings: list[str] = []
    artifacts: list[Artifact] = []
    if not mental_root.is_dir():
        return {
            "ok": False,
            "files": 0,
            "errors": [f"{mental_root}: not found"],
            "warnings": [],
        }
    if mental_root.is_symlink():
        return {
            "ok": False,
            "files": 0,
            "errors": [f"{mental_root}: must not be a symlink"],
            "warnings": [],
        }

    for path in sorted(mental_root.rglob("*")):
        if path.is_symlink():
            errors.append(f"{path}: artifact paths must not be symlinks")

    for path in sorted(mental_root.rglob("*.md")):
        if path.is_symlink():
            continue
        try:
            artifact, parse_errors = parse_frontmatter(path)
        except (OSError, UnicodeError) as exc:
            errors.append(f"{path}: cannot read artifact ({type(exc).__name__})")
            continue
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
                errors.append(
                    f"{artifact.path}: duplicate id '{artifact_id}' also in {ids[artifact_id]}"
                )
            else:
                ids[artifact_id] = artifact.path
        kind = artifact.fields.get("kind")
        if kind not in ALLOWED_KINDS:
            errors.append(f"{artifact.path}: unsupported kind '{kind}'")
        relative_parts = artifact.path.relative_to(mental_root).parts
        if kind == "lens" and (not relative_parts or relative_parts[0] != "lenses"):
            errors.append(
                f"{artifact.path}: kind 'lens' must live under mental/lenses/"
            )
        if relative_parts and relative_parts[0] == "lenses" and kind != "lens":
            errors.append(
                f"{artifact.path}: artifacts under mental/lenses/ must use kind 'lens'"
            )
        if kind == "conflict" and (
            not relative_parts or relative_parts[0] != "conflicts"
        ):
            errors.append(
                f"{artifact.path}: kind 'conflict' must live under mental/conflicts/"
            )
        if relative_parts and relative_parts[0] == "conflicts" and kind != "conflict":
            errors.append(
                f"{artifact.path}: artifacts under mental/conflicts/ must use kind 'conflict'"
            )
        if kind == "decision" and (
            not relative_parts or relative_parts[0] != "decisions"
        ):
            errors.append(
                f"{artifact.path}: kind 'decision' must live under mental/decisions/"
            )
        if relative_parts and relative_parts[0] == "decisions" and kind != "decision":
            errors.append(
                f"{artifact.path}: artifacts under mental/decisions/ must use kind 'decision'"
            )
        authority = artifact.fields.get("authority")
        if authority not in ALLOWED_AUTHORITIES:
            errors.append(f"{artifact.path}: unsupported authority '{authority}'")
        status = artifact.fields.get("status")
        if kind == "conflict":
            allowed_statuses = CONFLICT_STATUSES
        else:
            allowed_statuses = AUTHORITY_STATUSES.get(str(authority), set())
        if status not in allowed_statuses:
            errors.append(
                f"{artifact.path}: status '{status}' is invalid for authority '{authority}'"
            )
        required_authority = {
            "sources": "mechanical",
            "lens": "conceptual",
            "decision": "decision",
            "conflict": "decision",
            "change": "decision",
        }.get(str(kind))
        if required_authority and authority != required_authority:
            errors.append(
                f"{artifact.path}: kind '{kind}' requires authority '{required_authority}'"
            )
        if not is_iso_date(artifact.fields.get("updated_at")):
            errors.append(
                f"{artifact.path}: 'updated_at' must use ISO YYYY-MM-DD format"
            )
        if (
            kind == "index"
            and "mode" in artifact.fields
            and artifact.fields.get("mode")
            not in {
                "repository",
                "learning",
                "hybrid",
            }
        ):
            errors.append(
                f"{artifact.path}: unsupported mode '{artifact.fields.get('mode')}'"
            )
        for key in ("sources", "prerequisites"):
            if not isinstance(artifact.fields.get(key), list):
                errors.append(f"{artifact.path}: '{key}' must be a YAML list")
        if kind == "lens":
            for key in ("assumes", "prioritizes", "vocabulary"):
                if not isinstance(artifact.fields.get(key), list):
                    errors.append(
                        f"{artifact.path}: lens field '{key}' must be a YAML list"
                    )
        if kind == "conflict":
            for key in ("owner", "opened_at"):
                if not isinstance(artifact.fields.get(key), str):
                    errors.append(
                        f"{artifact.path}: conflict field '{key}' must be a scalar"
                    )
            if not is_iso_date(artifact.fields.get("opened_at")):
                errors.append(
                    f"{artifact.path}: conflict 'opened_at' must use ISO YYYY-MM-DD format"
                )
            if status == "resolved" and not is_iso_date(
                artifact.fields.get("resolved_at")
            ):
                errors.append(
                    f"{artifact.path}: resolved conflict requires ISO 'resolved_at'"
                )
        if kind == "decision":
            decision_fields = {
                "decision_owner": ALLOWED_DECISION_OWNERS,
                "surfaced": ALLOWED_SURFACED_STATES,
                "consequential": {"true", "false"},
                "reversibility": ALLOWED_REVERSIBILITY,
            }
            for key, allowed in decision_fields.items():
                value = artifact.fields.get(key)
                if value not in allowed:
                    errors.append(
                        f"{artifact.path}: decision field '{key}' has invalid value '{value}'"
                    )
        if (
            status in {"current", "active", "accepted", "resolved"}
            and kind not in {"index", "sources"}
            and not list_field(artifact, "sources")
        ):
            errors.append(f"{artifact.path}: active artifact state has no sources")

    source_catalog = next(
        (a for a in artifacts if a.fields.get("kind") == "sources"), None
    )
    source_ids = (
        set(SOURCE_HEADING_RE.findall(source_catalog.body)) if source_catalog else set()
    )
    if not source_catalog:
        errors.append(f"{mental_root}: missing a kind=sources artifact")

    all_ids = set(ids)
    for artifact in artifacts:
        for source_id in list_field(artifact, "sources"):
            if source_id not in source_ids:
                errors.append(f"{artifact.path}: unknown source id '{source_id}'")
        for prerequisite in list_field(artifact, "prerequisites"):
            if prerequisite not in all_ids:
                errors.append(
                    f"{artifact.path}: unknown prerequisite id '{prerequisite}'"
                )
        for target in LINK_RE.findall(artifact.body):
            target = markdown_destination(target)
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            target_path = unquote(target.split("#", 1)[0])
            if not target_path:
                continue
            destination = Path(target_path)
            if destination.is_absolute():
                errors.append(
                    f"{artifact.path}: local link must be relative and inside the workspace '{target}'"
                )
                continue
            resolved = (artifact.path.parent / destination).resolve()
            try:
                resolved.relative_to(workspace_root)
            except ValueError:
                errors.append(
                    f"{artifact.path}: local link escapes the workspace '{target}'"
                )
                continue
            if not resolved.exists():
                errors.append(f"{artifact.path}: broken local link '{target}'")

    token_paths: dict[str, set[Path]] = {}
    prerequisite_ids: set[str] = set()
    for artifact in artifacts:
        prerequisite_ids.update(list_field(artifact, "prerequisites"))
        for token in set(ID_TOKEN_RE.findall(artifact.body)):
            token_paths.setdefault(token, set()).add(artifact.path)
    for artifact in artifacts:
        if artifact.fields.get("kind") != "concept":
            continue
        artifact_id = str(artifact.fields.get("id", ""))
        other_paths = token_paths.get(artifact_id, set()) - {artifact.path}
        if artifact_id and artifact_id not in prerequisite_ids and not other_paths:
            warnings.append(
                f"{artifact.path}: concept '{artifact_id}' is not referenced by another artifact"
            )

    ignore_file = private_root / ".gitignore"
    if private_root.is_symlink():
        errors.append(f"{private_root}: private-state directory must not be a symlink")
    elif not ignore_file.exists():
        errors.append(f"{ignore_file}: private-state ignore file is missing")
    elif ignore_file.is_symlink():
        errors.append(f"{ignore_file}: private-state ignore file must not be a symlink")
    else:
        try:
            ignore_lines = {
                line.strip()
                for line in ignore_file.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            }
        except (OSError, UnicodeError) as exc:
            errors.append(
                f"{ignore_file}: cannot read ignore file ({type(exc).__name__})"
            )
        else:
            if ignore_lines != {"*", "!.gitignore"}:
                errors.append(
                    f"{ignore_file}: must ignore everything except .gitignore"
                )

    if private_root.is_dir() and not private_root.is_symlink():
        for path in sorted(private_root.rglob("*")):
            if path.is_symlink():
                errors.append(f"{path}: private-state paths must not be symlinks")

    inspect_git_privacy(workspace_root, private_root, errors, warnings)

    mastery_file = private_root / "mastery.json"
    if private_root.is_symlink():
        pass
    elif mastery_file.is_symlink():
        errors.append(f"{mastery_file}: private mastery file must not be a symlink")
    elif mastery_file.exists():
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
                if not is_iso_date(mastery.get("updated_at")):
                    errors.append(
                        f"{mastery_file}: updated_at must use ISO YYYY-MM-DD format"
                    )
                concepts = mastery.get("concepts")
                if not isinstance(concepts, dict):
                    errors.append(f"{mastery_file}: concepts must be an object")
                else:
                    for concept_id, entry in concepts.items():
                        if not isinstance(concept_id, str) or not ID_RE.match(
                            concept_id
                        ):
                            errors.append(
                                f"{mastery_file}: invalid concept id '{concept_id}'"
                            )
                            continue
                        if not isinstance(entry, dict):
                            errors.append(
                                f"{mastery_file}: mastery entry '{concept_id}' must be an object"
                            )
                            continue
                        if entry.get("state") not in ALLOWED_MASTERY_STATES:
                            errors.append(
                                f"{mastery_file}: invalid mastery state for '{concept_id}'"
                            )
                        evidence = entry.get("evidence")
                        if not isinstance(evidence, list) or not all(
                            isinstance(item, str) for item in evidence
                        ):
                            errors.append(
                                f"{mastery_file}: evidence for '{concept_id}' must be a string array"
                            )
                        if not is_iso_date(entry.get("updated_at")):
                            errors.append(
                                f"{mastery_file}: updated_at for '{concept_id}' must use ISO YYYY-MM-DD format"
                            )

    return {
        "ok": not errors,
        "files": len(artifacts),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate mental workspace artifacts")
    parser.add_argument("workspace", nargs="?", default=".")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    # Keep --json machine-readable even when an unexpected validator defect occurs.
    try:
        result = validate(Path(args.workspace))
    except Exception as exc:  # noqa: BLE001
        result = {
            "ok": False,
            "files": 0,
            "errors": [],
            "warnings": [],
            "validator_error": f"{type(exc).__name__}: {exc}",
        }
        exit_code = 2
    else:
        exit_code = 0 if result["ok"] else 1
    if args.as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Checked {result['files']} artifact(s).")
        for warning in result["warnings"]:
            print(f"warning: {warning}")
        for error in result["errors"]:
            print(f"error: {error}")
        if "validator_error" in result:
            print(f"validator error: {result['validator_error']}")
        print("OK" if result["ok"] else "FAILED")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
