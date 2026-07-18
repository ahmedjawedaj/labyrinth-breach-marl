#!/usr/bin/env python3
"""Compute canonical layout-balanced and hierarchical publication statistics."""

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
from typing import Callable


SENTINEL_WIN = "SentinelWinAllRunnersCaptured"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def safe_float(value: str | None) -> float:
    try:
        return float(value or 0.0)
    except ValueError:
        return 0.0


def percentile(values: list[float], probability: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        return float("nan"), float("nan")
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return max(0.0, center - half), min(1.0, center + half)


def resolve_run_root(results_root: Path, row: dict[str, str]) -> Path:
    policy_seed = (row.get("policy_seed") or "").strip()
    if policy_seed:
        seed_directory = f"policy_seed_{policy_seed}"
    else:
        seed_directory = f"evaluation_seed_{int(float(row['evaluation_seed']))}"
    return results_root / seed_directory / row["run_id"]


def build_episode_records(index_rows: list[dict[str, str]], results_root: Path) -> list[dict]:
    records: list[dict] = []
    for index_row in index_rows:
        run_root = resolve_run_root(results_root, index_row)
        episode_path = run_root / "logs" / "episode_log.csv"
        if not episode_path.exists():
            raise FileNotFoundError(f"Missing episode log: {episode_path}")
        policy_seed = (index_row.get("policy_seed") or "").strip()
        policy_id = policy_seed or str(index_row.get("source_run_id") or "legacy_checkpoint")
        for episode in read_csv(episode_path):
            outcome = episode.get("outcome") or ""
            records.append(
                {
                    "policy_id": policy_id,
                    "independent_policy_seed": bool(policy_seed),
                    "layout_id": index_row["split_id"],
                    "group": index_row["group"],
                    "run_id": index_row["run_id"],
                    "episode_id": episode.get("episode_id", ""),
                    "sentinel_win": 1.0 if outcome == SENTINEL_WIN else 0.0,
                    "escape": 1.0 if safe_float(episode.get("exit_count")) > 0 else 0.0,
                    "episode_duration_seconds": safe_float(episode.get("duration_seconds")),
                    "full_capture_seconds": (
                        safe_float(episode.get("duration_seconds")) if outcome == SENTINEL_WIN else None
                    ),
                }
            )
    return records


def metric_values(records: list[dict], metric: str) -> list[float]:
    return [float(record[metric]) for record in records if record.get(metric) is not None]


def mean_metric(records: list[dict], metric: str) -> float:
    values = metric_values(records, metric)
    return statistics.fmean(values) if values else float("nan")


def layout_balanced_metric(records: list[dict], metric: str) -> float:
    by_layout: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_layout[record["layout_id"]].append(record)
    values = [mean_metric(rows, metric) for rows in by_layout.values()]
    finite = [value for value in values if math.isfinite(value)]
    return statistics.fmean(finite) if finite else float("nan")


def hierarchical_bootstrap(
    records: list[dict],
    metric: str,
    replicates: int,
    rng: random.Random,
) -> tuple[float, float]:
    by_policy: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for record in records:
        by_policy[record["policy_id"]][record["layout_id"]].append(record)
    policy_ids = sorted(by_policy)
    if len(policy_ids) < 2:
        return float("nan"), float("nan")

    estimates: list[float] = []
    for _ in range(replicates):
        sampled_values: list[float] = []
        for _policy_index in policy_ids:
            policy_id = rng.choice(policy_ids)
            layouts = sorted(by_policy[policy_id])
            for _layout_index in layouts:
                layout_id = rng.choice(layouts)
                episodes = by_policy[policy_id][layout_id]
                sampled_episodes = [rng.choice(episodes) for _episode in episodes]
                sampled_values.extend(metric_values(sampled_episodes, metric))
        if sampled_values:
            estimates.append(statistics.fmean(sampled_values))
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def bootstrap_policy_generalization_gap(
    policy_records: list[dict],
    metric: str,
    replicates: int,
    rng: random.Random,
) -> tuple[float, float, float]:
    seen = [record for record in policy_records if record["group"] == "seen"]
    held_by_layout = _group_records(
        [record for record in policy_records if record["group"] == "unseen"],
        lambda row: row["layout_id"],
    )
    if not metric_values(seen, metric) or not held_by_layout:
        return float("nan"), float("nan"), float("nan")

    point = mean_metric(seen, metric) - layout_balanced_metric(
        [record for rows in held_by_layout.values() for record in rows],
        metric,
    )
    layout_ids = sorted(held_by_layout)
    estimates: list[float] = []
    for _ in range(replicates):
        sampled_seen = [rng.choice(seen) for _episode in seen]
        held_layout_means: list[float] = []
        for _layout in layout_ids:
            layout_id = rng.choice(layout_ids)
            episodes = held_by_layout[layout_id]
            sampled_episodes = [rng.choice(episodes) for _episode in episodes]
            value = mean_metric(sampled_episodes, metric)
            if math.isfinite(value):
                held_layout_means.append(value)
        seen_value = mean_metric(sampled_seen, metric)
        if math.isfinite(seen_value) and held_layout_means:
            estimates.append(seen_value - statistics.fmean(held_layout_means))
    return point, percentile(estimates, 0.025), percentile(estimates, 0.975)


def seed_layout_variance_components(records: list[dict], metric: str, group: str) -> dict:
    group_records = [record for record in records if record["group"] == group]
    policies = sorted({record["policy_id"] for record in group_records})
    layouts = sorted({record["layout_id"] for record in group_records})
    cells = _group_records(group_records, lambda row: (row["policy_id"], row["layout_id"]))
    if len(policies) < 2 or len(layouts) < 2:
        return {}
    if any((policy, layout) not in cells for policy in policies for layout in layouts):
        return {}

    cell_means = {
        cell: mean_metric(cell_records, metric)
        for cell, cell_records in cells.items()
    }
    if not all(math.isfinite(value) for value in cell_means.values()):
        return {}
    grand = statistics.fmean(cell_means.values())
    policy_means = {
        policy: statistics.fmean(cell_means[(policy, layout)] for layout in layouts)
        for policy in policies
    }
    layout_means = {
        layout: statistics.fmean(cell_means[(policy, layout)] for policy in policies)
        for layout in layouts
    }
    policy_ss = len(layouts) * sum((value - grand) ** 2 for value in policy_means.values())
    layout_ss = len(policies) * sum((value - grand) ** 2 for value in layout_means.values())
    residual_ss = sum(
        (cell_means[(policy, layout)] - policy_means[policy] - layout_means[layout] + grand) ** 2
        for policy in policies
        for layout in layouts
    )
    policy_ms = policy_ss / (len(policies) - 1)
    layout_ms = layout_ss / (len(layouts) - 1)
    residual_ms = residual_ss / ((len(policies) - 1) * (len(layouts) - 1))
    policy_variance = max(0.0, (policy_ms - residual_ms) / len(layouts))
    layout_variance = max(0.0, (layout_ms - residual_ms) / len(policies))
    interaction_residual_variance = max(0.0, residual_ms)
    total = policy_variance + layout_variance + interaction_residual_variance
    return {
        "group": group,
        "metric": metric,
        "policy_seeds": len(policies),
        "layouts": len(layouts),
        "policy_variance": policy_variance,
        "layout_variance": layout_variance,
        "policy_layout_interaction_plus_cell_error_variance": interaction_residual_variance,
        "policy_variance_fraction": policy_variance / total if total > 0 else 0.0,
        "layout_variance_fraction": layout_variance / total if total > 0 else 0.0,
        "interaction_plus_error_variance_fraction": (
            interaction_residual_variance / total if total > 0 else 0.0
        ),
    }


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-replicates", type=int, default=10000)
    parser.add_argument("--bootstrap-seed", type=int, default=2026)
    args = parser.parse_args()

    index_rows = read_csv(args.aggregate)
    records = build_episode_records(index_rows, args.results_dir)
    policy_ids = sorted({record["policy_id"] for record in records})
    independent_policy_ids = sorted(
        {record["policy_id"] for record in records if record["independent_policy_seed"]}
    )
    metrics = ("sentinel_win", "escape", "episode_duration_seconds", "full_capture_seconds")
    rng = random.Random(args.bootstrap_seed)

    cell_rows: list[dict] = []
    for (policy_id, layout_id, group), cell in sorted(
        _group_records(records, lambda row: (row["policy_id"], row["layout_id"], row["group"])).items()
    ):
        wins = int(sum(record["sentinel_win"] for record in cell))
        lower, upper = wilson(wins, len(cell))
        cell_rows.append(
            {
                "policy_id": policy_id,
                "layout_id": layout_id,
                "group": group,
                "episodes": len(cell),
                "sentinel_win_rate": mean_metric(cell, "sentinel_win"),
                "sentinel_win_wilson_low": lower,
                "sentinel_win_wilson_high": upper,
                "escape_rate": mean_metric(cell, "escape"),
                "mean_episode_duration_seconds": mean_metric(cell, "episode_duration_seconds"),
                "mean_full_capture_seconds": mean_metric(cell, "full_capture_seconds"),
            }
        )

    summary_rows: list[dict] = []
    for group, group_records in sorted(_group_records(records, lambda row: row["group"]).items()):
        for metric in metrics:
            per_policy = []
            for policy_id in policy_ids:
                policy_records = [record for record in group_records if record["policy_id"] == policy_id]
                if policy_records:
                    per_policy.append(layout_balanced_metric(policy_records, metric))
            finite_policy = [value for value in per_policy if math.isfinite(value)]
            ci_low, ci_high = hierarchical_bootstrap(
                group_records,
                metric,
                args.bootstrap_replicates,
                rng,
            )
            summary_rows.append(
                {
                    "group": group,
                    "metric": metric,
                    "episodes": len(group_records),
                    "policy_seeds": len(independent_policy_ids),
                    "layouts": len({record["layout_id"] for record in group_records}),
                    "episode_weighted_mean": mean_metric(group_records, metric),
                    "layout_balanced_mean": layout_balanced_metric(group_records, metric),
                    "policy_mean": statistics.fmean(finite_policy) if finite_policy else float("nan"),
                    "policy_sample_std": statistics.stdev(finite_policy) if len(finite_policy) > 1 else float("nan"),
                    "hierarchical_bootstrap_low": ci_low,
                    "hierarchical_bootstrap_high": ci_high,
                }
            )

    gap_rows: list[dict] = []
    for policy_id in policy_ids:
        policy_records = [record for record in records if record["policy_id"] == policy_id]
        for metric in metrics:
            gap, ci_low, ci_high = bootstrap_policy_generalization_gap(
                policy_records,
                metric,
                args.bootstrap_replicates,
                rng,
            )
            gap_rows.append(
                {
                    "policy_id": policy_id,
                    "metric": metric,
                    "seen_minus_layout_balanced_held_out": gap,
                    "bootstrap_low": ci_low,
                    "bootstrap_high": ci_high,
                    "held_out_layouts": len(
                        {
                            record["layout_id"]
                            for record in policy_records
                            if record["group"] == "unseen"
                        }
                    ),
                }
            )

    variance_rows = [
        row
        for group in sorted({record["group"] for record in records})
        for metric in metrics
        if (row := seed_layout_variance_components(records, metric, group))
    ]

    output_dir = args.output_dir
    write_csv(
        output_dir / "cell_statistics.csv",
        cell_rows,
        list(cell_rows[0]) if cell_rows else [],
    )
    write_csv(
        output_dir / "group_statistics.csv",
        summary_rows,
        list(summary_rows[0]) if summary_rows else [],
    )
    write_csv(
        output_dir / "generalization_gaps.csv",
        gap_rows,
        list(gap_rows[0]) if gap_rows else [],
    )
    write_csv(
        output_dir / "seed_layout_variance.csv",
        variance_rows,
        list(variance_rows[0]) if variance_rows else [],
    )
    payload = {
        "schema_version": 2,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "aggregate": str(args.aggregate),
        "results_dir": str(args.results_dir),
        "policy_ids": policy_ids,
        "independent_policy_seed_count": len(independent_policy_ids),
        "bootstrap_replicates": args.bootstrap_replicates,
        "bootstrap_seed": args.bootstrap_seed,
        "inference_warning": (
            None
            if len(independent_policy_ids) >= 2
            else "Hierarchical policy-level intervals are not estimable without independent policy seeds."
        ),
        "group_statistics": summary_rows,
        "generalization_gaps": gap_rows,
        "seed_layout_variance": variance_rows,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "publication_statistics.json").write_text(
        json.dumps(json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote statistics to: {output_dir}")
    print(payload["inference_warning"] or "Hierarchical intervals computed.")
    return 0


def _group_records(records: list[dict], key: Callable[[dict], object]) -> dict[object, list[dict]]:
    grouped: dict[object, list[dict]] = defaultdict(list)
    for record in records:
        grouped[key(record)].append(record)
    return grouped


if __name__ == "__main__":
    raise SystemExit(main())
