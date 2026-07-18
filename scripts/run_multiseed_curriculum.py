#!/usr/bin/env python3
"""Run staged curriculum training across multiple seeds."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

OFFICIAL_SEEDS = [42, 101, 202, 606, 707]
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

    expected_stage_ids = data.get("stage_ids", OFFICIAL_STAGE_IDS)
    if not isinstance(expected_stage_ids, list) or not expected_stage_ids:
        raise ValueError("matrix manifest stage_ids must be a non-empty list when provided.")
    stages = data.get("stages")
    if not isinstance(stages, list) or len(stages) != len(expected_stage_ids):
        raise ValueError(f"matrix manifest must define exactly {len(expected_stage_ids)} stages.")

    parsed_stages = []
    seen_ids: set[str] = set()
    for expected_order, stage in enumerate(stages, start=1):
        if not isinstance(stage, dict):
            raise ValueError("each matrix stage must be a mapping.")
        stage_id = str(stage.get("id", "")).strip()
        if stage_id not in expected_stage_ids:
            raise ValueError(f"unexpected stage id '{stage_id}'. Expected one of {expected_stage_ids}.")
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
                "reward_config": stage_manifest_data.get("reward_config"),
            }
        )

    if [stage["id"] for stage in parsed_stages] != expected_stage_ids:
        raise ValueError(f"stages must be ordered exactly as {expected_stage_ids}.")

    run_id_template = str(data.get("run_id_template", "")).strip()
    if not run_id_template:
        raise ValueError("matrix manifest missing required 'run_id_template'.")

    preflight_audits = data.get("preflight_audits", [])
    allowed_preflights = {"budgets", "reward", "memory_off"}
    if not isinstance(preflight_audits, list) or not set(preflight_audits).issubset(allowed_preflights):
        raise ValueError(f"matrix preflight_audits must use only {sorted(allowed_preflights)}")

    return {
        "manifest_path": str(path.relative_to(root)),
        "experiment_family": experiment_family,
        "seeds": seeds,
        "stages": parsed_stages,
        "run_id_template": run_id_template,
        "preflight_audits": preflight_audits,
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


def select_matrix_seeds(matrix: dict, requested_seeds: list[int] | None) -> dict:
    if requested_seeds is None:
        return matrix
    if not requested_seeds or len(set(requested_seeds)) != len(requested_seeds):
        raise ValueError("--seeds must contain one or more unique seed values.")
    unknown = sorted(set(requested_seeds) - set(matrix["seeds"]))
    if unknown:
        raise ValueError(f"Requested seeds are not registered in the matrix: {unknown}")
    selected = dict(matrix)
    selected["seeds"] = [seed for seed in matrix["seeds"] if seed in set(requested_seeds)]
    return selected


def write_matrix_status(
    root: Path,
    results_dir: str,
    matrix: dict,
    expected_runs: list[dict],
    completed_runs: list[dict],
    failed_run: dict | None,
    matrix_status_dir: str | None = None,
) -> None:
    status_dir = (
        root / matrix_status_dir / matrix["experiment_family"]
        if matrix_status_dir
        else root / results_dir / matrix["experiment_family"] / "matrix"
    )
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
    parser.add_argument(
        "--matrix-status-dir",
        help="Optional worker-local status directory when run artifacts use a shared results root.",
    )
    parser.add_argument("--run-prefix", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Only write run metadata for each matrix item without launching ML-Agents.",
    )
    parser.add_argument("--no-graphics", action="store_true")
    parser.add_argument("--env")
    parser.add_argument(
        "--base-port",
        type=int,
        help="ML-Agents base port; use a unique value for each isolated worker root.",
    )
    parser.add_argument("--torch-device")
    parser.add_argument("--allow-cpu", action="store_true")
    parser.add_argument(
        "--resume-completed",
        action="store_true",
        help="Skip runs whose completion status and strict training audit already pass.",
    )
    return parser


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def config_snapshots_match(root: Path, metadata: dict) -> bool:
    snapshots = metadata.get("config_snapshots") or []
    if not snapshots:
        return False
    for record in snapshots:
        source = root / str(record.get("source", ""))
        snapshot = root / str(record.get("snapshot", ""))
        expected_hash = str(record.get("sha256", ""))
        if not source.is_file() or not snapshot.is_file() or not expected_hash:
            return False
        if sha256_file(source) != expected_hash or sha256_file(snapshot) != expected_hash:
            return False
    return True


def completed_run_is_valid(root: Path, run_dir: Path, expected_initialize_from: str | None) -> bool:
    status_path = run_dir / "metadata" / "training_status.json"
    audit_path = run_dir / "metadata" / "training_audit.json"
    metadata_path = run_dir / "metadata" / "run_metadata.json"
    if not all(path.is_file() for path in (status_path, audit_path, metadata_path)):
        return False
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        status.get("success") is True
        and status.get("exit_code") == 0
        and audit.get("failed") == 0
        and len(audit.get("checks") or []) >= 33
        and metadata.get("initialize_from") == expected_initialize_from
        and config_snapshots_match(root, metadata)
    )


def main() -> int:
    args = build_parser().parse_args()
    root = Path(__file__).resolve().parents[1]

    if args.stage_manifest:
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
    elif args.matrix_manifest:
        matrix = select_matrix_seeds(
            parse_matrix_manifest(root, args.matrix_manifest),
            args.seeds,
        )
    else:
        raise ValueError("Pass --matrix-manifest or at least one --stage-manifest.")

    preflight_commands = {
        "budgets": [sys.executable, "scripts/validate_training_budgets.py"],
        "reward": [sys.executable, "scripts/validate_reward_ablation.py"],
        "memory_off": [
            sys.executable,
            "scripts/validate_ablation_controls.py",
            "--condition",
            "memory_off",
        ],
    }
    for audit_id in matrix.get("preflight_audits", []):
        audit_rc = subprocess.run(preflight_commands[audit_id], cwd=root).returncode
        if audit_rc != 0:
            print(f"Preflight '{audit_id}' failed; refusing training matrix launch.", file=sys.stderr)
            return audit_rc

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
                    "reward_config": stage.get("reward_config"),
                    "run_id": run_id,
                }
            )

    completed_runs: list[dict] = []
    failed_run: dict | None = None
    previous_run_by_seed: dict[int, str] = {}
    for item in expected_runs:
        previous_run = previous_run_by_seed.get(item["seed"])
        run_dir = root / args.results_dir / item["run_id"]
        if args.resume_completed and completed_run_is_valid(root, run_dir, previous_run):
            print(
                f"Skipping audited completed run: seed={item['seed']}, "
                f"stage={item['stage_id']}, run_id={item['run_id']}"
            )
            completed_runs.append(dict(item))
            previous_run_by_seed[item["seed"]] = item["run_id"]
            continue

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
        if previous_run:
            command.extend(["--initialize-from", previous_run])
        if args.force:
            command.append("--force")
        if args.metadata_only:
            command.append("--metadata-only")
        if args.no_graphics:
            command.append("--no-graphics")
        if args.env:
            command.extend(["--env", args.env])
        if args.base_port is not None:
            command.extend(["--base-port", str(args.base_port)])
        if args.torch_device:
            command.extend(["--torch-device", args.torch_device])
        if args.allow_cpu:
            command.append("--allow-cpu")

        print(f"\n=== Seed {item['seed']} | {item['stage_id']} | run_id={item['run_id']} ===")
        print(" ".join(command))
        rc = subprocess.run(command, cwd=root).returncode
        if rc != 0:
            failed_run = dict(item)
            failed_run["exit_code"] = rc
            write_matrix_status(
                root,
                args.results_dir,
                matrix,
                expected_runs,
                completed_runs,
                failed_run,
                args.matrix_status_dir,
            )
            print(
                f"Training failed at seed={item['seed']}, stage={item['stage_id']} (run_id={item['run_id']}).",
                file=sys.stderr,
            )
            return rc

        if not args.metadata_only:
            audit_command = [
                sys.executable,
                "scripts/audit_training_run.py",
                str(root / args.results_dir / item["run_id"]),
                "--expected-stage",
                str(item["curriculum_stage"]),
                "--expected-seed",
                str(item["seed"]),
                "--expected-reward-config",
                str(item["reward_config"]),
            ]
            if previous_run:
                audit_command.extend(["--expected-initialize-from", previous_run])
            audit_rc = subprocess.run(audit_command, cwd=root).returncode
            if audit_rc != 0:
                failed_run = dict(item)
                failed_run["exit_code"] = audit_rc
                failed_run["failure_kind"] = "training_audit"
                write_matrix_status(
                    root,
                    args.results_dir,
                    matrix,
                    expected_runs,
                    completed_runs,
                    failed_run,
                    args.matrix_status_dir,
                )
                print(
                    f"Training audit failed at seed={item['seed']}, stage={item['stage_id']} "
                    f"(run_id={item['run_id']}).",
                    file=sys.stderr,
                )
                return audit_rc
        completed_runs.append(dict(item))
        previous_run_by_seed[item["seed"]] = item["run_id"]

    write_matrix_status(
        root,
        args.results_dir,
        matrix,
        expected_runs,
        completed_runs,
        failed_run,
        args.matrix_status_dir,
    )
    print(f"Official matrix completed: family={matrix['experiment_family']}, runs={len(completed_runs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
