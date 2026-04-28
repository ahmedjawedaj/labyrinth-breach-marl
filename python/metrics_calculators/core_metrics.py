#!/usr/bin/env python3
"""Compute core evaluation metrics from Labyrinth Breach evaluation logs."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any


SENTINEL_WIN_OUTCOME = "SentinelWinAllRunnersCaptured"
RUNNER_WIN_OUTCOMES = {"RunnerWinExitReached", "RunnerWinTimeout"}


@dataclass
class EpisodeSummary:
    episode_id: int
    outcome: str
    duration_seconds: float
    capture_count: int
    exit_count: int


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


def load_episode_log(path: Path) -> list[EpisodeSummary]:
    if not path.exists():
        raise FileNotFoundError(f"Missing episode log: {path}")

    episodes: list[EpisodeSummary] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            episodes.append(
                EpisodeSummary(
                    episode_id=_safe_int(row.get("episode_id", "")),
                    outcome=(row.get("outcome", "") or "").strip(),
                    duration_seconds=_safe_float(row.get("duration_seconds", "")),
                    capture_count=_safe_int(row.get("capture_count", "")),
                    exit_count=_safe_int(row.get("exit_count", "")),
                )
            )

    if not episodes:
        raise ValueError(f"No episode rows found in {path}")

    return episodes


def load_replay_events(path: Path) -> dict[int, list[dict[str, str]]]:
    if not path.exists():
        return {}

    events_by_episode: dict[int, list[dict[str, str]]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            episode_id = _safe_int(row.get("episode_id", ""))
            events_by_episode.setdefault(episode_id, []).append(row)

    return events_by_episode


def _capture_times(events: list[dict[str, str]]) -> list[float]:
    times: list[float] = []
    for row in events:
        if (row.get("event_type", "") or "").strip() != "capture":
            continue
        times.append(_safe_float(row.get("time_seconds", "")))
    return sorted(times)


def _runner_survival_times(
    episode: EpisodeSummary,
    events: list[dict[str, str]],
    expected_runner_count: int,
) -> list[float]:
    # Start each runner alive until episode end, then overwrite capture/exit timestamps.
    per_runner_time: dict[str, float] = {}
    for row in events:
        event_type = (row.get("event_type", "") or "").strip()
        event_time = _safe_float(row.get("time_seconds", ""))

        if event_type == "capture":
            runner_id = (row.get("target_id", "") or "").strip()
            if runner_id:
                per_runner_time[runner_id] = min(per_runner_time.get(runner_id, event_time), event_time)
        elif event_type == "exit":
            runner_id = (row.get("actor_id", "") or "").strip()
            if runner_id:
                per_runner_time[runner_id] = min(per_runner_time.get(runner_id, event_time), event_time)

    # If IDs are unavailable, fallback to coarse estimate.
    if not per_runner_time and expected_runner_count > 0:
        captured = max(0, min(episode.capture_count, expected_runner_count))
        exited = max(0, min(episode.exit_count, expected_runner_count - captured))
        unresolved = max(0, expected_runner_count - captured - exited)
        # With no per-event times, we can only estimate survivors as episode duration.
        return [episode.duration_seconds] * unresolved

    if expected_runner_count <= 0:
        return list(per_runner_time.values())

    times = list(per_runner_time.values())
    if len(times) < expected_runner_count:
        times.extend([episode.duration_seconds] * (expected_runner_count - len(times)))
    return times[:expected_runner_count]


def compute_core_metrics(
    episodes: list[EpisodeSummary],
    events_by_episode: dict[int, list[dict[str, str]]],
    expected_runner_count: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    total = len(episodes)
    sentinel_wins = sum(1 for ep in episodes if ep.outcome == SENTINEL_WIN_OUTCOME)
    runner_wins = sum(1 for ep in episodes if ep.outcome in RUNNER_WIN_OUTCOMES)
    exit_successes = sum(1 for ep in episodes if ep.exit_count > 0 or ep.outcome == "RunnerWinExitReached")

    first_capture_values: list[float] = []
    full_capture_values: list[float] = []
    runner_survival_values: list[float] = []
    per_episode_rows: list[dict[str, Any]] = []

    for ep in episodes:
        events = events_by_episode.get(ep.episode_id, [])
        capture_times = _capture_times(events)
        first_capture = capture_times[0] if capture_times else None
        full_capture = (
            capture_times[expected_runner_count - 1]
            if expected_runner_count > 0 and len(capture_times) >= expected_runner_count
            else None
        )

        if first_capture is not None:
            first_capture_values.append(first_capture)
        if full_capture is not None:
            full_capture_values.append(full_capture)

        runner_survivals = _runner_survival_times(ep, events, expected_runner_count)
        runner_survival_values.extend(runner_survivals)

        per_episode_rows.append(
            {
                "episode_id": ep.episode_id,
                "outcome": ep.outcome,
                "duration_seconds": ep.duration_seconds,
                "exit_success": ep.exit_count > 0 or ep.outcome == "RunnerWinExitReached",
                "first_capture_time_seconds": first_capture,
                "full_capture_time_seconds": full_capture,
                "avg_runner_survival_time_seconds": mean(runner_survivals) if runner_survivals else None,
            }
        )

    summary = {
        "schema_version": 1,
        "episode_count": total,
        "expected_runner_count": expected_runner_count,
        "win_rate": {
            "sentinel_win_rate": sentinel_wins / total if total else 0.0,
            "runner_win_rate": runner_wins / total if total else 0.0,
            "sentinel_wins": sentinel_wins,
            "runner_wins": runner_wins,
        },
        "exit_success": {
            "exit_success_rate": exit_successes / total if total else 0.0,
            "exit_success_episodes": exit_successes,
        },
        "survival_time": {
            "avg_runner_survival_time_seconds": mean(runner_survival_values) if runner_survival_values else None,
            "runner_episode_samples": len(runner_survival_values),
        },
        "capture_times": {
            "avg_first_capture_time_seconds": mean(first_capture_values) if first_capture_values else None,
            "first_capture_episode_count": len(first_capture_values),
            "avg_full_capture_time_seconds": mean(full_capture_values) if full_capture_values else None,
            "full_capture_episode_count": len(full_capture_values),
        },
    }
    return summary, per_episode_rows


def write_per_episode_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--episode-log",
        type=Path,
        required=True,
        help="Path to Unity EpisodeLogger CSV (episode_log.csv).",
    )
    parser.add_argument(
        "--replay-log",
        type=Path,
        help="Path to replay_events.csv (optional but recommended for capture timing precision).",
    )
    parser.add_argument(
        "--expected-runners",
        type=int,
        default=2,
        help="Runner count in the environment (default: 2).",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        required=True,
        help="Output JSON path for aggregated metrics.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        help="Optional per-episode metrics CSV output path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    episodes = load_episode_log(args.episode_log)
    events_by_episode = load_replay_events(args.replay_log) if args.replay_log else {}
    summary, per_episode_rows = compute_core_metrics(
        episodes,
        events_by_episode,
        expected_runner_count=max(0, args.expected_runners),
    )

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.output_csv:
        write_per_episode_csv(args.output_csv, per_episode_rows)

    print(f"Wrote core metrics summary: {args.output_json}")
    if args.output_csv:
        print(f"Wrote per-episode metrics: {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
