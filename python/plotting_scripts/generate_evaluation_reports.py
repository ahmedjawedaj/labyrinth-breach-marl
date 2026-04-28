#!/usr/bin/env python3
"""Generate evaluation plots and summary tables under results/."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing JSON file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected object JSON at {path}")
    return data


def nested(data: dict[str, Any], *keys: str) -> float | None:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    if current is None:
        return None
    try:
        return float(current)
    except (TypeError, ValueError):
        return None


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def plot_two_group_bars(
    title: str,
    ylabel: str,
    labels: list[str],
    seen_values: list[float],
    unseen_values: list[float],
    output_path: Path,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("matplotlib is required to generate figures. Install dependencies from requirements.txt.") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    x = range(len(labels))
    width = 0.38
    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 1.2), 5))
    ax.bar([idx - width / 2 for idx in x], seen_values, width=width, label="Seen")
    ax.bar([idx + width / 2 for idx in x], unseen_values, width=width, label="Unseen")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def plot_single_bar(
    title: str,
    ylabel: str,
    labels: list[str],
    values: list[float],
    output_path: Path,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("matplotlib is required to generate figures. Install dependencies from requirements.txt.") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 1.1), 5))
    ax.bar(labels, values)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def build_core_table(seen_core: dict[str, Any], unseen_core: dict[str, Any]) -> list[dict[str, Any]]:
    metric_specs = [
        ("sentinel_win_rate", ("win_rate", "sentinel_win_rate")),
        ("runner_win_rate", ("win_rate", "runner_win_rate")),
        ("exit_success_rate", ("exit_success", "exit_success_rate")),
        ("avg_runner_survival_time_seconds", ("survival_time", "avg_runner_survival_time_seconds")),
        ("avg_first_capture_time_seconds", ("capture_times", "avg_first_capture_time_seconds")),
        ("avg_full_capture_time_seconds", ("capture_times", "avg_full_capture_time_seconds")),
    ]
    rows: list[dict[str, Any]] = []
    for metric_name, key_path in metric_specs:
        seen_value = nested(seen_core, *key_path)
        unseen_value = nested(unseen_core, *key_path)
        rows.append({"metric": metric_name, "seen": seen_value, "unseen": unseen_value})
    return rows


def build_coordination_table(seen_coord: dict[str, Any], unseen_coord: dict[str, Any]) -> list[dict[str, Any]]:
    metric_specs = [
        ("pincer_rate", ("coordination_metrics", "pincer_rate", "episodes_with_pincer_rate")),
        ("trap_frequency", ("coordination_metrics", "trap_frequency", "avg_trap_formations_per_episode")),
        ("sentinel_spread", ("coordination_metrics", "sentinel_spread", "avg_pairwise_distance")),
        ("runner_separation", ("coordination_metrics", "runner_separation", "avg_pairwise_distance")),
        ("corridor_block_avg", ("coordination_metrics", "corridor_block_count", "avg_per_episode")),
        ("exit_denial_avg", ("coordination_metrics", "exit_denial_count", "avg_per_episode")),
    ]
    rows: list[dict[str, Any]] = []
    for metric_name, key_path in metric_specs:
        rows.append(
            {
                "metric": metric_name,
                "seen": nested(seen_coord, *key_path),
                "unseen": nested(unseen_coord, *key_path),
            }
        )
    return rows


def build_path_table(seen_path: dict[str, Any], unseen_path: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant in ("static", "dynamic"):
        rows.append(
            {
                "variant": variant,
                "metric": "runner_path_efficiency_avg",
                "seen": nested(seen_path, "path_metrics", variant, "runner_path_efficiency_avg"),
                "unseen": nested(unseen_path, "path_metrics", variant, "runner_path_efficiency_avg"),
            }
        )
        rows.append(
            {
                "variant": variant,
                "metric": "runner_shortest_vs_actual_ratio_avg",
                "seen": nested(seen_path, "path_metrics", variant, "runner_shortest_vs_actual_ratio_avg"),
                "unseen": nested(unseen_path, "path_metrics", variant, "runner_shortest_vs_actual_ratio_avg"),
            }
        )
    return rows


def plot_table_rows(rows: list[dict[str, Any]], title: str, ylabel: str, output_path: Path) -> None:
    filtered = [row for row in rows if row["seen"] is not None and row["unseen"] is not None]
    if not filtered:
        return
    labels = [row.get("metric") if not row.get("variant") else f"{row['variant']}:{row['metric']}" for row in filtered]
    seen_values = [float(row["seen"]) for row in filtered]
    unseen_values = [float(row["unseen"]) for row in filtered]
    plot_two_group_bars(title, ylabel, labels, seen_values, unseen_values, output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seen-core", type=Path, required=True, help="Seen core_metrics summary JSON.")
    parser.add_argument("--unseen-core", type=Path, required=True, help="Unseen core_metrics summary JSON.")
    parser.add_argument("--seen-coordination", type=Path, required=True, help="Seen coordination summary JSON.")
    parser.add_argument("--unseen-coordination", type=Path, required=True, help="Unseen coordination summary JSON.")
    parser.add_argument("--seen-path", type=Path, required=True, help="Seen path metrics summary JSON.")
    parser.add_argument("--unseen-path", type=Path, required=True, help="Unseen path metrics summary JSON.")
    parser.add_argument(
        "--generalization-drop",
        type=Path,
        required=True,
        help="Seen-vs-unseen drop summary JSON.",
    )
    parser.add_argument("--results-dir", type=Path, default=Path("results"), help="Base results output directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    seen_core = load_json(args.seen_core)
    unseen_core = load_json(args.unseen_core)
    seen_coord = load_json(args.seen_coordination)
    unseen_coord = load_json(args.unseen_coordination)
    seen_path = load_json(args.seen_path)
    unseen_path = load_json(args.unseen_path)
    drop_summary = load_json(args.generalization_drop)

    tables_dir = args.results_dir / "tables"
    figures_dir = args.results_dir / "figures"

    core_rows = build_core_table(seen_core, unseen_core)
    coord_rows = build_coordination_table(seen_coord, unseen_coord)
    path_rows = build_path_table(seen_path, unseen_path)
    drop_rows = drop_summary.get("generalization_drop_table", [])
    if not isinstance(drop_rows, list):
        drop_rows = []

    write_csv(tables_dir / "core_metrics_comparison.csv", ["metric", "seen", "unseen"], core_rows)
    write_csv(tables_dir / "coordination_metrics_comparison.csv", ["metric", "seen", "unseen"], coord_rows)
    write_csv(tables_dir / "path_metrics_comparison.csv", ["variant", "metric", "seen", "unseen"], path_rows)
    if drop_rows:
        write_csv(
            tables_dir / "generalization_drop_table.csv",
            [
                "metric",
                "seen_value",
                "unseen_value",
                "absolute_drop",
                "relative_drop_percent",
                "higher_is_better",
                "status",
            ],
            [row for row in drop_rows if isinstance(row, dict)],
        )

    plot_table_rows(core_rows, "Core Metrics: Seen vs Unseen", "Metric Value", figures_dir / "core_metrics_seen_vs_unseen.png")
    plot_table_rows(
        coord_rows,
        "Coordination Metrics: Seen vs Unseen",
        "Metric Value",
        figures_dir / "coordination_metrics_seen_vs_unseen.png",
    )
    plot_table_rows(path_rows, "Path Metrics: Seen vs Unseen", "Metric Value", figures_dir / "path_metrics_seen_vs_unseen.png")

    drop_plot_rows = [
        row
        for row in drop_rows
        if isinstance(row, dict)
        and row.get("status") == "ok"
        and row.get("relative_drop_percent") is not None
    ]
    if drop_plot_rows:
        labels = [str(row["metric"]) for row in drop_plot_rows]
        values = [float(row["relative_drop_percent"]) for row in drop_plot_rows]
        plot_single_bar(
            "Generalization Drop (Seen -> Unseen)",
            "Relative Drop (%)",
            labels,
            values,
            figures_dir / "generalization_drop_percent.png",
        )

    manifest = {
        "schema_version": 1,
        "tables": [
            str(tables_dir / "core_metrics_comparison.csv"),
            str(tables_dir / "coordination_metrics_comparison.csv"),
            str(tables_dir / "path_metrics_comparison.csv"),
            str(tables_dir / "generalization_drop_table.csv"),
        ],
        "figures": [
            str(figures_dir / "core_metrics_seen_vs_unseen.png"),
            str(figures_dir / "coordination_metrics_seen_vs_unseen.png"),
            str(figures_dir / "path_metrics_seen_vs_unseen.png"),
            str(figures_dir / "generalization_drop_percent.png"),
        ],
    }
    (args.results_dir / "metrics").mkdir(parents=True, exist_ok=True)
    manifest_path = args.results_dir / "metrics" / "evaluation_report_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Wrote tables to: {tables_dir}")
    print(f"Wrote figures to: {figures_dir}")
    print(f"Wrote report manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
