#!/usr/bin/env python3
"""Block accidental commits of large artifacts outside the artifact policy."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


MAX_SIZE_BYTES = 25 * 1024 * 1024
LFS_EXTENSIONS = {
    ".ckpt",
    ".pth",
    ".h5",
    ".zip",
    ".onnx",
    ".pt",
    ".mp4",
    ".mov",
    ".avi",
}


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def staged_files() -> list[Path]:
    result = run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"])
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        return []
    names = [name for name in result.stdout.split("\0") if name]
    return [Path(name) for name in names]


def files_to_check() -> list[Path]:
    if len(sys.argv) > 1:
        return [Path(arg) for arg in sys.argv[1:]]
    return staged_files()


def lfs_filter_for(path: Path) -> str | None:
    result = run_git(["check-attr", "filter", "--", str(path)])
    if result.returncode != 0:
        return None
    # Output format: path: filter: lfs
    parts = result.stdout.strip().split(": ")
    return parts[-1] if parts else None


def main() -> int:
    failures: list[str] = []

    for path in files_to_check():
        if not path.exists() or not path.is_file():
            continue

        size = path.stat().st_size
        suffix = path.suffix.lower()
        filter_name = lfs_filter_for(path)

        if suffix in LFS_EXTENSIONS and filter_name != "lfs":
            failures.append(
                f"{path} has artifact extension {suffix} but is not tracked by Git LFS."
            )

        if size > MAX_SIZE_BYTES and filter_name != "lfs":
            size_mb = size / (1024 * 1024)
            failures.append(
                f"{path} is {size_mb:.1f} MB and is not tracked by Git LFS."
            )

    if failures:
        print("Large artifact policy violation:")
        for failure in failures:
            print(f"- {failure}")
        print()
        print("Use Git LFS for curated model artifacts, or move raw outputs to external storage.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
