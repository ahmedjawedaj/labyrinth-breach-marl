#!/usr/bin/env python3
"""Compute paired policy/topology effects for one publication ablation."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from analyze_publication_statistics import (
    build_episode_records,
    json_safe,
    layout_balanced_metric,
    mean_metric,
    percentile,
    read_csv,
    resolve_run_root,
)


EPISODE_METRICS = ("sentinel_win", "escape", "episode_duration_seconds", "full_capture_seconds")
KPI_METRICS = {
    "runner_survival_seconds": ("runner_survival_time_seconds_mean",),
    "sentinel_target_reacquisition_seconds": ("target_reacquisition", "mean_seconds"),
    "pincer_episode_rate": ("coordination", "pincer_episode_rate"),
    "pincer_events_per_episode": ("coordination", "pincer_events_per_episode"),
    "corridor_block_episode_rate": ("coordination", "corridor_block_episode_rate"),
    "corridor_block_events_per_episode": ("coordination", "corridor_block_events_per_episode"),
    "exit_denial_episode_rate": ("coordination", "exit_denial_episode_rate"),
    "exit_denial_events_per_episode": ("coordination", "exit_denial_events_per_episode"),
    "trap_episode_rate": ("coordination", "trap_episode_rate"),
    "trap_success_rate": ("coordination", "trap_success_rate"),
    "sentinel_spread_meters": ("spatial_coordination", "sentinel_spread_meters_mean"),
    "runner_separation_meters": ("spatial_coordination", "runner_separation_meters_mean"),
    "captures_per_meter": ("path_efficiency", "captures_per_meter"),
    "runner_path_meters_per_episode": ("path_efficiency", "runner_path_meters_per_episode"),
    "route_change_degrees": ("dynamic_route_change_proxy", "mean_abs_heading_change_degrees"),
    "route_change_rate_ge_45": ("dynamic_route_change_proxy", "rate_at_least_45_degrees"),
    "stall_step_fraction": ("wall_collision_recovery_time_proxy", "value"),
}


def cells(records: list[dict]) -> dict[tuple[str, str, str], list[dict]]:
    grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for record in records:
        grouped[(record["policy_id"], record["layout_id"], record["group"])].append(record)
    return grouped


def nested_number(payload: dict, path: tuple[str, ...]) -> float | None:
    value: object = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def load_kpi_cells(index_rows: list[dict[str, str]], results_root: Path) -> dict[tuple[str, str, str], dict]:
    output: dict[tuple[str, str, str], dict] = {}
    for row in index_rows:
        policy_seed = (row.get("policy_seed") or "").strip()
        policy_id = policy_seed or str(row.get("source_run_id") or "legacy_checkpoint")
        key = (policy_id, row["split_id"], row["group"])
        kpi_path = resolve_run_root(results_root, row) / "kpi" / "eval_kpi_summary.json"
        if not kpi_path.exists():
            raise FileNotFoundError(f"Missing KPI summary: {kpi_path}")
        output[key] = json.loads(kpi_path.read_text(encoding="utf-8"))
    return output


def bootstrap_paired_effect(
    full_cells: dict[tuple[str, str, str], list[dict]],
    ablated_cells: dict[tuple[str, str, str], list[dict]],
    group: str,
    metric: str,
    replicates: int,
    rng: random.Random,
) -> tuple[float, float]:
    common = sorted(set(full_cells) & set(ablated_cells))
    policy_ids = sorted({key[0] for key in common if key[2] == group})
    if len(policy_ids) < 2:
        return float("nan"), float("nan")
    layouts_by_policy = {
        policy_id: sorted(key[1] for key in common if key[0] == policy_id and key[2] == group)
        for policy_id in policy_ids
    }

    estimates: list[float] = []
    for _ in range(replicates):
        deltas: list[float] = []
        for _policy in policy_ids:
            policy_id = rng.choice(policy_ids)
            layouts = layouts_by_policy[policy_id]
            for _layout in layouts:
                layout_id = rng.choice(layouts)
                key = (policy_id, layout_id, group)
                full_episodes = full_cells[key]
                ablated_episodes = ablated_cells[key]
                sampled_full = [rng.choice(full_episodes) for _episode in full_episodes]
                sampled_ablated = [rng.choice(ablated_episodes) for _episode in ablated_episodes]
                full_mean = mean_metric(sampled_full, metric)
                ablated_mean = mean_metric(sampled_ablated, metric)
                if math.isfinite(full_mean) and math.isfinite(ablated_mean):
                    deltas.append(full_mean - ablated_mean)
        if deltas:
            estimates.append(statistics.fmean(deltas))
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def bootstrap_paired_cell_effect(rows: list[dict], replicates: int, rng: random.Random) -> tuple[float, float]:
    by_policy: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_policy[str(row["policy_id"])].append(float(row["full_minus_ablated"]))
    policy_ids = sorted(by_policy)
    if len(policy_ids) < 2:
        return float("nan"), float("nan")
    estimates: list[float] = []
    for _ in range(replicates):
        sampled: list[float] = []
        for _policy in policy_ids:
            policy_id = rng.choice(policy_ids)
            layout_deltas = by_policy[policy_id]
            sampled.extend(rng.choice(layout_deltas) for _layout in layout_deltas)
        estimates.append(statistics.fmean(sampled))
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-aggregate", type=Path, required=True)
    parser.add_argument("--full-results-dir", type=Path, required=True)
    parser.add_argument("--ablated-aggregate", type=Path, required=True)
    parser.add_argument("--ablated-results-dir", type=Path, required=True)
    parser.add_argument("--ablation-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-replicates", type=int, default=10000)
    parser.add_argument("--bootstrap-seed", type=int, default=2026)
    args = parser.parse_args()

    full_index = read_csv(args.full_aggregate)
    ablated_index = read_csv(args.ablated_aggregate)
    full_records = build_episode_records(full_index, args.full_results_dir)
    ablated_records = build_episode_records(ablated_index, args.ablated_results_dir)
    full_cells = cells(full_records)
    ablated_cells = cells(ablated_records)
    full_kpis = load_kpi_cells(full_index, args.full_results_dir)
    ablated_kpis = load_kpi_cells(ablated_index, args.ablated_results_dir)
    common = sorted(set(full_cells) & set(ablated_cells))
    if not common:
        raise RuntimeError("No matched policy/layout/group cells between full and ablated conditions.")

    rng = random.Random(args.bootstrap_seed)
    paired_rows: list[dict] = []
    summary_rows: list[dict] = []
    for key in common:
        policy_id, layout_id, group = key
        for metric in EPISODE_METRICS:
            full_mean = mean_metric(full_cells[key], metric)
            ablated_mean = mean_metric(ablated_cells[key], metric)
            if not math.isfinite(full_mean) or not math.isfinite(ablated_mean):
                continue
            paired_rows.append(
                {
                    "ablation_id": args.ablation_id,
                    "policy_id": policy_id,
                    "layout_id": layout_id,
                    "group": group,
                    "metric": metric,
                    "source": "episode_log",
                    "full_mean": full_mean,
                    "ablated_mean": ablated_mean,
                    "full_minus_ablated": full_mean - ablated_mean,
                }
            )

        if key not in full_kpis or key not in ablated_kpis:
            continue
        for metric, path in KPI_METRICS.items():
            full_mean = nested_number(full_kpis[key], path)
            ablated_mean = nested_number(ablated_kpis[key], path)
            if full_mean is None or ablated_mean is None:
                continue
            paired_rows.append(
                {
                    "ablation_id": args.ablation_id,
                    "policy_id": policy_id,
                    "layout_id": layout_id,
                    "group": group,
                    "metric": metric,
                    "source": "eval_kpi_summary",
                    "full_mean": full_mean,
                    "ablated_mean": ablated_mean,
                    "full_minus_ablated": full_mean - ablated_mean,
                }
            )

    full_by_policy = _group(full_records, lambda row: row["policy_id"])
    ablated_by_policy = _group(ablated_records, lambda row: row["policy_id"])
    for policy_id in sorted(set(full_by_policy) & set(ablated_by_policy)):
        for metric in ("sentinel_win", "escape"):
            full_seen = [row for row in full_by_policy[policy_id] if row["group"] == "seen"]
            full_held = [row for row in full_by_policy[policy_id] if row["group"] == "unseen"]
            ablated_seen = [row for row in ablated_by_policy[policy_id] if row["group"] == "seen"]
            ablated_held = [row for row in ablated_by_policy[policy_id] if row["group"] == "unseen"]
            full_gap = mean_metric(full_seen, metric) - layout_balanced_metric(full_held, metric)
            ablated_gap = mean_metric(ablated_seen, metric) - layout_balanced_metric(ablated_held, metric)
            if not math.isfinite(full_gap) or not math.isfinite(ablated_gap):
                continue
            paired_rows.append(
                {
                    "ablation_id": args.ablation_id,
                    "policy_id": policy_id,
                    "layout_id": "layout_balanced_held_out",
                    "group": "seen_vs_unseen",
                    "metric": f"absolute_generalization_gap_{metric}",
                    "source": "publication_statistics",
                    "full_mean": abs(full_gap),
                    "ablated_mean": abs(ablated_gap),
                    "full_minus_ablated": abs(full_gap) - abs(ablated_gap),
                }
            )

    for (group, metric), rows in sorted(_group(paired_rows, lambda row: (row["group"], row["metric"])).items()):
        deltas = [float(row["full_minus_ablated"]) for row in rows]
        sample_sd = statistics.stdev(deltas) if len(deltas) > 1 else float("nan")
        effect_dz = statistics.fmean(deltas) / sample_sd if sample_sd > 0 else float("nan")
        source = str(rows[0]["source"])
        if source == "episode_log":
            ci_low, ci_high = bootstrap_paired_effect(
                full_cells,
                ablated_cells,
                group,
                metric,
                args.bootstrap_replicates,
                rng,
            )
        else:
            ci_low, ci_high = bootstrap_paired_cell_effect(rows, args.bootstrap_replicates, rng)
        positive = sum(delta > 0 for delta in deltas)
        negative = sum(delta < 0 for delta in deltas)
        summary_rows.append(
            {
                "ablation_id": args.ablation_id,
                "group": group,
                "metric": metric,
                "source": source,
                "matched_cells": len(deltas),
                "policy_seeds": len({row["policy_id"] for row in rows}),
                "mean_full_minus_ablated": statistics.fmean(deltas),
                "paired_sample_std": sample_sd,
                "paired_effect_dz": effect_dz,
                "sign_consistency": max(positive, negative) / len(deltas),
                "hierarchical_bootstrap_low": ci_low,
                "hierarchical_bootstrap_high": ci_high,
            }
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(args.output_dir / "paired_cells.csv", paired_rows)
    _write_csv(args.output_dir / "paired_effects.csv", summary_rows)
    payload = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "ablation_id": args.ablation_id,
        "effect_convention": "full_minus_ablated",
        "bootstrap_replicates": args.bootstrap_replicates,
        "bootstrap_seed": args.bootstrap_seed,
        "matched_cell_count": len(common),
        "effects": summary_rows,
    }
    (args.output_dir / "paired_effects.json").write_text(
        json.dumps(json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote paired ablation effects: {args.output_dir}")
    return 0


def _group(rows: list[dict], key) -> dict[object, list[dict]]:
    grouped: dict[object, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[key(row)].append(row)
    return grouped


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise RuntimeError(f"No rows available for {path.name}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
