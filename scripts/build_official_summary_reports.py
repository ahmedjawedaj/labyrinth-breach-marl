#!/usr/bin/env python3
"""Build official summary CSV/JSON artifacts from current run-scoped outputs."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - repository environment includes PyYAML.
    yaml = None


OFFICIAL_SEEDS = [42, 101, 202]
EVAL_SPLITS = ("seen", "unseen")
FINAL_SUMMARY_FIELDS = [
    "seed",
    "seen_run_id",
    "unseen_run_id",
    "seen_sentinel_win_rate",
    "unseen_sentinel_win_rate",
    "seen_runner_win_rate",
    "unseen_runner_win_rate",
    "seen_full_capture_time",
    "unseen_full_capture_time",
    "seen_survival_time",
    "unseen_survival_time",
    "seen_path_ratio",
    "unseen_path_ratio",
    "seen_pincer_rate",
    "unseen_pincer_rate",
    "seen_corridor_rate",
    "unseen_corridor_rate",
    "seen_exit_denial_rate",
    "unseen_exit_denial_rate",
    "seen_capture_count_mean",
    "unseen_capture_count_mean",
    "sentinel_win_rate_drop",
    "runner_win_rate_increase",
    "capture_time_delta_seconds",
    "path_efficiency_delta",
    "exploration_time_proxy_delta_seconds",
    "coordination_capture_per_episode_delta",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required to parse evaluation matrices.")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def safe_float(value: Any) -> float:
    try:
        return float(value if value is not None else 0.0)
    except (TypeError, ValueError):
        return 0.0


def mean_from_rows(rows: list[dict[str, str]], key: str) -> float:
    values = [safe_float(row.get(key)) for row in rows]
    return statistics.fmean(values) if values else 0.0


def parse_eval_run(run_dir: Path) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    run_id = run_dir.name
    kpi_path = run_dir / "kpi" / "eval_kpi_summary.json"
    episode_path = run_dir / "logs" / "open_arena_episode_summary.csv"
    reward_path = run_dir / "logs" / "reward_breakdown.csv"
    event_path = run_dir / "logs" / "open_arena_events.csv"

    if not run_dir.exists():
        raise FileNotFoundError(f"Missing eval run directory for {run_id}: {run_dir}")

    missing = [path for path in (kpi_path, episode_path, reward_path, event_path) if not path.exists()]
    if missing:
        joined = "; ".join(str(path) for path in missing)
        raise FileNotFoundError(f"Missing eval artifacts for {run_id}: {joined}")

    kpi = load_json(kpi_path)
    episodes = read_csv_rows(episode_path)
    reward_rows = read_csv_rows(reward_path)
    try:
        event_rows = read_csv_rows(event_path)
    except Exception:
        event_rows = []
    return kpi, episodes, reward_rows, event_rows


def build_final_seen_unseen_summary(
    *,
    results_root: Path,
    eval_family: str,
    duration_minutes: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]]]:
    eval_root = results_root / eval_family / "eval"
    eval_root.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, str]] = []
    seen_unseen_by_seed: list[dict[str, Any]] = []

    for seed in OFFICIAL_SEEDS:
        seen_run_id = f"{eval_family}_seed{seed}_seen_{duration_minutes}m"
        unseen_run_id = f"{eval_family}_seed{seed}_unseen_{duration_minutes}m"
        seen_run_dir = results_root / f"seed_{seed}" / "eval" / seen_run_id
        unseen_run_dir = results_root / f"seed_{seed}" / "eval" / unseen_run_id

        try:
            seen_kpi, seen_episodes, _, _ = parse_eval_run(seen_run_dir)
            unseen_kpi, unseen_episodes, _, _ = parse_eval_run(unseen_run_dir)
        except FileNotFoundError as exc:
            missing_rows.append(
                {
                    "seed": seed,
                    "scope": "seen_unseen_eval",
                    "missing_artifact": str(exc),
                    "error": "Missing eval artifacts for official seen/unseen comparison.",
                }
            )
            continue

        seen_capture_count = mean_from_rows(seen_episodes, "capture_count")
        unseen_capture_count = mean_from_rows(unseen_episodes, "capture_count")

        seen_row = {
            "seed": seed,
            "seen_run_id": seen_run_id,
            "unseen_run_id": unseen_run_id,
            "seen_sentinel_win_rate": safe_float(seen_kpi.get("sentinel_win_rate")),
            "unseen_sentinel_win_rate": safe_float(unseen_kpi.get("sentinel_win_rate")),
            "seen_runner_win_rate": safe_float(seen_kpi.get("runner_win_rate")),
            "unseen_runner_win_rate": safe_float(unseen_kpi.get("runner_win_rate")),
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
            "seen_capture_count_mean": seen_capture_count,
            "unseen_capture_count_mean": unseen_capture_count,
        }
        seen_row.update(
            {
                "sentinel_win_rate_drop": seen_row["seen_sentinel_win_rate"] - seen_row["unseen_sentinel_win_rate"],
                "runner_win_rate_increase": seen_row["unseen_runner_win_rate"] - seen_row["seen_runner_win_rate"],
                "capture_time_delta_seconds": seen_row["unseen_full_capture_time"] - seen_row["seen_full_capture_time"],
                "path_efficiency_delta": seen_row["unseen_path_ratio"] - seen_row["seen_path_ratio"],
                "exploration_time_proxy_delta_seconds": seen_row["unseen_survival_time"] - seen_row["seen_survival_time"],
                "coordination_capture_per_episode_delta": seen_row["unseen_capture_count_mean"] - seen_row["seen_capture_count_mean"],
            }
        )
        rows.append(seen_row)

        seen_unseen_by_seed.append(
            {
                "seed": seed,
                "seen_run_id": seen_run_id,
                "unseen_run_id": unseen_run_id,
                "seen_sentinel_win_rate": seen_row["seen_sentinel_win_rate"],
                "unseen_sentinel_win_rate": seen_row["unseen_sentinel_win_rate"],
                "seen_runner_win_rate": seen_row["seen_runner_win_rate"],
                "unseen_runner_win_rate": seen_row["unseen_runner_win_rate"],
                "seen_full_capture_time": seen_row["seen_full_capture_time"],
                "unseen_full_capture_time": seen_row["unseen_full_capture_time"],
                "seen_survival_time": seen_row["seen_survival_time"],
                "unseen_survival_time": seen_row["unseen_survival_time"],
                "seen_path_ratio": seen_row["seen_path_ratio"],
                "unseen_path_ratio": seen_row["unseen_path_ratio"],
                "seen_pincer_rate": seen_row["seen_pincer_rate"],
                "unseen_pincer_rate": seen_row["unseen_pincer_rate"],
                "seen_corridor_rate": seen_row["seen_corridor_rate"],
                "unseen_corridor_rate": seen_row["unseen_corridor_rate"],
                "seen_exit_denial_rate": seen_row["seen_exit_denial_rate"],
                "unseen_exit_denial_rate": seen_row["unseen_exit_denial_rate"],
                "seen_capture_count_mean": seen_row["seen_capture_count_mean"],
                "unseen_capture_count_mean": seen_row["unseen_capture_count_mean"],
                "sentinel_win_rate_drop": seen_row["sentinel_win_rate_drop"],
                "runner_win_rate_increase": seen_row["runner_win_rate_increase"],
                "capture_time_delta_seconds": seen_row["capture_time_delta_seconds"],
                "path_efficiency_delta": seen_row["path_efficiency_delta"],
                "exploration_time_proxy_delta_seconds": seen_row["exploration_time_proxy_delta_seconds"],
                "coordination_capture_per_episode_delta": seen_row["coordination_capture_per_episode_delta"],
            }
        )

    family_json = {
        "schema_version": 1,
        "experiment_family": eval_family,
        "duration_minutes": duration_minutes,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "seed_summaries": seen_unseen_by_seed,
    }
    (eval_root / "final_seen_unseen_summary.json").write_text(
        json.dumps(family_json, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_csv(eval_root / "final_seen_unseen_summary.csv", rows, FINAL_SUMMARY_FIELDS)
    return rows, seen_unseen_by_seed, [family_json], missing_rows


def build_multiseed_rows(seed_summaries: list[dict[str, Any]], eval_family: str) -> list[dict[str, Any]]:
    if not seed_summaries:
        return []

    metrics = [
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
        "sentinel_win_rate_drop",
        "runner_win_rate_increase",
        "capture_time_delta_seconds",
        "path_efficiency_delta",
        "exploration_time_proxy_delta_seconds",
        "coordination_capture_per_episode_delta",
    ]

    rows: list[dict[str, Any]] = []
    for metric_name in metrics:
        values = [safe_float(row.get(metric_name)) for row in seed_summaries]
        per_seed = "; ".join(f"{row['seed']}:{safe_float(row.get(metric_name)):0.6f}" for row in seed_summaries)
        run_ids = "; ".join(f"{row['seed']}:{row['seen_run_id']}|{row['unseen_run_id']}" for row in seed_summaries)
        rows.append(
            {
                "metric": metric_name,
                "mean": statistics.fmean(values) if values else 0.0,
                "std": statistics.pstdev(values) if len(values) > 1 else 0.0,
                "min": min(values) if values else 0.0,
                "max": max(values) if values else 0.0,
                "per_seed": per_seed,
                "experiment_family": eval_family,
                "run_ids": run_ids,
            }
        )
    return rows


def build_coordination_rows(results_root: Path, eval_family: str, duration_minutes: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for seed in OFFICIAL_SEEDS:
        for split in EVAL_SPLITS:
            run_id = f"{eval_family}_seed{seed}_{split}_{duration_minutes}m"
            run_dir = results_root / f"seed_{seed}" / "eval" / run_id
            kpi_path = run_dir / "kpi" / "eval_kpi_summary.json"
            if not kpi_path.exists():
                continue
            kpi = load_json(kpi_path)
            coord = kpi.get("coordination") or {}
            rows.append(
                {
                    "seed": seed,
                    "run_id": run_id,
                    "pincer_rate": coord.get("pincer_rate", ""),
                    "corridor_block_rate": coord.get("corridor_block_rate", ""),
                    "exit_denial_rate": coord.get("exit_denial_rate", ""),
                    "trap_success_rate": coord.get("trap_success_rate", ""),
                    "enclosure_rate": coord.get("enclosure_rate", ""),
                }
            )
    return rows


def build_reward_rows(results_root: Path, eval_family: str, duration_minutes: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for seed in OFFICIAL_SEEDS:
        for split in EVAL_SPLITS:
            run_id = f"{eval_family}_seed{seed}_{split}_{duration_minutes}m"
            reward_path = results_root / f"seed_{seed}" / "eval" / run_id / "logs" / "reward_breakdown.csv"
            if not reward_path.exists():
                continue
            for row in read_csv_rows(reward_path):
                rows.append(
                    {
                        "seed": seed,
                        "run_id": run_id,
                        "team": row.get("team", ""),
                        "total_reward": row.get("total_reward", ""),
                        "terminal_reward": row.get("terminal_reward", ""),
                        "shaping_reward": row.get("shaping_reward", ""),
                        "trap_aware_reward": row.get("trap_aware_reward", ""),
                        "exploration_reward": row.get("exploration_reward", ""),
                        "penalties": row.get("penalties", ""),
                    }
                )
    return rows


def build_training_completion_rows(root: Path, training_family: str) -> list[dict[str, Any]]:
    tracker_path = root / training_family / "completion" / "seed_completion_report.csv"
    if not tracker_path.exists():
        return []
    with tracker_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--training-family", default="LB_3v2_curriculum_official_v1")
    parser.add_argument("--eval-family", default="LB_3v2_seen_unseen_eval_official_v1")
    args = parser.parse_args()

    root = repo_root()
    results_root = root / args.results_dir
    eval_matrix = load_yaml(root / "configs" / "experiment_manifests" / "official_seen_unseen_eval_matrix.yaml")
    duration_minutes = int(eval_matrix["duration_minutes"])

    # Family-level aggregate summaries used by the reporting scripts.
    final_rows, seed_summaries, _, missing_rows = build_final_seen_unseen_summary(
        results_root=results_root,
        eval_family=args.eval_family,
        duration_minutes=duration_minutes,
    )
    multiseed_rows = build_multiseed_rows(seed_summaries, args.eval_family)

    family_eval_root = results_root / args.eval_family / "eval"
    family_summary_root = results_root / args.eval_family / "summary"
    family_eval_root.mkdir(parents=True, exist_ok=True)
    family_summary_root.mkdir(parents=True, exist_ok=True)
    write_csv(family_summary_root / "multiseed_summary.csv", multiseed_rows, ["metric", "mean", "std", "min", "max", "per_seed", "experiment_family", "run_ids"])

    # Compatibility mirror for older summary consumers.
    official_summary_root = results_root / "official_summary"
    official_summary_root.mkdir(parents=True, exist_ok=True)
    write_csv(
        official_summary_root / "seen_unseen_comparison.csv",
        final_rows,
        FINAL_SUMMARY_FIELDS,
    )
    write_csv(
        official_summary_root / "multiseed_kpi_summary.csv",
        multiseed_rows,
        ["metric", "mean", "std", "min", "max", "per_seed", "experiment_family", "run_ids"],
    )

    # Training completion matrix remains a direct copy of the seed tracker output.
    training_rows = build_training_completion_rows(results_root, args.training_family)
    write_csv(
        official_summary_root / "training_completion_matrix.csv",
        training_rows,
        ["Seed", "Stage", "Complete/Incomplete", "Missing Artifact", "Error Description (if any)"],
    )

    coordination_rows = build_coordination_rows(results_root, args.eval_family, duration_minutes)
    reward_rows = build_reward_rows(results_root, args.eval_family, duration_minutes)
    write_csv(
        official_summary_root / "coordination_kpi_summary.csv",
        coordination_rows,
        ["seed", "run_id", "pincer_rate", "corridor_block_rate", "exit_denial_rate", "trap_success_rate", "enclosure_rate"],
    )
    write_csv(
        official_summary_root / "reward_breakdown_summary.csv",
        reward_rows,
        ["seed", "run_id", "team", "total_reward", "terminal_reward", "shaping_reward", "trap_aware_reward", "exploration_reward", "penalties"],
    )
    write_csv(
        official_summary_root / "missing_artifacts_report.csv",
        missing_rows,
        ["seed", "scope", "missing_artifact", "error"],
    )

    print(f"Wrote official summary files under: {official_summary_root}")
    print(f"Wrote family-level eval summary under: {family_eval_root}")
    print(f"Wrote family-level multiseed summary under: {family_summary_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
