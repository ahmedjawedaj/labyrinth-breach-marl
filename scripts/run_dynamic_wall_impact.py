#!/usr/bin/env python3
"""Static vs dynamic wall tactical impact validation."""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

SEEDS = [42, 101, 202]
STAGES = [
    ("stage1", "configs/experiment_manifests/exp_memory_ablation_stage1_openarena_seed42.yaml", "ablation_stage1_openarena_fixed"),
    ("stage2", "configs/experiment_manifests/exp_memory_ablation_stage2_static_random_seed42.yaml", "ablation_stage2_static_random"),
    ("stage3", "configs/experiment_manifests/exp_memory_ablation_stage3_dynamic_low_seed42.yaml", "ablation_stage3_dynamic_low"),
    ("stage4", "configs/experiment_manifests/exp_memory_ablation_stage4_dynamic_high_seed42.yaml", "ablation_stage4_dynamic_high"),
]
CONDITIONS = [
    ("static_maze", "configs/env_configs/maze_static_config.yaml"),
    ("dynamic_maze", "configs/env_configs/maze_dynamic_config.yaml"),
]


def run(command: list[str], root: Path) -> int:
    print(" ".join(command))
    return subprocess.run(command, cwd=root).returncode


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def safe_float(row: dict[str, str], key: str) -> float:
    try:
        return float((row.get(key) or "0").strip() or 0)
    except ValueError:
        return 0.0


def wall_impact_metrics(run_root: Path) -> dict:
    replay_rows = read_csv(run_root / "logs" / "replay_events.csv")
    step_rows = read_csv(run_root / "logs" / "agent_step_log.csv")
    shifts = [row for row in replay_rows if (row.get("event_type") or "") == "wall_shift"]
    shift_times = defaultdict(list)
    for row in shifts:
        ep = int(safe_float(row, "episode_id"))
        shift_times[ep].append(safe_float(row, "time_seconds"))

    heading_change_sum = 0.0
    heading_change_count = 0
    stall_after_shift = 0
    samples_after_shift = 0
    step_by_episode_agent = defaultdict(list)
    for row in step_rows:
        ep = int(safe_float(row, "episode_id"))
        agent = (row.get("agent_id") or "").strip()
        step_by_episode_agent[(ep, agent)].append(row)

    for (ep, _agent), rows in step_by_episode_agent.items():
        rows.sort(key=lambda r: safe_float(r, "time_seconds"))
        for shift_time in shift_times.get(ep, []):
            before = [r for r in rows if shift_time - 1.0 <= safe_float(r, "time_seconds") <= shift_time]
            after = [r for r in rows if shift_time < safe_float(r, "time_seconds") <= shift_time + 1.5]
            if before and after:
                b = before[-1]
                a = after[-1]
                bx, bz = safe_float(b, "heading_x"), safe_float(b, "heading_z")
                ax, az = safe_float(a, "heading_x"), safe_float(a, "heading_z")
                dot = max(-1.0, min(1.0, bx * ax + bz * az))
                heading_change_sum += math.acos(dot)
                heading_change_count += 1
            for row in after:
                speed = math.sqrt(safe_float(row, "vel_x") ** 2 + safe_float(row, "vel_z") ** 2)
                samples_after_shift += 1
                if speed < 0.1:
                    stall_after_shift += 1

    return {
        "wall_shift_events": len(shifts),
        "pathing_change_after_shift_radians_mean": heading_change_sum / max(1, heading_change_count),
        "stall_fraction_after_shift": stall_after_shift / max(1, samples_after_shift),
        "decision_change_samples": heading_change_count,
    }


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
        comp_rows = []
        for condition, rule_config in CONDITIONS:
            condition_root_rel = Path("results") / f"seed_{seed}" / condition
            condition_root = root / condition_root_rel
            condition_root.mkdir(parents=True, exist_ok=True)
            for stage_id, manifest, curriculum_stage in STAGES:
                run_id = f"LB_wallimpact_{condition}_seed{seed}_{stage_id}"
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
                    "--rule-config",
                    rule_config,
                    "--curriculum-stage",
                    curriculum_stage,
                    "--force",
                ]
                if args.no_graphics:
                    cmd.append("--no-graphics")
                rc = run(cmd, root)
                if rc != 0:
                    return rc

            source_run = f"LB_wallimpact_{condition}_seed{seed}_stage4"
            eval_run_id = f"{source_run}_seen_{args.duration_minutes}m"
            out_rel = condition_root_rel / "eval"
            cmd = [
                sys.executable,
                "scripts/evaluate_policy.py",
                "--manifest",
                "configs/experiment_manifests/exp_memory_ablation_seen_eval_seed42.yaml",
                "--source-run-id",
                source_run,
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
                "--rule-config",
                rule_config,
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
            wall = wall_impact_metrics(eval_root)
            comp_rows.append(
                {
                    "condition": condition,
                    "sentinel_win_rate": metric(kpi, "sentinel_win_rate"),
                    "runner_win_rate": metric(kpi, "runner_win_rate"),
                    "time_to_first_capture": metric(kpi, "mean_time_to_first_capture_seconds"),
                    "time_to_full_capture": metric(kpi, "mean_time_to_full_capture_seconds"),
                    "pincer_rate": metric(kpi, "coordination", "pincer_rate"),
                    "corridor_block_rate": metric(kpi, "coordination", "corridor_block_rate"),
                    "exit_denial_rate": metric(kpi, "coordination", "exit_denial_rate"),
                    "path_efficiency_ratio": metric(kpi, "path_efficiency", "shortest_path_vs_actual_ratio_proxy"),
                    "runner_survival_time": metric(kpi, "runner_survival_time_seconds_mean"),
                    "wall_shift_events": wall["wall_shift_events"],
                    "pathing_change_after_shift_radians_mean": wall["pathing_change_after_shift_radians_mean"],
                    "stall_fraction_after_shift": wall["stall_fraction_after_shift"],
                }
            )
            role_cmd = [
                sys.executable,
                "scripts/analyze_role_emergence.py",
                "--run-root",
                str(eval_root),
                "--seed",
                str(seed),
                "--stage-label",
                f"{condition}_seen",
                "--output-base",
                "results",
            ]
            rc = run(role_cmd, root)
            if rc != 0:
                return rc

        (seed_root / "static_dynamic_wall_impact.json").write_text(
            json.dumps({"seed": seed, "rows": comp_rows}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with (seed_root / "static_dynamic_wall_impact.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(comp_rows[0].keys()))
            writer.writeheader()
            for row in comp_rows:
                writer.writerow(row)
    print("Static vs dynamic wall tactical impact analysis completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
