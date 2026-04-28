#!/usr/bin/env python3
"""Deterministic runner role emergence analysis from run logs."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

ROLES = ["ExitRunner", "Splitter", "Decoy", "SurvivalOriented"]
WINDOW_STEPS = 12
EXIT_PROGRESS_THRESHOLD = 0.45
MAX_PATH_DEVIATION_RATIO = 1.35
SPLITTER_SEPARATION_THRESHOLD = 3.5
SPLITTER_GROWTH_THRESHOLD = 0.9
DECOY_PROXIMITY_THRESHOLD = 3.25
DECOY_MARGIN = 1.0
SURVIVAL_DISTANCE_THRESHOLD = 4.0
SURVIVAL_EXIT_PROGRESS_MAX = 0.15


def safe_float(row: dict[str, str], key: str) -> float:
    try:
        return float((row.get(key) or "0").strip() or 0)
    except ValueError:
        return 0.0


def safe_int(row: dict[str, str], key: str) -> int:
    return int(round(safe_float(row, key)))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def nearest_exit_distance(pos: tuple[float, float], exits: list[tuple[float, float]]) -> float:
    if not exits:
        return 0.0
    return min(math.dist(pos, exit_pos) for exit_pos in exits)


def infer_exit_positions(replay_rows: list[dict[str, str]], step_rows: list[dict[str, str]]) -> list[tuple[float, float]]:
    exits: list[tuple[float, float]] = []
    for row in replay_rows:
        if (row.get("event_type") or "").strip() != "exit":
            continue
        exits.append((safe_float(row, "x"), safe_float(row, "z")))
    if exits:
        return exits

    # Fallback: last known runner positions from timeout/episode-end windows.
    runner_positions = []
    for row in step_rows:
        if (row.get("team") or "").strip() == "Runner":
            runner_positions.append((safe_float(row, "pos_x"), safe_float(row, "pos_z")))
    if not runner_positions:
        return []
    return [runner_positions[-1]]


def build_episode_runner_series(step_rows: list[dict[str, str]]) -> dict[tuple[int, str], list[dict[str, float]]]:
    series: dict[tuple[int, str], list[dict[str, float]]] = defaultdict(list)
    for row in step_rows:
        if (row.get("team") or "").strip() != "Runner":
            continue
        ep = safe_int(row, "episode_id")
        runner = (row.get("agent_id") or "").strip()
        if not runner:
            continue
        series[(ep, runner)].append(
            {
                "step": safe_int(row, "step_id"),
                "time": safe_float(row, "time_seconds"),
                "x": safe_float(row, "pos_x"),
                "z": safe_float(row, "pos_z"),
                "nearest_sentinel_distance": safe_float(row, "visible_target_distance"),
                "alive": 1.0 if (row.get("alive") or "").strip().lower() == "true" else 0.0,
            }
        )
    for key in list(series.keys()):
        series[key].sort(key=lambda item: (item["step"], item["time"]))
    return series


def classify_role_window(
    runner_window: list[dict[str, float]],
    teammate_window: list[dict[str, float]] | None,
    exits: list[tuple[float, float]],
) -> str:
    first = runner_window[0]
    last = runner_window[-1]
    first_pos = (first["x"], first["z"])
    last_pos = (last["x"], last["z"])
    exit_dist_first = nearest_exit_distance(first_pos, exits)
    exit_dist_last = nearest_exit_distance(last_pos, exits)
    path_len = 0.0
    for i in range(1, len(runner_window)):
        a = runner_window[i - 1]
        b = runner_window[i]
        path_len += math.dist((a["x"], a["z"]), (b["x"], b["z"]))
    straight = math.dist(first_pos, last_pos)
    deviation_ratio = path_len / max(1e-4, straight)
    if (exit_dist_first - exit_dist_last) >= EXIT_PROGRESS_THRESHOLD and deviation_ratio <= MAX_PATH_DEVIATION_RATIO:
        return "ExitRunner"

    if teammate_window is not None:
        teammate_first = teammate_window[0]
        teammate_last = teammate_window[-1]
        sep_first = math.dist(first_pos, (teammate_first["x"], teammate_first["z"]))
        sep_last = math.dist(last_pos, (teammate_last["x"], teammate_last["z"]))
        if sep_last >= SPLITTER_SEPARATION_THRESHOLD and (sep_last - sep_first) >= SPLITTER_GROWTH_THRESHOLD:
            return "Splitter"

    nearest_values = [entry["nearest_sentinel_distance"] for entry in runner_window if entry["nearest_sentinel_distance"] > 0]
    nearest_mean = sum(nearest_values) / max(1, len(nearest_values))
    exit_progress = exit_dist_first - exit_dist_last
    if nearest_mean >= SURVIVAL_DISTANCE_THRESHOLD and exit_progress <= SURVIVAL_EXIT_PROGRESS_MAX:
        return "SurvivalOriented"

    return "Decoy"


def detect_runner_roles(
    step_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    episodes: list[dict[str, str]],
) -> tuple[list[dict], list[dict]]:
    exits = infer_exit_positions(replay_rows, step_rows)
    series = build_episode_runner_series(step_rows)
    episode_runner_ids: dict[int, list[str]] = defaultdict(list)
    for ep, runner in series.keys():
        episode_runner_ids[ep].append(runner)
    for ep in list(episode_runner_ids.keys()):
        episode_runner_ids[ep] = sorted(set(episode_runner_ids[ep]))

    outcome_by_episode = {safe_int(row, "episode_id"): (row.get("outcome") or "") for row in episodes}
    duration_by_episode = {safe_int(row, "episode_id"): safe_float(row, "duration_seconds") for row in episodes}

    episode_breakdown: list[dict] = []
    role_time_total: defaultdict[str, float] = defaultdict(float)
    role_episode_presence: defaultdict[str, int] = defaultdict(int)
    role_escape_success: defaultdict[str, int] = defaultdict(int)
    role_survival_sum: defaultdict[str, float] = defaultdict(float)
    role_survival_count: defaultdict[str, int] = defaultdict(int)

    for ep, runners in episode_runner_ids.items():
        episode_role_presence: dict[str, int] = {role: 0 for role in ROLES}
        for runner in runners:
            key = (ep, runner)
            runner_series = series[key]
            teammate = None
            for candidate in runners:
                if candidate != runner:
                    teammate = candidate
                    break
            teammate_series = series.get((ep, teammate), []) if teammate else []

            role_by_step: list[str] = []
            for idx in range(len(runner_series)):
                start = max(0, idx - WINDOW_STEPS + 1)
                runner_window = runner_series[start : idx + 1]
                teammate_window = None
                if teammate_series:
                    teammate_start = max(0, min(start, len(teammate_series) - 1))
                    teammate_end = min(len(teammate_series), teammate_start + len(runner_window))
                    teammate_window = teammate_series[teammate_start:teammate_end]
                    if len(teammate_window) < len(runner_window):
                        teammate_window = None

                role = classify_role_window(runner_window, teammate_window, exits)

                # Decoy refinement: check proximity concentration against teammate.
                if role == "Decoy" and teammate_window is not None:
                    runner_nearest = [entry["nearest_sentinel_distance"] for entry in runner_window if entry["nearest_sentinel_distance"] > 0]
                    teammate_nearest = [entry["nearest_sentinel_distance"] for entry in teammate_window if entry["nearest_sentinel_distance"] > 0]
                    if runner_nearest and teammate_nearest:
                        runner_mean = sum(runner_nearest) / len(runner_nearest)
                        teammate_mean = sum(teammate_nearest) / len(teammate_nearest)
                        if not (runner_mean <= DECOY_PROXIMITY_THRESHOLD and teammate_mean - runner_mean >= DECOY_MARGIN):
                            # fallback deterministic tie-break
                            role = "SurvivalOriented" if runner_mean > teammate_mean else "Decoy"

                role_by_step.append(role)
                role_time_total[role] += 1.0
                episode_role_presence[role] = 1

            transitions = 0
            for i in range(1, len(role_by_step)):
                if role_by_step[i] != role_by_step[i - 1]:
                    transitions += 1

            for role in ROLES:
                if role in role_by_step:
                    role_survival_sum[role] += duration_by_episode.get(ep, 0.0)
                    role_survival_count[role] += 1
                    if outcome_by_episode.get(ep, "") in {"RunnerWinExitReached", "RunnerWinTimeout"}:
                        role_escape_success[role] += 1

            role_counts = {role: role_by_step.count(role) for role in ROLES}
            episode_breakdown.append(
                {
                    "episode_id": ep,
                    "runner_id": runner,
                    "steps_total": len(role_by_step),
                    "role_transitions": transitions,
                    "time_exit_runner": role_counts["ExitRunner"],
                    "time_splitter": role_counts["Splitter"],
                    "time_decoy": role_counts["Decoy"],
                    "time_survival_oriented": role_counts["SurvivalOriented"],
                    "dominant_role": max(ROLES, key=lambda role: role_counts[role]),
                    "episode_outcome": outcome_by_episode.get(ep, ""),
                    "episode_survival_time_seconds": duration_by_episode.get(ep, 0.0),
                }
            )

        for role, present in episode_role_presence.items():
            role_episode_presence[role] += present

    total_steps = sum(row["steps_total"] for row in episode_breakdown)
    total_episodes = len({row["episode_id"] for row in episode_breakdown})
    role_summary: list[dict] = []
    for role in ROLES:
        role_summary.append(
            {
                "role": role,
                "percent_time": role_time_total[role] / max(1, total_steps),
                "role_frequency_per_episode": role_episode_presence[role] / max(1, total_episodes),
                "escape_success_correlation": role_escape_success[role] / max(1, role_survival_count[role]),
                "mean_survival_time_seconds_when_present": role_survival_sum[role] / max(1, role_survival_count[role]),
            }
        )
    return role_summary, episode_breakdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--stage-label", required=True)
    parser.add_argument("--output-base", type=Path, required=True)
    return parser


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise RuntimeError(f"No rows to write for {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    args = build_parser().parse_args()
    logs_dir = args.run_root / "logs"
    required = [
        logs_dir / "episode_log.csv",
        logs_dir / "agent_step_log.csv",
        logs_dir / "replay_events.csv",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        joined = "\n  ".join(missing)
        raise FileNotFoundError(f"Runner role analysis missing required logs:\n  {joined}")

    episode_rows = read_csv(required[0])
    step_rows = read_csv(required[1])
    replay_rows = read_csv(required[2])
    role_summary, episode_breakdown = detect_runner_roles(step_rows, replay_rows, episode_rows)

    # Required output path from task: results/<seed_id>/runner_role_analysis/
    numeric_seed_dir = args.output_base / str(args.seed) / "runner_role_analysis"
    numeric_seed_dir.mkdir(parents=True, exist_ok=True)
    write_csv(numeric_seed_dir / "role_summary.csv", role_summary)
    write_csv(numeric_seed_dir / "role_episode_breakdown.csv", episode_breakdown)

    # Keep compatibility with existing seed_<id> convention.
    compat_seed_dir = args.output_base / f"seed_{args.seed}" / "runner_role_analysis"
    compat_seed_dir.mkdir(parents=True, exist_ok=True)
    write_csv(compat_seed_dir / f"role_summary_{args.stage_label}.csv", role_summary)
    write_csv(compat_seed_dir / f"role_episode_breakdown_{args.stage_label}.csv", episode_breakdown)

    summary_payload = {
        "seed": args.seed,
        "stage_label": args.stage_label,
        "thresholds": {
            "window_steps": WINDOW_STEPS,
            "exit_progress_threshold": EXIT_PROGRESS_THRESHOLD,
            "max_path_deviation_ratio": MAX_PATH_DEVIATION_RATIO,
            "splitter_separation_threshold": SPLITTER_SEPARATION_THRESHOLD,
            "splitter_growth_threshold": SPLITTER_GROWTH_THRESHOLD,
            "decoy_proximity_threshold": DECOY_PROXIMITY_THRESHOLD,
            "decoy_margin": DECOY_MARGIN,
            "survival_distance_threshold": SURVIVAL_DISTANCE_THRESHOLD,
            "survival_exit_progress_max": SURVIVAL_EXIT_PROGRESS_MAX,
        },
        "role_summary": role_summary,
        "episode_breakdown_rows": len(episode_breakdown),
    }
    (numeric_seed_dir / "role_summary.json").write_text(json.dumps(summary_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote runner role emergence outputs for seed={args.seed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
