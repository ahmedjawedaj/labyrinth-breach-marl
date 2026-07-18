#!/usr/bin/env python3
"""Run publication-grade seen/unseen evaluations from a flexible matrix."""

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


def root_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML is required.")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def select_policy_seeds(matrix: dict, requested: list[int] | None) -> dict:
    if requested is None:
        return matrix
    registered = [int(seed) for seed in matrix.get("seeds") or []]
    unknown = sorted(set(requested) - set(registered))
    if unknown:
        raise ValueError(f"Requested policy seeds are not registered: {unknown}")
    selected = dict(matrix)
    selected["seeds"] = [seed for seed in registered if seed in set(requested)]
    return selected


def safe_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def nested(data: dict, *keys: str):
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def source_run_id_from_matrix(root: Path, matrix: dict, seed: int) -> str:
    training_matrix = load_yaml(root / matrix["training_matrix_manifest"])
    stage = next(stage for stage in training_matrix["stages"] if stage["id"] == matrix["source_stage_id"])
    return training_matrix["run_id_template"].format(
        experiment_family=training_matrix["experiment_family"],
        seed=seed,
        stage_id=stage["id"],
        stage_order=int(stage.get("order", 4)),
    )


def require_training_complete(root: Path, results_dir: str, run_id: str) -> None:
    status_path = root / results_dir / run_id / "metadata" / "training_status.json"
    if not status_path.exists():
        raise RuntimeError(f"Missing completed source training status: {status_path}")
    status = load_json(status_path)
    if not status.get("success"):
        raise RuntimeError(f"Source training did not complete successfully: {status_path}")


