"""Command line entry point."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from . import __version__
from .report import (
    filter_findings,
    render_github,
    render_json,
    render_text,
    threshold_failure,
)
from .rules import RULES, analyze

SKIP_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".tox",
    ".venv",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
    "__pycache__",
    "build",
    "dist",
    "site-packages",
    "venv",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skillvet",
        description="Lint Agent Skills before an agent loads them.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="files, skill directories, or trees to scan (default: .)",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json", "github"),
        default="text",
        help="output format (default: text)",
    )
    parser.add_argument(
        "--fail-on",
        choices=("error", "warning", "none"),
        default="error",
        help="lowest severity that produces a non-zero exit code (default: error)",
    )
    parser.add_argument(
        "--min-severity",
        choices=("error", "warning", "info"),
        default="info",
        help="hide findings below this severity (default: info)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="disable ANSI colors in text output",
    )
    parser.add_argument(
        "--list-rules",
        action="store_true",
        help="print every rule and exit",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="skillvet %s" % __version__,
    )
    return parser


def find_skill_files(root: Path) -> List[Path]:
    root = Path(root)
    if root.is_file():
        return [root]
    if not root.is_dir():
        raise FileNotFoundError(str(root))

    found: List[Path] = []
    for path in root.rglob("SKILL.md"):
        if path.is_file() and not _in_skipped_directory(path, root):
            found.append(path)
    return sorted(found, key=str)


def _in_skipped_directory(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        parts = path.parts
    return any(part in SKIP_DIRECTORIES for part in parts[:-1])


def _use_color(disabled: bool) -> bool:
    if disabled or os.environ.get("NO_COLOR"):
        return False
    stream = sys.stdout
    return bool(getattr(stream, "isatty", lambda: False)())


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_rules:
        width = max(len(code) for code in RULES)
        for code in sorted(RULES):
            severity, description = RULES[code]
            print("%-*s  %-7s  %s" % (width, code, severity, description))
        return 0

    roots = [Path(item) for item in args.paths]
    files: List[Path] = []
    seen = set()
    for root in roots:
        try:
            discovered = find_skill_files(root)
        except FileNotFoundError:
            print("skillvet: %s: no such file or directory" % root, file=sys.stderr)
            return 2
        for path in discovered:
            key = str(path.resolve())
            if key not in seen:
                seen.add(key)
                files.append(path)

    if not files:
        print(
            "skillvet: no SKILL.md files found in %s"
            % ", ".join(str(root) for root in roots),
            file=sys.stderr,
        )
        return 0

    try:
        reports = analyze(files)
    except OSError as exc:
        print("skillvet: %s" % exc, file=sys.stderr)
        return 2

    # Decide the exit code before filtering: hiding a warning from the output
    # must not silently downgrade a failing run to a pass.
    failed = threshold_failure(reports, args.fail_on)
    reports = filter_findings(reports, args.min_severity)
    root = Path.cwd()

    if args.format == "json":
        print(render_json(reports, root))
    elif args.format == "github":
        print(render_github(reports, root))
    else:
        print(render_text(reports, root, color=_use_color(args.no_color)))

    return 1 if failed else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
