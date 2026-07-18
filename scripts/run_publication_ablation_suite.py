#!/usr/bin/env python3
"""Run the registered retraining and evaluation ablation suite end to end."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping in {path}")
    return data


def run(command: list[str], dry_run: bool) -> int:
    print(" ".join(command))
    return 0 if dry_run else subprocess.run(command, cwd=ROOT).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite",
        default="configs/experiment_manifests/official_ablation_suite.yaml",
    )
    parser.add_argument(
        "--condition",
        action="append",
        help="Run one condition ID; repeat to select multiple. Defaults to all.",
    )
    parser.add_argument("--env", required=True)
    parser.add_argument("--training-results-dir", default="results")
    parser.add_argument("--full-eval-results-dir", default="results/publication_eval_official")
    parser.add_argument("--ablation-results-root", default="results/ablations")
    parser.add_argument("--analysis-output-root", default="results/official_summary/ablations")
    parser.add_argument("--run-full-evaluation", action="store_true")
    parser.add_argument("--skip-training", action="store_true")
    parser.add_argument("--allow-cpu", action="store_true")
    parser.add_argument("--no-graphics", action="store_true")
    parser.add_argument("--resume-completed", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    suite = load_yaml(ROOT / args.suite)
    conditions = suite.get("conditions") or []
    selected = set(args.condition or [item["id"] for item in conditions])
    unknown = selected - {item["id"] for item in conditions}
    if unknown:
        raise ValueError(f"Unknown conditions: {sorted(unknown)}")

    common_runtime = ["--env", args.env]
    if args.allow_cpu:
        common_runtime.append("--allow-cpu")
    if args.no_graphics:
        common_runtime.append("--no-graphics")

    if args.run_full_evaluation:
        command = [
            sys.executable,
            "scripts/run_publication_eval_matrix.py",
            "--results-dir",
            args.full_eval_results_dir,
            *common_runtime,
        ]
        if args.resume_completed:
            command.append("--resume-completed")
        if run(command, args.dry_run) != 0:
            return 1

    full_aggregate = ROOT / args.full_eval_results_dir / "aggregate" / "publication_eval_summary.csv"
    for condition in conditions:
        condition_id = condition["id"]
        if condition_id not in selected:
            continue
        print(f"\n=== Ablation: {condition_id} ===")
        training_matrix = condition.get("training_matrix")
        if condition["type"] == "retrain" and not args.skip_training:
            command = [
                sys.executable,
                "scripts/run_multiseed_curriculum.py",
                "--matrix-manifest",
                training_matrix,
                "--results-dir",
                args.training_results_dir,
                *common_runtime,
            ]
            if args.resume_completed:
                command.append("--resume-completed")
            if run(command, args.dry_run) != 0:
                return 1

        ablation_results = Path(args.ablation_results_root) / condition_id
        eval_command = [
            sys.executable,
            "scripts/run_publication_eval_matrix.py",
            "--matrix",
            condition["evaluation_matrix"],
            "--source-results-dir",
            args.training_results_dir,
            "--results-dir",
            str(ablation_results),
            *common_runtime,
        ]
        if args.resume_completed:
            eval_command.append("--resume-completed")
        if run(eval_command, args.dry_run) != 0:
            return 1

        paired_command = [
            sys.executable,
            "scripts/analyze_paired_ablation.py",
            "--full-aggregate",
            str(full_aggregate),
            "--full-results-dir",
            args.full_eval_results_dir,
            "--ablated-aggregate",
            str(ROOT / ablation_results / "aggregate" / "publication_eval_summary.csv"),
            "--ablated-results-dir",
            str(ablation_results),
            "--ablation-id",
            condition_id,
            "--output-dir",
            str(Path(args.analysis_output_root) / condition_id),
        ]
        if run(paired_command, args.dry_run) != 0:
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
