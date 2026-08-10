#!/usr/bin/env python3
"""Read-only status monitor for Labyrinth Breach publication evidence gates."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MEMORY_OFF_SEEDS = [42, 101, 202, 606, 707]
MEMORY_OFF_STAGE4_TARGET_STEPS = 1_500_000
PROCESS_PATTERNS = [
    "mlagents-learn",
    "LabyrinthBreach.app",
    "MacOS/Labyrinth Breach",
    "scripts/train_with_metadata.py",
    "run_memory_off_stage4",
]
STEP_RE = re.compile(
    r"^\[INFO\]\s+(?P<behavior>\w+)\.\s+Step:\s+(?P<step>\d+)\.\s+"
    r"Time Elapsed:\s+(?P<elapsed>\d+(?:\.\d+)?)\s+s\.\s+Mean Reward:\s+"
    r"(?P<reward>-?\d+(?:\.\d+)?)"
)
ELO_RE = re.compile(r"ELO:\s+(?P<elo>-?\d+(?:\.\d+)?)")
EXPORT_RE = re.compile(r"(?P<behavior>Runner|Sentinel)-(?P<step>\d+)\.(?:onnx|pt)$")
RESUME_FROM_RE = re.compile(r"^\[INFO\]\s+Resuming from .*/(?P<behavior>Runner|Sentinel)\.?$")
RESUME_STEP_RE = re.compile(r"^\[INFO\]\s+Resuming training from step (?P<step>\d+)\.")


def run_command(command: list[str]) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return completed.returncode, completed.stdout.strip()


def screen_status() -> dict[str, Any]:
    screen = shutil.which("screen") or "/opt/homebrew/bin/screen"
    rc, output = run_command([screen, "-ls"])
    sessions: list[str] = []
    for line in output.splitlines():
        match = re.search(r"\s+(\d+\.[^\s]+)\s+\(", line)
        if match:
            sessions.append(match.group(1))
    return {"returncode": rc, "sessions": sessions, "raw": output}


def process_status() -> list[dict[str, str]]:
    rc, output = run_command(["ps", "-eo", "pid=,etime=,args="])
    if rc != 0:
        return []
    rows: list[dict[str, str]] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not any(pattern in stripped for pattern in PROCESS_PATTERNS):
            continue
        pid, rest = stripped.split(None, 1)
        etime, _, command = rest.partition(" ")
        rows.append({"pid": pid, "etime": etime, "command": command})
    return rows


def disk_status() -> dict[str, Any]:
    usage = shutil.disk_usage(ROOT)
    gib = 1024**3
    return {
        "total_gib": round(usage.total / gib, 1),
        "used_gib": round(usage.used / gib, 1),
        "free_gib": round(usage.free / gib, 1),
        "used_percent": round((usage.used / usage.total) * 100, 1),
    }


def estimate_progress(row: dict[str, Any], resume_step: int | None) -> dict[str, Any]:
    step = int(row["step"])
    remaining = max(MEMORY_OFF_STAGE4_TARGET_STEPS - step, 0)
    row["target_steps"] = MEMORY_OFF_STAGE4_TARGET_STEPS
    row["progress_percent"] = round((step / MEMORY_OFF_STAGE4_TARGET_STEPS) * 100.0, 2)
    row["remaining_steps"] = remaining
    row["estimated_seconds_remaining"] = None
    if resume_step is not None and row["elapsed_seconds"] > 0 and step > resume_step:
        steps_per_second = (step - resume_step) / row["elapsed_seconds"]
        if steps_per_second > 0:
            row["estimated_seconds_remaining"] = round(remaining / steps_per_second)
    return row


def parse_training_log(path: Path) -> dict[str, Any]:
    latest: dict[str, dict[str, Any]] = {}
    resume_steps: dict[str, int] = {}
    current_resume_behavior: str | None = None
    exists = path.exists()
    if exists:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            resume_from = RESUME_FROM_RE.match(stripped)
            if resume_from:
                current_resume_behavior = resume_from.group("behavior")
                continue
            resume_step = RESUME_STEP_RE.match(stripped)
            if resume_step and current_resume_behavior:
                resume_steps[current_resume_behavior] = int(resume_step.group("step"))
                current_resume_behavior = None
                continue
            match = STEP_RE.match(stripped)
            if not match:
                continue
            elo_match = ELO_RE.search(stripped)
            behavior = match.group("behavior")
            latest[behavior] = estimate_progress(
                {
                    "step": int(match.group("step")),
                    "elapsed_seconds": float(match.group("elapsed")),
                    "mean_reward": float(match.group("reward")),
                    "elo": float(elo_match.group("elo")) if elo_match else None,
                },
                resume_steps.get(behavior),
            )
    return {
        "path": str(path.relative_to(ROOT)),
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else 0,
        "modified_utc": path.stat().st_mtime if exists else None,
        "age_seconds": round(time.time() - path.stat().st_mtime, 1) if exists else None,
        "resume_steps": resume_steps,
        "latest_steps": latest,
    }


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"json_error": "invalid json"}


def exported_steps(run_dir: Path) -> dict[str, list[int]]:
    exports: dict[str, set[int]] = {"Runner": set(), "Sentinel": set()}
    for behavior in exports:
        behavior_dir = run_dir / behavior
        if not behavior_dir.exists():
            continue
        for path in behavior_dir.iterdir():
            match = EXPORT_RE.match(path.name)
            if match:
                exports[behavior].add(int(match.group("step")))
    return {behavior: sorted(values) for behavior, values in exports.items()}


def memory_off_stage4_status() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for seed in MEMORY_OFF_SEEDS:
        run_id = f"LB_3v2_memory_off_seed{seed}_stage4"
        run_dir = ROOT / "results" / run_id
        status = load_json(run_dir / "metadata" / "training_status.json")
        rows.append(
            {
                "seed": seed,
                "run_id": run_id,
                "exists": run_dir.exists(),
                "status": status.get("status"),
                "success": status.get("success"),
                "exit_code": status.get("exit_code"),
                "error": status.get("error"),
                "exports": exported_steps(run_dir),
            }
        )
    return rows


def paired_ablation_status() -> dict[str, Any]:
    root = ROOT / "results" / "official_summary" / "ablations"
    files = sorted(root.glob("*/paired_effects.json")) if root.exists() else []
    return {
        "complete_families": [path.parent.name for path in files],
        "complete_count": len(files),
        "target_count": 5,
        "missing_registered": sorted(
            set(["action_assist_on", "dynamic_wall_off", "memory_off", "tactical_reward_off", "direct_dynamic_training"])
            - {path.parent.name for path in files}
        ),
    }


def completion_tracker_status() -> dict[str, Any]:
    path = (
        ROOT
        / "results"
        / "official_summary"
        / "ablations"
        / "memory_off_tracker"
        / "LB_3v2_memory_off_official_v2"
        / "completion"
        / "seed_completion_report.json"
    )
    report = load_json(path)
    rows = report.get("rows") or []
    complete = sum(1 for row in rows if row.get("Complete/Incomplete") == "Complete")
    incomplete = sum(1 for row in rows if row.get("Complete/Incomplete") == "Incomplete")
    return {
        "path": str(path.relative_to(ROOT)),
        "exists": bool(report),
        "all_complete": report.get("all_complete"),
        "complete_rows": complete,
        "incomplete_rows": incomplete,
    }


def build_status() -> dict[str, Any]:
    active_processes = process_status()
    seed101_log = parse_training_log(ROOT / "logs" / "memory_off_seed101_stage4_screen.log")
    rest_log = parse_training_log(ROOT / "logs" / "memory_off_stage4_remaining_screen.log")
    return {
        "screen": screen_status(),
        "active_processes": active_processes,
        "disk": disk_status(),
        "memory_off_seed101_log": seed101_log,
        "memory_off_remaining_log": rest_log,
        "memory_off_stage4": memory_off_stage4_status(),
        "memory_off_tracker": completion_tracker_status(),
        "paired_ablations": paired_ablation_status(),
        "next_action": next_action(active_processes, seed101_log),
    }


def next_action(active_processes: list[dict[str, str]], seed101_log: dict[str, Any]) -> str:
    if active_processes:
        runner = seed101_log.get("latest_steps", {}).get("Runner", {})
        step = runner.get("step")
        eta = runner.get("estimated_seconds_remaining")
        if step:
            if eta is not None:
                return f"wait for active training, latest Runner step {step}, estimated Runner ETA {format_duration(eta)}"
            return f"wait for active training, latest Runner step {step}"
        return "wait for active training"
    return "no active training process detected, inspect screen logs before starting evaluation"


def format_duration(seconds: int | float | None) -> str:
    if seconds is None:
        return "unknown"
    seconds = max(int(seconds), 0)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def print_text(status: dict[str, Any]) -> None:
    print("Labyrinth Breach evidence monitor")
    print(f"Screen sessions: {', '.join(status['screen']['sessions']) or 'none'}")
    print(f"Active process count: {len(status['active_processes'])}")
    for process in status["active_processes"]:
        command = process["command"]
        print(f"  pid={process['pid']} elapsed={process['etime']} command={command[:140]}")
    disk = status["disk"]
    print(f"Disk: {disk['free_gib']} GiB free, {disk['used_percent']}% used")
    latest = status["memory_off_seed101_log"]["latest_steps"]
    print(f"Seed101 log age: {status['memory_off_seed101_log']['age_seconds']}s")
    if latest:
        for behavior, row in latest.items():
            print(
                f"Seed101 {behavior}: step={row['step']}/{row['target_steps']} "
                f"({row['progress_percent']}%) elapsed={format_duration(row['elapsed_seconds'])} "
                f"eta={format_duration(row['estimated_seconds_remaining'])} "
                f"reward={row['mean_reward']} elo={row['elo']}"
            )
    else:
        print("Seed101 latest step: unavailable")
    tracker = status["memory_off_tracker"]
    print(
        f"Memory-off tracker: all_complete={tracker['all_complete']} "
        f"complete={tracker['complete_rows']} incomplete={tracker['incomplete_rows']}"
    )
    ablations = status["paired_ablations"]
    print(
        f"Paired ablations: {ablations['complete_count']}/{ablations['target_count']} complete, "
        f"missing={', '.join(ablations['missing_registered']) or 'none'}"
    )
    print(f"Next action: {status['next_action']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    status = build_status()
    if args.json:
        print(json.dumps(status, indent=2, sort_keys=True))
    else:
        print_text(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
