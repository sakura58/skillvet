"""Minimal, dependency-free YAML frontmatter reader for SKILL.md files.

Only the subset of YAML that appears in Agent Skills frontmatter is supported:
plain scalars, single/double quoted scalars, literal (``|``) and folded (``>``)
block scalars, plus comments. Anything richer raises ``FrontmatterError`` so the
linter can report a real problem instead of silently guessing.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

_KEY_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_FENCE = "---"

Scalar = str


class FrontmatterError(ValueError):
    """Raised when the frontmatter block cannot be understood."""

    def __init__(self, message: str, line: Optional[int] = None) -> None:
        super().__init__(message)
        self.line = line


def split(text: str) -> Tuple[Optional[Dict[str, Scalar]], str, int]:
    """Split a document into ``(metadata, body, body_start_line)``.

    ``metadata`` is ``None`` when the file has no frontmatter block. In that
    case the whole document is returned as the body and the body starts at
    line 1. ``body_start_line`` is 1-based.
    """

    if text.startswith("\ufeff"):
        text = text[1:]

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != _FENCE:
        return None, text, 1

    closing = None
    for index in range(1, len(lines)):
        if lines[index].strip() == _FENCE:
            closing = index
            break

    if closing is None:
        raise FrontmatterError(
            "frontmatter opened with '---' but never closed", line=1
        )

    raw = "".join(lines[1:closing])
    body = "".join(lines[closing + 1 :])
    metadata = _parse_mapping(raw, start_line=2)
    return metadata, body, closing + 2


def _parse_mapping(raw: str, start_line: int) -> Dict[str, Scalar]:
    result: Dict[str, Scalar] = {}
    lines = raw.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index]
        number = start_line + index

        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue

        stripped = line.lstrip(" \t")
        if len(stripped) != len(line):
            raise FrontmatterError(
                "unexpected indentation (block scalars must follow a key)", line=number
            )

        if ":" not in line:
            raise FrontmatterError("expected 'key: value'", line=number)

        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()

        if not key or not _KEY_RE.match(key):
            raise FrontmatterError("invalid key %r" % key, line=number)
        if key in result:
            raise FrontmatterError("duplicate key %r" % key, line=number)

        if value[:1] in ("|", ">"):
            index, value = _read_block(lines, index + 1, value[0], value[1:2])
            result[key] = value
            continue

        result[key] = _read_scalar(value)
        index += 1

    return result


def _read_block(
    lines: List[str], start: int, style: str, chomp: str
) -> Tuple[int, str]:
    """Consume an indented block. Returns ``(next_index, value)``."""

    index = start
    block: List[str] = []

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            block.append("")
            index += 1
            continue
        indented = line.lstrip(" \t")
        if len(indented) == len(line):
            break
        block.append(line)
        index += 1

    while block and not block[-1].strip():
        block.pop()

    if block:
        indent = min(
            len(line) - len(line.lstrip(" \t")) for line in block if line.strip()
        )
        block = [line[indent:] if line.strip() else "" for line in block]

    if style == "|":
        value = "\n".join(block)
    else:
        pieces: List[str] = []
        for line in block:
            if not line:
                pieces.append("\n")
            else:
                if pieces and not pieces[-1].endswith("\n"):
                    pieces.append(" ")
                pieces.append(line)
        value = "".join(pieces)

    if chomp != "+":
        value = value.rstrip("\n")
    return index, value


def _read_scalar(value: str) -> Scalar:
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return _unquote_double(value[1:-1])
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def _unquote_double(value: str) -> str:
    escapes = {
        "n": "\n",
        "t": "\t",
        "r": "\r",
        '"': '"',
        "\\": "\\",
        "/": "/",
        "0": "\0",
    }
    out: List[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\" and index + 1 < len(value):
            out.append(escapes.get(value[index + 1], value[index + 1]))
            index += 2
            continue
        out.append(char)
        index += 1
    return "".join(out)
