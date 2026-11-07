#!/usr/bin/env python3
"""Print the commits between two refs, one per line.

Usage: python scripts/collect_commits.py v1.2.0..HEAD
"""

import subprocess
import sys


def main() -> int:
    revision_range = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    result = subprocess.run(
        ["git", "log", "--no-merges", "--pretty=format:%h %s", revision_range],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return result.returncode
    print(result.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
