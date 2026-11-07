"""Rendering findings for humans, JSON consumers and GitHub Actions."""

from __future__ import annotations

import json
import os
from typing import Dict, List, Sequence

from . import __version__
from .rules import SEVERITY_ORDER, SkillReport

_COLORS = {
    "error": "\033[31m",
    "warning": "\033[33m",
    "info": "\033[36m",
    "ok": "\033[32m",
    "dim": "\033[2m",
    "reset": "\033[0m",
}


def display_path(path, root=None) -> str:
    """Path shown to the user: short, forward-slashed, stable across platforms."""

    try:
        if root is not None:
            value = os.path.relpath(str(path), str(root))
        else:
            value = os.path.relpath(str(path))
    except ValueError:
        value = str(path)
    return value.replace("\\", "/")


def counts(reports: Sequence[SkillReport]) -> Dict[str, int]:
    summary = {"skills": len(reports), "errors": 0, "warnings": 0, "info": 0}
    for report in reports:
        for finding in report.findings:
            if finding.severity == "error":
                summary["errors"] += 1
            elif finding.severity == "warning":
                summary["warnings"] += 1
            else:
                summary["info"] += 1
    return summary


def render_text(
    reports: Sequence[SkillReport], root, color: bool = False
) -> str:
    paint = _painter(color)
    summary = counts(reports)
    lines: List[str] = [
        "skillvet %s - %d skill%s checked"
        % (__version__, summary["skills"], "" if summary["skills"] == 1 else "s"),
        "",
    ]

    ordered = sorted(reports, key=lambda report: display_path(report.path, root))
    for report in ordered:
        path = display_path(report.path, root)
        if not report.findings:
            lines.append("%s  %s" % (path, paint("ok", "ok")))
            continue

        lines.append(path)
        for finding in sorted(report.findings, key=lambda item: item.sort_key()):
            message = finding.message
            if finding.line:
                message = "line %d: %s" % (finding.line, message)
            lines.append(
                "  %s  %-7s  %s"
                % (
                    paint(finding.severity, "%-7s" % finding.severity),
                    finding.code,
                    message,
                )
            )
        lines.append("")

    if lines[-1] == "":
        lines.pop()

    if summary["errors"] or summary["warnings"] or summary["info"]:
        lines.extend(
            [
                "",
                "%d error%s, %d warning%s, %d info"
                % (
                    summary["errors"],
                    "" if summary["errors"] == 1 else "s",
                    summary["warnings"],
                    "" if summary["warnings"] == 1 else "s",
                    summary["info"],
                ),
            ]
        )

    return "\n".join(lines)


def render_json(reports: Sequence[SkillReport], root) -> str:
    payload = {
        "tool": "skillvet",
        "version": __version__,
        "summary": counts(reports),
        "skills": [
            {
                "path": display_path(report.path, root),
                "name": report.skill.name if report.skill else None,
                "findings": [
                    {
                        "severity": finding.severity,
                        "code": finding.code,
                        "message": finding.message,
                        "file": display_path(finding.file, root),
                        "line": finding.line,
                    }
                    for finding in sorted(
                        report.findings, key=lambda item: item.sort_key()
                    )
                ],
            }
            for report in sorted(
                reports, key=lambda report: display_path(report.path, root)
            )
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def render_github(reports: Sequence[SkillReport], root) -> str:
    lines: List[str] = []
    for report in sorted(reports, key=lambda report: display_path(report.path, root)):
        for finding in sorted(report.findings, key=lambda item: item.sort_key()):
            properties = ["file=%s" % _escape_property(display_path(finding.file, root))]
            if finding.line:
                properties.append("line=%d" % finding.line)
                properties.append("endLine=%d" % finding.line)
            properties.append("title=%s" % finding.code)
            lines.append(
                "::%s %s::%s"
                % (finding.severity, ",".join(properties), _escape_message(finding.message))
            )

    summary = counts(reports)
    lines.append(
        "skillvet: %d error(s), %d warning(s), %d info in %d skill(s)"
        % (
            summary["errors"],
            summary["warnings"],
            summary["info"],
            summary["skills"],
        )
    )
    return "\n".join(lines)


def threshold_failure(
    reports: Sequence[SkillReport], fail_on: str
) -> bool:
    if fail_on == "none":
        return False
    limit = SEVERITY_ORDER[fail_on]
    for report in reports:
        for finding in report.findings:
            if SEVERITY_ORDER[finding.severity] <= limit:
                return True
    return False


def filter_findings(reports: Sequence[SkillReport], minimum: str) -> List[SkillReport]:
    # Mutating the dataclass is fine here: the reports are freshly built per run.
    limit = SEVERITY_ORDER[minimum]
    for report in reports:
        report.findings = [
            finding
            for finding in report.findings
            if SEVERITY_ORDER[finding.severity] <= limit
        ]
    return list(reports)


def _painter(enabled: bool):
    def paint(role: str, text: str) -> str:
        if not enabled:
            return text
        return "%s%s%s" % (_COLORS.get(role, ""), text, _COLORS["reset"])

    return paint


def _escape_message(value: str) -> str:
    return (
        value.replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
    )


def _escape_property(value: str) -> str:
    return (
        value.replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
        .replace(":", "%3A")
        .replace(",", "%2C")
    )
