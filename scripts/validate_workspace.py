"""Internal, dependency-free validator used by mental:doctor and mental:sync."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import stat
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
KIND_AUTHORITIES = {
    "index": {"conceptual"},
    "sources": {"mechanical"},
    "glossary": {"mechanical", "conceptual"},
    "lens": {"conceptual"},
    "map": {"mechanical"},
    "concept": {"mechanical", "conceptual"},
    "scenario": {"mechanical", "conceptual"},
    "architecture": {"mechanical", "conceptual"},
    "contract": {"mechanical", "conceptual"},
    "decision": {"decision"},
    "conflict": {"decision"},
    "change": {"decision"},
    "learning-path": {"conceptual"},
    "misconception": {"conceptual"},
    "exercise": {"conceptual"},
}
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
ALLOWED_PREDICTION_STATES = {"attempted", "skipped", "not-applicable"}
DECISION_TRANSITIONS = {
    "pending": {"accepted", "rejected", "superseded"},
    "accepted": {"superseded"},
    "rejected": {"superseded"},
    "superseded": set(),
}
ACTIVATION_FIELDS = {
    "verification_basis",
    "checked_predictions",
    "known_gaps",
    "conflicts",
}
ID_RE = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^]]*]\(([^)]+)\)")
SOURCE_HEADING_RE = re.compile(
    r"^##\s+([a-z0-9]+(?:[.-][a-z0-9]+)*)(?:\s+(?:—|-)\s+\S.*)?$",
    re.MULTILINE,
)
ID_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)*")
REFRESH_BASIS_RE = re.compile(r"^([a-z0-9]+(?:[.-][a-z0-9]+)*)@([^\s]+)$")
STATUS_HISTORY_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}):\s*(pending|accepted|rejected|superseded)$"
)
PLACEHOLDER_RE = re.compile(r"\b(?:pending|todo|tbd|looks good)\b", re.IGNORECASE)


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


def is_regular_file(path: Path) -> bool:
    return stat.S_ISREG(path.lstat().st_mode)


def require_regular_file(path: Path, label: str, errors: list[str]) -> bool:
    try:
        regular = is_regular_file(path)
    except OSError as exc:
        errors.append(f"{path}: cannot inspect {label} ({type(exc).__name__})")
        return False
    if not regular:
        errors.append(f"{path}: {label} must be regular")
        return False
    return True


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

    history_result = subprocess.run(
        [
            "git",
            "-C",
            str(workspace),
            "log",
            "--all",
            "--format=",
            "--name-only",
            "--",
            ".mental",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if history_result.returncode != 0:
        warnings.append(f"{workspace}: Git history privacy could not be inspected")
    else:
        historical_private_paths = {
            line.strip()
            for line in history_result.stdout.splitlines()
            if line.strip()
            and line.strip() != ".mental/.gitignore"
            and not line.strip().endswith("/.mental/.gitignore")
        }
        if historical_private_paths:
            warnings.append(
                f"{private_root}: Git history contains private-state paths; "
                "validation cannot remove copies from refs, forks, or remotes"
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

    ignore_self = subprocess.run(
        [
            "git",
            "-C",
            str(workspace),
            "check-ignore",
            "--no-index",
            "--quiet",
            "--",
            ".mental/.gitignore",
        ],
        check=False,
        capture_output=True,
    )
    if ignore_self.returncode == 0:
        errors.append(f"{private_root}: Git ignores '.mental/.gitignore' itself")
    elif ignore_self.returncode not in {0, 1}:
        warnings.append(f"{private_root}: Git could not inspect the ignore file itself")


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

    non_regular_artifacts: set[Path] = set()
    for path in sorted(mental_root.rglob("*")):
        if path.is_symlink():
            errors.append(f"{path}: artifact paths must not be symlinks")
        elif path.suffix == ".md":
            try:
                regular = is_regular_file(path)
            except OSError as exc:
                errors.append(
                    f"{path}: cannot inspect artifact path ({type(exc).__name__})"
                )
                non_regular_artifacts.add(path)
            else:
                if not regular:
                    errors.append(f"{path}: Markdown artifacts must be regular files")
                    non_regular_artifacts.add(path)

    for path in sorted(mental_root.rglob("*.md")):
        if path.is_symlink() or path in non_regular_artifacts:
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
        elif "id" in artifact.fields:
            errors.append(f"{artifact.path}: 'id' must be a scalar")
        raw_kind = artifact.fields.get("kind")
        kind = raw_kind if isinstance(raw_kind, str) else None
        if kind not in ALLOWED_KINDS:
            errors.append(f"{artifact.path}: unsupported kind '{raw_kind}'")
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
        raw_authority = artifact.fields.get("authority")
        authority = raw_authority if isinstance(raw_authority, str) else None
        if authority not in ALLOWED_AUTHORITIES:
            errors.append(f"{artifact.path}: unsupported authority '{raw_authority}'")
        elif kind in KIND_AUTHORITIES and authority not in KIND_AUTHORITIES[kind]:
            allowed = ", ".join(sorted(KIND_AUTHORITIES[kind]))
            errors.append(f"{artifact.path}: kind '{kind}' allows authority: {allowed}")
        raw_status = artifact.fields.get("status")
        status = raw_status if isinstance(raw_status, str) else None
        if kind == "conflict":
            allowed_statuses = CONFLICT_STATUSES
        else:
            allowed_statuses = AUTHORITY_STATUSES.get(str(authority), set())
        if status not in allowed_statuses:
            errors.append(
                f"{artifact.path}: status '{raw_status}' is invalid for authority '{raw_authority}'"
            )
        if not is_iso_date(artifact.fields.get("updated_at")):
            errors.append(
                f"{artifact.path}: 'updated_at' must use ISO YYYY-MM-DD format"
            )
        if (
            kind == "index"
            and "mode" in artifact.fields
            and (
                not isinstance(artifact.fields.get("mode"), str)
                or artifact.fields.get("mode")
                not in {"repository", "learning", "hybrid"}
            )
        ):
            errors.append(
                f"{artifact.path}: unsupported mode '{artifact.fields.get('mode')}'"
            )
        for key in ("sources", "prerequisites"):
            if not isinstance(artifact.fields.get(key), list):
                errors.append(f"{artifact.path}: '{key}' must be a YAML list")
        if kind == "lens":
            for key in ("assumes", "concerns", "vocabulary"):
                if not isinstance(artifact.fields.get(key), list):
                    errors.append(
                        f"{artifact.path}: lens field '{key}' must be a YAML list"
                    )
        if authority == "mechanical" and kind != "sources":
            refresh_basis = artifact.fields.get("refresh_basis")
            if not isinstance(refresh_basis, list):
                errors.append(
                    f"{artifact.path}: mechanical artifact requires a 'refresh_basis' list"
                )
            elif status == "current":
                if not refresh_basis:
                    errors.append(
                        f"{artifact.path}: current mechanical artifact has no refresh basis"
                    )
                for entry in refresh_basis:
                    match = REFRESH_BASIS_RE.fullmatch(str(entry))
                    if not match:
                        errors.append(
                            f"{artifact.path}: invalid refresh basis '{entry}'; "
                            "use <source-id>@<revision>"
                        )
                        continue
                    source_id, revision = match.groups()
                    if source_id not in list_field(artifact, "sources"):
                        errors.append(
                            f"{artifact.path}: refresh basis source '{source_id}' "
                            "is not listed in sources"
                        )
                    if PLACEHOLDER_RE.search(revision) or revision in {
                        "unknown",
                        "unrecorded",
                    }:
                        errors.append(
                            f"{artifact.path}: refresh basis requires a concrete revision"
                        )
                if "## Evidence" not in artifact.body:
                    errors.append(
                        f"{artifact.path}: current mechanical artifact requires an Evidence section"
                    )
        if authority == "conceptual":
            for key in ACTIVATION_FIELDS:
                value = artifact.fields.get(key)
                if value is not None and not isinstance(value, list):
                    errors.append(
                        f"{artifact.path}: conceptual field '{key}' must be a YAML list"
                    )
            if status == "active":
                for key in ACTIVATION_FIELDS:
                    if not isinstance(artifact.fields.get(key), list):
                        errors.append(
                            f"{artifact.path}: active conceptual artifact requires '{key}'"
                        )
                verification_basis = list_field(artifact, "verification_basis")
                checked_predictions = list_field(artifact, "checked_predictions")
                if not verification_basis or any(
                    PLACEHOLDER_RE.search(item) for item in verification_basis
                ):
                    errors.append(
                        f"{artifact.path}: active conceptual artifact needs a non-placeholder verification basis"
                    )
                prediction_kinds = {
                    item.split(":", 1)[0].strip().lower()
                    for item in checked_predictions
                    if ":" in item and not PLACEHOLDER_RE.search(item)
                }
                if "success" not in prediction_kinds:
                    errors.append(
                        f"{artifact.path}: active conceptual artifact needs a checked success prediction"
                    )
                if not prediction_kinds.intersection({"failure", "boundary"}):
                    errors.append(
                        f"{artifact.path}: active conceptual artifact needs a checked failure or boundary prediction"
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
                if not isinstance(value, str) or value not in allowed:
                    errors.append(
                        f"{artifact.path}: decision field '{key}' has invalid value '{value}'"
                    )
        if kind in {"decision", "change"}:
            for key in ("supersedes", "superseded_by"):
                if not isinstance(artifact.fields.get(key), list):
                    errors.append(
                        f"{artifact.path}: {kind} field '{key}' must be a YAML list"
                    )
            history = artifact.fields.get("status_history")
            parsed_history: list[tuple[str, str]] = []
            if not isinstance(history, list) or not history:
                errors.append(
                    f"{artifact.path}: {kind} requires a non-empty 'status_history' list"
                )
            else:
                for entry in history:
                    match = STATUS_HISTORY_RE.fullmatch(str(entry))
                    if not match or not is_iso_date(match.group(1) if match else None):
                        errors.append(
                            f"{artifact.path}: invalid status history entry '{entry}'"
                        )
                    else:
                        parsed_history.append((match.group(1), match.group(2)))
                if parsed_history and parsed_history[-1][1] != status:
                    errors.append(
                        f"{artifact.path}: latest status history entry must match status '{status}'"
                    )
                dates = [date for date, _ in parsed_history]
                if dates != sorted(dates):
                    errors.append(
                        f"{artifact.path}: status history dates must be chronological"
                    )
                states = [state for _, state in parsed_history]
                if states and states[0] != "pending":
                    errors.append(
                        f"{artifact.path}: status history must start with pending"
                    )
                for previous, current in zip(states, states[1:], strict=False):
                    if current not in DECISION_TRANSITIONS.get(previous, set()):
                        errors.append(
                            f"{artifact.path}: invalid status transition "
                            f"'{previous}' to '{current}'"
                        )
            if status == "superseded" and not list_field(artifact, "superseded_by"):
                errors.append(
                    f"{artifact.path}: superseded artifact requires 'superseded_by'"
                )
        if kind == "change" and (
            not isinstance(artifact.fields.get("prediction_status"), str)
            or artifact.fields.get("prediction_status") not in ALLOWED_PREDICTION_STATES
        ):
            errors.append(
                f"{artifact.path}: change field 'prediction_status' must be "
                "attempted, skipped, or not-applicable"
            )
        if (
            status in {"current", "active", "accepted", "resolved"}
            and kind not in {"index", "sources"}
            and not list_field(artifact, "sources")
        ):
            errors.append(f"{artifact.path}: active artifact state has no sources")

    source_catalog_path = mental_root / "sources.md"
    source_artifacts = [
        artifact for artifact in artifacts if artifact.fields.get("kind") == "sources"
    ]
    source_catalog = next(
        (artifact for artifact in artifacts if artifact.path == source_catalog_path),
        None,
    )
    if source_catalog is None:
        errors.append(f"{source_catalog_path}: required source catalog is missing")
    elif source_catalog.fields.get("kind") != "sources":
        errors.append(f"{source_catalog_path}: must use kind 'sources'")
        source_catalog = None
    for artifact in source_artifacts:
        if artifact.path != source_catalog_path:
            errors.append(
                f"{artifact.path}: kind 'sources' is only allowed at mental/sources.md"
            )
    source_id_entries = (
        SOURCE_HEADING_RE.findall(source_catalog.body) if source_catalog else []
    )
    source_ids = set(source_id_entries)
    duplicate_source_ids = sorted(
        source_id for source_id in source_ids if source_id_entries.count(source_id) > 1
    )
    for source_id in duplicate_source_ids:
        errors.append(f"{source_catalog_path}: duplicate source id '{source_id}'")

    all_ids = set(ids)
    artifact_kinds = {
        str(artifact.fields.get("id")): artifact.fields.get("kind")
        for artifact in artifacts
        if isinstance(artifact.fields.get("id"), str)
    }
    artifacts_by_id = {
        str(artifact.fields["id"]): artifact
        for artifact in artifacts
        if isinstance(artifact.fields.get("id"), str)
    }
    for artifact in artifacts:
        for source_id in list_field(artifact, "sources"):
            if source_id not in source_ids:
                errors.append(f"{artifact.path}: unknown source id '{source_id}'")
        for prerequisite in list_field(artifact, "prerequisites"):
            if prerequisite not in all_ids:
                errors.append(
                    f"{artifact.path}: unknown prerequisite id '{prerequisite}'"
                )
        for conflict_id in list_field(artifact, "conflicts"):
            if artifact_kinds.get(conflict_id) != "conflict":
                errors.append(f"{artifact.path}: unknown conflict id '{conflict_id}'")
        kind = artifact.fields.get("kind")
        if isinstance(kind, str) and kind in {"decision", "change"}:
            artifact_id = str(artifact.fields.get("id", ""))
            for field, reciprocal in (
                ("supersedes", "superseded_by"),
                ("superseded_by", "supersedes"),
            ):
                for target_id in list_field(artifact, field):
                    target = artifacts_by_id.get(target_id)
                    if target is None or target.fields.get("kind") != kind:
                        errors.append(
                            f"{artifact.path}: {field} target '{target_id}' "
                            f"must be another {kind} artifact"
                        )
                    elif artifact_id not in list_field(target, reciprocal):
                        errors.append(
                            f"{artifact.path}: {field} target '{target_id}' "
                            f"does not link back through {reciprocal}"
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
    elif require_regular_file(ignore_file, "private-state ignore file", errors):
        try:
            ignore_lines = [
                line.strip()
                for line in ignore_file.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
        except (OSError, UnicodeError) as exc:
            errors.append(
                f"{ignore_file}: cannot read ignore file ({type(exc).__name__})"
            )
        else:
            if ignore_lines != ["*", "!.gitignore"]:
                errors.append(
                    f"{ignore_file}: must contain '*' followed by '!.gitignore'"
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
        if require_regular_file(mastery_file, "private mastery file", errors):
            try:
                mastery = json.loads(mastery_file.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                errors.append(f"{mastery_file}: must contain UTF-8 valid JSON")
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

    draft_artifacts = sorted(
        str(artifact.fields.get("id"))
        for artifact in artifacts
        if artifact.fields.get("status") == "draft"
    )
    stale_artifacts = sorted(
        str(artifact.fields.get("id"))
        for artifact in artifacts
        if artifact.fields.get("status") == "stale"
    )
    pending_decisions = sorted(
        str(artifact.fields.get("id"))
        for artifact in artifacts
        if artifact.fields.get("status") == "pending"
    )
    open_conflicts = sorted(
        str(artifact.fields.get("id"))
        for artifact in artifacts
        if artifact.fields.get("kind") == "conflict"
        and artifact.fields.get("status") == "open"
    )
    incomplete = any(
        (draft_artifacts, stale_artifacts, pending_decisions, open_conflicts)
    )

    return {
        "ok": not errors,
        "files": len(artifacts),
        "errors": errors,
        "warnings": warnings,
        "readiness": {
            "state": "incomplete" if incomplete else "ready",
            "draft_artifacts": draft_artifacts,
            "stale_artifacts": stale_artifacts,
            "pending_decisions": pending_decisions,
            "open_conflicts": open_conflicts,
        },
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
        print(json.dumps(result, indent=2, ensure_ascii=True))
    else:
        print(f"Checked {result['files']} artifact(s).")
        for warning in result["warnings"]:
            print(f"warning: {warning}")
        for error in result["errors"]:
            print(f"error: {error}")
        if "validator_error" in result:
            print(f"validator error: {result['validator_error']}")
        if result["ok"]:
            readiness = result.get("readiness", {}).get("state", "unknown")
            print("Structure: valid")
            print(f"Readiness: {readiness}")
        else:
            print("Structure: invalid")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
