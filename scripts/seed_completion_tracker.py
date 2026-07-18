#!/usr/bin/env python3
"""Strict seed completion tracker for official training + seen/unseen evaluation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

OFFICIAL_STAGES = ["stage1", "stage2", "stage3", "stage4"]


def load_yaml(path: Path) -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML is required to parse manifests.")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
            if "exists" in entry and not bool(entry.get("exists")):
                invalid_snapshots.append(f"exists=false source={entry.get('source')}")
                continue
            snapshot_rel = entry.get("snapshot")
            if not snapshot_rel:
                invalid_snapshots.append(f"missing snapshot path source={entry.get('source')}")
                continue
            snapshot_path = root / str(snapshot_rel)
            if not snapshot_path.exists() or snapshot_path.is_dir() or snapshot_path.stat().st_size == 0:
                invalid_snapshots.append(f"missing snapshot file {snapshot_path}")
                continue
            expected_hash = str(entry.get("sha256") or "")
            if not expected_hash:
                invalid_snapshots.append(f"missing snapshot SHA-256 for {snapshot_path}")
            elif sha256_file(snapshot_path) != expected_hash:
                invalid_snapshots.append(f"snapshot SHA-256 mismatch for {snapshot_path}")
        if invalid_snapshots:
            error = "metadata snapshot integrity failure: " + "; ".join(invalid_snapshots[:4])
    if training_status_path.exists() and training_status_path.stat().st_size > 0:
        status = load_json(training_status_path)
        if not bool(status.get("success")):
            state = str(status.get("status") or "unknown").strip().lower()
            if state == "running":
                status_error = "training is still running"
            elif state == "invalidated":
                status_error = "training run was invalidated"
            elif state in {"interrupted", "cancelled", "canceled"}:
                status_error = f"training was {state} (exit_code={status.get('exit_code')})"
            else:
                status_error = f"training status is {state} (exit_code={status.get('exit_code')})"
            error = f"{error}; {status_error}" if error else status_error
    return (not missing and not error), missing, error


def validate_eval_split(root: Path, results_dir: str, seed: int, run_id: str) -> tuple[bool, list[str], str]:
    run_root = root / results_dir / f"policy_seed_{seed}" / run_id
    metadata_dir = run_root / "metadata"
    logs_dir = run_root / "logs"
    kpi_dir = run_root / "kpi"
    missing: list[str] = []
    required = [
        metadata_dir / "run_metadata.json",
        metadata_dir / "evaluation_metadata.json",
        metadata_dir / "evaluation_status.json",
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
            if not isinstance(entry, dict) or ("exists" in entry and not bool(entry.get("exists"))):
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
            expected_hash = str(entry.get("sha256") or "")
            if not expected_hash:
                error = f"metadata snapshot SHA-256 missing: {snapshot_path}"
                break
            if sha256_file(snapshot_path) != expected_hash:
                error = f"metadata snapshot SHA-256 mismatch: {snapshot_path}"
                break
    eval_metadata = metadata_dir / "evaluation_metadata.json"
    if eval_metadata.exists() and eval_metadata.stat().st_size > 0:
        data = load_json(eval_metadata)
        if int(data.get("seed", -1)) != seed:
            error = f"evaluation seed mismatch in {eval_metadata}"
    eval_status = metadata_dir / "evaluation_status.json"
    if eval_status.exists() and eval_status.stat().st_size > 0:
        status = load_json(eval_status)
        if status.get("success") is not True:
            state = str(status.get("status") or "unknown").strip().lower()
            status_error = "evaluation is still running" if state == "running" else f"evaluation status is {state}"
            error = f"{error}; {status_error}" if error else status_error
    return (not missing and not error), missing, error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--training-matrix-manifest",
        default="configs/experiment_manifests/official_curriculum_matrix.yaml",
    )
    parser.add_argument(
        "--eval-matrix-manifest",
        default="configs/experiment_manifests/official_publication_eval_matrix.yaml",
    )
    parser.add_argument("--results-dir", default="results", help="Root containing official training runs.")
    parser.add_argument(
        "--eval-results-dir",
        default="results/publication_eval_official",
        help="Root containing publication evaluation policy-seed directories.",
    )
    parser.add_argument("--output-dir", default="results")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    training_matrix = load_yaml(root / args.training_matrix_manifest)
    eval_matrix = load_yaml(root / args.eval_matrix_manifest)

    training_seeds = [int(seed) for seed in training_matrix.get("seeds") or []]
    eval_seeds = [int(seed) for seed in eval_matrix.get("seeds") or []]
    if len(training_seeds) < 5 or len(set(training_seeds)) != len(training_seeds):
        raise ValueError("Training matrix must define at least five unique official seeds.")
    if eval_seeds != training_seeds:
        raise ValueError("Training and evaluation matrices must use the same policy seeds.")
    stage_ids = [str(stage.get("id")) for stage in training_matrix.get("stages") or []]
    if stage_ids != OFFICIAL_STAGES:
        raise ValueError("Training matrix does not use the official four-stage order.")

    stage_orders = {stage["id"]: int(stage.get("order", idx + 1)) for idx, stage in enumerate(training_matrix["stages"])}
    rows: list[dict] = []
    all_complete = True

    target_episodes = int(eval_matrix.get("episodes_per_cell", 0))
    duration_minutes = int(eval_matrix.get("duration_minutes", 0))
    eval_splits = eval_matrix.get("splits") or []
    if not eval_splits:
        raise ValueError("Evaluation matrix defines no splits.")
    for seed in training_seeds:
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

        for split in eval_splits:
            split_id = str(split["id"])
            duration_label = f"{target_episodes}ep" if target_episodes else f"{duration_minutes}m"
            eval_run_id = f"{eval_matrix['experiment_family']}_policyseed{seed}_{split_id}_{duration_label}"
            complete, missing, error = validate_eval_split(root, args.eval_results_dir, seed, eval_run_id)
            append_row(rows, seed, f"eval_{split_id}", complete, missing, error)
            all_complete = all_complete and complete

    output_dir = root / args.output_dir / str(training_matrix["experiment_family"]) / "completion"
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": 2,
        "training_matrix_manifest": args.training_matrix_manifest,
        "eval_matrix_manifest": args.eval_matrix_manifest,
        "official_seeds": training_seeds,
        "training_results_dir": args.results_dir,
        "evaluation_results_dir": args.eval_results_dir,
        "evaluation_splits": [str(split["id"]) for split in eval_splits],
        "episodes_per_evaluation_cell": target_episodes or None,
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
