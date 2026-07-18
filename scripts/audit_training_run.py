#!/usr/bin/env python3
"""Audit one curriculum training run before it can enter the evidence pack."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import yaml


REQUIRED_LOGS = (
    "episode_log.csv",
    "agent_step_log.csv",
    "reward_audit.csv",
    "replay_events.csv",
)
REQUIRED_KPIS = ("eval_kpi_summary.json", "eval_kpi_summary.csv")
EPISODE_COLUMNS = (
    "episode_id",
    "outcome",
    "duration_seconds",
    "total_steps",
    "capture_count",
    "exit_count",
    "wall_shift_count",
    "trap_event_count",
    "rule_config_path",
    "reward_config_path",
    "reward_config_id",
    "curriculum_stage_id",
    "scene_name",
    "maze_layout_id",
    "maze_topology_seed",
    "sentinel_reward_total",
    "runner_reward_total",
    "capture_reward_total",
    "trap_reward_total",
    "shaping_reward_total",
    "penalty_reward_total",
    "terminal_reward_total",
)


def record(checks: list[dict], name: str, passed: bool, evidence: str) -> None:
    checks.append({"check": name, "status": "PASS" if passed else "FAIL", "evidence": evidence})


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_stage_line(player_text: str, stage_id: str) -> str:
    marker = f": {stage_id},"
    return next(
        (line.strip() for line in player_text.splitlines() if "Loaded curriculum config:" in line and marker in line),
        "",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--expected-stage", required=True)
    parser.add_argument("--expected-seed", type=int, required=True)
    parser.add_argument("--expected-reward-config", required=True)
    parser.add_argument("--expected-initialize-from")
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    logs_dir = run_dir / "logs"
    kpis_dir = run_dir / "kpis"
    metadata_path = run_dir / "metadata" / "run_metadata.json"
    status_path = run_dir / "metadata" / "training_status.json"
    player_logs = sorted((run_dir / "run_logs").glob("Player-*.log"))
    checks: list[dict] = []

    record(checks, "metadata exists", metadata_path.is_file() and metadata_path.stat().st_size > 0, str(metadata_path))
    record(checks, "training status exists", status_path.is_file() and status_path.stat().st_size > 0, str(status_path))
    record(checks, "run is not invalidated", not (run_dir / "metadata" / "INVALIDATED.md").exists(), str(run_dir))

    metadata = read_json(metadata_path) if metadata_path.is_file() else {}
    status = read_json(status_path) if status_path.is_file() else {}
    snapshot_records = metadata.get("config_snapshots") or []
    snapshots_valid = bool(snapshot_records)
    sources_current = bool(snapshot_records)
    snapshot_evidence: list[str] = []
    for item in snapshot_records:
        snapshot = Path(item.get("snapshot", ""))
        source = Path(item.get("source", ""))
        if not snapshot.is_absolute():
            snapshot = Path.cwd() / snapshot
        if not source.is_absolute():
            source = Path.cwd() / source
        expected_hash = str(item.get("sha256", ""))
        snapshot_ok = snapshot.is_file() and bool(expected_hash) and sha256_file(snapshot) == expected_hash
        source_ok = source.is_file() and bool(expected_hash) and sha256_file(source) == expected_hash
        snapshots_valid = snapshots_valid and snapshot_ok
        sources_current = sources_current and source_ok
        snapshot_evidence.append(f"{item.get('source')}:snapshot={snapshot_ok},source={source_ok}")
    record(checks, "config snapshots match recorded hashes", snapshots_valid, "; ".join(snapshot_evidence))
    record(checks, "current config sources match snapshots", sources_current, "; ".join(snapshot_evidence))
    record(checks, "training completed", status.get("success") is True and status.get("exit_code") == 0, json.dumps(status, sort_keys=True))
    record(checks, "seed matches", metadata.get("seed") == args.expected_seed, f"expected={args.expected_seed}, actual={metadata.get('seed')}")
    record(checks, "stage matches metadata", metadata.get("curriculum_stage") == args.expected_stage, f"expected={args.expected_stage}, actual={metadata.get('curriculum_stage')}")
    metadata_reward_name = Path((metadata.get("configs") or {}).get("reward_config", "")).name
    expected_reward_name = Path(args.expected_reward_config).name
    record(
        checks,
        "metadata reward matches manifest",
        metadata_reward_name == expected_reward_name,
        f"expected={expected_reward_name}, actual={metadata_reward_name}",
    )
    actual_initialize = metadata.get("initialize_from")
    record(
        checks,
        "checkpoint transfer matches",
        actual_initialize == args.expected_initialize_from,
        f"expected={args.expected_initialize_from}, actual={actual_initialize}",
    )

    for filename in REQUIRED_LOGS:
        path = logs_dir / filename
        record(checks, f"non-empty {filename}", path.is_file() and path.stat().st_size > 0, str(path))
    for filename in REQUIRED_KPIS:
        path = kpis_dir / filename
        record(checks, f"non-empty {filename}", path.is_file() and path.stat().st_size > 0, str(path))

    episode_path = logs_dir / "episode_log.csv"
    episodes: list[dict[str, str]] = []
    episode_fieldnames: list[str] = []
    if episode_path.is_file():
        with episode_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            episode_fieldnames = reader.fieldnames or []
            episodes = list(reader)
    record(checks, "completed episodes present", len(episodes) > 0, f"episodes={len(episodes)}")
    schema_ok = episode_fieldnames == list(EPISODE_COLUMNS) and all(None not in row for row in episodes)
    record(
        checks,
        "episode schema is canonical",
        schema_ok,
        f"columns={episode_fieldnames}, rows_with_extra_fields={sum(None in row for row in episodes)}",
    )
    episode_ids = [int(row["episode_id"]) for row in episodes if row.get("episode_id", "").isdigit()]
    expected_ids = list(range(1, len(episodes) + 1))
    record(
        checks,
        "episode IDs are unique and contiguous",
        episode_ids == expected_ids,
        f"observed={len(episode_ids)}, expected={len(expected_ids)}",
    )
    stage_values = sorted({row.get("curriculum_stage_id", "") for row in episodes})
    record(checks, "episode stage provenance", stage_values == [args.expected_stage], f"values={stage_values}")
    expected_scene = str(metadata.get("scene") or metadata.get("unity_scene_name") or "")
    scene_values = sorted({row.get("scene_name", "") for row in episodes})
    record(
        checks,
        "scene provenance matches metadata",
        bool(expected_scene) and scene_values == [expected_scene],
        f"expected={expected_scene}, values={scene_values}",
    )
    maze_provenance_ok = all(
        row.get("maze_layout_id", "").strip() and row.get("maze_topology_seed", "").lstrip("-").isdigit()
        for row in episodes
    )
    record(checks, "maze provenance present", maze_provenance_ok, "layout ID and topology seed populated")
    reward_names = sorted({Path(row.get("reward_config_path", "")).name for row in episodes})
    record(
        checks,
        "reward provenance matches manifest",
        reward_names == [expected_reward_name],
        f"expected={expected_reward_name}, values={reward_names}",
    )

    player_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in player_logs)
    record(checks, "player log present", bool(player_logs) and bool(player_text.strip()), ", ".join(str(path) for path in player_logs))
    record(checks, "stage applied at runtime", f": {args.expected_stage}," in player_text, args.expected_stage)

    curriculum_path = Path((metadata.get("configs") or {}).get("curriculum_config", ""))
    if not curriculum_path.is_absolute():
        curriculum_path = Path.cwd() / curriculum_path
    curriculum = yaml.safe_load(curriculum_path.read_text(encoding="utf-8")) if curriculum_path.is_file() else {}
    stage = next(
        (item for item in curriculum.get("stages", []) if item.get("stage_id") == args.expected_stage),
        None,
    )
    record(
        checks,
        "curriculum stage definition found",
        stage is not None,
        f"config={curriculum_path}, stage={args.expected_stage}",
    )
    applied_line = runtime_stage_line(player_text, args.expected_stage)
    maze = (stage or {}).get("maze", {})
    walls = (stage or {}).get("dynamic_walls", {})
    expected_runtime_tokens = {
        "maze mode applied at runtime": f"mode={str(maze.get('mode', '')).capitalize()}",
        "maze seed applied at runtime": f"mazeSeed={maze.get('seed')}",
        "spawn randomization applied at runtime": f"randomSpawns={maze.get('randomize_spawns')}",
        "exit randomization applied at runtime": f"randomExits={maze.get('randomize_exits')}",
        "dynamic-wall state applied at runtime": f"dynamicWalls={walls.get('enabled')}",
        "wall-shift interval applied at runtime": f"shiftInterval={float(walls.get('shift_interval_seconds', 0)):g}s",
    }
    for check_name, token in expected_runtime_tokens.items():
        record(checks, check_name, stage is not None and token in applied_line, f"expected={token}, line={applied_line}")
    record(checks, "all resets valid", "resetIntegrity=False" not in player_text and "resetIntegrity=True" in player_text, "runtime reset-integrity messages")

    passed = sum(item["status"] == "PASS" for item in checks)
    payload = {
        "schema_version": 1,
        "run_id": run_dir.name,
        "expected_seed": args.expected_seed,
        "expected_stage": args.expected_stage,
        "passed": passed,
        "failed": len(checks) - passed,
        "checks": checks,
    }
    audit_path = run_dir / "metadata" / "training_audit.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Training audit: {passed}/{len(checks)} checks passed")
    print(f"Wrote: {audit_path}")
    for item in checks:
        if item["status"] == "FAIL":
            print(f"FAIL: {item['check']}: {item['evidence']}")
    return 0 if passed == len(checks) else 2


if __name__ == "__main__":
    raise SystemExit(main())
