#!/usr/bin/env python3
"""Save reproducibility metadata and config snapshots for a training run."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - repository env includes PyYAML.
    yaml = None


CONFIG_FIELDS = [
    "trainer_config",
    "env_config",
    "reward_config",
    "curriculum_config",
    "rule_config",
]

CONFIG_DIRECTORIES = {
    "trainer_config": Path("configs/trainer_configs"),
    "env_config": Path("configs/env_configs"),
    "reward_config": Path("configs/reward_configs"),
    "curriculum_config": Path("configs/curriculum_configs"),
    "rule_config": Path("configs/env_configs"),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    if yaml is None:
        raise RuntimeError("PyYAML is required to parse run manifests.")

    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def run_git(args: list[str], root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unavailable"
    return completed.stdout.strip() or "unavailable"


def git_metadata(root: Path) -> dict[str, Any]:
    status = run_git(["status", "--porcelain"], root)
    dirty_files = [] if status == "unavailable" else status.splitlines()
    return {
        "commit_hash": run_git(["rev-parse", "HEAD"], root),
        "branch": run_git(["branch", "--show-current"], root),
        "dirty": bool(dirty_files),
        "dirty_files": dirty_files,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_path(root: Path, path_value: str | None) -> Path | None:
    if not path_value:
        return None

    path = Path(path_value)
    if path.is_absolute():
        return path
    return root / path


def resolve_config_path(root: Path, key: str, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path

    direct = root / path
    if direct.exists() or "/" in value or "\\" in value:
        return direct

    base_dir = CONFIG_DIRECTORIES.get(key)
    if base_dir is None:
        return direct
    return root / base_dir / path


def unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def copy_config_snapshots(root: Path, snapshot_dir: Path, paths: list[Path]) -> list[dict[str, Any]]:
    snapshot_records: list[dict[str, Any]] = []
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    missing_sources: list[str] = []
    for source in unique_paths(paths):
        if not source.exists():
            missing_sources.append(str(source))
            continue

        try:
            relative_source = source.resolve().relative_to(root.resolve())
        except ValueError:
            relative_source = Path(source.name)

        destination = snapshot_dir / relative_source
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        snapshot_records.append(
            {
                "source": str(relative_source),
                "snapshot": str(destination.relative_to(root)),
                "sha256": sha256_file(destination),
            }
        )

    if missing_sources:
        joined = "\n  ".join(missing_sources)
        raise FileNotFoundError(f"Metadata snapshot incomplete. Missing config files:\n  {joined}")

    return snapshot_records


def resolve_linked_config(root: Path, source: Path, key: str, value: str) -> Path:
    linked = Path(value)
    if linked.is_absolute():
        return linked
    if "/" in value or "\\" in value:
        return root / linked
    base_dir = CONFIG_DIRECTORIES.get(key)
    if base_dir is not None:
        return root / base_dir / linked
    return source.parent / linked


def iter_yaml_config_values(data: Any) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str) and key.endswith("config") and value.endswith((".yaml", ".yml")):
                values.append((key, value))
            else:
                values.extend(iter_yaml_config_values(value))
    elif isinstance(data, list):
        for item in data:
            values.extend(iter_yaml_config_values(item))
    return values


def collect_linked_config_paths(root: Path, initial_paths: list[Path]) -> list[Path]:
    collected = unique_paths(initial_paths)
    seen_resolved = {path.resolve() for path in collected}
    index = 0
    while index < len(collected):
        source = collected[index]
        index += 1
        if not source.exists() or source.suffix not in {".yaml", ".yml"}:
            continue

        try:
            data = load_yaml(source)
        except Exception:
            continue

        for key, value in iter_yaml_config_values(data):
            linked = resolve_linked_config(root, source, key, value)
            linked_resolved = linked.resolve()
            if linked_resolved not in seen_resolved:
                seen_resolved.add(linked_resolved)
                collected.append(linked)

    return collected


def merge_manifest_and_args(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    manifest_data: dict[str, Any] = {}
    manifest_path = resolve_path(root, args.manifest)
    if manifest_path is not None:
        manifest_data = load_yaml(manifest_path)

    metadata: dict[str, Any] = dict(manifest_data)
    for field in [
        "run_id",
        "seed",
        *CONFIG_FIELDS,
        "curriculum_stage",
        "scene",
        "notes",
        "experiment_family",
        "matrix_stage_id",
        "matrix_stage_order",
        "matrix_total_stages",
    ]:
        value = getattr(args, field, None)
        if value is not None:
            metadata[field] = value

    if manifest_path is not None:
        metadata["manifest"] = str(manifest_path.relative_to(root))

    if not metadata.get("run_id"):
        raise ValueError("run_id is required, either via --run-id or manifest.")

    for field in CONFIG_FIELDS:
        resolved = resolve_config_path(root, field, metadata.get(field))
        if resolved is not None:
            try:
                metadata[field] = str(resolved.resolve().relative_to(root.resolve()))
            except ValueError:
                metadata[field] = str(resolved.resolve())

    return metadata


def write_reproduction_command(metadata_dir: Path, command: str | None) -> None:
    if not command:
        return

    script_path = metadata_dir / "reproduce.sh"
    script_path.write_text("#!/usr/bin/env bash\nset -euo pipefail\n\n" + command + "\n")
    script_path.chmod(0o755)


def save_metadata(args: argparse.Namespace) -> Path:
    root = repo_root()
    metadata = merge_manifest_and_args(args, root)
    run_id = str(metadata["run_id"])
    results_dir = resolve_path(root, args.results_dir) or root / "results"
    run_dir = results_dir / run_id
    metadata_dir = run_dir / "metadata"
    snapshot_dir = metadata_dir / "config_snapshots"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    config_paths: list[Path] = []
    for field in CONFIG_FIELDS:
        resolved = resolve_config_path(root, field, metadata.get(field))
        if resolved is not None:
            config_paths.append(resolved)

    if args.manifest:
        manifest_path = resolve_path(root, args.manifest)
        if manifest_path is not None:
            config_paths.append(manifest_path)

    for extra_config in args.extra_config:
        resolved = resolve_path(root, extra_config)
        if resolved is not None:
            config_paths.append(resolved)

    config_paths = collect_linked_config_paths(root, config_paths)
    snapshots = copy_config_snapshots(root, snapshot_dir, config_paths)

    required_metadata_fields = [
        "trainer_config",
        "env_config",
        "reward_config",
        "curriculum_config",
        "manifest",
        "seed",
        "run_id",
        "scene",
    ]
    missing_required = [field for field in required_metadata_fields if not metadata.get(field)]
    if missing_required:
        raise ValueError(f"Metadata incomplete. Missing required fields: {', '.join(missing_required)}")

    run_metadata = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "seed": metadata.get("seed"),
        "scene": metadata.get("scene"),
        "curriculum_stage": metadata.get("curriculum_stage"),
        "stage_id": metadata.get("matrix_stage_id") or metadata.get("curriculum_stage"),
        "experiment_family": metadata.get("experiment_family"),
        "matrix_stage_id": metadata.get("matrix_stage_id"),
        "matrix_stage_order": metadata.get("matrix_stage_order"),
        "matrix_total_stages": metadata.get("matrix_total_stages"),
        "mode": metadata.get("mode", "training"),
        "unity_scene_name": metadata.get("scene"),
        "notes": metadata.get("notes"),
        "configs": {field: metadata.get(field) for field in CONFIG_FIELDS if metadata.get(field)},
        "manifest": metadata.get("manifest"),
        "git": git_metadata(root),
        "config_snapshots": snapshots,
        "training_command": args.training_command,
    }

    metadata_path = metadata_dir / "run_metadata.json"
    metadata_path.write_text(json.dumps(run_metadata, indent=2, sort_keys=True) + "\n")
    write_reproduction_command(metadata_dir, args.training_command)

    readme_path = metadata_dir / "README.md"
    readme_path.write_text(
        "# Run Metadata\n\n"
        f"- Run ID: `{run_id}`\n"
        f"- Metadata: `run_metadata.json`\n"
        "- Config snapshots: `config_snapshots/`\n"
        "- Reproduction command: `reproduce.sh` when a command was provided.\n"
    )

    return metadata_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--trainer-config")
    parser.add_argument("--env-config")
    parser.add_argument("--reward-config")
    parser.add_argument("--curriculum-config")
    parser.add_argument("--rule-config")
    parser.add_argument("--curriculum-stage")
    parser.add_argument("--scene")
    parser.add_argument("--manifest")
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--notes")
    parser.add_argument("--experiment-family")
    parser.add_argument("--matrix-stage-id")
    parser.add_argument("--matrix-stage-order", type=int)
    parser.add_argument("--matrix-total-stages", type=int)
    parser.add_argument("--training-command")
    parser.add_argument("--extra-config", action="append", default=[])
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        metadata_path = save_metadata(args)
    except Exception as exc:
        print(f"Failed to save run metadata: {exc}", file=sys.stderr)
        return 1

    print(f"Saved run metadata: {metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
