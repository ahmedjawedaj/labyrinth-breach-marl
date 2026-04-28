#!/usr/bin/env python3
"""Compute coordination metrics from Labyrinth Breach evaluation logs."""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any


TRAP_EVENT_NAMES = {
    "trap_pincer",
    "trap_enclosure",
    "trap_dead_end_forcing",
    "trap_exit_denial",
    "trap_corridor_control",
}


@dataclass
class EpisodeCoordination:
    episode_id: int
    pincer_formations: int
    trap_formations: int
    corridor_block_count: int
    exit_denial_count: int
    sentinel_spread_avg: float | None
    runner_separation_avg: float | None


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


def load_episode_ids(path: Path) -> list[int]:
    if not path.exists():
        raise FileNotFoundError(f"Missing episode log: {path}")

    episode_ids: list[int] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            episode_ids.append(_safe_int(row.get("episode_id", "")))
    if not episode_ids:
        raise ValueError(f"No episode rows found in {path}")
    return episode_ids


def _formation_key(row: dict[str, str]) -> tuple[int, str, str, str]:
    # Deduplicate repeated per-agent rewards for the same trap formation.
    return (
        _safe_int(row.get("step_id", "")),
        (row.get("event_name", "") or "").strip(),
        (row.get("target_id", "") or "").strip(),
        (row.get("details", "") or "").strip(),
    )


def load_trap_formations(replay_log: Path) -> dict[int, dict[str, set[tuple[int, str, str, str]]]]:
    if not replay_log.exists():
        raise FileNotFoundError(f"Missing replay log: {replay_log}")

    by_episode: dict[int, dict[str, set[tuple[int, str, str, str]]]] = {}
    with replay_log.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            event_type = (row.get("event_type", "") or "").strip()
            event_name = (row.get("event_name", "") or "").strip()
            if event_type != "reward" or event_name not in TRAP_EVENT_NAMES:
                continue

            episode_id = _safe_int(row.get("episode_id", ""))
            by_event = by_episode.setdefault(episode_id, {})
            by_event.setdefault(event_name, set()).add(_formation_key(row))

    return by_episode


