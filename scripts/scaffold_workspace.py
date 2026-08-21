#!/usr/bin/env python3
"""Internal helper used by mental:build to create a non-destructive workspace skeleton."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Iterable


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "assets" / "templates"


def render_template(name: str, values: dict[str, str]) -> str:
    content = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
    for key, value in values.items():
        content = content.replace("{{" + key + "}}", value)
    return content


def write_new(path: Path, content: str, created: list[Path], skipped: list[Path]) -> None:
    if path.exists():
        skipped.append(path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    created.append(path)


def ensure_directories(paths: Iterable[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def scaffold(workspace: Path, mode: str, language: str, today: str) -> tuple[list[Path], list[Path]]:
    workspace = workspace.resolve()
    mental_root = workspace / "mental"
    private_root = workspace / ".mental"
    source_id = "source-workspace" if mode in {"repository", "hybrid"} else "source-material"
    source_type = "repository" if mode in {"repository", "hybrid"} else "provided-material"
    values = {
        "TODAY": today,
        "MODE": mode,
        "LANGUAGE": language,
        "SOURCE_ID": source_id,
        "SOURCE_TYPE": source_type,
        "SOURCE_LOCATION": "." if source_type == "repository" else "replace-with-supplied-source",
    }

    ensure_directories(
        [
            mental_root / "concepts",
            mental_root / "model",
            mental_root / "scenarios",
            private_root / "sessions",
        ]
    )
    if mode in {"repository", "hybrid"}:
        ensure_directories(
            [mental_root / "contracts", mental_root / "decisions", mental_root / "changes"]
        )
    if mode in {"learning", "hybrid"}:
        ensure_directories(
            [mental_root / "learning", mental_root / "misconceptions", mental_root / "exercises"]
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
        write_new(path, render_template(template, values), created, skipped)

    write_new(private_root / ".gitignore", "*\n!.gitignore\n", created, skipped)
    write_new(
        private_root / "profile.md",
        render_template("private-profile.md", values),
        created,
        skipped,
    )
    write_new(
        private_root / "mastery.json",
        render_template("private-mastery.json", values),
        created,
        skipped,
    )
    return created, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="Create mental's draft workspace artifacts")
    parser.add_argument("workspace", nargs="?", default=".")
    parser.add_argument(
        "--mode", choices=("repository", "learning", "hybrid"), default="hybrid"
    )
    parser.add_argument("--language", default="en")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    args = parser.parse_args()

    created, skipped = scaffold(Path(args.workspace), args.mode, args.language, args.date)
    print(f"Created {len(created)} file(s); skipped {len(skipped)} existing file(s).")
    for path in created:
        print(f"created: {path}")
    for path in skipped:
        print(f"kept: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
