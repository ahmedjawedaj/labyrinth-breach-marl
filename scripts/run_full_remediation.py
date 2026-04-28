#!/usr/bin/env python3
"""Run full post-audit remediation pipeline in strict order."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run(root: Path, command: list[str]) -> int:
    print("\n>>>", " ".join(command))
    return subprocess.run(command, cwd=root).returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--allow-cpu", action="store_true")
    parser.add_argument("--no-graphics", action="store_true")
    parser.add_argument("--timeout-wait", type=int, default=120)
    parser.add_argument("--skip-training-matrix", action="store_true")
    parser.add_argument("--skip-seen-unseen", action="store_true")
    parser.add_argument("--skip-memory-ablation", action="store_true")
    parser.add_argument("--skip-reward-ablation", action="store_true")
    parser.add_argument("--skip-wall-impact", action="store_true")
    parser.add_argument("--skip-metadata-repair", action="store_true")
    return parser.parse_args()


def maybe_flag(args: argparse.Namespace, name: str) -> list[str]:
    return [name] if getattr(args, name.lstrip("-").replace("-", "_")) else []


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]

    if not args.skip_metadata_repair:
        rc = run(
            root,
            [
                sys.executable,
                "scripts/repair_metadata_snapshots.py",
                "--results-dir",
                args.results_dir,
                "--strict",
            ],
        )
        if rc != 0:
            return rc

    if not args.skip_training_matrix:
        training_cmd = [
            sys.executable,
            "scripts/run_multiseed_curriculum.py",
            "--matrix-manifest",
            "configs/experiment_manifests/official_curriculum_matrix.yaml",
            "--results-dir",
            args.results_dir,
            "--force",
            *maybe_flag(args, "--no-graphics"),
        ]
        rc = run(root, training_cmd)
        if rc != 0:
            return rc

    if not args.skip_seen_unseen:
        seen_unseen_cmd = [
            sys.executable,
            "scripts/run_seen_unseen_eval_matrix.py",
            "--eval-matrix-manifest",
            "configs/experiment_manifests/official_seen_unseen_eval_matrix.yaml",
            "--results-dir",
            args.results_dir,
            "--source-results-dir",
            args.results_dir,
            "--timeout-wait",
            str(args.timeout_wait),
            *maybe_flag(args, "--allow-cpu"),
            *maybe_flag(args, "--no-graphics"),
        ]
        rc = run(root, seen_unseen_cmd)
        if rc != 0:
            return rc

    if not args.skip_memory_ablation:
        memory_cmd = [
            sys.executable,
            "scripts/run_memory_ablation.py",
            "--matrix-manifest",
            "configs/experiment_manifests/official_memory_ablation_matrix.yaml",
            "--timeout-wait",
            str(args.timeout_wait),
            *maybe_flag(args, "--allow-cpu"),
            *maybe_flag(args, "--no-graphics"),
        ]
        rc = run(root, memory_cmd)
        if rc != 0:
            return rc

    if not args.skip_reward_ablation:
        reward_cmd = [
            sys.executable,
            "scripts/run_reward_config_ablation.py",
            *maybe_flag(args, "--allow-cpu"),
            *maybe_flag(args, "--no-graphics"),
        ]
        rc = run(root, reward_cmd)
        if rc != 0:
            return rc

    if not args.skip_wall_impact:
        wall_cmd = [
            sys.executable,
            "scripts/run_dynamic_wall_impact.py",
            *maybe_flag(args, "--allow-cpu"),
            *maybe_flag(args, "--no-graphics"),
        ]
        rc = run(root, wall_cmd)
        if rc != 0:
            return rc

    # Final strict checks and paper outputs.
    rc = run(
        root,
        [
            sys.executable,
            "scripts/seed_completion_tracker.py",
            "--training-matrix-manifest",
            "configs/experiment_manifests/official_curriculum_matrix.yaml",
            "--eval-matrix-manifest",
            "configs/experiment_manifests/official_seen_unseen_eval_matrix.yaml",
            "--results-dir",
            args.results_dir,
            "--output-dir",
            args.results_dir,
        ],
    )
    if rc != 0:
        return rc

    rc = run(
        root,
        [
            sys.executable,
            "scripts/build_paper_ready_outputs.py",
            "--experiment-family",
            "LB_seen_unseen_official_v1",
            "--results-dir",
            args.results_dir,
        ],
    )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
