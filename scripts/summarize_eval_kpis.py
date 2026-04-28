#!/usr/bin/env python3
"""Summarize protocol-aligned evaluation KPIs from raw logs."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from artifact_validation import (
    ArtifactRequirement,
    format_problem_report,
    validate_artifacts,
)


SENTINEL_WIN = "SentinelWinAllRunnersCaptured"
RUNNER_WINS = {"RunnerWinExitReached", "RunnerWinTimeout"}
PROTOCOL_VERSION = "evaluation_protocol.md@v1"


def read_episode_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_step_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def safe_float(row: dict[str, str], key: str) -> float:
    try:
        return float(row.get(key, "0") or 0)
    except ValueError:
        return 0.0


def safe_int(row: dict[str, str], key: str) -> int:
    try:
        return int(float(row.get(key, "0") or 0))
    except ValueError:
        return 0


def parse_episode_id(row: dict[str, str], key: str = "episode_id") -> int:
    return safe_int(row, key)


def load_replay_capture_times(path: Path) -> tuple[dict[int, float], dict[int, list[float]]]:
    first_capture_by_episode: dict[int, float] = {}
    captures_by_episode: dict[int, list[float]] = defaultdict(list)
    rows = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        event_type = (row.get("event_type") or "").strip().lower()
        if event_type != "capture":
            continue
        episode_id = parse_episode_id(row)
        timestamp = safe_float(row, "time")
        captures_by_episode[episode_id].append(timestamp)
        if episode_id not in first_capture_by_episode:
            first_capture_by_episode[episode_id] = timestamp
        else:
            first_capture_by_episode[episode_id] = min(first_capture_by_episode[episode_id], timestamp)
    return first_capture_by_episode, captures_by_episode


def parse_reward_audit(path: Path) -> tuple[dict[int, dict[str, float]], dict[str, float]]:
    per_episode: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    global_totals: dict[str, float] = defaultdict(float)
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        episode_id = parse_episode_id(row)
        event_name = (row.get("event_name") or "").strip()
        total = safe_float(row, "total")
        per_episode[episode_id][event_name] += total
        global_totals[event_name] += total
    return per_episode, global_totals


def summarize_coordination(
    episodes: list[dict[str, str]],
    reward_events_per_episode: dict[int, dict[str, float]],
) -> dict:
    total_episodes = max(1, len(episodes))
    sentinel_wins = {parse_episode_id(row) for row in episodes if row.get("outcome") == SENTINEL_WIN}
    pincer_presence = 0
    corridor_presence = 0
    exit_denial_presence = 0
    enclosure_presence = 0
    trap_presence = 0
    pincer_success = 0
    corridor_success = 0
    exit_success = 0
    enclosure_success = 0

    for row in episodes:
        episode_id = parse_episode_id(row)
        events = reward_events_per_episode.get(episode_id, {})
        has_pincer = events.get("pincer_event_count", 0.0) > 0
        has_corridor = events.get("corridor_block_event_count", 0.0) > 0
        has_exit = events.get("exit_denial_event_count", 0.0) > 0
        has_enclosure = events.get("enclosure_event_count", 0.0) > 0
        has_trap = events.get("trap_event_count", 0.0) > 0
        if has_pincer:
            pincer_presence += 1
            if episode_id in sentinel_wins:
                pincer_success += 1
        if has_corridor:
            corridor_presence += 1
            if episode_id in sentinel_wins:
                corridor_success += 1
        if has_exit:
            exit_denial_presence += 1
            if episode_id in sentinel_wins:
                exit_success += 1
        if has_enclosure:
            enclosure_presence += 1
            if episode_id in sentinel_wins:
                enclosure_success += 1
        if has_trap:
            trap_presence += 1

    def safe_rate(numerator: int, denominator: int) -> float:
        return numerator / denominator if denominator > 0 else 0.0

    return {
        "pincer_rate": safe_rate(pincer_presence, total_episodes),
        "corridor_block_rate": safe_rate(corridor_presence, total_episodes),
        "exit_denial_rate": safe_rate(exit_denial_presence, total_episodes),
        "trap_success_rate": safe_rate(sum(1 for episode_id in sentinel_wins if reward_events_per_episode.get(episode_id, {}).get("trap_event_count", 0.0) > 0), trap_presence),
        "enclosure_rate": safe_rate(enclosure_presence, total_episodes),
        "pincer_capture_correlation": safe_rate(pincer_success, pincer_presence),
        "corridor_capture_correlation": safe_rate(corridor_success, corridor_presence),
        "exit_denial_capture_correlation": safe_rate(exit_success, exit_denial_presence),
        "enclosure_capture_correlation": safe_rate(enclosure_success, enclosure_presence),
    }


def summarize(args: argparse.Namespace) -> dict:
    episodes = read_episode_rows(args.episode_log)
    total = len(episodes)
    sentinel_wins = sum(1 for row in episodes if row.get("outcome") == SENTINEL_WIN)
    runner_wins = sum(1 for row in episodes if row.get("outcome") in RUNNER_WINS)
    escapes = sum(int(safe_float(row, "exit_count")) > 0 for row in episodes)
    mean_full_capture_time = (
        sum(safe_float(row, "duration_seconds") for row in episodes if row.get("outcome") == SENTINEL_WIN)
        / max(1, sentinel_wins)
    )
    first_capture_by_episode, captures_by_episode = load_replay_capture_times(args.replay_log)
    mean_first_capture_time = (
        sum(first_capture_by_episode.values()) / max(1, len(first_capture_by_episode))
    )
    reward_events_per_episode, reward_event_totals = parse_reward_audit(args.reward_audit_log)

    summary = {
        "schema_version": 2,
        "protocol_version": PROTOCOL_VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": args.run_id,
        "seed": args.seed,
        "episodes": total,
        "sentinel_win_rate": sentinel_wins / max(1, total),
        "runner_win_rate": runner_wins / max(1, total),
        "escape_rate": escapes / max(1, total),
        "mean_time_to_first_capture_seconds": mean_first_capture_time,
        "mean_time_to_full_capture_seconds": mean_full_capture_time,
        "target_checks": {
            "sentinel_win_rate_45_55": 0.45 <= (sentinel_wins / max(1, total)) <= 0.55,
            "runner_win_rate_le_60": (runner_wins / max(1, total)) <= 0.60,
        },
        "coordination": summarize_coordination(episodes, reward_events_per_episode),
        "exploration_rewards_penalties": {
            "exploration_bonus_total": reward_event_totals.get("exploration_bonus", 0.0),
            "wall_loop_penalty_total": reward_event_totals.get("wall_loop_penalty", 0.0),
            "orbit_stall_penalty_total": reward_event_totals.get("orbit_stall_penalty", 0.0),
            "threat_approach_penalty_total": reward_event_totals.get("threat_approach_penalty", 0.0),
        },
    }

    if args.step_log and args.step_log.exists():
        steps = read_step_rows(args.step_log)
        path_by_agent = defaultdict(float)
        prev_pos = {}
        stalled = 0
        survival_time_by_runner: dict[str, float] = defaultdict(float)
        for row in steps:
            agent_id = row.get("agent_id", "")
            pos = (safe_float(row, "pos_x"), safe_float(row, "pos_z"))
            speed = math.sqrt(
                safe_float(row, "vel_x") ** 2 + safe_float(row, "vel_z") ** 2
            )
            if speed < args.stall_speed_threshold:
                stalled += 1
            if agent_id in prev_pos:
                dx = pos[0] - prev_pos[agent_id][0]
                dz = pos[1] - prev_pos[agent_id][1]
                path_by_agent[agent_id] += math.sqrt(dx * dx + dz * dz)
            prev_pos[agent_id] = pos
            if "Runner" in agent_id and (row.get("alive") or "").strip().lower() == "true":
                survival_time_by_runner[agent_id] = max(survival_time_by_runner[agent_id], safe_float(row, "time_seconds"))

        sentinel_path = sum(v for k, v in path_by_agent.items() if "Sentinel" in k)
        runner_path = sum(v for k, v in path_by_agent.items() if "Runner" in k)
        captures = sum(safe_float(row, "capture_count") for row in episodes)
        runner_displacement = 0.0
        runner_steps_first: dict[str, tuple[float, float]] = {}
        runner_steps_last: dict[str, tuple[float, float]] = {}
        for row in steps:
            agent_id = row.get("agent_id", "")
            if "Runner" not in agent_id:
                continue
            pos = (safe_float(row, "pos_x"), safe_float(row, "pos_z"))
            if agent_id not in runner_steps_first:
                runner_steps_first[agent_id] = pos
            runner_steps_last[agent_id] = pos
        for agent_id, first_pos in runner_steps_first.items():
            last_pos = runner_steps_last.get(agent_id, first_pos)
            dx = last_pos[0] - first_pos[0]
            dz = last_pos[1] - first_pos[1]
            runner_displacement += math.sqrt(dx * dx + dz * dz)

        summary["path_efficiency"] = {
            "captures_per_meter": captures / max(1.0, sentinel_path),
            "shortest_path_vs_actual_ratio_proxy": runner_displacement / max(1.0, runner_path),
            "note": "Shortest path ratio uses straight-line proxy from step traces.",
        }
        summary["wall_collision_recovery_time_proxy"] = {
            "metric": "stall_step_fraction",
            "value": stalled / max(1, len(steps)),
            "note": "Proxy from low-speed step fraction; direct collision recovery time is not logged yet.",
        }
        summary["runner_survival_time_seconds_mean"] = (
            sum(survival_time_by_runner.values()) / max(1, len(survival_time_by_runner))
        )
        summary["dynamic_route_change_proxy"] = {
            "metric": "runner_path_per_episode",
            "value": runner_path / max(1, total),
            "note": "Proxy for route changes after wall shifts.",
        }

    capture_sequence = {
        str(k): sorted(v) for k, v in captures_by_episode.items()
    }
    summary["capture_sequence_by_episode"] = capture_sequence

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs-dir", type=Path, help="Directory containing raw logs from one evaluation run.")
    parser.add_argument("--episode-log", type=Path)
    parser.add_argument("--step-log", type=Path)
    parser.add_argument("--reward-audit-log", type=Path)
    parser.add_argument("--replay-log", type=Path)
    parser.add_argument("--stall-speed-threshold", type=float, default=0.1)
    parser.add_argument("--run-id")
    parser.add_argument("--seed", type=int)
    parser.add_argument(
        "--expected-eval-shard",
        action="append",
        default=[],
        help="Optional expected file relative to logs-dir; warns if missing.",
    )
    parser.add_argument("--output", type=Path, default=Path("results/eval_kpi_summary.json"))
    parser.add_argument(
        "--csv-output",
        type=Path,
        help="Optional CSV output path. Defaults to <output parent>/eval_kpi_summary.csv.",
    )
    args = parser.parse_args()

    if args.logs_dir:
        logs_dir = args.logs_dir
        args.episode_log = args.episode_log or (logs_dir / "episode_log.csv")
        args.step_log = args.step_log or (logs_dir / "agent_step_log.csv")
        args.reward_audit_log = args.reward_audit_log or (logs_dir / "reward_audit.csv")
        args.replay_log = args.replay_log or (logs_dir / "replay_events.csv")

    required_inputs = [
        ("episode log", args.episode_log),
        ("step log", args.step_log),
        ("reward audit log", args.reward_audit_log),
        ("replay events log", args.replay_log),
    ]
    unresolved = [label for label, path in required_inputs if path is None]
    if unresolved:
        unresolved_text = ", ".join(unresolved)
        print(
            "Missing required input paths for KPI summarization. "
            "Provide --logs-dir or explicit --episode-log/--step-log/--reward-audit-log/--replay-log paths.\n"
            f"Unresolved inputs: {unresolved_text}"
        )
        return 2

    raw_requirements = [
        ArtifactRequirement(path=args.episode_log, label="episode_log.csv"),
        ArtifactRequirement(path=args.step_log, label="agent_step_log.csv"),
        ArtifactRequirement(path=args.reward_audit_log, label="reward_audit.csv"),
        ArtifactRequirement(path=args.replay_log, label="replay_events.csv"),
    ]
    validation_problems = validate_artifacts(raw_requirements)
    if validation_problems:
        print(format_problem_report(validation_problems, heading="Raw artifact validation failed"))
        return 2

    missing_shards: list[str] = []
    for shard in args.expected_eval_shard:
        shard_path = (args.logs_dir / shard) if args.logs_dir else Path(shard)
        if not shard_path.exists():
            missing_shards.append(str(shard_path))
    if missing_shards:
        print("Warning: missing optional eval shards:")
        for shard in missing_shards:
            print(f"- {shard}")

    summary = summarize(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    csv_output = args.csv_output or (args.output.parent / "eval_kpi_summary.csv")
    csv_output.parent.mkdir(parents=True, exist_ok=True)
    with csv_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        for key, value in summary.items():
            if isinstance(value, dict):
                writer.writerow([key, json.dumps(value, sort_keys=True)])
            else:
                writer.writerow([key, value])

    output_requirements = [
        args.output,
        csv_output,
    ]
    output_problems = validate_artifacts(
        [ArtifactRequirement(path=path, label=path.name, must_be_non_empty=True) for path in output_requirements]
    )
    if output_problems:
        print(format_problem_report(output_problems, heading="KPI output validation failed"))
        return 2

    print(f"Wrote KPI summary: {args.output}")
    print(f"Wrote KPI CSV summary: {csv_output}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
