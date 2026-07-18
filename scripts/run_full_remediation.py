#!/usr/bin/env python3
"""Run the canonical publication training, evaluation, and ablation pipeline."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> int:
    print("\n>>>", " ".join(command))
    return subprocess.run(command, cwd=ROOT).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", required=True, help="Unity standalone executable or .app path.")
    parser.add_argument("--training-results-dir", default="results")
    parser.add_argument("--evaluation-results-dir", default="results/publication_eval_official")
    parser.add_argument("--ablation-results-root", default="results/ablations")
    parser.add_argument("--analysis-output-root", default="results/official_summary/ablations")
    parser.add_argument("--allow-cpu", action="store_true")
    parser.add_argument("--no-graphics", action="store_true")
    parser.add_argument("--skip-training", action="store_true")
    parser.add_argument("--skip-evaluation", action="store_true")
    parser.add_argument("--skip-ablations", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    runtime = ["--env", args.env]
    if args.allow_cpu:
        runtime.append("--allow-cpu")
    if args.no_graphics:
        runtime.append("--no-graphics")

    preflights = [
        [sys.executable, "scripts/pretraining_implementation_audit.py"],
        [sys.executable, "scripts/validate_training_budgets.py"],
        [sys.executable, "scripts/validate_evaluation_controls.py"],
    ]
    if not args.dry_run:
        for command in preflights:
            if run(command) != 0:
                return 2

    if not args.skip_training:
        command = [
            sys.executable,
            "scripts/run_multiseed_curriculum.py",
            "--matrix-manifest",
            "configs/experiment_manifests/official_curriculum_matrix.yaml",
            "--results-dir",
            args.training_results_dir,
            "--resume-completed",
            *runtime,
        ]
        if args.dry_run:
            print("\n>>>", " ".join(command))
        elif run(command) != 0:
            return 2

    curve_command = [sys.executable, "scripts/analyze_official_training_curves.py"]
    if args.dry_run:
        print("\n>>>", " ".join(curve_command))
    elif run(curve_command) != 0:
        return 2

    if not args.skip_evaluation:
        command = [
            sys.executable,
            "scripts/run_publication_eval_matrix.py",
            "--source-results-dir",
            args.training_results_dir,
            "--results-dir",
            args.evaluation_results_dir,
            "--resume-completed",
            *runtime,
        ]
        if args.dry_run:
            print("\n>>>", " ".join(command))
        elif run(command) != 0:
            return 2

    if not args.skip_ablations:
        command = [
            sys.executable,
            "scripts/run_publication_ablation_suite.py",
            "--training-results-dir",
            args.training_results_dir,
            "--full-eval-results-dir",
            args.evaluation_results_dir,
            "--ablation-results-root",
            args.ablation_results_root,
            "--analysis-output-root",
            args.analysis_output_root,
            "--resume-completed",
            *runtime,
        ]
        if args.dry_run:
            print("\n>>>", " ".join(command))
        elif run(command) != 0:
            return 2

    final_checks = [
        [
            sys.executable,
            "scripts/seed_completion_tracker.py",
            "--results-dir",
            args.training_results_dir,
            "--eval-results-dir",
            args.evaluation_results_dir,
        ],
        [sys.executable, "scripts/audit_publication_readiness.py"],
    ]
    if args.dry_run:
        for command in final_checks:
            print("\n>>>", " ".join(command))
        return 0
    for command in final_checks:
        if run(command) != 0:
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
