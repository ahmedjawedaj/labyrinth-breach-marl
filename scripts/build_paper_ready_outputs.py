#!/usr/bin/env python3
"""Build paper-ready multi-seed tables and plots."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path

import matplotlib.pyplot as plt


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def safe_float(value: str | float | int | None) -> float:
    try:
        return float(value if value is not None else 0.0)
    except (TypeError, ValueError):
        return 0.0


def ensure_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")


def metric(stats_rows: list[dict], key: str) -> dict[str, float]:
    values = [safe_float(row.get(key)) for row in stats_rows]
    return {
        "mean": statistics.fmean(values) if values else 0.0,
        "std": statistics.pstdev(values) if len(values) > 1 else 0.0,
        "min": min(values) if values else 0.0,
        "max": max(values) if values else 0.0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-family", required=True)
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 101, 202])
    parser.add_argument("--results-dir", default="results")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    results_root = root / args.results_dir
    summary_dir = results_root / args.experiment_family / "summary"
    plots_dir = results_root / args.experiment_family / "plots"
    reward_plot_dir = plots_dir / "reward"
    coord_plot_dir = plots_dir / "coordination"
    path_plot_dir = plots_dir / "path"
    summary_dir.mkdir(parents=True, exist_ok=True)
    reward_plot_dir.mkdir(parents=True, exist_ok=True)
    coord_plot_dir.mkdir(parents=True, exist_ok=True)
    path_plot_dir.mkdir(parents=True, exist_ok=True)

    final_seen_unseen_path = results_root / args.experiment_family / "eval" / "final_seen_unseen_summary.json"
    ensure_exists(final_seen_unseen_path, "final seen/unseen summary")
    final_seen_unseen = read_json(final_seen_unseen_path)

    seed_rows: list[dict] = []
    generalization_rows: list[dict] = []
    for seed in args.seeds:
        summary_item = next((item for item in final_seen_unseen.get("seed_summaries", []) if int(item.get("seed", -1)) == seed), None)
        if summary_item is None:
            raise RuntimeError(f"Missing seen/unseen summary for seed {seed}")
        seen_run_id = summary_item["seen_run_id"]
        unseen_run_id = summary_item["unseen_run_id"]
        seen_kpi_path = results_root / f"seed_{seed}" / "eval" / seen_run_id / "kpi" / "eval_kpi_summary.json"
        unseen_kpi_path = results_root / f"seed_{seed}" / "eval" / unseen_run_id / "kpi" / "eval_kpi_summary.json"
        ensure_exists(seen_kpi_path, f"seen KPI seed {seed}")
        ensure_exists(unseen_kpi_path, f"unseen KPI seed {seed}")
        seen_kpi = read_json(seen_kpi_path)
        unseen_kpi = read_json(unseen_kpi_path)

        row = {
            "seed": seed,
            "experiment_family": args.experiment_family,
            "seen_run_id": seen_run_id,
            "unseen_run_id": unseen_run_id,
            "seen_sentinel_win_rate": safe_float(seen_kpi.get("sentinel_win_rate")),
            "unseen_sentinel_win_rate": safe_float(unseen_kpi.get("sentinel_win_rate")),
            "seen_runner_win_rate": safe_float(seen_kpi.get("runner_win_rate")),
            "unseen_runner_win_rate": safe_float(unseen_kpi.get("runner_win_rate")),
            "seen_first_capture_time": safe_float(seen_kpi.get("mean_time_to_first_capture_seconds")),
            "unseen_first_capture_time": safe_float(unseen_kpi.get("mean_time_to_first_capture_seconds")),
            "seen_full_capture_time": safe_float(seen_kpi.get("mean_time_to_full_capture_seconds")),
            "unseen_full_capture_time": safe_float(unseen_kpi.get("mean_time_to_full_capture_seconds")),
            "seen_survival_time": safe_float(seen_kpi.get("runner_survival_time_seconds_mean")),
            "unseen_survival_time": safe_float(unseen_kpi.get("runner_survival_time_seconds_mean")),
            "seen_path_ratio": safe_float((seen_kpi.get("path_efficiency") or {}).get("shortest_path_vs_actual_ratio_proxy")),
            "unseen_path_ratio": safe_float((unseen_kpi.get("path_efficiency") or {}).get("shortest_path_vs_actual_ratio_proxy")),
            "seen_pincer_rate": safe_float((seen_kpi.get("coordination") or {}).get("pincer_rate")),
            "unseen_pincer_rate": safe_float((unseen_kpi.get("coordination") or {}).get("pincer_rate")),
            "seen_corridor_rate": safe_float((seen_kpi.get("coordination") or {}).get("corridor_block_rate")),
            "unseen_corridor_rate": safe_float((unseen_kpi.get("coordination") or {}).get("corridor_block_rate")),
            "seen_exit_denial_rate": safe_float((seen_kpi.get("coordination") or {}).get("exit_denial_rate")),
            "unseen_exit_denial_rate": safe_float((unseen_kpi.get("coordination") or {}).get("exit_denial_rate")),
        }
        seed_rows.append(row)
        generalization_rows.append(
            {
                "seed": seed,
                "experiment_family": args.experiment_family,
                "seen_run_id": seen_run_id,
                "unseen_run_id": unseen_run_id,
                "win_rate_drop_sentinel": row["seen_sentinel_win_rate"] - row["unseen_sentinel_win_rate"],
                "capture_time_delta_full": row["unseen_full_capture_time"] - row["seen_full_capture_time"],
                "survival_time_delta_runner": row["unseen_survival_time"] - row["seen_survival_time"],
                "path_efficiency_delta": row["unseen_path_ratio"] - row["seen_path_ratio"],
                "coordination_pincer_delta": row["unseen_pincer_rate"] - row["seen_pincer_rate"],
                "coordination_corridor_delta": row["unseen_corridor_rate"] - row["seen_corridor_rate"],
                "coordination_exit_denial_delta": row["unseen_exit_denial_rate"] - row["seen_exit_denial_rate"],
            }
        )

    # Multi-seed summary table.
    summary_fields = [
        "seen_sentinel_win_rate",
        "unseen_sentinel_win_rate",
        "seen_full_capture_time",
        "unseen_full_capture_time",
        "seen_survival_time",
        "unseen_survival_time",
        "seen_path_ratio",
        "unseen_path_ratio",
        "seen_pincer_rate",
        "unseen_pincer_rate",
    ]
    multiseed_rows: list[dict] = []
    for field in summary_fields:
        stats = metric(seed_rows, field)
        multiseed_rows.append(
            {
                "metric": field,
                "mean": stats["mean"],
                "std": stats["std"],
                "min": stats["min"],
                "max": stats["max"],
                "per_seed": "; ".join(f"{row['seed']}:{row[field]:0.6f}" for row in seed_rows),
                "experiment_family": args.experiment_family,
                "run_ids": "; ".join(f"{row['seed']}:{row['seen_run_id']}|{row['unseen_run_id']}" for row in seed_rows),
            }
        )
    with (summary_dir / "multiseed_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(multiseed_rows[0].keys()))
        writer.writeheader()
        for row in multiseed_rows:
            writer.writerow(row)

    with (summary_dir / "generalization_comparison.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(generalization_rows[0].keys()))
        writer.writeheader()
        for row in generalization_rows:
            writer.writerow(row)

    # Ablation comparison table from existing outputs; strict on all seeds.
    ablation_rows: list[dict] = []
    for seed in args.seeds:
        memory_path = results_root / f"seed_{seed}" / "memory_ablation_comparison.csv"
        reward_path = results_root / f"seed_{seed}" / "reward_config_comparison.csv"
        wall_path = results_root / f"seed_{seed}" / "static_dynamic_wall_impact.csv"
        ensure_exists(memory_path, f"memory ablation comparison seed {seed}")
        ensure_exists(reward_path, f"reward ablation comparison seed {seed}")
        ensure_exists(wall_path, f"wall impact comparison seed {seed}")
        memory_rows = read_csv(memory_path)
        reward_rows = read_csv(reward_path)
        wall_rows = read_csv(wall_path)
        ablation_rows.append(
            {
                "seed": seed,
                "experiment_family": args.experiment_family,
                "memory_metrics_count": len(memory_rows),
                "reward_config_rows": len(reward_rows),
                "wall_condition_rows": len(wall_rows),
                "memory_file": str(memory_path.relative_to(root)),
                "reward_file": str(reward_path.relative_to(root)),
                "wall_file": str(wall_path.relative_to(root)),
            }
        )
    with (summary_dir / "ablation_comparison.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ablation_rows[0].keys()))
        writer.writeheader()
        for row in ablation_rows:
            writer.writerow(row)

    # Plot helpers
    seeds = [row["seed"] for row in seed_rows]

    # Reward plot
    reward_components = [
        ("terminal", [safe_float((read_json(results_root / f"seed_{seed}" / "eval" / row["seen_run_id"] / "kpi" / "eval_kpi_summary.json").get("exploration_rewards_penalties") or {}).get("exploration_bonus_total")) for seed, row in zip(seeds, seed_rows)]),
        ("penalties", [safe_float((read_json(results_root / f"seed_{seed}" / "eval" / row["seen_run_id"] / "kpi" / "eval_kpi_summary.json").get("exploration_rewards_penalties") or {}).get("wall_loop_penalty_total")) for seed, row in zip(seeds, seed_rows)]),
    ]
    plt.figure(figsize=(9, 5))
    for name, values in reward_components:
        plt.plot(seeds, values, marker="o", label=name)
    plt.title("Reward Component Trends by Seed")
    plt.xlabel("Seed")
    plt.ylabel("Component Total (proxy)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(reward_plot_dir / "reward_components.png")
    plt.close()

    # Coordination plots
    plt.figure(figsize=(9, 5))
    plt.plot(seeds, [row["seen_pincer_rate"] for row in seed_rows], marker="o", label="pincer_rate")
    plt.plot(seeds, [row["seen_corridor_rate"] for row in seed_rows], marker="o", label="corridor_control")
    plt.plot(seeds, [row["seen_exit_denial_rate"] for row in seed_rows], marker="o", label="exit_denial")
    plt.title("Coordination KPIs by Seed (Seen)")
    plt.xlabel("Seed")
    plt.ylabel("Rate")
    plt.legend()
    plt.tight_layout()
    plt.savefig(coord_plot_dir / "coordination_metrics_seen.png")
    plt.close()

    # Path plots
    plt.figure(figsize=(9, 5))
    plt.plot(seeds, [row["seen_path_ratio"] for row in seed_rows], marker="o", label="seen_ratio")
    plt.plot(seeds, [row["unseen_path_ratio"] for row in seed_rows], marker="o", label="unseen_ratio")
    plt.title("Path Efficiency Ratio (Shortest/Actual Proxy)")
    plt.xlabel("Seed")
    plt.ylabel("Ratio")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path_plot_dir / "path_efficiency_ratio.png")
    plt.close()

    print(f"Paper-ready outputs generated under: {results_root / args.experiment_family}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
