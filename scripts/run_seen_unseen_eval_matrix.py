#!/usr/bin/env python3
"""Run strict seen/unseen evaluation for official seeds and write comparison reports."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

OFFICIAL_SEEDS = [42, 101, 202]
OFFICIAL_SPLITS = ["seen", "unseen"]


def load_yaml(path: Path) -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML is required to parse manifests.")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_training_matrix(root: Path, manifest_path: Path) -> dict:
    data = load_yaml(manifest_path)
    return {
        "experiment_family": str(data["experiment_family"]),
        "seeds": data["seeds"],
        "stages": data["stages"],
        "run_id_template": str(data["run_id_template"]),
    }


def run_id_from_template(template: str, experiment_family: str, seed: int, stage_id: str, stage_order: int) -> str:
    return template.format(
        experiment_family=experiment_family,
        seed=seed,
        stage_id=stage_id,
        stage_order=stage_order,
    )


def parse_eval_matrix(root: Path, path: Path) -> dict:
    data = load_yaml(path)
    seeds = data.get("seeds")
    if seeds != OFFICIAL_SEEDS:
        raise ValueError(f"Evaluation matrix seeds must be exactly {OFFICIAL_SEEDS}, got {seeds}")
    splits = data.get("splits")
    if not isinstance(splits, list) or [split.get("id") for split in splits] != OFFICIAL_SPLITS:
        raise ValueError(f"Evaluation matrix must define splits exactly as {OFFICIAL_SPLITS}")
    for split in splits:
        manifest = root / split["manifest"]
        if not manifest.exists():
            raise FileNotFoundError(f"Missing split manifest: {manifest}")
    return data


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def safe_float(row: dict[str, str], key: str) -> float:
    try:
        return float((row.get(key) or "0").strip() or 0)
    except (ValueError, AttributeError):
        return 0.0


def derive_extra_metrics(logs_dir: Path) -> dict:
    episode_rows = read_csv_rows(logs_dir / "episode_log.csv")
    reward_rows = read_csv_rows(logs_dir / "reward_audit.csv")
    episodes = max(1, len(episode_rows))
    capture_total = sum(safe_float(row, "capture_count") for row in episode_rows)
    multi_capture = sum(1 for row in episode_rows if safe_float(row, "capture_count") >= 2)
    runner_win_rows = [row for row in episode_rows if row.get("outcome") in {"RunnerWinExitReached", "RunnerWinTimeout"}]
    exploration_time_proxy = (
        sum(safe_float(row, "duration_seconds") for row in runner_win_rows) / max(1, len(runner_win_rows))
    )

    reward_breakdown: dict[str, float] = {}
    for row in reward_rows:
        team = (row.get("team") or "unknown").strip() or "unknown"
        reason = (row.get("reason") or "unknown").strip() or "unknown"
        key = f"{team}:{reason}"
        reward_breakdown[key] = reward_breakdown.get(key, 0.0) + safe_float(row, "delta")

    return {
        "exploration_time_proxy_seconds": exploration_time_proxy,
        "coordination_capture_per_episode": capture_total / episodes,
        "coordination_multi_capture_episode_rate": multi_capture / episodes,
        "reward_shaping_breakdown": reward_breakdown,
    }


def verify_eval_metadata(eval_metadata_path: Path, *, seed: int, deterministic_expected: bool, source_run_id: str) -> None:
    data = load_json(eval_metadata_path)
    if int(data.get("seed", -1)) != seed:
        raise RuntimeError(f"Seed mismatch in {eval_metadata_path}: expected {seed}, got {data.get('seed')}")
    if bool(data.get("deterministic")) != deterministic_expected:
        raise RuntimeError(
            f"Deterministic flag mismatch in {eval_metadata_path}: "
            f"expected {deterministic_expected}, got {data.get('deterministic')}"
        )
    if str(data.get("fixed_policy_source_run_id")) != source_run_id:
        raise RuntimeError(
            f"Source run mismatch in {eval_metadata_path}: expected {source_run_id}, "
            f"got {data.get('fixed_policy_source_run_id')}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--eval-matrix-manifest",
        default="configs/experiment_manifests/official_seen_unseen_eval_matrix.yaml",
    )
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--source-results-dir", default="results")
    parser.add_argument("--allow-cpu", action="store_true")
    parser.add_argument("--no-graphics", action="store_true")
    parser.add_argument("--timeout-wait", type=int, default=120)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    eval_matrix_path = root / args.eval_matrix_manifest
    eval_matrix = parse_eval_matrix(root, eval_matrix_path)

    training_matrix_path = root / eval_matrix["training_matrix_manifest"]
    training_matrix = parse_training_matrix(root, training_matrix_path)
    if training_matrix["seeds"] != OFFICIAL_SEEDS:
        raise ValueError("Training matrix seeds do not match official seeds.")

    stage4 = next((stage for stage in training_matrix["stages"] if stage.get("id") == eval_matrix["source_stage_id"]), None)
    if stage4 is None:
        raise ValueError(f"Training matrix does not contain source stage '{eval_matrix['source_stage_id']}'")
    stage4_order = int(stage4.get("order", 4))

    duration_minutes = int(eval_matrix["duration_minutes"])
    max_runtime_seconds = max(60, duration_minutes * 60)
    deterministic_expected = bool(eval_matrix.get("deterministic_inference", True))
    run_summaries: list[dict] = []

    for seed in OFFICIAL_SEEDS:
        for stage in training_matrix["stages"]:
            stage_id = str(stage["id"])
            stage_order = int(stage.get("order", 1))
            training_run_id = run_id_from_template(
                training_matrix["run_id_template"],
                training_matrix["experiment_family"],
                seed,
                stage_id,
                stage_order,
            )
            training_status_path = root / args.source_results_dir / training_run_id / "metadata" / "training_status.json"
            if not training_status_path.exists():
                raise RuntimeError(
                    f"Training stage is incomplete for seed {seed}: missing {training_status_path}. "
                    "Evaluation can run only after all training stages complete."
                )
            training_status_data = load_json(training_status_path)
            if not bool(training_status_data.get("success")):
                raise RuntimeError(
                    f"Training stage '{stage_id}' failed for seed {seed}: {training_status_path} "
                    f"(exit_code={training_status_data.get('exit_code')})"
                )

        source_run_id = run_id_from_template(
            training_matrix["run_id_template"],
            training_matrix["experiment_family"],
            seed,
            eval_matrix["source_stage_id"],
            stage4_order,
        )
        source_training_status = root / args.source_results_dir / source_run_id / "metadata" / "training_status.json"
        if not source_training_status.exists():
            raise RuntimeError(f"Training is incomplete for seed {seed}: missing {source_training_status}")
        training_status = load_json(source_training_status)
        if not bool(training_status.get("success")):
            raise RuntimeError(f"Training stage4 failed for seed {seed}: {source_training_status}")

        seed_eval_root = root / args.results_dir / f"seed_{seed}" / "eval"
        seed_eval_root.mkdir(parents=True, exist_ok=True)
        split_results: dict[str, dict] = {}
        for split in eval_matrix["splits"]:
            split_id = split["id"]
            manifest = split["manifest"]
            eval_run_id = f"{eval_matrix['experiment_family']}_seed{seed}_{split_id}_{duration_minutes}m"
            command = [
                sys.executable,
                "scripts/evaluate_policy.py",
                "--manifest",
                manifest,
                "--source-run-id",
                source_run_id,
                "--source-results-dir",
                args.source_results_dir,
                "--output-dir",
                str(Path(args.results_dir) / f"seed_{seed}" / "eval"),
                "--seed",
                str(seed),
                "--eval-run-id",
                eval_run_id,
                "--max-runtime-seconds",
                str(max_runtime_seconds),
                "--timeout-wait",
                str(args.timeout_wait),
            ]
            if args.allow_cpu:
                command.append("--allow-cpu")
            if args.no_graphics:
                command.append("--no-graphics")
            if deterministic_expected:
                command.append("--deterministic")

            print(f"\n=== Seen/Unseen eval: seed={seed}, split={split_id}, run={eval_run_id} ===")
            print(" ".join(command))
            rc = subprocess.run(command, cwd=root).returncode
            if rc not in (0, 124):
                print(f"Evaluation failed for seed={seed}, split={split_id}, exit={rc}", file=sys.stderr)
                return rc

            run_root = seed_eval_root / eval_run_id
            eval_metadata_path = run_root / "metadata" / "evaluation_metadata.json"
            verify_eval_metadata(
                eval_metadata_path,
                seed=seed,
                deterministic_expected=deterministic_expected,
                source_run_id=source_run_id,
            )
            kpi_path = run_root / "kpi" / "eval_kpi_summary.json"
            kpi = load_json(kpi_path)
            extra = derive_extra_metrics(run_root / "logs")
            split_results[split_id] = {
                "run_id": eval_run_id,
                "run_root": str(run_root.relative_to(root)),
                "kpi": kpi,
                "extra_metrics": extra,
            }

        seen = split_results["seen"]
        unseen = split_results["unseen"]
        comparison = {
            "seed": seed,
            "source_training_run_id": source_run_id,
            "duration_minutes": duration_minutes,
            "deterministic_inference": deterministic_expected,
            "seen": seen,
            "unseen": unseen,
            "generalization_drop": {
                "sentinel_win_rate_drop": seen["kpi"].get("sentinel_win_rate", 0.0) - unseen["kpi"].get("sentinel_win_rate", 0.0),
                "runner_win_rate_increase": unseen["kpi"].get("runner_win_rate", 0.0) - seen["kpi"].get("runner_win_rate", 0.0),
                "capture_time_delta_seconds": unseen["kpi"].get("mean_capture_time_seconds", 0.0)
                - seen["kpi"].get("mean_capture_time_seconds", 0.0),
                "path_efficiency_delta": unseen["kpi"].get("path_efficiency_proxy_captures_per_meter", 0.0)
                - seen["kpi"].get("path_efficiency_proxy_captures_per_meter", 0.0),
                "exploration_time_proxy_delta_seconds": unseen["extra_metrics"].get("exploration_time_proxy_seconds", 0.0)
                - seen["extra_metrics"].get("exploration_time_proxy_seconds", 0.0),
                "coordination_capture_per_episode_delta": unseen["extra_metrics"].get("coordination_capture_per_episode", 0.0)
                - seen["extra_metrics"].get("coordination_capture_per_episode", 0.0),
            },
        }
        comparison_path = seed_eval_root / "seen_unseen_comparison.json"
        comparison_path.write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with (seed_eval_root / "seen_unseen_comparison.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["metric", "seen", "unseen", "delta_unseen_minus_seen"])
            rows = [
                ("sentinel_win_rate", seen["kpi"].get("sentinel_win_rate", 0.0), unseen["kpi"].get("sentinel_win_rate", 0.0)),
                ("runner_win_rate", seen["kpi"].get("runner_win_rate", 0.0), unseen["kpi"].get("runner_win_rate", 0.0)),
                (
                    "mean_capture_time_seconds",
                    seen["kpi"].get("mean_capture_time_seconds", 0.0),
                    unseen["kpi"].get("mean_capture_time_seconds", 0.0),
                ),
                (
                    "path_efficiency_proxy_captures_per_meter",
                    seen["kpi"].get("path_efficiency_proxy_captures_per_meter", 0.0),
                    unseen["kpi"].get("path_efficiency_proxy_captures_per_meter", 0.0),
                ),
                (
                    "exploration_time_proxy_seconds",
                    seen["extra_metrics"].get("exploration_time_proxy_seconds", 0.0),
                    unseen["extra_metrics"].get("exploration_time_proxy_seconds", 0.0),
                ),
                (
                    "coordination_capture_per_episode",
                    seen["extra_metrics"].get("coordination_capture_per_episode", 0.0),
                    unseen["extra_metrics"].get("coordination_capture_per_episode", 0.0),
                ),
            ]
            for metric, seen_val, unseen_val in rows:
                writer.writerow([metric, seen_val, unseen_val, unseen_val - seen_val])

        meta_eval = {
            "schema_version": 1,
            "seed": seed,
            "source_stage_id": eval_matrix["source_stage_id"],
            "source_training_run_id": source_run_id,
            "duration_minutes": duration_minutes,
            "deterministic_inference": deterministic_expected,
            "split_run_ids": {split: split_results[split]["run_id"] for split in OFFICIAL_SPLITS},
        }
        (seed_eval_root / "meta_evaluation.json").write_text(json.dumps(meta_eval, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        run_summaries.append(
            {
                "seed": seed,
                "eval_root": str(seed_eval_root.relative_to(root)),
                "seen_run_id": split_results["seen"]["run_id"],
                "unseen_run_id": split_results["unseen"]["run_id"],
                "generalization_drop": comparison["generalization_drop"],
            }
        )

    aggregate = {
        "schema_version": 1,
        "experiment_family": eval_matrix["experiment_family"],
        "training_matrix_manifest": eval_matrix["training_matrix_manifest"],
        "eval_matrix_manifest": str(eval_matrix_path.relative_to(root)),
        "seeds": OFFICIAL_SEEDS,
        "duration_minutes": duration_minutes,
        "deterministic_inference": deterministic_expected,
        "seed_summaries": run_summaries,
    }
    family_dir = root / args.results_dir / eval_matrix["experiment_family"] / "eval"
    family_dir.mkdir(parents=True, exist_ok=True)
    (family_dir / "final_seen_unseen_summary.json").write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (family_dir / "final_seen_unseen_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "seed",
                "seen_run_id",
                "unseen_run_id",
                "sentinel_win_rate_drop",
                "runner_win_rate_increase",
                "capture_time_delta_seconds",
                "path_efficiency_delta",
                "exploration_time_proxy_delta_seconds",
                "coordination_capture_per_episode_delta",
            ]
        )
        for item in run_summaries:
            drop = item["generalization_drop"]
            writer.writerow(
                [
                    item["seed"],
                    item["seen_run_id"],
                    item["unseen_run_id"],
                    drop["sentinel_win_rate_drop"],
                    drop["runner_win_rate_increase"],
                    drop["capture_time_delta_seconds"],
                    drop["path_efficiency_delta"],
                    drop["exploration_time_proxy_delta_seconds"],
                    drop["coordination_capture_per_episode_delta"],
                ]
            )
    tracker_command = [
        sys.executable,
        "scripts/seed_completion_tracker.py",
        "--training-matrix-manifest",
        eval_matrix["training_matrix_manifest"],
        "--eval-matrix-manifest",
        str(eval_matrix_path.relative_to(root)),
        "--results-dir",
        args.results_dir,
        "--output-dir",
        args.results_dir,
    ]
    print("Running seed completion tracker:")
    print(" ".join(tracker_command))
    tracker_rc = subprocess.run(tracker_command, cwd=root).returncode
    if tracker_rc != 0:
        print(f"Seed completion tracker failed with exit code {tracker_rc}.", file=sys.stderr)
        return tracker_rc
    paper_command = [
        sys.executable,
        "scripts/build_paper_ready_outputs.py",
        "--experiment-family",
        eval_matrix["experiment_family"],
        "--results-dir",
        args.results_dir,
    ]
    print("Running paper-ready output builder:")
    print(" ".join(paper_command))
    paper_rc = subprocess.run(paper_command, cwd=root).returncode
    if paper_rc != 0:
        print(f"Paper-ready output builder failed with exit code {paper_rc}.", file=sys.stderr)
        return paper_rc
    print(f"Seen/unseen evaluation matrix completed for seeds: {OFFICIAL_SEEDS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
