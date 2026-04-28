#!/usr/bin/env python3
"""Build required official summary CSV artifacts from available outputs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


OFFICIAL_SEEDS = [42, 101, 202]
OFFICIAL_STAGES = ["stage1", "stage2", "stage3", "stage4"]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--training-family", default="LB_3v2_curriculum_official_v1")
    parser.add_argument("--eval-family", default="LB_3v2_seen_unseen_eval_official_v1")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    results_root = root / args.results_dir
    out_dir = results_root / "official_summary"
    out_dir.mkdir(parents=True, exist_ok=True)

    tracker_path = results_root / args.training_family / "completion" / "seed_completion_report.csv"
    training_rows: list[dict] = []
    missing_rows: list[dict] = []
    if tracker_path.exists():
        with tracker_path.open("r", encoding="utf-8", newline="") as handle:
            training_rows = list(csv.DictReader(handle))
            for row in training_rows:
                if row.get("Complete/Incomplete") != "Complete":
                    missing_rows.append(
                        {
                            "seed": row.get("Seed", ""),
                            "scope": row.get("Stage", ""),
                            "missing_artifact": row.get("Missing Artifact", ""),
                            "error": row.get("Error Description (if any)", ""),
                        }
                    )

    write_csv(
        out_dir / "training_completion_matrix.csv",
        training_rows,
        ["Seed", "Stage", "Complete/Incomplete", "Missing Artifact", "Error Description (if any)"],
    )

    seen_unseen_rows: list[dict] = []
    final_summary = results_root / args.eval_family / "eval" / "final_seen_unseen_summary.csv"
    if final_summary.exists():
        with final_summary.open("r", encoding="utf-8", newline="") as handle:
            seen_unseen_rows = list(csv.DictReader(handle))
    else:
        for seed in OFFICIAL_SEEDS:
            seen_unseen_rows.append(
                {
                    "seed": seed,
                    "seen_run_id": "",
                    "unseen_run_id": "",
                    "sentinel_win_rate_drop": "",
                    "runner_win_rate_increase": "",
                    "capture_time_delta_seconds": "",
                    "path_efficiency_delta": "",
                    "exploration_time_proxy_delta_seconds": "",
                    "coordination_capture_per_episode_delta": "",
                }
            )
            missing_rows.append(
                {
                    "seed": seed,
                    "scope": "seen_unseen_summary",
                    "missing_artifact": str(final_summary),
                    "error": "Missing final seen/unseen summary.",
                }
            )
    write_csv(
        out_dir / "seen_unseen_comparison.csv",
        seen_unseen_rows,
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
        ],
    )

    multiseed_path = results_root / args.eval_family / "summary" / "multiseed_summary.csv"
    multiseed_rows = []
    if multiseed_path.exists():
        with multiseed_path.open("r", encoding="utf-8", newline="") as handle:
            multiseed_rows = list(csv.DictReader(handle))
    else:
        missing_rows.append({"seed": "", "scope": "multiseed_kpi", "missing_artifact": str(multiseed_path), "error": "Missing multiseed KPI summary."})
    write_csv(
        out_dir / "multiseed_kpi_summary.csv",
        multiseed_rows,
        ["metric", "mean", "std", "min", "max", "per_seed", "experiment_family", "run_ids"] if multiseed_rows else ["metric", "mean", "std", "min", "max", "per_seed", "experiment_family", "run_ids"],
    )

    # Coordination/reward summary extraction from per-seed eval outputs (best effort).
    coord_rows: list[dict] = []
    reward_rows: list[dict] = []
    for seed in OFFICIAL_SEEDS:
        seed_eval_root = results_root / f"seed_{seed}" / "eval"
        if not seed_eval_root.exists():
            missing_rows.append(
                {
                    "seed": seed,
                    "scope": "seed_eval_root",
                    "missing_artifact": str(seed_eval_root),
                    "error": "Evaluation root missing.",
                }
            )
            continue
        for run_dir in sorted([p for p in seed_eval_root.iterdir() if p.is_dir()]):
            kpi_json = run_dir / "kpi" / "eval_kpi_summary.json"
            if kpi_json.exists():
                kpi = read_json(kpi_json)
                coord = kpi.get("coordination") or {}
                coord_rows.append(
                    {
                        "seed": seed,
                        "run_id": run_dir.name,
                        "pincer_rate": coord.get("pincer_rate", ""),
                        "corridor_block_rate": coord.get("corridor_block_rate", ""),
                        "exit_denial_rate": coord.get("exit_denial_rate", ""),
                        "trap_success_rate": coord.get("trap_success_rate", ""),
                        "enclosure_rate": coord.get("enclosure_rate", ""),
                    }
                )
            else:
                missing_rows.append({"seed": seed, "scope": run_dir.name, "missing_artifact": str(kpi_json), "error": "Missing eval_kpi_summary.json"})

            reward_csv = run_dir / "logs" / "reward_breakdown.csv"
            if reward_csv.exists():
                with reward_csv.open("r", encoding="utf-8", newline="") as handle:
                    reader = csv.DictReader(handle)
                    for row in reader:
                        reward_rows.append(
                            {
                                "seed": seed,
                                "run_id": run_dir.name,
                                "team": row.get("team", ""),
                                "total_reward": row.get("total_reward", ""),
                                "terminal_reward": row.get("terminal_reward", ""),
                                "shaping_reward": row.get("shaping_reward", ""),
                                "trap_aware_reward": row.get("trap_aware_reward", ""),
                                "exploration_reward": row.get("exploration_reward", ""),
                                "penalties": row.get("penalties", ""),
                            }
                        )
            else:
                missing_rows.append({"seed": seed, "scope": run_dir.name, "missing_artifact": str(reward_csv), "error": "Missing reward_breakdown.csv"})

    write_csv(
        out_dir / "coordination_kpi_summary.csv",
        coord_rows,
        ["seed", "run_id", "pincer_rate", "corridor_block_rate", "exit_denial_rate", "trap_success_rate", "enclosure_rate"],
    )
    write_csv(
        out_dir / "reward_breakdown_summary.csv",
        reward_rows,
        ["seed", "run_id", "team", "total_reward", "terminal_reward", "shaping_reward", "trap_aware_reward", "exploration_reward", "penalties"],
    )
    write_csv(
        out_dir / "missing_artifacts_report.csv",
        missing_rows,
        ["seed", "scope", "missing_artifact", "error"],
    )
    print(f"Wrote official summary files under: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
