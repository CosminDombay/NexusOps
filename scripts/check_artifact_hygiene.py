from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BLOCKED_PATTERNS = (
    "frontend/dist/",
    "frontend/node_modules/",
    ".pytest_cache/",
    "__pycache__/",
    ".mypy_cache/",
    ".ruff_cache/",
)
BLOCKED_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".tsbuildinfo",
    ".log",
)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    offenders = []
    for raw_path in result.stdout.splitlines():
        normalized = raw_path.replace("\\", "/")
        if any(normalized.startswith(pattern) for pattern in BLOCKED_PATTERNS):
            offenders.append(raw_path)
        elif normalized.endswith(BLOCKED_SUFFIXES):
            offenders.append(raw_path)

    if offenders:
        print("Generated or local artifact files are tracked:")
        for offender in offenders:
            print(f" - {offender}")
        return 1

    print("Artifact hygiene check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
