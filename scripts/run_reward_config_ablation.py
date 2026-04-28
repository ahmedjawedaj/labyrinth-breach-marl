#!/usr/bin/env python3
"""Reward configuration ablation across stages and seeds."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

SEEDS = [42, 101, 202]
STAGES = [
    ("stage1", "configs/experiment_manifests/exp_memory_ablation_stage1_openarena_seed42.yaml", "ablation_stage1_openarena_fixed"),
    ("stage2", "configs/experiment_manifests/exp_memory_ablation_stage2_static_random_seed42.yaml", "ablation_stage2_static_random"),
    ("stage3", "configs/experiment_manifests/exp_memory_ablation_stage3_dynamic_low_seed42.yaml", "ablation_stage3_dynamic_low"),
    ("stage4", "configs/experiment_manifests/exp_memory_ablation_stage4_dynamic_high_seed42.yaml", "ablation_stage4_dynamic_high"),
]
REWARD_CONFIGS = [
    ("reward_baseline", "configs/reward_configs/reward_shared_basic_v1.yaml"),
    ("reward_shared_plus_individual", "configs/reward_configs/reward_shared_plus_individual_v2.yaml"),
    ("reward_trap_aware", "configs/reward_configs/reward_trap_aware_v3.yaml"),
    ("reward_dynamicmaze_memory", "configs/reward_configs/reward_dynamicmaze_memory_v4.yaml"),
]


def run(command: list[str], root: Path) -> int:
    print(" ".join(command))
    return subprocess.run(command, cwd=root).returncode


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def metric(summary: dict, *keys: str) -> float:
    current = summary
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return 0.0
        current = current[key]
    return float(current) if isinstance(current, (int, float)) else 0.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-minutes", type=int, default=30)
    parser.add_argument("--allow-cpu", action="store_true")
    parser.add_argument("--no-graphics", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    max_runtime = max(60, args.duration_minutes * 60)

    for seed in SEEDS:
        seed_root = root / "results" / f"seed_{seed}"
        comparison_rows: list[dict] = []
        for reward_label, reward_config in REWARD_CONFIGS:
            condition_root_rel = Path("results") / f"seed_{seed}" / reward_label
            condition_root = root / condition_root_rel
            condition_root.mkdir(parents=True, exist_ok=True)

            for stage_id, manifest, curriculum_stage in STAGES:
                run_id = f"LB_reward_ablation_{reward_label}_seed{seed}_{stage_id}"
                cmd = [
                    sys.executable,
                    "scripts/train_with_metadata.py",
                    "--manifest",
                    manifest,
                    "--seed",
                    str(seed),
                    "--run-id",
                    run_id,
                    "--results-dir",
                    str(condition_root_rel),
                    "--reward-config",
                    reward_config,
                    "--curriculum-stage",
                    curriculum_stage,
                    "--force",
                ]
                if args.no_graphics:
                    cmd.append("--no-graphics")
                rc = run(cmd, root)
                if rc != 0:
                    return rc

            source_run_id = f"LB_reward_ablation_{reward_label}_seed{seed}_stage4"
            split_kpis: dict[str, dict] = {}
            for split, manifest in (
                ("seen", "configs/experiment_manifests/exp_memory_ablation_seen_eval_seed42.yaml"),
                ("unseen", "configs/experiment_manifests/exp_unseen_eval_seed101.yaml"),
            ):
                eval_run_id = f"{source_run_id}_{split}_{args.duration_minutes}m"
                out_rel = condition_root_rel / "eval"
                cmd = [
                    sys.executable,
                    "scripts/evaluate_policy.py",
                    "--manifest",
                    manifest,
                    "--source-run-id",
                    source_run_id,
                    "--source-results-dir",
                    str(condition_root_rel),
                    "--output-dir",
                    str(out_rel),
                    "--seed",
                    str(seed),
                    "--eval-run-id",
                    eval_run_id,
                    "--max-runtime-seconds",
                    str(max_runtime),
                    "--reward-config",
                    reward_config,
                ]
                if args.allow_cpu:
                    cmd.append("--allow-cpu")
                if args.no_graphics:
                    cmd.append("--no-graphics")
                rc = run(cmd, root)
                if rc not in (0, 124):
                    return rc

                eval_root = root / out_rel / eval_run_id
                kpi = read_json(eval_root / "kpi" / "eval_kpi_summary.json")
                split_kpis[split] = kpi
                role_cmd = [
                    sys.executable,
                    "scripts/analyze_role_emergence.py",
                    "--run-root",
                    str(eval_root),
                    "--seed",
                    str(seed),
                    "--stage-label",
                    f"{reward_label}_{split}",
                    "--output-base",
                    "results",
                ]
                rc = run(role_cmd, root)
                if rc != 0:
                    return rc

            row = {
                "reward_config": reward_label,
                "seen_sentinel_win_rate": metric(split_kpis["seen"], "sentinel_win_rate"),
                "unseen_sentinel_win_rate": metric(split_kpis["unseen"], "sentinel_win_rate"),
                "seen_first_capture_time": metric(split_kpis["seen"], "mean_time_to_first_capture_seconds"),
                "unseen_full_capture_time": metric(split_kpis["unseen"], "mean_time_to_full_capture_seconds"),
                "seen_exploration_time": metric(split_kpis["seen"], "dynamic_route_change_proxy", "value"),
                "unseen_survival_time": metric(split_kpis["unseen"], "runner_survival_time_seconds_mean"),
                "seen_pincer_rate": metric(split_kpis["seen"], "coordination", "pincer_rate"),
                "seen_corridor_rate": metric(split_kpis["seen"], "coordination", "corridor_block_rate"),
                "seen_exit_denial_rate": metric(split_kpis["seen"], "coordination", "exit_denial_rate"),
                "seen_path_efficiency_ratio": metric(split_kpis["seen"], "path_efficiency", "shortest_path_vs_actual_ratio_proxy"),
            }
            comparison_rows.append(row)
            (condition_root / "reward_config_summary.json").write_text(
                json.dumps({"seed": seed, "reward_config": reward_label, "kpis": split_kpis}, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        comp_json = seed_root / "reward_config_comparison.json"
        comp_csv = seed_root / "reward_config_comparison.csv"
        comp_json.write_text(json.dumps({"seed": seed, "rows": comparison_rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with comp_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(comparison_rows[0].keys()))
            writer.writeheader()
            for row in comparison_rows:
                writer.writerow(row)
    print("Reward configuration ablation completed for seeds 42, 101, 202.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