def write_aggregate(rows: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "publication_eval_summary.csv"
    json_path = output_dir / "publication_eval_summary.json"
    fieldnames = [
        "source_run_id",
        "policy_seed",
        "evaluation_seed",
        "split_id",
        "group",
        "run_id",
        "episodes",
        "sentinel_win_rate",
        "runner_win_rate",
        "escape_rate",
        "mean_time_to_first_capture_seconds",
        "mean_time_to_full_capture_seconds",
        "pincer_episode_rate",
        "corridor_block_episode_rate",
        "exit_denial_episode_rate",
        "trap_success_rate",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    json_path.write_text(json.dumps({"rows": rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote publication CSV: {csv_path}")
    print(f"Wrote publication JSON: {json_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", default="configs/experiment_manifests/official_publication_eval_matrix.yaml")
    parser.add_argument("--source-run-id", help="Use one existing checkpoint run for all policy seeds.")
    parser.add_argument("--source-results-dir", default="results")
    parser.add_argument("--results-dir", default="results/publication_eval")
    parser.add_argument("--seeds", nargs="+", type=int)
    parser.add_argument("--env", help="Path to a Unity standalone player.")
    parser.add_argument("--allow-cpu", action="store_true")
    parser.add_argument("--no-graphics", action="store_true")
    parser.add_argument("--timeout-wait", type=int, default=120)
    parser.add_argument("--base-port", type=int)
    parser.add_argument("--max-runtime-seconds", type=int)
    parser.add_argument("--target-episodes", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-training-status-check", action="store_true")
    parser.add_argument(
        "--aggregate-only",
        action="store_true",
        help="Skip Unity evaluation and rebuild the aggregate from existing run directories.",
    )
    parser.add_argument(
        "--resummarize-existing",
        action="store_true",
        help="With --aggregate-only, regenerate each KPI summary from its existing raw logs.",
    )
    parser.add_argument(
        "--resume-completed",
        action="store_true",
        help="Reuse cells whose successful status and KPI already match the episode target.",
    )
    parser.add_argument(
        "--force-output",
        action="store_true",
        help="Clean an existing incomplete evaluation cell before rerunning it.",
    )
    parser.add_argument(
        "--skip-finalize",
        action="store_true",
        help="Run shard cells without writing shared aggregate, audit, or statistics outputs.",
    )
    args = parser.parse_args()

    root = root_dir()
    matrix = select_policy_seeds(load_yaml(root / args.matrix), args.seeds)
    intervention = matrix.get("intervention")
    reward_intervention = matrix.get("reward_intervention")
    control_command = (
        [sys.executable, "scripts/validate_reward_ablation.py"]
        if reward_intervention
        else
        [
            sys.executable,
            "scripts/validate_ablation_controls.py",
            "--condition",
            str(intervention),
        ]
        if intervention
        else [sys.executable, "scripts/validate_evaluation_controls.py"]
    )
    control_audit_rc = subprocess.run(control_command, cwd=root).returncode
    if control_audit_rc != 0:
        print("Seen/held-out control audit failed; refusing publication evaluation.", file=sys.stderr)
        return control_audit_rc
    duration_seconds = args.max_runtime_seconds or int(matrix["duration_minutes"]) * 60
    target_episodes = args.target_episodes or int(matrix.get("episodes_per_cell", 0))
    duration_label = f"{target_episodes}ep" if target_episodes else (
        f"{duration_seconds}s" if args.max_runtime_seconds else f"{matrix['duration_minutes']}m"
    )
    rows: list[dict] = []
    deterministic = bool(matrix.get("deterministic_inference", True))

    for policy_seed in matrix["seeds"]:
        source_run_id = args.source_run_id or source_run_id_from_matrix(root, matrix, int(policy_seed))
        if not args.skip_training_status_check and not args.source_run_id:
            require_training_complete(root, args.source_results_dir, source_run_id)

        for split in matrix["splits"]:
            split_id = str(split["id"])
            group = str(split.get("group", split_id))
            seed_label = "evalseed" if args.source_run_id else "policyseed"
            seed_directory = f"evaluation_seed_{policy_seed}" if args.source_run_id else f"policy_seed_{policy_seed}"
            eval_run_id = f"{matrix['experiment_family']}_{seed_label}{policy_seed}_{split_id}_{duration_label}"
            command = [
                sys.executable,
                "scripts/evaluate_policy.py",
                "--manifest",
                split["manifest"],
                "--source-run-id",
                source_run_id,
                "--source-results-dir",
                args.source_results_dir,
                "--output-dir",
                str(Path(args.results_dir) / seed_directory),
                "--seed",
                str(policy_seed),
                "--eval-run-id",
                eval_run_id,
                "--max-runtime-seconds",
                str(duration_seconds),
                "--timeout-wait",
                str(args.timeout_wait),
                "--forbid-fallback-log-copy",
            ]
            if target_episodes:
                command.extend(["--target-episodes", str(target_episodes)])
            if deterministic:
                command.append("--deterministic")
            if args.env:
                command.extend(["--env", args.env])
            if args.allow_cpu:
                command.append("--allow-cpu")
            if args.no_graphics:
                command.append("--no-graphics")
            if args.base_port is not None:
                command.extend(["--base-port", str(args.base_port)])
            if args.dry_run:
                command.append("--dry-run")

            run_root = root / args.results_dir / seed_directory / eval_run_id
            reusable = False
            if args.resume_completed and run_root.exists():
                status_path = run_root / "metadata" / "evaluation_status.json"
                kpi_path = run_root / "kpi" / "eval_kpi_summary.json"
                if status_path.is_file() and kpi_path.is_file():
                    status = load_json(status_path)
                    required_existing = [
                        run_root / "metadata" / "run_metadata.json",
                        run_root / "metadata" / "evaluation_metadata.json",
                        run_root / "logs" / "episode_log.csv",
                        run_root / "logs" / "agent_step_log.csv",
                        run_root / "logs" / "reward_audit.csv",
                        run_root / "logs" / "replay_events.csv",
                    ]
                    reusable = (
                        status.get("success") is True
                        and int(status.get("completed_episodes") or 0) >= target_episodes
                        and int(status.get("target_episodes") or 0) == target_episodes
                        and all(path.is_file() and path.stat().st_size > 0 for path in required_existing)
                    )
            if not args.aggregate_only:
                if reusable:
                    print(f"Reusing completed evaluation cell: {eval_run_id}")
                else:
                    if run_root.exists() and (args.force_output or args.resume_completed):
                        command.append("--force-output")
                    print("\n=== Publication eval ===")
                    print(" ".join(command))
                    rc = subprocess.run(command, cwd=root).returncode
                    if rc != 0:
                        return rc
                    if args.dry_run:
                        continue
            elif args.resummarize_existing:
                summarize_command = [
                    sys.executable,
                    "scripts/summarize_eval_kpis.py",
                    "--logs-dir",
                    str(run_root / "logs"),
                    "--run-id",
                    eval_run_id,
                    "--seed",
                    str(policy_seed),
                    "--output",
                    str(run_root / "kpi" / "eval_kpi_summary.json"),
                    "--csv-output",
                    str(run_root / "kpi" / "eval_kpi_summary.csv"),
                ]
                print("\n=== Re-summarize existing eval ===")
                print(" ".join(summarize_command))
                rc = subprocess.run(summarize_command, cwd=root).returncode
                if rc != 0:
                    return rc

            kpi = load_json(run_root / "kpi" / "eval_kpi_summary.json")
            coord = kpi.get("coordination") or {}
            rows.append(
                {
                    "source_run_id": source_run_id,
                    "policy_seed": "" if args.source_run_id else policy_seed,
                    "evaluation_seed": policy_seed,
                    "split_id": split_id,
                    "group": group,
                    "run_id": eval_run_id,
                    "episodes": kpi.get("episodes"),
                    "sentinel_win_rate": kpi.get("sentinel_win_rate"),
                    "runner_win_rate": kpi.get("runner_win_rate"),
                    "escape_rate": kpi.get("escape_rate"),
                    "mean_time_to_first_capture_seconds": kpi.get("mean_time_to_first_capture_seconds"),
                    "mean_time_to_full_capture_seconds": kpi.get("mean_time_to_full_capture_seconds"),
                    "pincer_episode_rate": coord.get("pincer_episode_rate"),
                    "corridor_block_episode_rate": coord.get("corridor_block_episode_rate"),
                    "exit_denial_episode_rate": coord.get("exit_denial_episode_rate"),
                    "trap_success_rate": coord.get("trap_success_rate"),
                }
            )

    if rows and not args.skip_finalize:
        aggregate_dir = root / args.results_dir / "aggregate"
        write_aggregate(rows, aggregate_dir)
        if not args.dry_run:
            audit_command = [
                sys.executable,
                "scripts/audit_publication_eval_matrix.py",
                "--aggregate",
                str(aggregate_dir / "publication_eval_summary.json"),
                "--results-dir",
                str(root / args.results_dir),
                "--output",
                str(aggregate_dir / "publication_eval_audit.json"),
                "--matrix",
                args.matrix,
            ]
            if target_episodes:
                audit_command.extend(["--enforce-episode-target", "--expected-episodes", str(target_episodes)])
            if not args.source_run_id:
                audit_command.append("--enforce-topology-provenance")
            audit_rc = subprocess.run(audit_command, cwd=root).returncode
            if audit_rc != 0:
                return audit_rc

            statistics_command = [
                sys.executable,
                "scripts/analyze_publication_statistics.py",
                "--aggregate",
                str(aggregate_dir / "publication_eval_summary.csv"),
                "--results-dir",
                str(root / args.results_dir),
                "--output-dir",
                str(aggregate_dir / "statistics"),
            ]
            statistics_rc = subprocess.run(statistics_command, cwd=root).returncode
            if statistics_rc != 0:
                return statistics_rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
