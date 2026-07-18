#!/usr/bin/env python3
"""Audit publication-evaluation artifacts, provenance, and episode-level totals."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml


REQUIRED_ARTIFACTS = (
    "logs/episode_log.csv",
    "logs/agent_step_log.csv",
    "logs/reward_audit.csv",
    "logs/replay_events.csv",
    "kpi/eval_kpi_summary.json",
    "kpi/eval_kpi_summary.csv",
)
SENTINEL_WIN = "SentinelWinAllRunnersCaptured"
RUNNER_WINS = {"RunnerWinExitReached", "RunnerWinTimeout"}
EPISODE_COLUMNS = (
    "episode_id", "outcome", "duration_seconds", "total_steps", "capture_count",
    "exit_count", "wall_shift_count", "trap_event_count", "rule_config_path",
    "reward_config_path", "reward_config_id", "curriculum_stage_id", "scene_name",
    "maze_layout_id", "maze_topology_seed", "sentinel_reward_total",
    "runner_reward_total", "capture_reward_total", "trap_reward_total",
    "shaping_reward_total", "penalty_reward_total", "terminal_reward_total",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 0.0
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    half_width = z * math.sqrt((proportion * (1 - proportion) + z * z / (4 * total)) / total) / denominator
    return max(0.0, center - half_width), min(1.0, center + half_width)


def curriculum_stage_maze_seeds(root: Path, manifest: dict) -> dict[str, int]:
    curriculum_config = str(manifest.get("curriculum_config") or "").strip()
    if not curriculum_config:
        return {}
    curriculum_path = root / curriculum_config
    curriculum = load_yaml(curriculum_path)
    seeds: dict[str, int] = {}
    for stage in curriculum.get("stages", []):
        if not isinstance(stage, dict):
            continue
        stage_id = str(stage.get("stage_id") or "").strip()
        maze = stage.get("maze") if isinstance(stage.get("maze"), dict) else {}
        if stage_id and "seed" in maze:
            seeds[stage_id] = int(maze["seed"])
    return seeds


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", default="results/publication_eval_v2/aggregate/publication_eval_summary.json")
    parser.add_argument("--results-dir", default="results/publication_eval_v2")
    parser.add_argument("--output", default="results/publication_eval_v2/aggregate/publication_eval_audit.json")
    parser.add_argument("--matrix", default="configs/experiment_manifests/official_publication_eval_matrix.yaml")
    parser.add_argument("--enforce-episode-target", action="store_true")
    parser.add_argument(
        "--expected-episodes",
        type=int,
        help="Override the matrix episode target, for explicitly budgeted smoke runs.",
    )
    parser.add_argument("--enforce-topology-provenance", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    aggregate_path = root / args.aggregate
    results_root = root / args.results_dir
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    matrix = load_yaml(root / args.matrix)
    split_provenance: dict[str, dict] = {}
    for split in matrix.get("splits", []):
        manifest = load_yaml(root / split["manifest"])
        split_provenance[str(split["id"])] = {
            "scene": str(manifest.get("scene", "")),
            "rule": Path(str(manifest.get("rule_config", ""))).name,
            "reward": Path(str(manifest.get("reward_config", ""))).name,
            "curriculum_stage_maze_seeds": curriculum_stage_maze_seeds(root, manifest),
        }
    expected_rows = len(matrix.get("seeds", [])) * len(matrix.get("splits", []))
    episode_target = args.expected_episodes or int(matrix.get("episodes_per_cell", 0))
    rows = aggregate.get("rows") or []
    problems: list[str] = []
    run_audits: list[dict] = []
    group_counts: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    if len(rows) != expected_rows:
        problems.append(f"Expected {expected_rows} matrix rows, found {len(rows)}")

    for row in rows:
        evaluation_seed = int(row["evaluation_seed"])
        is_legacy_diagnostic = not str(row.get("policy_seed", "")).strip()
        seed_directory = f"evaluation_seed_{evaluation_seed}" if is_legacy_diagnostic else f"policy_seed_{row['policy_seed']}"
        run_root = results_root / seed_directory / row["run_id"]
        run_problems: list[str] = []
        if (run_root / "metadata" / "INVALIDATED.md").exists():
            run_problems.append("run_marked_invalidated")

        for relative_path in REQUIRED_ARTIFACTS:
            artifact = run_root / relative_path
            if not artifact.exists() or artifact.stat().st_size == 0:
                run_problems.append(f"missing_or_empty:{relative_path}")

        episode_path = run_root / "logs/episode_log.csv"
        episode_fieldnames: list[str] = []
        episodes: list[dict[str, str]] = []
        if episode_path.exists():
            with episode_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                episode_fieldnames = reader.fieldnames or []
                episodes = list(reader)
        if not episodes:
            run_problems.append("episode_log_has_no_completed_episodes")
        if episode_fieldnames != list(EPISODE_COLUMNS) or any(None in episode for episode in episodes):
            run_problems.append("episode_schema_mismatch")
        episode_ids = [int(item["episode_id"]) for item in episodes if item.get("episode_id", "").isdigit()]
        if episode_ids != list(range(1, len(episodes) + 1)):
            run_problems.append("episode_ids_not_unique_contiguous")
        if args.enforce_episode_target and len(episodes) < episode_target:
            run_problems.append(f"episode_target_not_met:{len(episodes)}/{episode_target}")

        provenance = split_provenance.get(row["split_id"], {})
        expected_scene = str(provenance.get("scene", ""))
        expected_rule = str(provenance.get("rule", ""))
        expected_reward = str(provenance.get("reward", ""))
        stage_maze_seeds = provenance.get("curriculum_stage_maze_seeds", {})
        if not expected_scene or not expected_rule or not expected_reward:
            run_problems.append(f"missing_split_provenance:{row['split_id']}")
        rule_topology_seed = -1
        if args.enforce_topology_provenance and expected_rule:
            rule_config = load_yaml(root / "configs" / "env_configs" / expected_rule)
            rule_topology_seed = int((rule_config.get("randomization") or {}).get("maze_seed", -1))
        for episode in episodes:
            scene = (episode.get("scene_name") or "").strip()
            rule_name = Path(episode.get("rule_config_path") or "").name
            reward_name = Path(episode.get("reward_config_path") or "").name
            if scene != expected_scene:
                run_problems.append(f"scene_mismatch:{scene or '<empty>'}")
            if rule_name != expected_rule:
                run_problems.append(f"rule_mismatch:{rule_name or '<empty>'}")
            if reward_name != expected_reward:
                run_problems.append(f"reward_mismatch:{reward_name or '<empty>'}")
            if args.enforce_topology_provenance:
                expected_topology_seed = rule_topology_seed
                stage_id = (episode.get("curriculum_stage_id") or "").strip()
                if stage_id and isinstance(stage_maze_seeds, dict) and stage_id in stage_maze_seeds:
                    expected_topology_seed = int(stage_maze_seeds[stage_id])
                expected_layout_id = (
                    f"procedural_seed_{expected_topology_seed}"
                    if row["group"] == "unseen"
                    else "training_layout_v1"
                )
                observed_layout_id = (episode.get("maze_layout_id") or "").strip()
                observed_topology_seed = int(float(episode.get("maze_topology_seed") or -1))
                if observed_layout_id != expected_layout_id:
                    run_problems.append(f"layout_id_mismatch:{observed_layout_id or '<empty>'}")
                if observed_topology_seed != expected_topology_seed:
                    run_problems.append(f"topology_seed_mismatch:{observed_topology_seed}")

            group = row["group"]
            group_counts[group]["episodes"] += 1
            outcome = episode.get("outcome") or ""
            if outcome == SENTINEL_WIN:
                group_counts[group]["sentinel_wins"] += 1
                group_counts[group]["full_capture_seconds_total"] += float(episode.get("duration_seconds") or 0)
            if outcome in RUNNER_WINS:
                group_counts[group]["runner_wins"] += 1
            if float(episode.get("exit_count") or 0) > 0:
                group_counts[group]["escapes"] += 1

        metadata_path = run_root / "metadata/evaluation_metadata.json"
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if metadata.get("fixed_policy_source_run_id") != row.get("source_run_id"):
                run_problems.append("source_run_id_mismatch")
            if int(metadata.get("seed", -1)) != evaluation_seed:
                run_problems.append("evaluation_seed_mismatch")
        else:
            run_problems.append("missing:evaluation_metadata.json")

        if args.enforce_episode_target:
            status_path = run_root / "metadata/evaluation_status.json"
            if not status_path.exists():
                run_problems.append("missing:evaluation_status.json")
            else:
                status = json.loads(status_path.read_text(encoding="utf-8"))
                if status.get("success") is not True:
                    run_problems.append("evaluation_status_failed")
                if int(status.get("target_episodes") or 0) != episode_target:
                    run_problems.append("evaluation_target_mismatch")

        run_problems = sorted(set(run_problems))
        if run_problems:
            problems.extend(f"{row['run_id']}:{problem}" for problem in run_problems)
        run_audits.append(
            {
                "run_id": row["run_id"],
                "evaluation_seed": evaluation_seed,
                "split_id": row["split_id"],
                "completed_episodes": len(episodes),
                "expected_scene": expected_scene,
                "expected_rule_config": expected_rule,
                "expected_reward_config": expected_reward,
                "problems": run_problems,
                "valid": not run_problems,
            }
        )

    group_summary: dict[str, dict] = {}
    for group, counts in sorted(group_counts.items()):
        episodes = int(counts["episodes"])
        sentinel_wins = int(counts["sentinel_wins"])
        runner_wins = int(counts["runner_wins"])
        lower, upper = wilson_interval(sentinel_wins, episodes)
        group_summary[group] = {
            "episodes": episodes,
            "sentinel_wins": sentinel_wins,
            "sentinel_win_rate": sentinel_wins / episodes if episodes else 0.0,
            "sentinel_win_rate_wilson_95_ci": [lower, upper],
            "runner_wins": runner_wins,
            "runner_win_rate": runner_wins / episodes if episodes else 0.0,
            "escapes": int(counts["escapes"]),
            "escape_rate": counts["escapes"] / episodes if episodes else 0.0,
            "mean_full_capture_seconds": (
                counts["full_capture_seconds_total"] / sentinel_wins if sentinel_wins else 0.0
            ),
        }

    output = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "aggregate": str(aggregate_path.relative_to(root)),
        "results_dir": str(results_root.relative_to(root)),
        "matrix_manifest": args.matrix,
        "expected_matrix_rows": expected_rows,
        "observed_matrix_rows": len(rows),
        "episode_target_per_cell": episode_target if args.enforce_episode_target else None,
        "topology_provenance_enforced": args.enforce_topology_provenance,
        "required_artifacts_per_run": len(REQUIRED_ARTIFACTS),
        "expected_required_artifacts": len(rows) * len(REQUIRED_ARTIFACTS),
        "group_summary": group_summary,
        "runs": run_audits,
        "problems": problems,
        "valid": not problems,
    }
    output_path = root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if not problems else 2


if __name__ == "__main__":
    raise SystemExit(main())
