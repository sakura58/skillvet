---
name: release-notes
description: Use this skill when the user asks to draft release notes, a changelog, or a summary of changes between two git refs. Produces grouped, user-facing notes from commit history.
---

# Release Notes

Turn a range of commits into notes that a user can actually read.

## Workflow

1. Confirm the two refs to compare, for example `v1.2.0..HEAD`.
2. Run `scripts/collect_commits.py` to print the raw commit list.
3. Group commits into Features, Fixes, Performance, Documentation, and Internal.
4. Drop merge commits, dependency bumps, and pure refactors unless they change behaviour.
5. Write for users, not for contributors. Lead with the impact, not the implementation.

## Output

Return Markdown with one `##` heading per non-empty group.
Keep every bullet under 20 words and link an issue only when the commit references one.

## Rules

- Never invent a change that is not in the commit range.
- Keep the tone factual. No marketing language.
- If the range contains no user-visible change, say so in one sentence.