def _distance_2d(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _average_pairwise_distance(points: list[tuple[float, float]]) -> float | None:
    if len(points) < 2:
        return None
    distances: list[float] = []
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            distances.append(_distance_2d(points[i], points[j]))
    return mean(distances) if distances else None


def load_spread_metrics(step_log: Path) -> tuple[dict[int, float], dict[int, float]]:
    if not step_log.exists():
        raise FileNotFoundError(f"Missing step log: {step_log}")

    # episode -> step -> list[(x,z)]
    sentinel_positions: dict[int, dict[int, list[tuple[float, float]]]] = {}
    runner_positions: dict[int, dict[int, list[tuple[float, float]]]] = {}

    with step_log.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if (row.get("alive", "") or "").strip().lower() != "true":
                continue

            episode_id = _safe_int(row.get("episode_id", ""))
            step_id = _safe_int(row.get("step_id", ""))
            team = (row.get("team", "") or "").strip()
            x = _safe_float(row.get("pos_x", ""))
            z = _safe_float(row.get("pos_z", ""))

            if team == "Sentinel":
                sentinel_positions.setdefault(episode_id, {}).setdefault(step_id, []).append((x, z))
            elif team == "Runner":
                runner_positions.setdefault(episode_id, {}).setdefault(step_id, []).append((x, z))

    sentinel_spread: dict[int, float] = {}
    runner_separation: dict[int, float] = {}

    for episode_id, by_step in sentinel_positions.items():
        step_values = [
            pairwise
            for pairwise in (_average_pairwise_distance(points) for points in by_step.values())
            if pairwise is not None
        ]
        if step_values:
            sentinel_spread[episode_id] = mean(step_values)

    for episode_id, by_step in runner_positions.items():
        step_values = [
            pairwise
            for pairwise in (_average_pairwise_distance(points) for points in by_step.values())
            if pairwise is not None
        ]
        if step_values:
            runner_separation[episode_id] = mean(step_values)

    return sentinel_spread, runner_separation


def compute_coordination_metrics(
    episode_ids: list[int],
    trap_formations: dict[int, dict[str, set[tuple[int, str, str, str]]]],
    sentinel_spread: dict[int, float],
    runner_separation: dict[int, float],
) -> tuple[dict[str, Any], list[EpisodeCoordination]]:
    per_episode: list[EpisodeCoordination] = []

    for episode_id in episode_ids:
        by_event = trap_formations.get(episode_id, {})
        pincer_count = len(by_event.get("trap_pincer", set()))
        corridor_count = len(by_event.get("trap_corridor_control", set()))
        exit_denial_count = len(by_event.get("trap_exit_denial", set()))
        total_traps = sum(len(formations) for formations in by_event.values())

        per_episode.append(
            EpisodeCoordination(
                episode_id=episode_id,
                pincer_formations=pincer_count,
                trap_formations=total_traps,
                corridor_block_count=corridor_count,
                exit_denial_count=exit_denial_count,
                sentinel_spread_avg=sentinel_spread.get(episode_id),
                runner_separation_avg=runner_separation.get(episode_id),
            )
        )

    total_episodes = len(per_episode)
    pincer_episode_count = sum(1 for ep in per_episode if ep.pincer_formations > 0)
    trap_episode_count = sum(1 for ep in per_episode if ep.trap_formations > 0)

    summary = {
        "schema_version": 1,
        "episode_count": total_episodes,
        "coordination_metrics": {
            "pincer_rate": {
                "episodes_with_pincer_rate": pincer_episode_count / total_episodes if total_episodes else 0.0,
                "avg_pincer_formations_per_episode": mean([ep.pincer_formations for ep in per_episode])
                if per_episode
                else 0.0,
                "episodes_with_pincer": pincer_episode_count,
            },
            "trap_frequency": {
                "episodes_with_trap_rate": trap_episode_count / total_episodes if total_episodes else 0.0,
                "avg_trap_formations_per_episode": mean([ep.trap_formations for ep in per_episode]) if per_episode else 0.0,
                "total_trap_formations": sum(ep.trap_formations for ep in per_episode),
            },
            "sentinel_spread": {
                "avg_pairwise_distance": mean(
                    [ep.sentinel_spread_avg for ep in per_episode if ep.sentinel_spread_avg is not None]
                )
                if any(ep.sentinel_spread_avg is not None for ep in per_episode)
                else None,
            },
            "runner_separation": {
                "avg_pairwise_distance": mean(
                    [ep.runner_separation_avg for ep in per_episode if ep.runner_separation_avg is not None]
                )
                if any(ep.runner_separation_avg is not None for ep in per_episode)
                else None,
            },
            "corridor_block_count": {
                "total": sum(ep.corridor_block_count for ep in per_episode),
                "avg_per_episode": mean([ep.corridor_block_count for ep in per_episode]) if per_episode else 0.0,
            },
            "exit_denial_count": {
                "total": sum(ep.exit_denial_count for ep in per_episode),
                "avg_per_episode": mean([ep.exit_denial_count for ep in per_episode]) if per_episode else 0.0,
            },
        },
    }
    return summary, per_episode


def write_episode_csv(path: Path, per_episode: list[EpisodeCoordination]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "episode_id",
                "pincer_formations",
                "trap_formations",
                "corridor_block_count",
                "exit_denial_count",
                "sentinel_spread_avg",
                "runner_separation_avg",
            ],
        )
        writer.writeheader()
        for ep in per_episode:
            writer.writerow(
                {
                    "episode_id": ep.episode_id,
                    "pincer_formations": ep.pincer_formations,
                    "trap_formations": ep.trap_formations,
                    "corridor_block_count": ep.corridor_block_count,
                    "exit_denial_count": ep.exit_denial_count,
                    "sentinel_spread_avg": ep.sentinel_spread_avg,
                    "runner_separation_avg": ep.runner_separation_avg,
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode-log", type=Path, required=True, help="Path to episode_log.csv.")
    parser.add_argument("--replay-log", type=Path, required=True, help="Path to replay_events.csv.")
    parser.add_argument("--step-log", type=Path, required=True, help="Path to agent_step_log.csv.")
    parser.add_argument("--output-json", type=Path, required=True, help="Output JSON summary path.")
    parser.add_argument("--output-csv", type=Path, help="Optional per-episode CSV output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    episode_ids = load_episode_ids(args.episode_log)
    trap_formations = load_trap_formations(args.replay_log)
    sentinel_spread, runner_separation = load_spread_metrics(args.step_log)
    summary, per_episode = compute_coordination_metrics(
        episode_ids=episode_ids,
        trap_formations=trap_formations,
        sentinel_spread=sentinel_spread,
        runner_separation=runner_separation,
    )

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.output_csv:
        write_episode_csv(args.output_csv, per_episode)

    print(f"Wrote coordination metrics summary: {args.output_json}")
    if args.output_csv:
        print(f"Wrote per-episode coordination metrics: {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
