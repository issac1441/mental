"""Internal helper used by mental:build to create a non-destructive workspace skeleton."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from collections.abc import Iterable
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "assets" / "templates"
LANGUAGE_RE = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")


class ScaffoldError(ValueError):
    """Raised when scaffold input or an existing path is unsafe."""


def validate_inputs(language: str, today: str) -> None:
    if not LANGUAGE_RE.fullmatch(language):
        raise ScaffoldError(
            "language must be a BCP-47-style tag such as 'en' or 'zh-TW'"
        )
    try:
        parsed_date = dt.date.fromisoformat(today)
    except ValueError as exc:
        raise ScaffoldError("date must use ISO YYYY-MM-DD format") from exc
    if parsed_date.isoformat() != today:
        raise ScaffoldError("date must use ISO YYYY-MM-DD format")


def require_safe_path(workspace: Path, path: Path) -> None:
    try:
        relative = path.relative_to(workspace)
    except ValueError as exc:
        raise ScaffoldError(f"refusing to write outside workspace: {path}") from exc

    current = workspace
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ScaffoldError(f"refusing to follow symlink: {current}")


def render_template(name: str, values: dict[str, str]) -> str:
    content = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
    for key, value in values.items():
        content = content.replace("{{" + key + "}}", value)
    return content


def write_new(
    workspace: Path,
    path: Path,
    content: str,
    created: list[Path],
    skipped: list[Path],
) -> None:
    require_safe_path(workspace, path)
    if path.exists():
        if not path.is_file():
            raise ScaffoldError(
                f"expected a regular file but found another path type: {path}"
            )
        skipped.append(path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    created.append(path)


def ensure_directories(workspace: Path, paths: Iterable[Path]) -> None:
    for path in paths:
        require_safe_path(workspace, path)
        path.mkdir(parents=True, exist_ok=True)


def scaffold(
    workspace: Path, mode: str, language: str, today: str
) -> tuple[list[Path], list[Path]]:
    workspace = workspace.resolve()
    validate_inputs(language, today)
    mental_root = workspace / "mental"
    private_root = workspace / ".mental"
    source_id = (
        "source-workspace" if mode in {"repository", "hybrid"} else "source-material"
    )
    source_type = (
        "repository" if mode in {"repository", "hybrid"} else "provided-material"
    )
    values = {
        "TODAY": today,
        "MODE": mode,
        "LANGUAGE": language,
        "SOURCE_ID": source_id,
        "SOURCE_TYPE": source_type,
        "SOURCE_LOCATION": (
            "." if source_type == "repository" else "replace-with-supplied-source"
        ),
    }

    ensure_directories(
        workspace,
        [
            mental_root / "concepts",
            mental_root / "model",
            mental_root / "scenarios",
            mental_root / "conflicts",
            private_root / "sessions",
        ],
    )
    if mode in {"repository", "hybrid"}:
        ensure_directories(
            workspace,
            [
                mental_root / "contracts",
                mental_root / "decisions",
                mental_root / "changes",
            ],
        )
    if mode in {"learning", "hybrid"}:
        ensure_directories(
            workspace,
            [
                mental_root / "learning",
                mental_root / "misconceptions",
                mental_root / "exercises",
            ],
        )

    created: list[Path] = []
    skipped: list[Path] = []
    shared = {
        mental_root / "index.md": "index.md",
        mental_root / "model" / "map.md": "map.md",
        mental_root / "sources.md": "sources.md",
        mental_root / "glossary.md": "glossary.md",
    }
    if mode in {"learning", "hybrid"}:
        shared[mental_root / "learning" / "path.md"] = "learning-path.md"
    for path, template in shared.items():
        write_new(workspace, path, render_template(template, values), created, skipped)

    write_new(
        workspace, private_root / ".gitignore", "*\n!.gitignore\n", created, skipped
    )
    write_new(
        workspace,
        private_root / "profile.md",
        render_template("private-profile.md", values),
        created,
        skipped,
    )
    write_new(
        workspace,
        private_root / "mastery.json",
        render_template("private-mastery.json", values),
        created,
        skipped,
    )
    return created, skipped


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create mental's draft workspace artifacts"
    )
    parser.add_argument("workspace", nargs="?", default=".")
    parser.add_argument(
        "--mode", choices=("repository", "learning", "hybrid"), default="hybrid"
    )
    parser.add_argument("--language", default="en")
    parser.add_argument(
        "--date", default=dt.datetime.now().astimezone().date().isoformat()
    )
    args = parser.parse_args()

    try:
        created, skipped = scaffold(
            Path(args.workspace), args.mode, args.language, args.date
        )
    except (OSError, ScaffoldError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Created {len(created)} file(s); skipped {len(skipped)} existing file(s).")
    for path in created:
        print(f"created: {path}")
    for path in skipped:
        print(f"kept: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
