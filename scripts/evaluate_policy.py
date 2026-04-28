#!/usr/bin/env python3
"""Run fixed-policy ML-Agents evaluation without learning updates."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

from artifact_validation import ArtifactRequirement, format_problem_report, validate_artifacts
from run_log_artifacts import collect_run_log_artifacts, prepare_run_log_routing
from save_run_metadata import load_yaml, repo_root, save_metadata, sha256_file


CONFIG_DIRECTORIES = {
    "trainer_config": Path("configs/trainer_configs"),
    "env_config": Path("configs/env_configs"),
    "reward_config": Path("configs/reward_configs"),
    "curriculum_config": Path("configs/curriculum_configs"),
    "rule_config": Path("configs/env_configs"),
}


def resolve(root: Path, path_value: str | None) -> Path | None:
    if not path_value:
        return None
    path = Path(path_value)
    return path if path.is_absolute() else root / path


def resolve_config(root: Path, key: str, value: str | None) -> str | None:
    if not value:
        return None

    path = Path(value)
    if path.is_absolute():
        return str(path)

    direct = root / path
    if direct.exists() or "/" in value or "\\" in value:
        return str(path)

    base_dir = CONFIG_DIRECTORIES.get(key)
    if base_dir is None:
        return str(path)

    candidate = base_dir / path
    return str(candidate)


def manifest_value(args: argparse.Namespace, key: str) -> Any:
    value = getattr(args, key, None)
    return value if value is not None else args.manifest_data.get(key)


def shell_join(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def cuda_available() -> bool:
    try:
        import torch
    except ImportError:
        return False

    return bool(torch.cuda.is_available())


def ensure_eval_preflight() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        if sock.connect_ex(("127.0.0.1", 5004)) == 0:
            raise RuntimeError("Preflight failed: port 5004 is already in use.")

    current_pid = str(os.getpid())
    proc_list = subprocess.run(
        ["ps", "-eo", "pid=,args="],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ).stdout.splitlines()
    stale = []
    for line in proc_list:
        stripped = line.strip()
        if not stripped:
            continue
        pid, _, args = stripped.partition(" ")
        if "mlagents-learn" in args and pid != current_pid:
            stale.append(f"{pid} {args}")
    if stale:
        raise RuntimeError("Preflight failed: stale mlagents-learn process detected.\n  " + "\n  ".join(stale[:5]))


def resolve_torch_device(args: argparse.Namespace) -> str | None:
    if args.torch_device:
        if args.torch_device.startswith("cuda") and not cuda_available():
            raise RuntimeError(
                "CUDA was requested, but PyTorch cannot access a GPU. "
                "Run scripts/check_gpu_training.py for diagnostics."
            )
        if args.torch_device == "cpu" and not args.allow_cpu:
            raise RuntimeError("CPU evaluation was requested. Add --allow-cpu if this is intentional.")
        return args.torch_device

    if cuda_available():
        return "cuda"

    if args.allow_cpu:
        return None

    raise RuntimeError(
        "GPU evaluation is required, but CUDA is not available to PyTorch. "
        "Run scripts/check_gpu_training.py, then fix the NVIDIA driver/CUDA setup or use --allow-cpu."
    )


def behavior_checkpoint_paths(results_dir: Path, run_id: str, behaviors: list[str]) -> list[Path]:
    return [results_dir / run_id / behavior / "checkpoint.pt" for behavior in behaviors]


def behavior_policy_paths(results_dir: Path, run_id: str, behaviors: list[str]) -> list[Path]:
    return [results_dir / run_id / f"{behavior}.onnx" for behavior in behaviors]


def require_existing(paths: list[Path], label: str) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        joined = "\n  ".join(missing)
        raise FileNotFoundError(f"Missing {label}:\n  {joined}")


def build_evaluation_command(args: argparse.Namespace, root: Path) -> list[str]:
    trainer_config = manifest_value(args, "trainer_config")
    seed = manifest_value(args, "seed")
    torch_device = resolve_torch_device(args)

    if not trainer_config:
        raise ValueError("trainer_config is required, either via --trainer-config or manifest.")
    if not args.source_run_id:
        raise ValueError("--source-run-id is required so evaluation knows which fixed checkpoint to load.")

    normalized_trainer_config = resolve_config(root, "trainer_config", str(trainer_config))
    command = [
        "mlagents-learn",
        normalized_trainer_config,
        "--run-id",
        args.source_run_id,
        "--results-dir",
        args.source_results_dir,
        "--resume",
        "--inference",
    ]

    if seed is not None:
        command.extend(["--seed", str(seed)])
    if args.deterministic:
        command.append("--deterministic")
    if args.env:
        command.extend(["--env", args.env])
    if args.no_graphics:
        command.append("--no-graphics")
    if torch_device:
        command.extend(["--torch-device", torch_device])
    if args.timeout_wait is not None:
        command.extend(["--timeout-wait", str(args.timeout_wait)])
    if args.extra_mlagents_args:
        command.extend(args.extra_mlagents_args)

    return command


def build_metadata_args(args: argparse.Namespace, command: list[str]) -> argparse.Namespace:
    manifest = args.manifest_data
    root = repo_root()
    eval_run_id = args.eval_run_id or manifest.get("run_id")
    if not eval_run_id:
        seed = manifest_value(args, "seed")
        seed_suffix = f"_seed{seed}" if seed is not None else ""
        eval_run_id = f"{args.source_run_id}_eval{seed_suffix}"

    metadata_args = argparse.Namespace(
        run_id=eval_run_id,
        seed=manifest_value(args, "seed"),
        trainer_config=resolve_config(root, "trainer_config", manifest_value(args, "trainer_config")),
        env_config=resolve_config(root, "env_config", manifest_value(args, "env_config")),
        reward_config=resolve_config(root, "reward_config", manifest_value(args, "reward_config")),
        curriculum_config=resolve_config(
            root,
            "curriculum_config",
            manifest_value(args, "curriculum_config"),
        ),
        curriculum_stage=manifest_value(args, "curriculum_stage"),
        scene=manifest_value(args, "scene"),
        manifest=args.manifest,
        results_dir=args.output_dir,
        notes=args.notes or manifest.get("notes"),
        training_command=shell_join(command),
        extra_config=list(args.extra_config),
    )

    rule_config = resolve_config(root, "rule_config", manifest.get("rule_config"))
    if rule_config:
        metadata_args.extra_config.append(rule_config)

    return metadata_args


def resolve_eval_run_id(args: argparse.Namespace) -> str:
    manifest = args.manifest_data
    eval_run_id = args.eval_run_id or manifest.get("run_id")
    if not eval_run_id:
        seed = manifest_value(args, "seed")
        seed_suffix = f"_seed{seed}" if seed is not None else ""
        eval_run_id = f"{args.source_run_id}_eval{seed_suffix}"
    return str(eval_run_id)


def write_runtime_config_overrides(args: argparse.Namespace, root: Path) -> None:
    override_dir = root / "configs" / "runtime_overrides"
    override_dir.mkdir(parents=True, exist_ok=True)

    curriculum_value = manifest_value(args, "curriculum_config")
    curriculum_override = override_dir / "active_curriculum_config.txt"
    if curriculum_value:
        curriculum_override.write_text(str(curriculum_value).strip() + "\n", encoding="utf-8")
    else:
        curriculum_override.write_text("", encoding="utf-8")

    rule_value = manifest_value(args, "rule_config")
    if rule_value is None:
        rule_value = args.manifest_data.get("rule_config")
    rule_override = override_dir / "active_rule_config.txt"
    if rule_value:
        rule_override.write_text(str(rule_value).strip() + "\n", encoding="utf-8")
    else:
        rule_override.write_text("", encoding="utf-8")


def file_record(root: Path, path: Path, label: str) -> dict[str, Any]:
    try:
        display_path = path.resolve().relative_to(root.resolve())
    except ValueError:
        display_path = path

    return {
        "label": label,
        "path": str(display_path),
        "exists": path.exists(),
        "sha256": sha256_file(path) if path.exists() else None,
    }


def write_evaluation_metadata(
    metadata_path: Path,
    args: argparse.Namespace,
    command: list[str],
    checkpoints: list[Path],
    policies: list[Path],
) -> Path:
    root = repo_root()
    eval_metadata_path = metadata_path.parent / "evaluation_metadata.json"
    eval_metadata = {
        "schema_version": 1,
        "mode": "evaluation",
        "learning_disabled": True,
        "fixed_policy_source_run_id": args.source_run_id,
        "source_results_dir": args.source_results_dir,
        "eval_run_id": metadata_path.parents[1].name,
        "seed": manifest_value(args, "seed"),
        "eval_environment_type": args.manifest_data.get("layout_split", "unspecified"),
        "scene": manifest_value(args, "scene"),
        "deterministic": args.deterministic,
        "max_runtime_seconds": args.max_runtime_seconds,
        "timeout_wait_seconds": args.timeout_wait,
        "mlagents_inference_flags": ["--resume", "--inference"],
        "command": command,
        "command_text": shell_join(command),
        "dry_run": args.dry_run,
        "trainer_config": resolve_config(root, "trainer_config", manifest_value(args, "trainer_config")),
        "env_config": resolve_config(root, "env_config", manifest_value(args, "env_config")),
        "reward_config": resolve_config(root, "reward_config", manifest_value(args, "reward_config")),
        "curriculum_config": resolve_config(root, "curriculum_config", manifest_value(args, "curriculum_config")),
        "rule_config": resolve_config(root, "rule_config", args.manifest_data.get("rule_config")),
        "checkpoints": [file_record(root, path, path.parent.name) for path in checkpoints],
        "onnx_policies": [file_record(root, path, path.stem) for path in policies],
        "model_paths": [str(path) for path in policies],
    }
    eval_metadata_path.write_text(json.dumps(eval_metadata, indent=2, sort_keys=True) + "\n")
    return eval_metadata_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="configs/experiment_manifests/exp_unseen_eval_seed101.yaml")
    parser.add_argument("--eval-run-id")
    parser.add_argument("--source-run-id", help="Existing training run ID whose checkpoints will be loaded.")
    parser.add_argument("--source-results-dir", default="results")
    parser.add_argument("--output-dir", default="results")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--trainer-config")
    parser.add_argument("--env-config")
    parser.add_argument("--reward-config")
    parser.add_argument("--curriculum-config")
    parser.add_argument("--curriculum-stage")
    parser.add_argument("--rule-config")
    parser.add_argument("--scene")
    parser.add_argument("--notes")
    parser.add_argument("--extra-config", action="append", default=[])
    parser.add_argument("--behavior", action="append", dest="behaviors")
    parser.add_argument("--torch-device")
    parser.add_argument("--allow-cpu", action="store_true")
    parser.add_argument("--env")
    parser.add_argument("--no-graphics", action="store_true")
    parser.add_argument("--timeout-wait", type=int, default=120)
    parser.add_argument("--deterministic", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--skip-checkpoint-check", action="store_true")
    parser.add_argument(
        "--max-runtime-seconds",
        type=int,
        help="Stop evaluation after this many seconds (fixed-duration comparisons).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write metadata and print the command without launching ML-Agents.",
    )
    parser.add_argument(
        "--skip-kpi-summarization",
        action="store_true",
        help="Skip strict KPI summarization and output validation after evaluation.",
    )
    parser.add_argument("extra_mlagents_args", nargs=argparse.REMAINDER)
    return parser


def main() -> int:
    root = repo_root()
    parser = build_parser()
    args = parser.parse_args()
    args.manifest_data = {}
    args.behaviors = args.behaviors or ["Sentinel", "Runner"]
    if args.extra_mlagents_args and args.extra_mlagents_args[0] == "--":
        args.extra_mlagents_args = args.extra_mlagents_args[1:]

    manifest_path = resolve(root, args.manifest)
    if manifest_path is not None:
        args.manifest_data = load_yaml(manifest_path)

    try:
        ensure_eval_preflight()
        command = build_evaluation_command(args, root)
        source_results_dir = resolve(root, args.source_results_dir) or root / "results"
        checkpoints = behavior_checkpoint_paths(
            source_results_dir,
            args.source_run_id,
            args.behaviors,
        )
        policies = behavior_policy_paths(
            source_results_dir,
            args.source_run_id,
            args.behaviors,
        )

        if not args.skip_checkpoint_check:
            require_existing(checkpoints, "ML-Agents checkpoints")

        metadata_args = build_metadata_args(args, command)
        metadata_path = save_metadata(metadata_args)
        eval_metadata_path = write_evaluation_metadata(metadata_path, args, command, checkpoints, policies)
        eval_run_id = resolve_eval_run_id(args)
        write_runtime_config_overrides(args, root)
        prepare_run_log_routing(root, eval_run_id, args.output_dir, mode="evaluation")
    except Exception as exc:
        print(f"Failed to prepare evaluation run: {exc}", file=sys.stderr)
        return 1

    print(f"Saved run metadata: {metadata_path}")
    print(f"Saved evaluation metadata: {eval_metadata_path}")
    print(f"Evaluation command: {shell_join(command)}")
    print("Learning disabled: --resume --inference")

    if args.dry_run:
        return 0

    eval_run_id = resolve_eval_run_id(args)
    try:
        process = subprocess.Popen(command, cwd=root)
    except FileNotFoundError as exc:
        if exc.filename == "mlagents-learn":
            print(
                "Failed to launch evaluation: 'mlagents-learn' was not found in PATH.\n"
                "Activate the project environment first, for example:\n"
                "  source \"/home/code/anaconda3/etc/profile.d/conda.sh\"\n"
                "  conda activate labyrinth-breach\n"
                "Then verify with:\n"
                "  mlagents-learn --help",
                file=sys.stderr,
            )
            return 127
        raise
    try:
        timeout = args.max_runtime_seconds if args.max_runtime_seconds and args.max_runtime_seconds > 0 else None
        rc = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        print(
            f"Max runtime reached ({args.max_runtime_seconds}s). Terminating evaluation process.",
            file=sys.stderr,
        )
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        rc = 124

    try:
        sync = collect_run_log_artifacts(
            root,
            eval_run_id,
            args.output_dir,
            strict=rc in (0, 124),
        )
        copied = ", ".join(sync.copied) if sync.copied else "none"
        missing = ", ".join(sync.missing) if sync.missing else "none"
        print(f"Run log sync target: {sync.logs_dir}")
        print(f"Run log sync copied: {copied}")
        print(f"Run log sync missing: {missing}")
    except Exception as exc:
        print(f"Run log sync failed: {exc}", file=sys.stderr)
        return 2 if rc in (0, 124) else rc

    if rc in (0, 124) and not args.skip_kpi_summarization:
        logs_dir = root / args.output_dir / eval_run_id / "logs"
        kpi_dir = root / args.output_dir / eval_run_id / "kpi"
        kpi_json = kpi_dir / "eval_kpi_summary.json"
        kpi_csv = kpi_dir / "eval_kpi_summary.csv"
        eval_seed = manifest_value(args, "seed")
        summarize_command = [
            sys.executable,
            "scripts/summarize_eval_kpis.py",
            "--logs-dir",
            str(logs_dir),
            "--run-id",
            eval_run_id,
            "--seed",
            str(eval_seed if eval_seed is not None else -1),
            "--output",
            str(kpi_json),
            "--csv-output",
            str(kpi_csv),
        ]
        print(f"KPI summarization command: {shell_join(summarize_command)}")
        summarize_rc = subprocess.run(summarize_command, cwd=root).returncode
        if summarize_rc != 0:
            print(
                f"KPI summarization failed for run '{eval_run_id}' with exit code {summarize_rc}.",
                file=sys.stderr,
            )
            return summarize_rc

        output_problems = validate_artifacts(
            [
                ArtifactRequirement(path=kpi_json, label="eval_kpi_summary.json"),
                ArtifactRequirement(path=kpi_csv, label="eval_kpi_summary.csv"),
            ]
        )
        if output_problems:
            print(format_problem_report(output_problems, heading="Post-summarization KPI validation failed"), file=sys.stderr)
            return 2

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
