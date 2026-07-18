#!/usr/bin/env python3
"""Summarize protocol-aligned evaluation KPIs from raw logs."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
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
PROTOCOL_VERSION = "evaluation_protocol.md@v2"


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
        timestamp_key = "time_seconds" if (row.get("time_seconds") or "").strip() else "time"
        timestamp = safe_float(row, timestamp_key)
        captures_by_episode[episode_id].append(timestamp)
        if episode_id not in first_capture_by_episode:
            first_capture_by_episode[episode_id] = timestamp
        else:
            first_capture_by_episode[episode_id] = min(first_capture_by_episode[episode_id], timestamp)
    return first_capture_by_episode, captures_by_episode


def load_wall_shift_times(path: Path) -> dict[int, list[float]]:
    shifts_by_episode: dict[int, list[float]] = defaultdict(list)
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if (row.get("event_type") or "").strip().lower() != "wall_shift":
                continue
            episode_id = parse_episode_id(row)
            if episode_id <= 0:
                continue
            shifts_by_episode[episode_id].append(safe_float(row, "time_seconds"))
    return shifts_by_episode


def summarize_route_changes(
    steps: list[dict[str, str]],
    shifts_by_episode: dict[int, list[float]],
    window_seconds: float = 1.0,
    minimum_displacement: float = 0.05,
) -> dict:
    runner_steps: dict[tuple[int, str], list[tuple[float, float, float]]] = defaultdict(list)
    for row in steps:
        agent_id = row.get("agent_id", "")
        if "Runner" not in agent_id or (row.get("alive") or "").strip().lower() != "true":
            continue
        runner_steps[(parse_episode_id(row), agent_id)].append(
            (safe_float(row, "time_seconds"), safe_float(row, "pos_x"), safe_float(row, "pos_z"))
        )
    for trace in runner_steps.values():
        trace.sort(key=lambda item: item[0])

    def displacement(trace: list[tuple[float, float, float]], start: float, end: float) -> tuple[float, float] | None:
        window = [sample for sample in trace if start <= sample[0] <= end]
        if len(window) < 2:
            return None
        vector = (window[-1][1] - window[0][1], window[-1][2] - window[0][2])
        if math.hypot(*vector) < minimum_displacement:
            return None
        return vector

    angles: list[float] = []
    for episode_id, shift_times in shifts_by_episode.items():
        episode_traces = [trace for (trace_episode, _), trace in runner_steps.items() if trace_episode == episode_id]
        for shift_time in shift_times:
            for trace in episode_traces:
                before = displacement(trace, shift_time - window_seconds, shift_time)
                after = displacement(trace, shift_time, shift_time + window_seconds)
                if before is None or after is None:
                    continue
                denominator = math.hypot(*before) * math.hypot(*after)
                cosine = max(-1.0, min(1.0, (before[0] * after[0] + before[1] * after[1]) / denominator))
                angles.append(math.degrees(math.acos(cosine)))

    return {
        "metric": "runner_heading_deflection_after_wall_shift",
        "value": sum(angles) / len(angles) if angles else None,
        "mean_abs_heading_change_degrees": sum(angles) / len(angles) if angles else None,
        "rate_at_least_45_degrees": sum(angle >= 45.0 for angle in angles) / len(angles) if angles else None,
        "runner_shift_observations": len(angles),
        "wall_shift_events": sum(len(times) for times in shifts_by_episode.values()),
        "window_seconds_before_and_after": window_seconds,
        "minimum_displacement_meters_per_window": minimum_displacement,
        "note": "Angle between Runner displacement vectors immediately before and after each logged wall shift.",
    }


def mean_team_spread(steps: list[dict[str, str]], team: str) -> float | None:
    positions_by_snapshot: dict[tuple[int, int], list[tuple[float, float]]] = defaultdict(list)
    for row in steps:
        if (row.get("team") or "").strip() != team:
            continue
        if (row.get("alive") or "").strip().lower() != "true":
            continue
        positions_by_snapshot[(parse_episode_id(row), safe_int(row, "step_id"))].append(
            (safe_float(row, "pos_x"), safe_float(row, "pos_z"))
        )

    snapshot_means_by_episode: dict[int, list[float]] = defaultdict(list)
    for (episode_id, _), positions in positions_by_snapshot.items():
        distances = [
            math.dist(positions[left], positions[right])
            for left in range(len(positions))
            for right in range(left + 1, len(positions))
        ]
        if distances:
            snapshot_means_by_episode[episode_id].append(sum(distances) / len(distances))
    episode_means = [sum(values) / len(values) for values in snapshot_means_by_episode.values() if values]
    return sum(episode_means) / len(episode_means) if episode_means else None


def summarize_target_reacquisition(steps: list[dict[str, str]], team: str = "Sentinel") -> dict:
    snapshots: dict[tuple[int, int], dict[str, object]] = {}
    for row in steps:
        if (row.get("team") or "").strip() != team:
            continue
        if (row.get("alive") or "").strip().lower() != "true":
            continue
        key = (parse_episode_id(row), safe_int(row, "step_id"))
        snapshot = snapshots.setdefault(
            key,
            {"time_seconds": safe_float(row, "time_seconds"), "target_visible": False},
        )
        snapshot["time_seconds"] = max(
            float(snapshot["time_seconds"]), safe_float(row, "time_seconds")
        )
        if (row.get("visible_target_id") or "").strip():
            snapshot["target_visible"] = True

    by_episode: dict[int, list[tuple[int, float, bool]]] = defaultdict(list)
    for (episode_id, step_id), snapshot in snapshots.items():
        by_episode[episode_id].append(
            (step_id, float(snapshot["time_seconds"]), bool(snapshot["target_visible"]))
        )

    completed_gaps: list[float] = []
    right_censored = 0
    for episode_snapshots in by_episode.values():
        has_seen_target = False
        occlusion_started: float | None = None
        for _, timestamp, target_visible in sorted(episode_snapshots):
            if target_visible:
                if occlusion_started is not None:
                    completed_gaps.append(max(0.0, timestamp - occlusion_started))
                    occlusion_started = None
                has_seen_target = True
            elif has_seen_target and occlusion_started is None:
                occlusion_started = timestamp
        if occlusion_started is not None:
            right_censored += 1

    return {
        "metric": "sentinel_team_target_reacquisition_delay",
        "mean_seconds": statistics.fmean(completed_gaps) if completed_gaps else None,
        "median_seconds": statistics.median(completed_gaps) if completed_gaps else None,
        "completed_occlusion_gaps": len(completed_gaps),
        "right_censored_occlusion_gaps": right_censored,
        "note": (
            "Elapsed time from loss of all team-level visible Runner targets to the next visible target; "
            "initial acquisition is excluded."
        ),
    }


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
        "pincer_episode_rate": safe_rate(pincer_presence, total_episodes),
        "corridor_block_episode_rate": safe_rate(corridor_presence, total_episodes),
        "exit_denial_episode_rate": safe_rate(exit_denial_presence, total_episodes),
        "trap_episode_rate": safe_rate(trap_presence, total_episodes),
        "trap_success_rate": safe_rate(sum(1 for episode_id in sentinel_wins if reward_events_per_episode.get(episode_id, {}).get("trap_event_count", 0.0) > 0), trap_presence),
        "enclosure_episode_rate": safe_rate(enclosure_presence, total_episodes),
        "pincer_events_per_episode": sum(events.get("pincer_event_count", 0.0) for events in reward_events_per_episode.values()) / total_episodes,
        "corridor_block_events_per_episode": sum(events.get("corridor_block_event_count", 0.0) for events in reward_events_per_episode.values()) / total_episodes,
        "exit_denial_events_per_episode": sum(events.get("exit_denial_event_count", 0.0) for events in reward_events_per_episode.values()) / total_episodes,
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
    wall_shifts_by_episode = load_wall_shift_times(args.replay_log)
    mean_first_capture_time = (
        sum(first_capture_by_episode.values()) / max(1, len(first_capture_by_episode))
    )
    reward_events_per_episode, reward_event_totals = parse_reward_audit(args.reward_audit_log)

    summary = {
        "schema_version": 3,
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
        path_by_agent_episode: dict[tuple[int, str], float] = defaultdict(float)
        prev_pos: dict[tuple[int, str], tuple[float, float]] = {}
        stalled = 0
        survival_time_by_runner_episode: dict[tuple[int, str], float] = defaultdict(float)
        for row in steps:
            agent_id = row.get("agent_id", "")
            episode_agent = (parse_episode_id(row), agent_id)
            pos = (safe_float(row, "pos_x"), safe_float(row, "pos_z"))
            speed = math.sqrt(
                safe_float(row, "vel_x") ** 2 + safe_float(row, "vel_z") ** 2
            )
            if speed < args.stall_speed_threshold:
                stalled += 1
            if episode_agent in prev_pos:
                dx = pos[0] - prev_pos[episode_agent][0]
                dz = pos[1] - prev_pos[episode_agent][1]
                path_by_agent_episode[episode_agent] += math.sqrt(dx * dx + dz * dz)
            prev_pos[episode_agent] = pos
            if "Runner" in agent_id and (row.get("alive") or "").strip().lower() == "true":
                survival_time_by_runner_episode[episode_agent] = max(
                    survival_time_by_runner_episode[episode_agent], safe_float(row, "time_seconds")
                )

        sentinel_path = sum(v for (_, agent_id), v in path_by_agent_episode.items() if "Sentinel" in agent_id)
        runner_path = sum(v for (_, agent_id), v in path_by_agent_episode.items() if "Runner" in agent_id)
        captures = sum(safe_float(row, "capture_count") for row in episodes)
        runner_displacement = 0.0
        runner_steps_first: dict[tuple[int, str], tuple[float, float]] = {}
        runner_steps_last: dict[tuple[int, str], tuple[float, float]] = {}
        for row in steps:
            agent_id = row.get("agent_id", "")
            if "Runner" not in agent_id:
                continue
            episode_agent = (parse_episode_id(row), agent_id)
            pos = (safe_float(row, "pos_x"), safe_float(row, "pos_z"))
            if episode_agent not in runner_steps_first:
                runner_steps_first[episode_agent] = pos
            runner_steps_last[episode_agent] = pos
        for episode_agent, first_pos in runner_steps_first.items():
            last_pos = runner_steps_last.get(episode_agent, first_pos)
            dx = last_pos[0] - first_pos[0]
            dz = last_pos[1] - first_pos[1]
            runner_displacement += math.sqrt(dx * dx + dz * dz)

        summary["path_efficiency"] = {
            "captures_per_meter": captures / max(1.0, sentinel_path),
            "shortest_path_vs_actual_ratio_proxy": runner_displacement / max(1.0, runner_path),
            "sentinel_path_meters_per_episode": sentinel_path / max(1, total),
            "runner_path_meters_per_episode": runner_path / max(1, total),
            "note": "Shortest path ratio uses straight-line proxy from step traces.",
        }
        summary["wall_collision_recovery_time_proxy"] = {
            "metric": "stall_step_fraction",
            "value": stalled / max(1, len(steps)),
            "note": "Proxy from low-speed step fraction; direct collision recovery time is not logged yet.",
        }
        summary["runner_survival_time_seconds_mean"] = (
            sum(survival_time_by_runner_episode.values()) / max(1, len(survival_time_by_runner_episode))
        )
        summary["spatial_coordination"] = {
            "sentinel_spread_meters_mean": mean_team_spread(steps, "Sentinel"),
            "runner_separation_meters_mean": mean_team_spread(steps, "Runner"),
            "note": "Within-team pairwise planar distance averaged over snapshots per episode, then equally over episodes.",
        }
        summary["target_reacquisition"] = summarize_target_reacquisition(steps)
        summary["dynamic_route_change_proxy"] = summarize_route_changes(steps, wall_shifts_by_episode)

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
