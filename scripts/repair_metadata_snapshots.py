#!/usr/bin/env python3
"""Repair legacy run_metadata config snapshots with exists=false entries."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

CONFIG_DIRECTORIES = [
    Path("configs/trainer_configs"),
    Path("configs/env_configs"),
    Path("configs/reward_configs"),
    Path("configs/curriculum_configs"),
    Path("configs/experiment_manifests"),
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def candidate_sources(root: Path, source_value: str) -> list[Path]:
    source_path = Path(source_value)
    candidates: list[Path] = []
    if source_path.is_absolute():
        candidates.append(source_path)
    else:
        candidates.append(root / source_path)
    basename = source_path.name
    if basename:
        for base in CONFIG_DIRECTORIES:
            candidates.append(root / base / basename)
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def repair_metadata_file(root: Path, metadata_path: Path) -> tuple[int, int]:
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    snapshots = data.get("config_snapshots")
    if not isinstance(snapshots, list):
        return 0, 0

    fixed = 0
    unresolved = 0
    snapshot_root = metadata_path.parent / "config_snapshots"
    snapshot_root.mkdir(parents=True, exist_ok=True)

    for entry in snapshots:
        if not isinstance(entry, dict):
            continue
        if bool(entry.get("exists", False)):
            continue
        source_value = str(entry.get("source") or "").strip()
        if not source_value:
            unresolved += 1
            continue
        source_file = next((path for path in candidate_sources(root, source_value) if path.exists() and path.is_file()), None)
        if source_file is None:
            unresolved += 1
            continue
        try:
            relative_source = source_file.resolve().relative_to(root.resolve())
        except ValueError:
            relative_source = Path(source_file.name)
        destination = snapshot_root / relative_source
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, destination)
        entry["exists"] = True
        entry["source"] = str(relative_source)
        entry["snapshot"] = str(destination.relative_to(root))
        entry["sha256"] = sha256_file(destination)
        fixed += 1

    if fixed:
        data["config_snapshots"] = snapshots
        metadata_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return fixed, unresolved


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    results_root = root / args.results_dir
    if not results_root.exists():
        print(f"Results directory does not exist: {results_root}")
        return 0

    metadata_files = sorted(results_root.glob("**/metadata/run_metadata.json"))
    total_fixed = 0
    total_unresolved = 0
    files_touched = 0
    for path in metadata_files:
        fixed, unresolved = repair_metadata_file(root, path)
        if fixed:
            files_touched += 1
        total_fixed += fixed
        total_unresolved += unresolved

    print(f"Metadata files scanned: {len(metadata_files)}")
    print(f"Metadata files updated: {files_touched}")
    print(f"Snapshot entries repaired: {total_fixed}")
    print(f"Snapshot entries unresolved: {total_unresolved}")
    if args.strict and total_unresolved > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
