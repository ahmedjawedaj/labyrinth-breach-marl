#!/usr/bin/env python3
"""Detect evicted (dataless) files that stat as present but cannot be read.

macOS with iCloud Drive "Optimize Mac Storage" evicts file contents while
leaving the directory entry and st_size intact. Such a file reports a real size
but st_blocks == 0, and any read fails. Under a remote mount the failure surfaces
as OSError errno 35, "Resource deadlock avoided".

This matters because a tournament cell that hits an evicted checkpoint dies with
an opaque I/O error partway through a long run. Check first, fail fast.

Re-materialise on the Mac with either of:
    find results -name '*.pt' -print0 | xargs -0 -n1 -P4 brctl download
    find results -name '*.pt' -exec cat {} + > /dev/null
or disable System Settings > Apple Account > iCloud > Optimise Mac Storage.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def is_dataless(path: Path) -> bool:
    """True when the file has content on paper but no blocks allocated locally."""
    try:
        st = path.stat()
    except OSError:
        return False
    return st.st_size > 0 and getattr(st, "st_blocks", 1) == 0


def verify_readable(path: Path, probe_bytes: int = 4096) -> tuple[bool, str]:
    """Confirm the first bytes actually read. Catches evictions stat cannot see."""
    try:
        with path.open("rb") as handle:
            handle.read(probe_bytes)
        return True, ""
    except OSError as exc:
        return False, f"{type(exc).__name__}: {exc}"


def check(paths: list[Path], probe: bool) -> dict[str, list[str]]:
    evicted, unreadable, ok = [], [], []
    for path in paths:
        if is_dataless(path):
            evicted.append(str(path))
            continue
        if probe:
            readable, reason = verify_readable(path)
            if not readable:
                unreadable.append(f"{path}  [{reason}]")
                continue
        ok.append(str(path))
    return {"evicted": evicted, "unreadable": unreadable, "ok": ok}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default="results")
    parser.add_argument("--glob", action="append", default=None,
                        help="Repeatable. Defaults to checkpoint and policy files.")
    parser.add_argument("--probe", action="store_true", help="Also attempt a short read of every file.")
    parser.add_argument("--output")
    args = parser.parse_args()

    patterns = args.glob or ["**/*.pt", "**/*.onnx"]
    root = Path(args.root)
    paths = sorted({p for pattern in patterns for p in root.glob(pattern) if p.is_file()})
    if not paths:
        print(f"No files matched under {root} for {patterns}", file=sys.stderr)
        return 1

    report = check(paths, args.probe)
    total = len(paths)
    bad = len(report["evicted"]) + len(report["unreadable"])

    print(f"Scanned {total} files under {root}")
    print(f"  readable: {len(report['ok'])}")
    print(f"  evicted:  {len(report['evicted'])}")
    if args.probe:
        print(f"  unreadable (probe failed): {len(report['unreadable'])}")

    for label in ("evicted", "unreadable"):
        if report[label]:
            print(f"\n{label.upper()}:")
            for item in report[label][:40]:
                print(f"  {item}")
            if len(report[label]) > 40:
                print(f"  ... and {len(report[label]) - 40} more")

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"\nWrote {out}")

    if bad:
        print(f"\n{bad} of {total} files cannot be read. Re-materialise them before running the tournament.")
        print("  find results -name '*.pt' -exec cat {} + > /dev/null")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
