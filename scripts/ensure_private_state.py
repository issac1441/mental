"""Create mental's private learner state after explicit session consent.

This helper is internal to the learning skills. It never creates shared
``mental/`` artifacts and never overwrites an existing private file.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "assets" / "templates"
LANGUAGE_RE = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")
PRIVATE_IGNORE = "*\n!.gitignore\n"


class PrivateStateError(ValueError):
    """Raised when private state cannot be created without crossing a boundary."""


def validate_inputs(language: str, today: str) -> None:
    if not LANGUAGE_RE.fullmatch(language):
        raise PrivateStateError(
            "language must be a BCP-47-style tag such as 'en' or 'zh-TW'"
        )
    try:
        parsed_date = dt.date.fromisoformat(today)
    except ValueError as exc:
        raise PrivateStateError("date must use ISO YYYY-MM-DD format") from exc
    if parsed_date.isoformat() != today:
        raise PrivateStateError("date must use ISO YYYY-MM-DD format")


def require_regular_directory(path: Path, label: str) -> None:
    if path.is_symlink():
        raise PrivateStateError(f"refusing to follow {label} symlink: {path}")
    if path.exists() and not path.is_dir():
        raise PrivateStateError(f"expected {label} directory: {path}")


def render_template(name: str, language: str, today: str) -> str:
    try:
        content = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PrivateStateError(f"cannot read private template {name}: {exc}") from exc
    return content.replace("{{LANGUAGE}}", language).replace("{{TODAY}}", today)


def write_exclusive(path: Path, content: str, created: list[Path]) -> None:
    if path.is_symlink():
        raise PrivateStateError(f"refusing to follow private-state symlink: {path}")
    if path.exists():
        if not path.is_file():
            raise PrivateStateError(f"expected a regular private file: {path}")
        return
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
    except FileExistsError:
        if path.is_symlink() or not path.is_file():
            raise PrivateStateError(f"unsafe private path appeared: {path}")
        return
    created.append(path)


def ensure_private_state(
    workspace: Path, language: str, today: str
) -> tuple[list[Path], list[Path]]:
    validate_inputs(language, today)
    if workspace.is_symlink():
        raise PrivateStateError(f"workspace must not be a symlink: {workspace}")
    workspace = workspace.resolve(strict=True)
    require_regular_directory(workspace, "workspace")

    private_root = workspace / ".mental"
    sessions = private_root / "sessions"
    require_regular_directory(private_root, "private-state")
    private_root.mkdir(mode=0o700, exist_ok=True)

    ignore_path = private_root / ".gitignore"
    if ignore_path.is_symlink():
        raise PrivateStateError(f"refusing to follow private ignore symlink: {ignore_path}")
    if ignore_path.exists():
        if not ignore_path.is_file():
            raise PrivateStateError(f"expected a regular private ignore file: {ignore_path}")
        try:
            current_ignore = ignore_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise PrivateStateError(f"cannot verify private ignore rules: {exc}") from exc
        if current_ignore != PRIVATE_IGNORE:
            raise PrivateStateError(
                ".mental/.gitignore must contain exactly '*\\n!.gitignore\\n' before private writes"
            )

    created: list[Path] = []
    write_exclusive(ignore_path, PRIVATE_IGNORE, created)
    require_regular_directory(sessions, "sessions")
    sessions.mkdir(mode=0o700, exist_ok=True)
    write_exclusive(
        private_root / "profile.md",
        render_template("private-profile.md", language, today),
        created,
    )
    write_exclusive(
        private_root / "mastery.json",
        render_template("private-mastery.json", language, today),
        created,
    )
    kept = [
        path
        for path in (
            ignore_path,
            private_root / "profile.md",
            private_root / "mastery.json",
        )
        if path not in created
    ]
    return created, kept


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create consent-gated private mental learner state"
    )
    parser.add_argument("workspace", nargs="?", default=".")
    parser.add_argument("--language", default="en")
    parser.add_argument(
        "--date", default=dt.datetime.now().astimezone().date().isoformat()
    )
    args = parser.parse_args()
    try:
        created, kept = ensure_private_state(
            Path(args.workspace), args.language, args.date
        )
    except (OSError, PrivateStateError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"Created {len(created)} private file(s); kept {len(kept)} existing file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
