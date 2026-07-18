#!/usr/bin/env python3
"""Export audited multi-seed ML-Agents learning curves and uncertainty bands."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import yaml
from scipy.stats import t as student_t
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TAGS = (
    "Environment/Cumulative Reward",
    "Environment/Episode Length",
    "Self-play/ELO",
    "Policy/Entropy",
    "Losses/Policy Loss",
    "Losses/Value Loss",
)
ROLE_COLORS = {"Sentinel": "#2457A6", "Runner": "#B63A3A"}


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_name(tag: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", tag.lower()).strip("_")


def run_is_complete(run_dir: Path, minimum_checks: int) -> bool:
    status_path = run_dir / "metadata" / "training_status.json"
    audit_path = run_dir / "metadata" / "training_audit.json"
    if not status_path.is_file() or not audit_path.is_file():
        return False
    status = load_json(status_path)
    audit = load_json(audit_path)
    return (
        status.get("success") is True
        and status.get("exit_code") == 0
        and int(audit.get("failed", 1)) == 0
        and len(audit.get("checks") or []) >= minimum_checks
    )


def stage_trainer_config(stage: dict) -> dict:
    manifest = load_yaml(ROOT / stage["manifest"])
    return load_yaml(ROOT / manifest["trainer_config"])


def scalar_events(role_dir: Path, requested_tags: tuple[str, ...]) -> dict[str, list]:
    by_tag: dict[str, dict[int, object]] = defaultdict(dict)
    for event_path in sorted(role_dir.glob("events.out.tfevents*")):
        accumulator = EventAccumulator(str(event_path), size_guidance={"scalars": 0})
        accumulator.Reload()
        available = set(accumulator.Tags().get("scalars", []))
        for tag in requested_tags:
            if tag not in available:
                continue
            for event in accumulator.Scalars(tag):
                previous = by_tag[tag].get(event.step)
                if previous is None or event.wall_time >= previous.wall_time:
                    by_tag[tag][event.step] = event
    return {tag: [events[step] for step in sorted(events)] for tag, events in by_tag.items()}


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def aggregate_rows(raw_rows: list[dict]) -> list[dict]:
    grouped: dict[tuple, list[float]] = defaultdict(list)
    metadata: dict[tuple, dict] = {}
    for row in raw_rows:
        key = (
            row["stage_id"],
            row["stage_order"],
            row["curriculum_stage"],
            row["role"],
            row["tag"],
            row["step"],
            row["stage_progress"],
            row["curriculum_progress"],
        )
        grouped[key].append(float(row["value"]))
        metadata[key] = {name: row[name] for name in (
            "stage_id", "stage_order", "curriculum_stage", "role", "tag",
            "step", "stage_progress", "curriculum_progress",
        )}

    result: list[dict] = []
    for key, values in sorted(grouped.items(), key=lambda item: (item[0][4], item[0][3], item[0][1], item[0][5])):
        array = np.asarray(values, dtype=float)
        count = len(array)
        mean = float(np.mean(array))
        std = float(np.std(array, ddof=1)) if count > 1 else math.nan
        sem = std / math.sqrt(count) if count > 1 else math.nan
        margin = float(student_t.ppf(0.975, count - 1) * sem) if count > 1 else math.nan
        result.append({
            **metadata[key],
            "policy_seed_count": count,
            "mean": mean,
            "std": std,
            "sem": sem,
            "t95_low": mean - margin if count > 1 else math.nan,
            "t95_high": mean + margin if count > 1 else math.nan,
        })
    return result


def make_plots(raw_rows: list[dict], summary_rows: list[dict], output_dir: Path, tags: tuple[str, ...]) -> None:
    stage_labels = {
        1: "Static fixed",
        2: "Static random",
        3: "Dynamic low",
        4: "Dynamic high",
    }
    for tag in tags:
        if not any(row["tag"] == tag for row in raw_rows):
            continue
        figure, axes = plt.subplots(1, 2, figsize=(10.0, 3.6), sharey=False)
        for axis, role in zip(axes, ("Sentinel", "Runner")):
            role_raw = [row for row in raw_rows if row["tag"] == tag and row["role"] == role]
            for seed in sorted({int(row["seed"]) for row in role_raw}):
                seed_rows = sorted(
                    (row for row in role_raw if int(row["seed"]) == seed),
                    key=lambda row: float(row["curriculum_progress"]),
                )
                axis.plot(
                    [float(row["curriculum_progress"]) for row in seed_rows],
                    [float(row["value"]) for row in seed_rows],
                    color=ROLE_COLORS[role], alpha=0.20, linewidth=0.8,
                )
            role_summary = sorted(
                (row for row in summary_rows if row["tag"] == tag and row["role"] == role),
                key=lambda row: float(row["curriculum_progress"]),
            )
            x = np.asarray([float(row["curriculum_progress"]) for row in role_summary])
            mean = np.asarray([float(row["mean"]) for row in role_summary])
            axis.plot(x, mean, color=ROLE_COLORS[role], linewidth=1.8, label="Policy-seed mean")
            valid = np.asarray([int(row["policy_seed_count"]) > 1 for row in role_summary])
            if np.any(valid):
                low = np.asarray([float(row["t95_low"]) for row in role_summary])
                high = np.asarray([float(row["t95_high"]) for row in role_summary])
                axis.fill_between(x[valid], low[valid], high[valid], color=ROLE_COLORS[role], alpha=0.16, label="95% t interval")
            for boundary in (1, 2, 3):
                axis.axvline(boundary, color="#777777", linewidth=0.7, linestyle="--")
            axis.set_title(role)
            axis.set_xlim(0, 4)
            axis.set_xticks((0.5, 1.5, 2.5, 3.5), [stage_labels[index] for index in range(1, 5)], rotation=20)
            axis.set_xlabel("Curriculum stage and normalized progress")
            axis.grid(alpha=0.20, linewidth=0.6)
            axis.legend(frameon=False, fontsize=8)
        axes[0].set_ylabel(tag.split("/", 1)[-1])
        figure.suptitle(f"Official multi-seed training: {tag}")
        figure.tight_layout()
        stem = output_dir / f"training_curve_{safe_name(tag)}"
        figure.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
        figure.savefig(stem.with_suffix(".png"), dpi=220, bbox_inches="tight")
        plt.close(figure)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=ROOT / "configs/experiment_manifests/official_curriculum_matrix.yaml")
    parser.add_argument("--results-root", type=Path, default=ROOT / "results")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/official_summary/training_curves")
    parser.add_argument("--include-running", action="store_true", help="Diagnostic only: include runs that have not passed the completion audit.")
    parser.add_argument("--minimum-audit-checks", type=int, default=33)
    parser.add_argument("--tag", action="append", dest="tags")
    args = parser.parse_args()

    matrix = load_yaml(args.matrix)
    tags = tuple(args.tags or DEFAULT_TAGS)
    raw_rows: list[dict] = []
    missing: list[str] = []
    trainer_configs = {stage["id"]: stage_trainer_config(stage) for stage in matrix["stages"]}

    for seed in matrix["seeds"]:
        for stage in matrix["stages"]:
            run_id = matrix["run_id_template"].format(
                experiment_family=matrix["experiment_family"], seed=seed,
                stage_id=stage["id"], stage_order=stage["order"],
            )
            run_dir = args.results_root / run_id
            complete = run_is_complete(run_dir, args.minimum_audit_checks)
            if not complete and not args.include_running:
                missing.append(run_id)
                continue
            behavior_configs = trainer_configs[stage["id"]].get("behaviors", {})
            for role, role_config in behavior_configs.items():
                max_steps = int(role_config["max_steps"])
                events = scalar_events(run_dir / role, tags)
                if not events:
                    missing.append(f"{run_id}/{role}: no scalar events")
                    continue
                for tag, values in events.items():
                    for event in values:
                        progress = min(float(event.step) / max_steps, 1.0)
                        raw_rows.append({
                            "experiment_family": matrix["experiment_family"],
                            "run_id": run_id,
                            "seed": int(seed),
                            "stage_id": stage["id"],
                            "stage_order": int(stage["order"]),
                            "curriculum_stage": stage["curriculum_stage"],
                            "role": role,
                            "tag": tag,
                            "step": int(event.step),
                            "max_steps": max_steps,
                            "stage_progress": progress,
                            "curriculum_progress": int(stage["order"]) - 1 + progress,
                            "value": float(event.value),
                            "wall_time": float(event.wall_time),
                            "run_complete": complete,
                        })

    if missing and not args.include_running:
        print(f"Refusing official curve export: {len(missing)} required runs/artifacts are incomplete.")
        for item in missing[:20]:
            print(f"MISSING: {item}")
        return 2
    if not raw_rows:
        print("No TensorBoard scalar data found.")
        return 2

    summary_rows = aggregate_rows(raw_rows)
    raw_fields = list(raw_rows[0])
    summary_fields = list(summary_rows[0])
    write_csv(args.output_dir / "official_training_curves_raw.csv", raw_rows, raw_fields)
    write_csv(args.output_dir / "official_training_curves_summary.csv", summary_rows, summary_fields)
    make_plots(raw_rows, summary_rows, args.output_dir, tags)
    manifest = {
        "schema_version": 1,
        "experiment_family": matrix["experiment_family"],
        "include_running": args.include_running,
        "minimum_audit_checks": args.minimum_audit_checks,
        "tags": list(tags),
        "raw_row_count": len(raw_rows),
        "summary_row_count": len(summary_rows),
        "policy_seeds_observed": sorted({int(row["seed"]) for row in raw_rows}),
        "missing_or_incomplete": missing,
        "uncertainty": "two-sided 95% Student-t interval across independent policy seeds at matched stage/role/tag/step",
    }
    (args.output_dir / "training_curve_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    print(f"Exported {len(raw_rows)} raw and {len(summary_rows)} summarized scalar rows to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
