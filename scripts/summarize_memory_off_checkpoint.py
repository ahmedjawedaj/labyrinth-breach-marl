#!/usr/bin/env python3
"""Summarize the completed memory-off retraining checkpoint for the paper."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "LB_3v2_memory_off_seed202_stage4"
RUN_DIR = ROOT / "results" / RUN_ID
OUTPUT_DIR = ROOT / "results" / "official_summary"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def latest_checkpoint(agent: str, suffix: str) -> str:
    files = sorted((RUN_DIR / agent).glob(f"{agent}-*.{suffix}"), key=lambda p: p.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"Missing {agent} .{suffix} checkpoint in {RUN_DIR / agent}")
    return str(files[-1].relative_to(ROOT))


def pct(value: float) -> str:
    return f"{100.0 * value:.1f}%"


def main() -> int:
    status = load_json(RUN_DIR / "metadata" / "training_status.json")
    metadata = load_json(RUN_DIR / "metadata" / "run_metadata.json")
    kpi = load_json(RUN_DIR / "kpis" / "eval_kpi_summary.json")
    control = load_json(OUTPUT_DIR / "memory_off_control_audit.json")

    logs = {
        "episode_log_rows": line_count(RUN_DIR / "logs" / "episode_log.csv") - 1,
        "agent_step_log_rows": line_count(RUN_DIR / "logs" / "agent_step_log.csv") - 1,
        "reward_audit_rows": line_count(RUN_DIR / "logs" / "reward_audit.csv") - 1,
        "replay_event_rows": line_count(RUN_DIR / "logs" / "replay_events.csv") - 1,
    }

    payload: dict[str, Any] = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": RUN_ID,
        "status": status.get("status"),
        "success": status.get("success") is True,
        "exit_code": status.get("exit_code"),
        "missing_logs": status.get("missing_logs") or [],
        "seed": metadata.get("seed"),
        "stage_id": metadata.get("stage_id"),
        "curriculum_stage": metadata.get("curriculum_stage"),
        "experiment_family": metadata.get("experiment_family"),
        "initialize_from": metadata.get("initialize_from"),
        "runner_checkpoint": latest_checkpoint("Runner", "onnx"),
        "sentinel_checkpoint": latest_checkpoint("Sentinel", "onnx"),
        "control_audit_passed": control.get("passed") is True,
        "episodes": int(kpi.get("episodes", 0)),
        "sentinel_win_rate": float(kpi.get("sentinel_win_rate", 0.0)),
        "runner_win_rate": float(kpi.get("runner_win_rate", 0.0)),
        "escape_rate": float(kpi.get("escape_rate", 0.0)),
        "mean_time_to_first_capture_seconds": float(kpi.get("mean_time_to_first_capture_seconds", 0.0)),
        "mean_time_to_full_capture_seconds": float(kpi.get("mean_time_to_full_capture_seconds", 0.0)),
        "runner_survival_time_seconds_mean": float(kpi.get("runner_survival_time_seconds_mean", 0.0)),
        "target_reacquisition_seconds_mean": float((kpi.get("target_reacquisition") or {}).get("mean_seconds", 0.0)),
        "pincer_episode_rate": float((kpi.get("coordination") or {}).get("pincer_episode_rate", 0.0)),
        "corridor_block_episode_rate": float((kpi.get("coordination") or {}).get("corridor_block_episode_rate", 0.0)),
        "exit_denial_episode_rate": float((kpi.get("coordination") or {}).get("exit_denial_episode_rate", 0.0)),
        "trap_episode_rate": float((kpi.get("coordination") or {}).get("trap_episode_rate", 0.0)),
        "trap_success_rate": float((kpi.get("coordination") or {}).get("trap_success_rate", 0.0)),
        "logs": logs,
        "claim_scope": "completed single-seed memory-off stage-4 checkpoint and KPI audit",
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / "memory_off_checkpoint_summary.json"
    csv_path = OUTPUT_DIR / "memory_off_checkpoint_summary.csv"
    md_path = OUTPUT_DIR / "memory_off_checkpoint_summary.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    fieldnames = [
        "run_id",
        "seed",
        "stage_id",
        "success",
        "episodes",
        "sentinel_win_rate",
        "runner_win_rate",
        "escape_rate",
        "mean_time_to_full_capture_seconds",
        "target_reacquisition_seconds_mean",
        "pincer_episode_rate",
        "exit_denial_episode_rate",
        "trap_episode_rate",
        "runner_checkpoint",
        "sentinel_checkpoint",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({field: payload[field] for field in fieldnames})

    lines = [
        "# Memory-Off Checkpoint Summary",
        "",
        f"Generated UTC: `{payload['generated_utc']}`",
        "",
        f"- Run: `{RUN_ID}`",
        f"- Status: `{payload['status']}`, success `{payload['success']}`, exit code `{payload['exit_code']}`",
        f"- Seed and stage: `{payload['seed']}` / `{payload['stage_id']}`",
        f"- Episodes: `{payload['episodes']}`",
        f"- Sentinel win: `{pct(payload['sentinel_win_rate'])}`",
        f"- Runner win: `{pct(payload['runner_win_rate'])}`",
        f"- Escape: `{pct(payload['escape_rate'])}`",
        f"- Full capture time: `{payload['mean_time_to_full_capture_seconds']:.2f} s`",
        f"- Reacquisition delay: `{payload['target_reacquisition_seconds_mean']:.2f} s`",
        f"- Pincer episode rate: `{pct(payload['pincer_episode_rate'])}`",
        f"- Exit-denial episode rate: `{pct(payload['exit_denial_episode_rate'])}`",
        f"- Trap episode rate: `{pct(payload['trap_episode_rate'])}`",
        f"- Control audit passed: `{payload['control_audit_passed']}`",
        "",
        "This artifact is a completed single-seed memory-off stage-4 checkpoint summary.",
        "It is not a full five-seed paired memory ablation result.",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
