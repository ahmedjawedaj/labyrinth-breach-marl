#!/usr/bin/env python3
"""Run-scoped Unity log routing and artifact collection helpers."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from artifact_validation import format_problem_report, required_raw_log_requirements, validate_artifacts

REQUIRED_LOG_ARTIFACTS = (
    "episode_log.csv",
    "agent_step_log.csv",
    "reward_audit.csv",
    "replay_events.csv",
)


@dataclass(frozen=True)
class LogSyncResult:
    run_id: str
    logs_dir: Path
    copied: tuple[str, ...]
    missing: tuple[str, ...]
    candidates_checked: tuple[str, ...]


def _runtime_override_dir(root: Path) -> Path:
    directory = root / "configs" / "runtime_overrides"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def prepare_run_log_routing(root: Path, run_id: str, results_dir: str, mode: str) -> Path:
    logs_dir = (root / results_dir / run_id / "logs").resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "run_id": run_id,
        "mode": mode,
        "results_dir": str((root / results_dir).resolve()),
        "logs_dir": str(logs_dir),
        "required_artifacts": list(REQUIRED_LOG_ARTIFACTS),
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    context_path = _runtime_override_dir(root) / "active_run_context.json"
    context_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return logs_dir


def _candidate_dirs(root: Path, logs_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    if logs_dir.exists():
        candidates.append(logs_dir)

    override_dir = _runtime_override_dir(root)
    for marker_name in ("last_unity_log_dir.txt", "last_unity_log_dir_fallback.txt"):
        marker_path = override_dir / marker_name
        if marker_path.exists():
            raw = marker_path.read_text(encoding="utf-8").strip()
            if raw:
                path = Path(raw)
                if path.exists():
                    candidates.append(path)

    home = Path.home()
    pattern_roots = (
        home / ".config" / "unity3d",
        home / "Library" / "Application Support" / "unity3d",
    )
    for base in pattern_roots:
        if not base.exists():
            continue
        for match in base.glob("**/LabyrinthBreachLogs"):
            if match.is_dir():
                candidates.append(match)

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve())
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def collect_run_log_artifacts(
    root: Path,
    run_id: str,
    results_dir: str,
    *,
    strict: bool,
) -> LogSyncResult:
    logs_dir = (root / results_dir / run_id / "logs").resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    missing = [name for name in REQUIRED_LOG_ARTIFACTS if not (logs_dir / name).exists()]
    candidates = _candidate_dirs(root, logs_dir)

    if missing:
        for source_dir in candidates:
            for name in tuple(missing):
                source = source_dir / name
                target = logs_dir / name
                if not source.exists() or target.exists():
                    continue
                shutil.copy2(source, target)
                copied.append(name)
            missing = [name for name in REQUIRED_LOG_ARTIFACTS if not (logs_dir / name).exists()]
            if not missing:
                break

    result = LogSyncResult(
        run_id=run_id,
        logs_dir=logs_dir,
        copied=tuple(sorted(set(copied))),
        missing=tuple(missing),
        candidates_checked=tuple(str(path) for path in candidates),
    )
    if strict:
        problems = validate_artifacts(required_raw_log_requirements(logs_dir))
        if not problems:
            return result
        missing_text = ", ".join(result.missing) if result.missing else "none"
        checked_text = "\n  ".join(result.candidates_checked) if result.candidates_checked else "(none)"
        problem_report = format_problem_report(problems, heading="Required raw log artifact problems")
        raise RuntimeError(
            "Required run logs are missing after collection.\n"
            f"run_id: {run_id}\n"
            f"target: {logs_dir}\n"
            f"missing: {missing_text}\n"
            f"candidates checked:\n  {checked_text}\n"
            f"{problem_report}"
        )
    return result
