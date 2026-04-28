#!/usr/bin/env python3
"""Run fixed-duration evaluation across multiple seeds."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from artifact_validation import ArtifactRequirement, format_problem_report, required_raw_log_requirements, validate_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="configs/experiment_manifests/exp_unseen_eval_seed101.yaml")
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 101, 202])
    parser.add_argument("--duration-minutes", type=int, default=30)
    parser.add_argument("--output-dir", default="results")
    parser.add_argument("--source-results-dir", default="results")
    parser.add_argument("--env")
    parser.add_argument("--no-graphics", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]
    max_runtime_seconds = max(60, int(args.duration_minutes * 60))

    for seed in args.seeds:
        eval_run_id = f"{args.source_run_id}_eval_seed{seed}_{args.duration_minutes}m"
        command = [
            sys.executable,
            "scripts/evaluate_policy.py",
            "--manifest",
            args.manifest,
            "--source-run-id",
            args.source_run_id,
            "--source-results-dir",
            args.source_results_dir,
            "--output-dir",
            args.output_dir,
            "--seed",
            str(seed),
            "--eval-run-id",
            eval_run_id,
            "--max-runtime-seconds",
            str(max_runtime_seconds),
        ]
        if args.env:
            command.extend(["--env", args.env])
        if args.no_graphics:
            command.append("--no-graphics")

        print(f"\n=== Fixed-duration eval: seed={seed}, run={eval_run_id} ===")
        print(" ".join(command))
        rc = subprocess.run(command, cwd=root).returncode
        if rc not in (0, 124):
            print(f"Evaluation failed for seed={seed} with exit code {rc}.", file=sys.stderr)
            return rc

        run_root = root / args.output_dir / eval_run_id
        logs_dir = run_root / "logs"
        kpi_dir = run_root / "kpi"
        kpi_requirements = [
            ArtifactRequirement(path=kpi_dir / "eval_kpi_summary.json", label="eval_kpi_summary.json"),
            ArtifactRequirement(path=kpi_dir / "eval_kpi_summary.csv", label="eval_kpi_summary.csv"),
        ]
        all_problems = validate_artifacts(required_raw_log_requirements(logs_dir)) + validate_artifacts(kpi_requirements)
        if all_problems:
            print(format_problem_report(all_problems, heading=f"Artifact validation failed for seed {seed}"), file=sys.stderr)
            return 2

    print("Fixed-duration multi-seed evaluation completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
