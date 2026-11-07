"""The checks skillvet runs against a SKILL.md file."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .frontmatter import FrontmatterError, split

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}

#: Every rule knows its default severity. Findings inherit it, so users can
#: reason about ``--fail-on`` without reading the implementation.
RULES: Dict[str, Tuple[str, str]] = {
    "FM001": ("error", "SKILL.md has no YAML frontmatter"),
    "FM002": ("error", "frontmatter cannot be parsed"),
    "NAME001": ("error", "missing `name` field"),
    "NAME002": ("error", "missing `description` field"),
    "NAME003": ("error", "`name` is not a valid skill identifier"),
    "NAME005": ("warning", "`name` does not match the directory name"),
    "DESC001": ("error", "`description` is longer than 1024 characters"),
    "DESC002": ("warning", "`description` is too short to route reliably"),
    "DESC003": ("info", "`description` never says when to use the skill"),
    "SIZE001": ("warning", "SKILL.md body is longer than 500 lines"),
    "SIZE002": ("warning", "SKILL.md body is above the ~5k token budget"),
    "LINK001": ("warning", "relative link points to a missing file"),
    "REF001": ("warning", "bundled file mentioned in the body is missing"),
    "SEC001": ("error", "pipes a remote script into a shell"),
    "SEC002": ("error", "reads credential or secret files"),
    "SEC003": ("error", "destructive recursive delete"),
    "SEC004": ("error", "prompt-injection style instruction"),
    "SEC005": ("warning", "uploads local data to a remote endpoint"),
    "SEC006": ("error", "hardcoded credential"),
    "DUP001": ("error", "duplicate skill name"),
}

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MIN_DESCRIPTION_LENGTH = 40
MAX_BODY_LINES = 500
MAX_BODY_TOKENS = 5000

_SECURITY_RULES: Sequence[Tuple[str, "re.Pattern[str]", str]] = (
    (
        "SEC001",
        re.compile(r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:ba|z|k)?sh\b"),
        "piping a remote script straight into a shell lets the remote side run "
        "arbitrary code with the agent's privileges",
    ),
    (
        "SEC002",
        re.compile(
            r"(?:~?/\.ssh/|\.ssh/|\.aws/credentials|(?:^|[\s`'\"])\.env\b"
            r"|id_rsa|id_ed25519|\.netrc|\.npmrc|\.pypirc|\.git-credentials)"
        ),
        "skill instructions should never read private keys or credential files",
    ),
    (
        "SEC003",
        re.compile(
            r"\brm\s+-[A-Za-z]*[rR][A-Za-z]*[fF]?[A-Za-z]*\s+"
            r"(?:/|~|\$HOME|\*|\.{1,2})(?=$|[\s`'\".,;)])"
        ),
        "recursive deletion of a broad path can destroy the user's machine",
    ),
    (
        "SEC004",
        re.compile(
            r"(?:ignore\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above)\s+"
            r"(?:instructions|rules|prompts)"
            r"|disregard\s+(?:the\s+|all\s+)?(?:previous|system)"
            r"|you\s+are\s+now\s+(?:dan|in\s+developer\s+mode)"
            r"|reveal\s+(?:your|the)\s+system\s+prompt)",
            re.IGNORECASE,
        ),
        "instructions that try to override the agent's system prompt are a "
        "classic prompt-injection payload",
    ),
    (
        "SEC005",
        re.compile(r"\b(?:curl|wget)\b[^\n]*(?:\s-d\s|\s--data|\s--upload-file|\s-F\s)"),
        "sending local data to an external endpoint can exfiltrate the user's files",
    ),
    (
        "SEC006",
        re.compile(
            r"(?:sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}"
            r"|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,})"
        ),
        "hardcoded credentials in a public skill will be scraped",
    ),
)

_IGNORE_RE = re.compile(
    r"skillvet-ignore\s+([A-Z]{3}[0-9]{3}(?:\s*,\s*[A-Z]{3}[0-9]{3})*)"
)
_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_CODE_REF_RE = re.compile(r"`([^`\n]+)`")
_BUNDLED_PREFIXES = ("scripts/", "references/", "assets/", "templates/")


@dataclass
class Finding:
    code: str
    message: str
    file: Path
    line: Optional[int] = None

    @property
    def severity(self) -> str:
        return RULES[self.code][0]

    def sort_key(self) -> Tuple[str, int, int, str]:
        return (
            str(self.file),
            self.line or 0,
            SEVERITY_ORDER[self.severity],
            self.code,
        )


@dataclass
class Skill:
    path: Path
    meta: Dict[str, str]
    body: str
    body_start_line: int

    @property
    def directory_name(self) -> str:
        return self.path.parent.name

    @property
    def name(self) -> Optional[str]:
        value = self.meta.get("name")
        return value if isinstance(value, str) and value else None


@dataclass
class SkillReport:
    path: Path
    skill: Optional[Skill] = None
    findings: List[Finding] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "error")

    @property
    def ok(self) -> bool:
        return not self.findings


def estimate_tokens(text: str) -> int:
    """Rough token estimate. Deliberately conservative and dependency-free."""

    return (len(text) + 3) // 4


def analyze(files: Sequence[Path]) -> List[SkillReport]:
    reports: List[SkillReport] = []

    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        report = SkillReport(path=path)

        try:
            meta, body, body_start = split(text)
        except FrontmatterError as exc:
            report.findings.append(
                Finding("FM002", str(exc), path, getattr(exc, "line", None))
            )
            reports.append(report)
            continue

        has_frontmatter = meta is not None
        skill = Skill(path=path, meta=meta or {}, body=body, body_start_line=body_start)
        report.skill = skill

        if not has_frontmatter:
            report.findings.append(
                Finding(
                    "FM001",
                    "add a '---' frontmatter block with at least 'name' and "
                    "'description' so agents can discover this skill",
                    path,
                    1,
                )
            )

        report.findings.extend(_check_single(skill, has_frontmatter))
        reports.append(report)

    _check_duplicates(reports)
    return reports


def _check_single(skill: Skill, has_frontmatter: bool) -> List[Finding]:
    findings: List[Finding] = []
    if has_frontmatter:
        findings.extend(_check_fields(skill))
    findings.extend(_check_size(skill))
    findings.extend(_check_links(skill))
    findings.extend(_check_security(skill))
    return findings


def _check_fields(skill: Skill) -> List[Finding]:
    findings: List[Finding] = []
    path = skill.path
    name = skill.meta.get("name")
    description = skill.meta.get("description")

    if name is None or not str(name).strip():
        findings.append(
            Finding("NAME001", "frontmatter needs a 'name' field", path, 2)
        )
    else:
        name = str(name).strip()
        problems = []
        if len(name) > MAX_NAME_LENGTH:
            problems.append("longer than %d characters" % MAX_NAME_LENGTH)
        if not NAME_RE.match(name):
            problems.append("must be lowercase letters, digits and single hyphens")
        if problems:
            findings.append(
                Finding(
                    "NAME003",
                    "name %r is invalid: %s" % (name, ", ".join(problems)),
                    path,
                    2,
                )
            )
        if skill.directory_name and skill.directory_name != name:
            findings.append(
                Finding(
                    "NAME005",
                    "name %r should match its directory %r so hosts can load it "
                    "unambiguously" % (name, skill.directory_name),
                    path,
                    2,
                )
            )

    if description is None or not str(description).strip():
        findings.append(
            Finding(
                "NAME002",
                "frontmatter needs a 'description' field; it is the only text "
                "an agent sees before deciding to load the skill",
                path,
                2,
            )
        )
        return findings

    description = str(description).strip()
    if len(description) > MAX_DESCRIPTION_LENGTH:
        findings.append(
            Finding(
                "DESC001",
                "description is %d characters, over the %d character limit"
                % (len(description), MAX_DESCRIPTION_LENGTH),
                path,
                2,
            )
        )
    elif len(description) < MIN_DESCRIPTION_LENGTH:
        findings.append(
            Finding(
                "DESC002",
                "description is only %d characters; say what the skill does and "
                "when it applies" % len(description),
                path,
                2,
            )
        )

    if not re.search(r"\b(use|when|whenever|trigger|if the user)\b", description,
                     re.IGNORECASE):
        findings.append(
            Finding(
                "DESC003",
                "description does not mention when to use the skill; add a "
                "trigger clause such as 'Use when ...'",
                path,
                2,
            )
        )

    return findings


def _check_size(skill: Skill) -> List[Finding]:
    findings: List[Finding] = []
    lines = len(skill.body.splitlines())
    tokens = estimate_tokens(skill.body)

    if lines > MAX_BODY_LINES:
        findings.append(
            Finding(
                "SIZE001",
                "body has %d lines (keep SKILL.md under %d and move detail into "
                "references/)" % (lines, MAX_BODY_LINES),
                skill.path,
                skill.body_start_line,
            )
        )
    if tokens > MAX_BODY_TOKENS:
        findings.append(
            Finding(
                "SIZE002",
                "body is roughly %d tokens (budget is about %d); split it so the "
                "skill does not flood the context window" % (tokens, MAX_BODY_TOKENS),
                skill.path,
                skill.body_start_line,
            )
        )
    return findings


def _check_links(skill: Skill) -> List[Finding]:
    findings: List[Finding] = []
    base = skill.path.parent

    for match in _LINK_RE.finditer(skill.body):
        target = match.group(1).strip()
        if target.startswith(("http://", "https://", "mailto:", "tel:", "#")):
            continue
        target = target.split("#", 1)[0]
        if not target:
            continue
        if not (base / target).exists():
            findings.append(
                Finding(
                    "LINK001",
                    "link target %r does not exist" % match.group(1),
                    skill.path,
                    _line_of(skill, match.start()),
                )
            )

    seen = set()
    for match in _CODE_REF_RE.finditer(skill.body):
        token = match.group(1).strip()
        if not token.startswith(_BUNDLED_PREFIXES):
            continue
        if not (base / token).exists() and token not in seen:
            seen.add(token)
            findings.append(
                Finding(
                    "REF001",
                    "body references %r but the file is not shipped with the skill"
                    % token,
                    skill.path,
                    _line_of(skill, match.start()),
                )
            )

    return findings


def _check_security(skill: Skill) -> List[Finding]:
    findings: List[Finding] = []

    for offset, line in enumerate(skill.body.splitlines()):
        ignored = set()
        ignore_match = _IGNORE_RE.search(line)
        if ignore_match:
            ignored = {
                code.strip() for code in ignore_match.group(1).split(",")
            }

        for code, pattern, why in _SECURITY_RULES:
            if code in ignored:
                continue
            if pattern.search(line):
                findings.append(
                    Finding(
                        code,
                        "%s -- %s" % (why, _excerpt(line)),
                        skill.path,
                        skill.body_start_line + offset,
                    )
                )

    return findings


def _check_duplicates(reports: List[SkillReport]) -> None:
    by_name: Dict[str, List[SkillReport]] = {}
    for report in reports:
        if report.skill and report.skill.name:
            by_name.setdefault(report.skill.name, []).append(report)

    for name, group in by_name.items():
        if len(group) < 2:
            continue
        for report in group:
            others = ", ".join(
                str(other.path) for other in group if other is not report
            )
            report.findings.append(
                Finding(
                    "DUP001",
                    "skill name %r is also used by %s; loading becomes ambiguous"
                    % (name, others),
                    report.path,
                )
            )


def _line_of(skill: Skill, offset: int) -> int:
    return skill.body_start_line + skill.body.count("\n", 0, offset)


def _excerpt(line: str, width: int = 72) -> str:
    text = " ".join(line.split())
    if len(text) > width:
        text = text[: width - 3] + "..."
    return "found: %r" % text


def iter_findings(reports: Iterable[SkillReport]) -> Iterable[Finding]:
    for report in reports:
        for finding in report.findings:
            yield finding
