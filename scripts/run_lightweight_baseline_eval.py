#!/usr/bin/env python3
"""Run low-cost evaluation-only random and heuristic baselines.

This is intentionally smaller than the official publication matrix. It reuses
the fixed-checkpoint ML-Agents inference path and KPI summarizer, while the
Unity controller overrides received actions with the requested baseline policy.
The retained evidence level is KPI/metadata summaries; rerun without cleanup if
full raw CSV logs are required for a formal evidence pack.
"""

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


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML is required.")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def metric(summary: dict, *keys: str) -> float:
    current = summary
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return 0.0
        current = current[key]
    return float(current) if isinstance(current, (int, float)) else 0.0


def run_command(command: list[str], root: Path) -> int:
    print(" ".join(command), flush=True)
    return subprocess.run(command, cwd=root).returncode


def write_aggregate(rows: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "baseline_eval_summary.csv"
    json_path = output_dir / "baseline_eval_summary.json"
    fields = [
        "baseline_policy",
        "source_run_id",
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
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})

    grouped: dict[str, dict[str, list[float]]] = {}
    for row in rows:
        key = f"{row['baseline_policy']}|{row['group']}"
        bucket = grouped.setdefault(key, {})
        for metric_name in (
            "episodes",
            "sentinel_win_rate",
            "runner_win_rate",
            "escape_rate",
            "pincer_episode_rate",
            "corridor_block_episode_rate",
            "exit_denial_episode_rate",
            "trap_success_rate",
        ):
            bucket.setdefault(metric_name, []).append(float(row[metric_name]))

    group_rows = []
    for key, values in sorted(grouped.items()):
        baseline_policy, group = key.split("|", 1)
        group_rows.append(
            {
                "baseline_policy": baseline_policy,
                "group": group,
                **{
                    f"{metric_name}_mean": sum(metric_values) / max(1, len(metric_values))
                    for metric_name, metric_values in values.items()
                },
                "cells": len(next(iter(values.values()))) if values else 0,
            }
        )

    json_path.write_text(
        json.dumps({"rows": rows, "group_summary": group_rows}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote baseline CSV: {csv_path}")
    print(f"Wrote baseline JSON: {json_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", default="configs/experiment_manifests/official_publication_eval_matrix.yaml")
    parser.add_argument("--source-run-id", default="LB_3v2_official_seed42_stage4")
    parser.add_argument("--source-results-dir", default="results")
    parser.add_argument("--results-dir", default="results/lightweight_baselines")
    parser.add_argument("--baseline-policy", choices=("random", "heuristic"), action="append")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--target-episodes", type=int, default=25)
    parser.add_argument("--max-runtime-seconds", type=int, default=900)
    parser.add_argument("--timeout-wait", type=int, default=120)
    parser.add_argument("--env")
    parser.add_argument("--allow-cpu", action="store_true")
    parser.add_argument("--no-graphics", action="store_true")
    parser.add_argument("--base-port", type=int, default=5300)
    parser.add_argument("--resume-completed", action="store_true")
    parser.add_argument("--force-output", action="store_true")
    parser.add_argument("--aggregate-only", action="store_true")
    args = parser.parse_args()

    root = repo_root()
    matrix = load_yaml(root / args.matrix)
    baseline_policies = args.baseline_policy or ["random", "heuristic"]
    rows: list[dict] = []

    for baseline_index, baseline_policy in enumerate(baseline_policies):
        for split_index, split in enumerate(matrix["splits"]):
            split_id = str(split["id"])
            group = str(split.get("group", split_id))
            run_id = f"LB_lightweight_{baseline_policy}_{split_id}_{args.target_episodes}ep_seed{args.seed}"
            output_dir = Path(args.results_dir) / baseline_policy
            run_root = root / output_dir / run_id
            kpi_path = run_root / "kpi" / "eval_kpi_summary.json"
            status_path = run_root / "metadata" / "evaluation_status.json"
            reusable = False
            if args.resume_completed and kpi_path.is_file() and status_path.is_file():
                status = load_json(status_path)
                reusable = (
                    status.get("success") is True
                    and int(status.get("completed_episodes") or 0) >= args.target_episodes
                    and status.get("baseline_policy") == baseline_policy
                )

            if not args.aggregate_only and not reusable:
                command = [
                    sys.executable,
                    "scripts/evaluate_policy.py",
                    "--manifest",
                    split["manifest"],
                    "--source-run-id",
                    args.source_run_id,
                    "--source-results-dir",
                    args.source_results_dir,
                    "--output-dir",
                    str(output_dir),
                    "--seed",
                    str(args.seed),
                    "--eval-run-id",
                    run_id,
                    "--target-episodes",
                    str(args.target_episodes),
                    "--max-runtime-seconds",
                    str(args.max_runtime_seconds),
                    "--timeout-wait",
                    str(args.timeout_wait),
                    "--baseline-policy",
                    baseline_policy,
                    "--forbid-fallback-log-copy",
                    "--base-port",
                    str(args.base_port + baseline_index * 100 + split_index),
                ]
                if args.env:
                    command.extend(["--env", args.env])
                if args.allow_cpu:
                    command.append("--allow-cpu")
                if args.no_graphics:
                    command.append("--no-graphics")
                if args.force_output or args.resume_completed:
                    command.append("--force-output")
                rc = run_command(command, root)
                if rc != 0:
                    return rc
            elif reusable:
                print(f"Reusing completed baseline cell: {run_id}")

            if not kpi_path.is_file():
                raise FileNotFoundError(f"Missing KPI summary for baseline cell: {kpi_path}")
            summary = load_json(kpi_path)
            rows.append(
                {
                    "baseline_policy": baseline_policy,
                    "source_run_id": args.source_run_id,
                    "evaluation_seed": args.seed,
                    "split_id": split_id,
                    "group": group,
                    "run_id": run_id,
                    "episodes": int(summary.get("episodes", 0)),
                    "sentinel_win_rate": metric(summary, "sentinel_win_rate"),
                    "runner_win_rate": metric(summary, "runner_win_rate"),
                    "escape_rate": metric(summary, "escape_rate"),
                    "mean_time_to_first_capture_seconds": metric(summary, "mean_time_to_first_capture_seconds"),
                    "mean_time_to_full_capture_seconds": metric(summary, "mean_time_to_full_capture_seconds"),
                    "pincer_episode_rate": metric(summary, "coordination", "pincer_episode_rate"),
                    "corridor_block_episode_rate": metric(summary, "coordination", "corridor_block_episode_rate"),
                    "exit_denial_episode_rate": metric(summary, "coordination", "exit_denial_episode_rate"),
                    "trap_success_rate": metric(summary, "trap_success_rate"),
                }
            )

    write_aggregate(rows, root / args.results_dir / "aggregate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
