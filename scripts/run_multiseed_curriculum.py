#!/usr/bin/env python3
"""Run staged curriculum training across multiple seeds."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

OFFICIAL_SEEDS = [42, 101, 202]
OFFICIAL_STAGE_IDS = ["stage1", "stage2", "stage3", "stage4"]


def load_yaml(path: Path) -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML is required to parse matrix manifests.")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def parse_matrix_manifest(root: Path, matrix_manifest: str) -> dict:
    path = Path(matrix_manifest)
    path = path if path.is_absolute() else root / path
    data = load_yaml(path)

    experiment_family = str(data.get("experiment_family", "")).strip()
    if not experiment_family:
        raise ValueError("matrix manifest missing required 'experiment_family'.")

    seeds = data.get("seeds")
    if seeds != OFFICIAL_SEEDS:
        raise ValueError(f"matrix manifest seeds must be exactly {OFFICIAL_SEEDS}, got: {seeds}")

    stages = data.get("stages")
    if not isinstance(stages, list) or len(stages) != 4:
        raise ValueError("matrix manifest must define exactly four stages.")

    parsed_stages = []
    seen_ids: set[str] = set()
    for expected_order, stage in enumerate(stages, start=1):
        if not isinstance(stage, dict):
            raise ValueError("each matrix stage must be a mapping.")
        stage_id = str(stage.get("id", "")).strip()
        if stage_id not in OFFICIAL_STAGE_IDS:
            raise ValueError(f"unexpected stage id '{stage_id}'. Expected one of {OFFICIAL_STAGE_IDS}.")
        if stage_id in seen_ids:
            raise ValueError(f"duplicate stage id '{stage_id}' in matrix manifest.")
        seen_ids.add(stage_id)

        order = int(stage.get("order", expected_order))
        if order != expected_order:
            raise ValueError(f"stage '{stage_id}' has order {order}; expected {expected_order}.")

        manifest = str(stage.get("manifest", "")).strip()
        if not manifest:
            raise ValueError(f"stage '{stage_id}' missing 'manifest'.")
        manifest_path = Path(manifest)
        manifest_path = manifest_path if manifest_path.is_absolute() else root / manifest_path
        if not manifest_path.exists():
            raise FileNotFoundError(f"stage manifest not found for '{stage_id}': {manifest_path}")
        stage_manifest_data = load_yaml(manifest_path)
        stage_curriculum = stage_manifest_data.get("curriculum_stage")
        if stage.get("curriculum_stage") and stage_curriculum != stage.get("curriculum_stage"):
            raise ValueError(
                f"stage '{stage_id}' curriculum mismatch: matrix='{stage.get('curriculum_stage')}', "
                f"manifest='{stage_curriculum}'"
            )

        parsed_stages.append(
            {
                "id": stage_id,
                "order": order,
                "manifest": str(manifest_path.relative_to(root)),
                "curriculum_stage": stage.get("curriculum_stage") or stage_curriculum,
            }
        )

    if [stage["id"] for stage in parsed_stages] != OFFICIAL_STAGE_IDS:
        raise ValueError(f"stages must be ordered exactly as {OFFICIAL_STAGE_IDS}.")

    run_id_template = str(data.get("run_id_template", "")).strip()
    if not run_id_template:
        raise ValueError("matrix manifest missing required 'run_id_template'.")

    return {
        "manifest_path": str(path.relative_to(root)),
        "experiment_family": experiment_family,
        "seeds": seeds,
        "stages": parsed_stages,
        "run_id_template": run_id_template,
    }


def run_id_from_template(template: str, experiment_family: str, seed: int, stage_id: str, stage_order: int) -> str:
    run_id = template.format(
        experiment_family=experiment_family,
        seed=seed,
        stage_id=stage_id,
        stage_order=stage_order,
    )
    if not run_id or " " in run_id:
        raise ValueError(f"invalid run id generated from template: '{run_id}'")
    return run_id


def write_matrix_status(
    root: Path,
    results_dir: str,
    matrix: dict,
    expected_runs: list[dict],
    completed_runs: list[dict],
    failed_run: dict | None,
) -> None:
    status_dir = root / results_dir / matrix["experiment_family"] / "matrix"
    status_dir.mkdir(parents=True, exist_ok=True)
    status = {
        "schema_version": 1,
        "experiment_family": matrix["experiment_family"],
        "matrix_manifest": matrix["manifest_path"],
        "official_seeds": matrix["seeds"],
        "official_stages": [stage["id"] for stage in matrix["stages"]],
        "expected_run_count": len(expected_runs),
        "completed_run_count": len(completed_runs),
        "is_complete": failed_run is None and len(completed_runs) == len(expected_runs),
        "failed_run": failed_run,
        "expected_runs": expected_runs,
        "completed_runs": completed_runs,
        "pending_runs": [run for run in expected_runs if run["run_id"] not in {item["run_id"] for item in completed_runs}],
    }
    (status_dir / "matrix_status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = ["seed,stage_id,stage_order,run_id,status"]
    completed_set = {run["run_id"] for run in completed_runs}
    failed_id = failed_run["run_id"] if failed_run else None
    for run in expected_runs:
        if run["run_id"] in completed_set:
            state = "completed"
        elif run["run_id"] == failed_id:
            state = "failed"
        else:
            state = "pending"
        lines.append(f"{run['seed']},{run['stage_id']},{run['stage_order']},{run['run_id']},{state}")
    (status_dir / "matrix_status.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--matrix-manifest",
        default="configs/experiment_manifests/official_curriculum_matrix.yaml",
        help="YAML defining the official experiment family, seeds, and stage manifests.",
    )
    parser.add_argument(
        "--stage-manifest",
        action="append",
        default=[],
        help="Manifest path for one curriculum stage. Pass in stage order.",
    )
    parser.add_argument("--seeds", nargs="+", type=int, default=None)
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--run-prefix", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Only write run metadata for each matrix item without launching ML-Agents.",
    )
    parser.add_argument("--no-graphics", action="store_true")
    parser.add_argument("--env")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]

    if args.matrix_manifest:
        matrix = parse_matrix_manifest(root, args.matrix_manifest)
    else:
        if not args.stage_manifest:
            raise ValueError("Pass --stage-manifest values when --matrix-manifest is not used.")
        seeds = args.seeds if args.seeds is not None else OFFICIAL_SEEDS
        run_prefix = args.run_prefix or "LB_3v2_curriculum"
        matrix = {
            "manifest_path": "(cli stage-manifest list)",
            "experiment_family": run_prefix,
            "seeds": seeds,
            "stages": [
                {"id": f"stage{idx}", "order": idx, "manifest": manifest, "curriculum_stage": None}
                for idx, manifest in enumerate(args.stage_manifest, start=1)
            ],
            "run_id_template": "{experiment_family}_seed{seed}_{stage_id}",
        }

    expected_runs: list[dict] = []
    for seed in matrix["seeds"]:
        for stage in matrix["stages"]:
            run_id = run_id_from_template(
                matrix["run_id_template"],
                matrix["experiment_family"],
                int(seed),
                stage["id"],
                int(stage["order"]),
            )
            expected_runs.append(
                {
                    "seed": int(seed),
                    "stage_id": stage["id"],
                    "stage_order": int(stage["order"]),
                    "manifest": stage["manifest"],
                    "curriculum_stage": stage.get("curriculum_stage"),
                    "run_id": run_id,
                }
            )

    completed_runs: list[dict] = []
    failed_run: dict | None = None
    for item in expected_runs:
        command = [
            sys.executable,
            "scripts/train_with_metadata.py",
            "--manifest",
            item["manifest"],
            "--seed",
            str(item["seed"]),
            "--run-id",
            item["run_id"],
            "--results-dir",
            args.results_dir,
            "--experiment-family",
            matrix["experiment_family"],
            "--matrix-stage-id",
            item["stage_id"],
            "--matrix-stage-order",
            str(item["stage_order"]),
            "--matrix-total-stages",
            str(len(matrix["stages"])),
        ]
        if args.force:
            command.append("--force")
        if args.metadata_only:
            command.append("--metadata-only")
        if args.no_graphics:
            command.append("--no-graphics")
        if args.env:
            command.extend(["--env", args.env])

        print(f"\n=== Seed {item['seed']} | {item['stage_id']} | run_id={item['run_id']} ===")
        print(" ".join(command))
        rc = subprocess.run(command, cwd=root).returncode
        if rc != 0:
            failed_run = dict(item)
            failed_run["exit_code"] = rc
            write_matrix_status(root, args.results_dir, matrix, expected_runs, completed_runs, failed_run)
            print(
                f"Training failed at seed={item['seed']}, stage={item['stage_id']} (run_id={item['run_id']}).",
                file=sys.stderr,
            )
            return rc
        completed_runs.append(dict(item))

    write_matrix_status(root, args.results_dir, matrix, expected_runs, completed_runs, failed_run)
    print(f"Official matrix completed: family={matrix['experiment_family']}, runs={len(completed_runs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
