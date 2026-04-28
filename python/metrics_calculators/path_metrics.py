#!/usr/bin/env python3
"""Compute path metrics for static and dynamic maze evaluation logs."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any


@dataclass
class StepPoint:
    step_id: int
    time_seconds: float
    x: float
    z: float


@dataclass
class EpisodeMeta:
    episode_id: int
    outcome: str
    wall_shift_count: int


def _safe_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _distance_2d(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def load_episode_meta(path: Path) -> dict[int, EpisodeMeta]:
    if not path.exists():
        raise FileNotFoundError(f"Missing episode log: {path}")

    by_episode: dict[int, EpisodeMeta] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            episode_id = _safe_int(row.get("episode_id", ""))
            by_episode[episode_id] = EpisodeMeta(
                episode_id=episode_id,
                outcome=(row.get("outcome", "") or "").strip(),
                wall_shift_count=_safe_int(row.get("wall_shift_count", "")),
            )

    if not by_episode:
        raise ValueError(f"No episode rows found in {path}")
    return by_episode


def load_step_paths(path: Path) -> dict[int, dict[str, list[StepPoint]]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing step log: {path}")

    by_episode_agent: dict[int, dict[str, list[StepPoint]]] = defaultdict(lambda: defaultdict(list))
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            episode_id = _safe_int(row.get("episode_id", ""))
            agent_id = (row.get("agent_id", "") or "").strip()
            if not agent_id:
                continue
            by_episode_agent[episode_id][agent_id].append(
                StepPoint(
                    step_id=_safe_int(row.get("step_id", "")),
                    time_seconds=_safe_float(row.get("time_seconds", "")),
                    x=_safe_float(row.get("pos_x", "")),
                    z=_safe_float(row.get("pos_z", "")),
                )
            )

    for episode_agents in by_episode_agent.values():
        for path_points in episode_agents.values():
            path_points.sort(key=lambda point: (point.step_id, point.time_seconds))

    return by_episode_agent


def load_agent_teams(path: Path) -> dict[int, dict[str, str]]:
    by_episode_agent_team: dict[int, dict[str, str]] = defaultdict(dict)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            episode_id = _safe_int(row.get("episode_id", ""))
            agent_id = (row.get("agent_id", "") or "").strip()
            team = (row.get("team", "") or "").strip()
            if episode_id and agent_id and team:
                by_episode_agent_team[episode_id][agent_id] = team
    return by_episode_agent_team


def load_exit_positions(replay_log: Path | None) -> dict[int, dict[str, tuple[float, float]]]:
    if replay_log is None or not replay_log.exists():
        return {}

    by_episode_runner: dict[int, dict[str, tuple[float, float]]] = defaultdict(dict)
    with replay_log.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            event_type = (row.get("event_type", "") or "").strip()
            if event_type != "exit":
                continue
            episode_id = _safe_int(row.get("episode_id", ""))
            runner_id = (row.get("actor_id", "") or "").strip()
            x = _safe_float(row.get("x", ""))
            z = _safe_float(row.get("z", ""))
            if episode_id and runner_id:
                by_episode_runner[episode_id][runner_id] = (x, z)
    return by_episode_runner


def path_length(points: list[StepPoint]) -> float:
    if len(points) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(points)):
        total += _distance_2d((points[i - 1].x, points[i - 1].z), (points[i].x, points[i].z))
    return total


def compute_path_metrics(
    episode_meta: dict[int, EpisodeMeta],
    step_paths: dict[int, dict[str, list[StepPoint]]],
    episode_teams: dict[int, dict[str, str]],
    exit_positions: dict[int, dict[str, tuple[float, float]]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    per_episode_rows: list[dict[str, Any]] = []

    runner_efficiencies_static: list[float] = []
    runner_efficiencies_dynamic: list[float] = []
    runner_shortest_ratios_static: list[float] = []
    runner_shortest_ratios_dynamic: list[float] = []
    sentinel_efficiencies_static: list[float] = []
    sentinel_efficiencies_dynamic: list[float] = []

    for episode_id, meta in episode_meta.items():
        agents = step_paths.get(episode_id, {})
        teams = episode_teams.get(episode_id, {})
        variant = "dynamic" if meta.wall_shift_count > 0 else "static"

        runner_eff_episode: list[float] = []
        runner_ratio_episode: list[float] = []
        sentinel_eff_episode: list[float] = []

        for agent_id, points in agents.items():
            if len(points) < 2:
                continue
            team = teams.get(agent_id, "")
            start = (points[0].x, points[0].z)
            end = (points[-1].x, points[-1].z)
            actual = path_length(points)
            if actual <= 0:
                continue

            net_displacement = _distance_2d(start, end)
            path_efficiency = net_displacement / actual

            if team == "Runner":
                target = exit_positions.get(episode_id, {}).get(agent_id, end)
                shortest_estimate = _distance_2d(start, target)
                shortest_ratio = shortest_estimate / actual
                runner_eff_episode.append(path_efficiency)
                runner_ratio_episode.append(shortest_ratio)
            elif team == "Sentinel":
                sentinel_eff_episode.append(path_efficiency)

        if variant == "dynamic":
            runner_efficiencies_dynamic.extend(runner_eff_episode)
            runner_shortest_ratios_dynamic.extend(runner_ratio_episode)
            sentinel_efficiencies_dynamic.extend(sentinel_eff_episode)
        else:
            runner_efficiencies_static.extend(runner_eff_episode)
            runner_shortest_ratios_static.extend(runner_ratio_episode)
            sentinel_efficiencies_static.extend(sentinel_eff_episode)

        per_episode_rows.append(
            {
                "episode_id": episode_id,
                "maze_variant": variant,
                "outcome": meta.outcome,
                "wall_shift_count": meta.wall_shift_count,
                "runner_path_efficiency_avg": mean(runner_eff_episode) if runner_eff_episode else None,
                "runner_shortest_vs_actual_ratio_avg": mean(runner_ratio_episode) if runner_ratio_episode else None,
                "sentinel_path_efficiency_avg": mean(sentinel_eff_episode) if sentinel_eff_episode else None,
                "runner_samples": len(runner_eff_episode),
                "sentinel_samples": len(sentinel_eff_episode),
            }
        )

    summary = {
        "schema_version": 1,
        "episode_count": len(episode_meta),
        "path_metrics": {
            "static": {
                "runner_path_efficiency_avg": mean(runner_efficiencies_static) if runner_efficiencies_static else None,
                "runner_shortest_vs_actual_ratio_avg": mean(runner_shortest_ratios_static)
                if runner_shortest_ratios_static
                else None,
                "sentinel_path_efficiency_avg": mean(sentinel_efficiencies_static) if sentinel_efficiencies_static else None,
                "runner_sample_count": len(runner_efficiencies_static),
                "sentinel_sample_count": len(sentinel_efficiencies_static),
            },
            "dynamic": {
                "runner_path_efficiency_avg": mean(runner_efficiencies_dynamic) if runner_efficiencies_dynamic else None,
                "runner_shortest_vs_actual_ratio_avg": mean(runner_shortest_ratios_dynamic)
                if runner_shortest_ratios_dynamic
                else None,
                "sentinel_path_efficiency_avg": mean(sentinel_efficiencies_dynamic)
                if sentinel_efficiencies_dynamic
                else None,
                "runner_sample_count": len(runner_efficiencies_dynamic),
                "sentinel_sample_count": len(sentinel_efficiencies_dynamic),
            },
        },
        "notes": {
            "shortest_path_estimation": (
                "Shortest-path distance is estimated from start to exit-event position (if available) "
                "or final observed position; ratio is shortest_estimate / actual_path_length."
            )
        },
    }
    return summary, per_episode_rows


def write_episode_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode-log", type=Path, required=True, help="Path to episode_log.csv.")
    parser.add_argument("--step-log", type=Path, required=True, help="Path to agent_step_log.csv.")
    parser.add_argument(
        "--replay-log",
        type=Path,
        help="Optional replay_events.csv for runner exit target positions.",
    )
    parser.add_argument("--output-json", type=Path, required=True, help="Output summary JSON path.")
    parser.add_argument("--output-csv", type=Path, help="Optional per-episode CSV path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    episode_meta = load_episode_meta(args.episode_log)
    step_paths = load_step_paths(args.step_log)
    teams = load_agent_teams(args.step_log)
    exit_positions = load_exit_positions(args.replay_log)
    summary, rows = compute_path_metrics(episode_meta, step_paths, teams, exit_positions)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.output_csv:
        write_episode_csv(args.output_csv, rows)

    print(f"Wrote path metrics summary: {args.output_json}")
    if args.output_csv:
        print(f"Wrote per-episode path metrics: {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
