#!/usr/bin/env python3
"""Run memory on/off ablation across official seeds and export comparisons."""

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

OFFICIAL_SEEDS = [42, 101, 202]
OFFICIAL_CONDITIONS = ["memory_on", "memory_off"]


def load_yaml(path: Path) -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML is required.")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_cmd(command: list[str], root: Path) -> int:
    print(" ".join(command))
    return subprocess.run(command, cwd=root).returncode


def read_reward_breakdown_summary(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing reward breakdown file: {path}")

    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError(f"Reward breakdown file is empty: {path}")

    per_team: dict[str, dict[str, float]] = {}
    for team in ("Sentinel", "Runner"):
        team_rows = [row for row in rows if (row.get("team") or "").strip() == team]
        if not team_rows:
            continue

        def mean_float(key: str) -> float:
            values: list[float] = []
            for row in team_rows:
                try:
                    values.append(float((row.get(key) or "0").strip() or 0))
                except ValueError:
                    values.append(0.0)
            return sum(values) / max(1, len(values))

        per_team[team] = {
            "total_reward_mean": mean_float("total_reward"),
            "terminal_reward_mean": mean_float("terminal_reward"),
            "shaping_reward_mean": mean_float("shaping_reward"),
            "trap_aware_reward_mean": mean_float("trap_aware_reward"),
            "exploration_reward_mean": mean_float("exploration_reward"),
            "penalties_mean": mean_float("penalties"),
        }

    return per_team


def metric_from_summary(summary: dict, path: list[str], default: float = 0.0) -> float:
    current = summary
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    if isinstance(current, (int, float)):
        return float(current)
    return default


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--matrix-manifest",
        default="configs/experiment_manifests/official_memory_ablation_matrix.yaml",
    )
    parser.add_argument("--allow-cpu", action="store_true")
    parser.add_argument("--no-graphics", action="store_true")
    parser.add_argument("--timeout-wait", type=int, default=120)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    matrix_path = root / args.matrix_manifest
    matrix = load_yaml(matrix_path)

    if matrix.get("seeds") != OFFICIAL_SEEDS:
        raise ValueError(f"Matrix seeds must be {OFFICIAL_SEEDS}")

    stages = matrix.get("stages", [])
    if not stages or len(stages) != 4:
        raise ValueError("Ablation matrix must define 4 stages.")
    stage_by_id = {stage["id"]: stage for stage in stages}
    stage4 = stage_by_id["stage4"]

    condition_map = {condition["id"]: condition for condition in matrix.get("conditions", [])}
    if sorted(condition_map.keys()) != sorted(OFFICIAL_CONDITIONS):
        raise ValueError(f"Ablation conditions must be {OFFICIAL_CONDITIONS}")

    duration_minutes = int(matrix.get("duration_minutes", 30))
    max_runtime_seconds = max(60, duration_minutes * 60)
    deterministic = bool(matrix.get("deterministic_inference", True))

    all_runs: list[dict] = []
    for seed in OFFICIAL_SEEDS:
        seed_result_root = root / "results" / f"seed_{seed}"
        for condition_id in OFFICIAL_CONDITIONS:
            condition = condition_map[condition_id]
            condition_root_rel = Path("results") / f"seed_{seed}" / condition_id
            condition_root = root / condition_root_rel
            condition_root.mkdir(parents=True, exist_ok=True)

            # Training stages 1-4
            for stage in stages:
                run_id = f"{matrix['experiment_family']}_{condition_id}_seed{seed}_{stage['id']}"
                train_command = [
                    sys.executable,
                    "scripts/train_with_metadata.py",
                    "--manifest",
                    stage["manifest"],
                    "--seed",
                    str(seed),
                    "--run-id",
                    run_id,
                    "--results-dir",
                    str(condition_root_rel),
                    "--curriculum-config",
                    condition["curriculum_config"],
                    "--curriculum-stage",
                    stage["id"].replace("stage", "ablation_stage") + ("_openarena_fixed" if stage["id"] == "stage1" else ""),
                    "--experiment-family",
                    matrix["experiment_family"],
                    "--matrix-stage-id",
                    stage["id"],
                    "--matrix-stage-order",
                    str(stage["order"]),
                    "--matrix-total-stages",
                    str(len(stages)),
                    "--force",
                ]
                # Fix exact curriculum stage ids used by curriculum config.
                if stage["id"] == "stage1":
                    train_command[train_command.index("--curriculum-stage") + 1] = "ablation_stage1_openarena_fixed"
                elif stage["id"] == "stage2":
                    train_command[train_command.index("--curriculum-stage") + 1] = "ablation_stage2_static_random"
                elif stage["id"] == "stage3":
                    train_command[train_command.index("--curriculum-stage") + 1] = "ablation_stage3_dynamic_low"
                else:
                    train_command[train_command.index("--curriculum-stage") + 1] = "ablation_stage4_dynamic_high"

                if args.no_graphics:
                    train_command.append("--no-graphics")
                rc = run_cmd(train_command, root)
                if rc != 0:
                    print(f"Training failed: seed={seed}, condition={condition_id}, stage={stage['id']}, exit={rc}", file=sys.stderr)
                    return rc

                status_path = condition_root / run_id / "metadata" / "training_status.json"
                if not status_path.exists():
                    print(f"Missing training status: {status_path}", file=sys.stderr)
                    return 2
                status_data = load_json(status_path)
                if not bool(status_data.get("success")):
                    print(f"Training status indicates failure: {status_path}", file=sys.stderr)
                    return 2

            source_run_id = f"{matrix['experiment_family']}_{condition_id}_seed{seed}_{stage4['id']}"
            eval_manifests = {
                "seen": matrix["evaluation"]["seen_manifest"],
                "unseen": matrix["evaluation"]["unseen_manifest"],
            }
            eval_rule_configs = {
                "seen": condition["seen_rule_config"],
                "unseen": condition["unseen_rule_config"],
            }
            split_outputs: dict[str, dict] = {}
            for split in ("seen", "unseen"):
                eval_run_id = f"{matrix['experiment_family']}_{condition_id}_seed{seed}_{split}_{duration_minutes}m"
                output_dir_rel = condition_root_rel / "eval"
                eval_command = [
                    sys.executable,
                    "scripts/evaluate_policy.py",
                    "--manifest",
                    eval_manifests[split],
                    "--source-run-id",
                    source_run_id,
                    "--source-results-dir",
                    str(condition_root_rel),
                    "--output-dir",
                    str(output_dir_rel),
                    "--seed",
                    str(seed),
                    "--eval-run-id",
                    eval_run_id,
                    "--max-runtime-seconds",
                    str(max_runtime_seconds),
                    "--timeout-wait",
                    str(args.timeout_wait),
                    "--rule-config",
                    eval_rule_configs[split],
                ]
                if deterministic:
                    eval_command.append("--deterministic")
                if args.allow_cpu:
                    eval_command.append("--allow-cpu")
                if args.no_graphics:
                    eval_command.append("--no-graphics")

                rc = run_cmd(eval_command, root)
                if rc not in (0, 124):
                    print(f"Evaluation failed: seed={seed}, condition={condition_id}, split={split}, exit={rc}", file=sys.stderr)
                    return rc

                eval_root = root / output_dir_rel / eval_run_id
                kpi_path = eval_root / "kpi" / "eval_kpi_summary.json"
                reward_breakdown_path = eval_root / "logs" / "reward_breakdown.csv"
                if not kpi_path.exists():
                    print(f"Missing KPI summary: {kpi_path}", file=sys.stderr)
                    return 2
                if not reward_breakdown_path.exists():
                    print(f"Missing reward breakdown: {reward_breakdown_path}", file=sys.stderr)
                    return 2
                split_outputs[split] = {
                    "run_id": eval_run_id,
                    "kpi": load_json(kpi_path),
                    "reward_breakdown": read_reward_breakdown_summary(reward_breakdown_path),
                }

            condition_summary = {
                "seed": seed,
                "condition": condition_id,
                "source_training_run_id": source_run_id,
                "seen": split_outputs["seen"],
                "unseen": split_outputs["unseen"],
            }
            condition_summary_path = condition_root / "eval" / "memory_condition_summary.json"
            condition_summary_path.parent.mkdir(parents=True, exist_ok=True)
            condition_summary_path.write_text(json.dumps(condition_summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            all_runs.append(condition_summary)

        # Side-by-side comparison for this seed
        on_summary = next(item for item in all_runs if item["seed"] == seed and item["condition"] == "memory_on")
        off_summary = next(item for item in all_runs if item["seed"] == seed and item["condition"] == "memory_off")
        compare = {
            "seed": seed,
            "memory_on": on_summary,
            "memory_off": off_summary,
            "delta_memory_on_minus_off": {
                "seen_sentinel_win_rate": metric_from_summary(on_summary, ["seen", "kpi", "sentinel_win_rate"])
                - metric_from_summary(off_summary, ["seen", "kpi", "sentinel_win_rate"]),
                "unseen_sentinel_win_rate": metric_from_summary(on_summary, ["unseen", "kpi", "sentinel_win_rate"])
                - metric_from_summary(off_summary, ["unseen", "kpi", "sentinel_win_rate"]),
                "seen_mean_time_to_first_capture": metric_from_summary(on_summary, ["seen", "kpi", "mean_time_to_first_capture_seconds"])
                - metric_from_summary(off_summary, ["seen", "kpi", "mean_time_to_first_capture_seconds"]),
                "unseen_mean_time_to_full_capture": metric_from_summary(on_summary, ["unseen", "kpi", "mean_time_to_full_capture_seconds"])
                - metric_from_summary(off_summary, ["unseen", "kpi", "mean_time_to_full_capture_seconds"]),
                "seen_exploration_time_proxy": metric_from_summary(on_summary, ["seen", "kpi", "dynamic_route_change_proxy", "value"])
                - metric_from_summary(off_summary, ["seen", "kpi", "dynamic_route_change_proxy", "value"]),
                "unseen_runner_survival_time": metric_from_summary(on_summary, ["unseen", "kpi", "runner_survival_time_seconds_mean"])
                - metric_from_summary(off_summary, ["unseen", "kpi", "runner_survival_time_seconds_mean"]),
                "seen_path_efficiency_ratio_proxy": metric_from_summary(on_summary, ["seen", "kpi", "path_efficiency", "shortest_path_vs_actual_ratio_proxy"])
                - metric_from_summary(off_summary, ["seen", "kpi", "path_efficiency", "shortest_path_vs_actual_ratio_proxy"]),
                "unseen_pincer_rate": metric_from_summary(on_summary, ["unseen", "kpi", "coordination", "pincer_rate"])
                - metric_from_summary(off_summary, ["unseen", "kpi", "coordination", "pincer_rate"]),
                "seen_runner_terminal_reward_mean": metric_from_summary(
                    on_summary,
                    ["seen", "reward_breakdown", "Runner", "terminal_reward_mean"],
                )
                - metric_from_summary(
                    off_summary,
                    ["seen", "reward_breakdown", "Runner", "terminal_reward_mean"],
                ),
            },
        }
        compare_path = seed_result_root / "memory_ablation_comparison.json"
        compare_path.write_text(json.dumps(compare, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with (seed_result_root / "memory_ablation_comparison.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["metric", "memory_on", "memory_off", "delta_on_minus_off"])
            rows = [
                ("seen_sentinel_win_rate", metric_from_summary(on_summary, ["seen", "kpi", "sentinel_win_rate"]), metric_from_summary(off_summary, ["seen", "kpi", "sentinel_win_rate"])),
                ("unseen_sentinel_win_rate", metric_from_summary(on_summary, ["unseen", "kpi", "sentinel_win_rate"]), metric_from_summary(off_summary, ["unseen", "kpi", "sentinel_win_rate"])),
                ("seen_capture_time_first", metric_from_summary(on_summary, ["seen", "kpi", "mean_time_to_first_capture_seconds"]), metric_from_summary(off_summary, ["seen", "kpi", "mean_time_to_first_capture_seconds"])),
                ("unseen_capture_time_full", metric_from_summary(on_summary, ["unseen", "kpi", "mean_time_to_full_capture_seconds"]), metric_from_summary(off_summary, ["unseen", "kpi", "mean_time_to_full_capture_seconds"])),
                ("seen_exploration_time_proxy", metric_from_summary(on_summary, ["seen", "kpi", "dynamic_route_change_proxy", "value"]), metric_from_summary(off_summary, ["seen", "kpi", "dynamic_route_change_proxy", "value"])),
                ("unseen_survival_time_runner", metric_from_summary(on_summary, ["unseen", "kpi", "runner_survival_time_seconds_mean"]), metric_from_summary(off_summary, ["unseen", "kpi", "runner_survival_time_seconds_mean"])),
                ("seen_path_efficiency_ratio_proxy", metric_from_summary(on_summary, ["seen", "kpi", "path_efficiency", "shortest_path_vs_actual_ratio_proxy"]), metric_from_summary(off_summary, ["seen", "kpi", "path_efficiency", "shortest_path_vs_actual_ratio_proxy"])),
                ("unseen_coordination_pincer_rate", metric_from_summary(on_summary, ["unseen", "kpi", "coordination", "pincer_rate"]), metric_from_summary(off_summary, ["unseen", "kpi", "coordination", "pincer_rate"])),
                ("seen_runner_terminal_reward_mean", metric_from_summary(on_summary, ["seen", "reward_breakdown", "Runner", "terminal_reward_mean"]), metric_from_summary(off_summary, ["seen", "reward_breakdown", "Runner", "terminal_reward_mean"])),
            ]
            for metric, on_value, off_value in rows:
                writer.writerow([metric, on_value, off_value, on_value - off_value])

    family_dir = root / "results" / matrix["experiment_family"]
    family_dir.mkdir(parents=True, exist_ok=True)
    summary_payload = {
        "schema_version": 1,
        "matrix_manifest": str(matrix_path.relative_to(root)),
        "seeds": OFFICIAL_SEEDS,
        "conditions": OFFICIAL_CONDITIONS,
        "duration_minutes": duration_minutes,
        "runs": all_runs,
    }
    (family_dir / "memory_ablation_summary.json").write_text(json.dumps(summary_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Memory on/off ablation completed for seeds 42, 101, 202.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
