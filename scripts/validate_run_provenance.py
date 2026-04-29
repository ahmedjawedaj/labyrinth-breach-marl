#!/usr/bin/env python3
"""Validate canonical run provenance for official training and evaluation artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from hashlib import sha256
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - repo environment includes PyYAML.
    yaml = None

OFFICIAL_SEEDS = [42, 101, 202]
OFFICIAL_EVAL_SPLITS = ("seen", "unseen")
TRAINING_FAMILY_DEFAULT = "LB_3v2_curriculum_official_v1"
EVAL_FAMILY_DEFAULT = "LB_3v2_seen_unseen_eval_official_v1"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required for provenance validation.")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_repo_path(root: Path, value: str | None, *, context: Path | None = None) -> str | None:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = (context / path) if context is not None else (root / path)
    path = path.resolve()
    try:
        return str(path.relative_to(root.resolve()))
    except ValueError:
        return str(path)


def resolve_repo_path(root: Path, value: str | None, *, context: Path | None = None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return (context / path) if context is not None else (root / path)


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_problem(problems: list[str], message: str) -> None:
    problems.append(message)


def expect(condition: bool, problems: list[str], message: str) -> None:
    if not condition:
        add_problem(problems, message)


def check_file_exists(path: Path, problems: list[str], label: str) -> None:
    if not path.exists():
        add_problem(problems, f"Missing {label}: {path}")


def check_sha_snapshot(root: Path, snapshot_record: dict[str, Any], problems: list[str], label: str) -> None:
    snapshot = resolve_repo_path(root, snapshot_record.get("snapshot"))
    source = snapshot_record.get("source")
    expected_sha = snapshot_record.get("sha256")
    if snapshot is None:
        add_problem(problems, f"{label}: snapshot path missing")
        return
    snapshot_path = snapshot
    if not snapshot_path.exists():
        add_problem(problems, f"{label}: snapshot file missing: {snapshot_path}")
        return
    actual_sha = sha256_file(snapshot_path)
    if expected_sha and actual_sha != expected_sha:
        add_problem(
            problems,
            f"{label}: SHA mismatch for {source or snapshot_path}: expected {expected_sha}, got {actual_sha}",
        )


def parse_behavior_names(configuration_path: Path) -> list[str]:
    if yaml is None:
        raise RuntimeError("PyYAML is required for provenance validation.")
    data = yaml.safe_load(configuration_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return []
    behaviors = data.get("behaviors")
    if isinstance(behaviors, dict):
        return [str(name) for name in behaviors.keys()]
    return []


def stage_map(path: Path) -> dict[str, dict[str, Any]]:
    data = load_yaml(path)
    stages = data.get("stages")
    if not isinstance(stages, list):
        raise ValueError(f"Expected 'stages' list in {path}")
    mapping: dict[str, dict[str, Any]] = {}
    for stage in stages:
        if isinstance(stage, dict) and stage.get("id"):
            mapping[str(stage["id"])] = stage
    return mapping


def expected_run_id(template: str, experiment_family: str, seed: int, stage_id: str, stage_order: int) -> str:
    return template.format(
        experiment_family=experiment_family,
        seed=seed,
        stage_id=stage_id,
        stage_order=stage_order,
    )


def normalize_runtime_episode_path(root: Path, run_dir: Path, value: str | None) -> str | None:
    normalized = normalize_repo_path(root, value, context=run_dir / "logs")
    if normalized is None:
        return None

    try:
        results_root = (root / "results").resolve()
        run_relative = run_dir.resolve().relative_to(results_root).as_posix()
        prefix = f"results/{run_relative}/"
        if normalized.startswith(prefix):
            return normalized[len(prefix):]
    except Exception:
        pass

    return normalized


def validate_training_run(
    root: Path,
    run_dir: Path,
    expected: dict[str, Any],
    problems: list[str],
) -> None:
    metadata_path = run_dir / "metadata" / "run_metadata.json"
    status_path = run_dir / "metadata" / "training_status.json"
    config_path = run_dir / "configuration.yaml"
    episode_log_path = run_dir / "logs" / "episode_log.csv"
    reward_breakdown_path = run_dir / "logs" / "reward_breakdown.csv"

    check_file_exists(metadata_path, problems, "training metadata")
    check_file_exists(status_path, problems, "training status")
    check_file_exists(config_path, problems, "configuration")
    check_file_exists(episode_log_path, problems, "episode log")
    check_file_exists(reward_breakdown_path, problems, "reward breakdown")

    if not metadata_path.exists() or not status_path.exists():
        return

    metadata = load_json(metadata_path)
    status = load_json(status_path)
    manifest_path = resolve_repo_path(root, metadata.get("manifest"))

    expect(metadata.get("mode") == "training", problems, f"{run_dir}: mode should be training, got {metadata.get('mode')}")
    expect(metadata.get("run_id") == run_dir.name, problems, f"{run_dir}: run_id mismatch: {metadata.get('run_id')}")
    expect(int(metadata.get("seed", -1)) == expected["seed"], problems, f"{run_dir}: seed mismatch: {metadata.get('seed')} != {expected['seed']}")
    expect(metadata.get("experiment_family") == expected["experiment_family"], problems, f"{run_dir}: experiment family mismatch: {metadata.get('experiment_family')}")
    expect(metadata.get("stage_id") == expected["stage_id"], problems, f"{run_dir}: stage_id mismatch: {metadata.get('stage_id')} != {expected['stage_id']}")
    expect(metadata.get("matrix_stage_id") == expected["stage_id"], problems, f"{run_dir}: matrix_stage_id mismatch: {metadata.get('matrix_stage_id')} != {expected['stage_id']}")
    expect(int(metadata.get("matrix_stage_order", -1)) == expected["stage_order"], problems, f"{run_dir}: matrix_stage_order mismatch: {metadata.get('matrix_stage_order')} != {expected['stage_order']}")
    expect(bool(status.get("success")) is True, problems, f"{run_dir}: training status is not successful")
    expect(status.get("run_id") == run_dir.name, problems, f"{run_dir}: training status run_id mismatch: {status.get('run_id')}")
    expect(metadata.get("scene") == expected["scene"], problems, f"{run_dir}: scene mismatch: {metadata.get('scene')} != {expected['scene']}")
    expect(metadata.get("unity_scene_name") == expected["scene"], problems, f"{run_dir}: unity_scene_name mismatch: {metadata.get('unity_scene_name')} != {expected['scene']}")
    expect(metadata.get("curriculum_stage") == expected["curriculum_stage"], problems, f"{run_dir}: curriculum stage mismatch: {metadata.get('curriculum_stage')} != {expected['curriculum_stage']}")

    manifest = load_yaml(manifest_path) if manifest_path and manifest_path.exists() else {}
    expect(manifest.get("scene") == expected["scene"], problems, f"{run_dir}: manifest scene mismatch: {manifest.get('scene')} != {expected['scene']}")

    config_snapshot_entries = metadata.get("config_snapshots") or []
    expect(bool(config_snapshot_entries), problems, f"{run_dir}: no config snapshots recorded")
    for snapshot in config_snapshot_entries:
        check_sha_snapshot(root, snapshot, problems, f"{run_dir} config snapshot")

    behaviors = set(parse_behavior_names(config_path))
    expect(
        behaviors == {"Sentinel", "Runner"},
        problems,
        f"{run_dir}: behavior names mismatch: expected Sentinel/Runner, got {sorted(behaviors)}",
    )

    rows = read_csv_rows(episode_log_path)
    expect(bool(rows), problems, f"{run_dir}: episode log is empty")
    if rows:
        runtime_reward_paths = {normalize_runtime_episode_path(root, run_dir, row.get("reward_config_path")) for row in rows if row.get("reward_config_path")}
        runtime_rule_paths = {normalize_runtime_episode_path(root, run_dir, row.get("rule_config_path")) for row in rows if row.get("rule_config_path")}
        runtime_reward_ids = {row.get("reward_config_id") for row in rows if row.get("reward_config_id")}
        expected_reward = normalize_repo_path(root, metadata.get("configs", {}).get("reward_config"))
        expected_rule = normalize_repo_path(root, metadata.get("configs", {}).get("rule_config"))
        expected_reward_id = Path(str(metadata.get("configs", {}).get("reward_config", ""))).stem or None
        expect(runtime_reward_paths == {expected_reward}, problems, f"{run_dir}: runtime reward config path mismatch: {sorted(runtime_reward_paths)} vs {expected_reward}")
        expect(runtime_rule_paths == {expected_rule}, problems, f"{run_dir}: runtime rule config path mismatch: {sorted(runtime_rule_paths)} vs {expected_rule}")
        if expected_reward_id is not None:
            expect(runtime_reward_ids == {expected_reward_id}, problems, f"{run_dir}: runtime reward config ID mismatch: {sorted(runtime_reward_ids)} vs {expected_reward_id}")

    check_file_exists(reward_breakdown_path, problems, "training reward breakdown")


def validate_evaluation_run(
    root: Path,
    run_dir: Path,
    expected: dict[str, Any],
    problems: list[str],
) -> None:
    source_training_run_id = expected["source_training_run_id"]
    source_training_dir = root / "results" / source_training_run_id
    config_path = run_dir / "configuration.yaml"
    if not config_path.exists():
        config_path = source_training_dir / "configuration.yaml"

    run_metadata_path = run_dir / "metadata" / "run_metadata.json"
    eval_metadata_path = run_dir / "metadata" / "evaluation_metadata.json"
    episode_log_path = run_dir / "logs" / "episode_log.csv"
    summary_path = run_dir / "logs" / "open_arena_episode_summary.csv"
    events_path = run_dir / "logs" / "open_arena_events.csv"
    reward_breakdown_path = run_dir / "logs" / "reward_breakdown.csv"
    agent_step_path = run_dir / "logs" / "agent_step_log.csv"
    replay_path = run_dir / "logs" / "replay_events.csv"

    check_file_exists(run_metadata_path, problems, "evaluation run metadata")
    check_file_exists(eval_metadata_path, problems, "evaluation metadata")
    check_file_exists(config_path, problems, "evaluation configuration")
    check_file_exists(episode_log_path, problems, "evaluation episode log")
    check_file_exists(summary_path, problems, "evaluation summary")
    check_file_exists(events_path, problems, "evaluation events")
    check_file_exists(reward_breakdown_path, problems, "evaluation reward breakdown")
    check_file_exists(agent_step_path, problems, "evaluation agent step log")
    check_file_exists(replay_path, problems, "evaluation replay events")

    if not run_metadata_path.exists() or not eval_metadata_path.exists():
        return

    run_metadata = load_json(run_metadata_path)
    eval_metadata = load_json(eval_metadata_path)
    source_training_run_id = str(eval_metadata.get("fixed_policy_source_run_id") or "")
    source_training_status = source_training_dir / "metadata" / "training_status.json"

    expect(run_metadata.get("mode") == "evaluation", problems, f"{run_dir}: mode should be evaluation, got {run_metadata.get('mode')}")
    expect(run_metadata.get("run_id") == run_dir.name, problems, f"{run_dir}: run_id mismatch: {run_metadata.get('run_id')}")
    expect(eval_metadata.get("eval_run_id") == run_dir.name, problems, f"{run_dir}: eval_run_id mismatch: {eval_metadata.get('eval_run_id')}")
    expect(eval_metadata.get("seed") == expected["seed"], problems, f"{run_dir}: eval seed mismatch: {eval_metadata.get('seed')} != {expected['seed']}")
    expect(bool(eval_metadata.get("deterministic")) is True, problems, f"{run_dir}: deterministic evaluation required")
    expect(bool(eval_metadata.get("learning_disabled")) is True, problems, f"{run_dir}: learning must be disabled during evaluation")
    expect(eval_metadata.get("fixed_policy_source_run_id") == source_training_run_id, problems, f"{run_dir}: source run mismatch: {eval_metadata.get('fixed_policy_source_run_id')} != {source_training_run_id}")
    expect(source_training_status.exists(), problems, f"{run_dir}: missing source training status: {source_training_status}")

    manifest_path = resolve_repo_path(root, run_metadata.get("manifest"))
    manifest = load_yaml(manifest_path) if manifest_path and manifest_path.exists() else {}
    expect(run_metadata.get("scene") == expected["scene"], problems, f"{run_dir}: scene mismatch: {run_metadata.get('scene')} != {expected['scene']}")
    expect(run_metadata.get("unity_scene_name") == expected["scene"], problems, f"{run_dir}: unity_scene_name mismatch: {run_metadata.get('unity_scene_name')} != {expected['scene']}")
    expect(manifest.get("scene") == expected["scene"], problems, f"{run_dir}: manifest scene mismatch: {manifest.get('scene')} != {expected['scene']}")
    expect(manifest.get("layout_split") == expected["split"], problems, f"{run_dir}: manifest split mismatch: {manifest.get('layout_split')} != {expected['split']}")

    config_snapshot_entries = run_metadata.get("config_snapshots") or []
    expect(bool(config_snapshot_entries), problems, f"{run_dir}: no config snapshots recorded")
    for snapshot in config_snapshot_entries:
        check_sha_snapshot(root, snapshot, problems, f"{run_dir} config snapshot")

    behaviors = set(parse_behavior_names(config_path))
    expect(
        behaviors == {"Sentinel", "Runner"},
        problems,
        f"{run_dir}: behavior names mismatch: expected Sentinel/Runner, got {sorted(behaviors)}",
    )

    onnx_policies = eval_metadata.get("onnx_policies") or []
    labels = {str(item.get("label")) for item in onnx_policies if isinstance(item, dict)}
    expect(labels == {"Sentinel", "Runner"}, problems, f"{run_dir}: ONNX policy labels mismatch: {sorted(labels)}")
    for item in onnx_policies:
        if isinstance(item, dict):
            policy_path = resolve_repo_path(root, item.get("path"))
            if policy_path is not None:
                check_file_exists(policy_path, problems, f"ONNX policy {item.get('label')}")

    checkpoints = eval_metadata.get("checkpoints") or []
    for item in checkpoints:
        if isinstance(item, dict):
            checkpoint_path = resolve_repo_path(root, item.get("path"))
            if checkpoint_path is not None:
                check_file_exists(checkpoint_path, problems, f"checkpoint {item.get('label')}")

    rows = read_csv_rows(episode_log_path)
    expect(bool(rows), problems, f"{run_dir}: evaluation episode log is empty")
    if rows:
        runtime_reward_paths = {normalize_runtime_episode_path(root, run_dir, row.get("reward_config_path")) for row in rows if row.get("reward_config_path")}
        runtime_rule_paths = {normalize_runtime_episode_path(root, run_dir, row.get("rule_config_path")) for row in rows if row.get("rule_config_path")}
        runtime_reward_ids = {row.get("reward_config_id") for row in rows if row.get("reward_config_id")}
        expected_reward = normalize_repo_path(root, eval_metadata.get("reward_config"))
        expected_rule = normalize_repo_path(root, eval_metadata.get("rule_config"))
        expected_reward_id = Path(str(eval_metadata.get("reward_config", ""))).stem or None
        expect(runtime_reward_paths == {expected_reward}, problems, f"{run_dir}: runtime reward config path mismatch: {sorted(runtime_reward_paths)} vs {expected_reward}")
        expect(runtime_rule_paths == {expected_rule}, problems, f"{run_dir}: runtime rule config path mismatch: {sorted(runtime_rule_paths)} vs {expected_rule}")
        if expected_reward_id is not None:
            expect(runtime_reward_ids == {expected_reward_id}, problems, f"{run_dir}: runtime reward config ID mismatch: {sorted(runtime_reward_ids)} vs {expected_reward_id}")

    summary_rows = read_csv_rows(summary_path)
    expect(bool(summary_rows), problems, f"{run_dir}: summary CSV is empty")

    expect(run_metadata.get("run_id") == expected["run_id"], problems, f"{run_dir}: run_id is not canonical")


def training_matrix_entries(root: Path, training_matrix: dict[str, Any]) -> list[dict[str, Any]]:
    experiment_family = str(training_matrix["experiment_family"])
    run_id_template = str(training_matrix["run_id_template"])
    rows: list[dict[str, Any]] = []
    for seed in training_matrix["seeds"]:
        for stage in training_matrix["stages"]:
            stage_id = str(stage["id"])
            stage_order = int(stage.get("order", 0))
            manifest_path = root / str(stage["manifest"])
            manifest = load_yaml(manifest_path) if manifest_path.exists() else {}
            rows.append(
                {
                    "seed": int(seed),
                    "experiment_family": experiment_family,
                    "stage_id": stage_id,
                    "stage_order": stage_order,
                    "curriculum_stage": stage.get("curriculum_stage"),
                    "scene": manifest.get("scene") or stage.get("scene") or "03_DynamicMaze_3v2",
                    "run_id": expected_run_id(run_id_template, experiment_family, int(seed), stage_id, stage_order),
                    "manifest": manifest_path,
                }
            )
    return rows


def evaluation_matrix_entries(root: Path, eval_matrix: dict[str, Any], training_matrix: dict[str, Any]) -> list[dict[str, Any]]:
    duration_minutes = int(eval_matrix["duration_minutes"])
    experiment_family = str(eval_matrix["experiment_family"])
    source_stage_id = str(eval_matrix["source_stage_id"])
    stage_map_data = {str(stage["id"]): stage for stage in training_matrix["stages"] if isinstance(stage, dict) and stage.get("id")}
    source_stage = stage_map_data.get(source_stage_id)
    if source_stage is None:
        raise ValueError(f"Source stage '{source_stage_id}' not found in training matrix")
    source_stage_order = int(source_stage.get("order", 0))

    rows: list[dict[str, Any]] = []
    for seed in eval_matrix["seeds"]:
        for split in eval_matrix["splits"]:
            split_id = str(split["id"])
            rows.append(
                {
                    "seed": int(seed),
                    "split": split_id,
                    "scene": "03_DynamicMaze_3v2" if split_id == "seen" else "04_Eval_UnseenMaze_3v2",
                    "run_id": f"{experiment_family}_seed{int(seed)}_{split_id}_{duration_minutes}m",
                    "source_training_run_id": expected_run_id(
                        str(training_matrix["run_id_template"]),
                        str(training_matrix["experiment_family"]),
                        int(seed),
                        source_stage_id,
                        source_stage_order,
                    ),
                    "manifest": root / str(split["manifest"]),
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--training-family", default=TRAINING_FAMILY_DEFAULT)
    parser.add_argument("--eval-family", default=EVAL_FAMILY_DEFAULT)
    args = parser.parse_args()

    root = repo_root()
    results_root = root / args.results_dir
    problems: list[str] = []

    training_matrix_path = root / "configs" / "experiment_manifests" / "official_curriculum_matrix.yaml"
    eval_matrix_path = root / "configs" / "experiment_manifests" / "official_seen_unseen_eval_matrix.yaml"
    check_file_exists(training_matrix_path, problems, "training matrix manifest")
    check_file_exists(eval_matrix_path, problems, "evaluation matrix manifest")
    if problems:
        for item in problems:
            print(f"ERROR: {item}")
        return 1

    training_matrix = load_yaml(training_matrix_path)
    eval_matrix = load_yaml(eval_matrix_path)

    if training_matrix.get("seeds") != OFFICIAL_SEEDS:
        add_problem(problems, f"Training matrix seeds mismatch: {training_matrix.get('seeds')}")
    if eval_matrix.get("seeds") != OFFICIAL_SEEDS:
        add_problem(problems, f"Evaluation matrix seeds mismatch: {eval_matrix.get('seeds')}")
    splits = eval_matrix.get("splits") or []
    if [str(split.get("id")) for split in splits if isinstance(split, dict)] != list(OFFICIAL_EVAL_SPLITS):
        add_problem(problems, f"Evaluation matrix split order mismatch: {[str(split.get('id')) for split in splits if isinstance(split, dict)]}")

    training_entries = training_matrix_entries(root, training_matrix)
    for entry in training_entries:
        validate_training_run(root, results_root / entry["run_id"], entry, problems)

    eval_entries = evaluation_matrix_entries(root, eval_matrix, training_matrix)
    for entry in eval_entries:
        validate_evaluation_run(root, results_root / "seed_{}".format(entry["seed"]) / "eval" / entry["run_id"], entry, problems)

    family_summary_json = results_root / args.eval_family / "eval" / "final_seen_unseen_summary.json"
    family_summary_csv = results_root / args.eval_family / "eval" / "final_seen_unseen_summary.csv"
    official_summary_root = results_root / "official_summary"
    for path, label in [
        (family_summary_json, "family summary JSON"),
        (family_summary_csv, "family summary CSV"),
        (official_summary_root / "seen_unseen_comparison.csv", "official seen/unseen comparison"),
        (official_summary_root / "multiseed_kpi_summary.csv", "official multiseed KPI summary"),
        (official_summary_root / "training_completion_matrix.csv", "official training completion matrix"),
        (official_summary_root / "coordination_kpi_summary.csv", "official coordination KPI summary"),
        (official_summary_root / "reward_breakdown_summary.csv", "official reward breakdown summary"),
        (official_summary_root / "missing_artifacts_report.csv", "official missing artifacts report"),
    ]:
        check_file_exists(path, problems, label)

    if problems:
        print("Provenance validation failed:")
        for item in problems:
            print(f"- {item}")
        return 1

    print("Provenance validation passed for official training and evaluation artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
