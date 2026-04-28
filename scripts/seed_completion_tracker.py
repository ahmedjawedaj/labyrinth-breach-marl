#!/usr/bin/env python3
"""Strict seed completion tracker for official training + seen/unseen evaluation."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

OFFICIAL_SEEDS = [42, 101, 202]
OFFICIAL_STAGES = ["stage1", "stage2", "stage3", "stage4"]
EVAL_SPLITS = ["seen", "unseen"]


def load_yaml(path: Path) -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML is required to parse manifests.")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_id_from_template(template: str, experiment_family: str, seed: int, stage_id: str, stage_order: int) -> str:
    return template.format(
        experiment_family=experiment_family,
        seed=seed,
        stage_id=stage_id,
        stage_order=stage_order,
    )


def append_row(rows: list[dict], seed: int, stage: str, complete: bool, missing: list[str], error: str) -> None:
    rows.append(
        {
            "Seed": seed,
            "Stage": stage,
            "Complete/Incomplete": "Complete" if complete else "Incomplete",
            "Missing Artifact": "; ".join(missing) if missing else "",
            "Error Description (if any)": error,
        }
    )


def validate_training_stage(root: Path, results_dir: str, run_id: str) -> tuple[bool, list[str], str]:
    run_root = root / results_dir / run_id
    metadata_dir = run_root / "metadata"
    missing: list[str] = []
    run_metadata_path = metadata_dir / "run_metadata.json"
    training_status_path = metadata_dir / "training_status.json"
    logs_dir = run_root / "logs"
    required_logs = [
        logs_dir / "episode_log.csv",
        logs_dir / "agent_step_log.csv",
        logs_dir / "reward_audit.csv",
        logs_dir / "replay_events.csv",
    ]
    for path in [run_metadata_path, training_status_path, *required_logs]:
        if not path.exists() or path.is_dir() or path.stat().st_size == 0:
            missing.append(str(path))
    error = ""
    if run_metadata_path.exists() and run_metadata_path.stat().st_size > 0:
        metadata = load_json(run_metadata_path)
        snapshot_entries = metadata.get("config_snapshots") or []
        invalid_snapshots: list[str] = []
        for entry in snapshot_entries:
            if not isinstance(entry, dict):
                invalid_snapshots.append("non-dict snapshot entry")
                continue
            if not bool(entry.get("exists", False)):
                invalid_snapshots.append(f"exists=false source={entry.get('source')}")
                continue
            snapshot_rel = entry.get("snapshot")
            if not snapshot_rel:
                invalid_snapshots.append(f"missing snapshot path source={entry.get('source')}")
                continue
            snapshot_path = root / str(snapshot_rel)
            if not snapshot_path.exists() or snapshot_path.is_dir() or snapshot_path.stat().st_size == 0:
                invalid_snapshots.append(f"missing snapshot file {snapshot_path}")
        if invalid_snapshots:
            error = "metadata snapshot integrity failure: " + "; ".join(invalid_snapshots[:4])
    if training_status_path.exists() and training_status_path.stat().st_size > 0:
        status = load_json(training_status_path)
        if not bool(status.get("success")):
            error = f"training status indicates failure (exit_code={status.get('exit_code')})"
    return (not missing and not error), missing, error


def validate_eval_split(root: Path, results_dir: str, seed: int, run_id: str) -> tuple[bool, list[str], str]:
    run_root = root / results_dir / f"seed_{seed}" / "eval" / run_id
    metadata_dir = run_root / "metadata"
    logs_dir = run_root / "logs"
    kpi_dir = run_root / "kpi"
    missing: list[str] = []
    required = [
        metadata_dir / "run_metadata.json",
        metadata_dir / "evaluation_metadata.json",
        logs_dir / "episode_log.csv",
        logs_dir / "agent_step_log.csv",
        logs_dir / "reward_audit.csv",
        logs_dir / "replay_events.csv",
        kpi_dir / "eval_kpi_summary.json",
        kpi_dir / "eval_kpi_summary.csv",
    ]
    for path in required:
        if not path.exists() or path.is_dir() or path.stat().st_size == 0:
            missing.append(str(path))
    error = ""
    run_metadata_path = metadata_dir / "run_metadata.json"
    if run_metadata_path.exists() and run_metadata_path.stat().st_size > 0:
        metadata = load_json(run_metadata_path)
        snapshot_entries = metadata.get("config_snapshots") or []
        for entry in snapshot_entries:
            if not isinstance(entry, dict) or not bool(entry.get("exists", False)):
                error = "metadata snapshot integrity failure in evaluation run metadata"
                break
            snapshot_rel = entry.get("snapshot")
            if not snapshot_rel:
                error = "metadata snapshot integrity failure: missing snapshot path"
                break
            snapshot_path = root / str(snapshot_rel)
            if not snapshot_path.exists() or snapshot_path.is_dir() or snapshot_path.stat().st_size == 0:
                error = f"metadata snapshot missing/empty: {snapshot_path}"
                break
    eval_metadata = metadata_dir / "evaluation_metadata.json"
    if eval_metadata.exists() and eval_metadata.stat().st_size > 0:
        data = load_json(eval_metadata)
        if int(data.get("seed", -1)) != seed:
            error = f"evaluation seed mismatch in {eval_metadata}"
    return (not missing and not error), missing, error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--training-matrix-manifest",
        default="configs/experiment_manifests/official_curriculum_matrix.yaml",
    )
    parser.add_argument(
        "--eval-matrix-manifest",
        default="configs/experiment_manifests/official_seen_unseen_eval_matrix.yaml",
    )
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--output-dir", default="results")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    training_matrix = load_yaml(root / args.training_matrix_manifest)
    eval_matrix = load_yaml(root / args.eval_matrix_manifest)

    if training_matrix.get("seeds") != OFFICIAL_SEEDS:
        raise ValueError("Training matrix does not use official seeds.")
    if eval_matrix.get("seeds") != OFFICIAL_SEEDS:
        raise ValueError("Eval matrix does not use official seeds.")

    stage_orders = {stage["id"]: int(stage.get("order", idx + 1)) for idx, stage in enumerate(training_matrix["stages"])}
    rows: list[dict] = []
    all_complete = True

    duration_minutes = int(eval_matrix["duration_minutes"])
    for seed in OFFICIAL_SEEDS:
        for stage_id in OFFICIAL_STAGES:
            stage_order = stage_orders[stage_id]
            run_id = run_id_from_template(
                str(training_matrix["run_id_template"]),
                str(training_matrix["experiment_family"]),
                seed,
                stage_id,
                stage_order,
            )
            complete, missing, error = validate_training_stage(root, args.results_dir, run_id)
            append_row(rows, seed, stage_id, complete, missing, error)
            all_complete = all_complete and complete

        for split in EVAL_SPLITS:
            eval_run_id = f"{eval_matrix['experiment_family']}_seed{seed}_{split}_{duration_minutes}m"
            complete, missing, error = validate_eval_split(root, args.results_dir, seed, eval_run_id)
            append_row(rows, seed, f"eval_{split}", complete, missing, error)
            all_complete = all_complete and complete

        meta_eval = root / args.results_dir / f"seed_{seed}" / "eval" / "meta_evaluation.json"
        if not meta_eval.exists() or meta_eval.is_dir() or meta_eval.stat().st_size == 0:
            append_row(rows, seed, "meta_evaluation", False, [str(meta_eval)], "Missing seed meta-evaluation file.")
            all_complete = False
        else:
            append_row(rows, seed, "meta_evaluation", True, [], "")

    output_dir = root / args.output_dir / str(training_matrix["experiment_family"]) / "completion"
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": 1,
        "training_matrix_manifest": args.training_matrix_manifest,
        "eval_matrix_manifest": args.eval_matrix_manifest,
        "official_seeds": OFFICIAL_SEEDS,
        "rows": rows,
        "all_complete": all_complete,
    }
    (output_dir / "seed_completion_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    csv_path = output_dir / "seed_completion_report.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["Seed", "Stage", "Complete/Incomplete", "Missing Artifact", "Error Description (if any)"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Wrote seed completion report: {output_dir / 'seed_completion_report.json'}")
    print(f"Wrote seed completion table: {csv_path}")
    if not all_complete:
        print("Incomplete entries:")
        for row in rows:
            if row["Complete/Incomplete"] != "Complete":
                print(
                    f"- seed={row['Seed']} stage={row['Stage']} missing={row['Missing Artifact']} "
                    f"error={row['Error Description (if any)']}"
                )
        print("Seed completion check FAILED: one or more stages/splits are incomplete.", flush=True)
        return 2
    print("Seed completion check PASSED for all official seeds and stages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
