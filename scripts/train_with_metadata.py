#!/usr/bin/env python3
"""Save run metadata, then launch ML-Agents training."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from run_log_artifacts import collect_run_log_artifacts, prepare_run_log_routing
from save_run_metadata import load_yaml, repo_root, save_metadata


def resolve(root: Path, path_value: str | None) -> Path | None:
    if not path_value:
        return None
    path = Path(path_value)
    return path if path.is_absolute() else root / path


def manifest_value(args: argparse.Namespace, key: str):
    return getattr(args, key) if getattr(args, key) is not None else args.manifest_data.get(key)


def clean_forced_run_directory(args: argparse.Namespace, root: Path) -> None:
    if not args.force or args.metadata_only:
        return
    if args.resume:
        raise ValueError("--force and --resume cannot be used together.")
    run_id = str(manifest_value(args, "run_id") or "").strip()
    if not run_id or Path(run_id).name != run_id:
        raise ValueError(f"Unsafe run ID for force cleanup: {run_id!r}")
    results_root = resolve(root, args.results_dir)
    if results_root is None:
        raise ValueError("results directory is required for force cleanup.")
    run_dir = (results_root / run_id).resolve()
    if results_root.resolve() not in run_dir.parents:
        raise ValueError(f"Refusing to clean a run outside the results root: {run_dir}")
    if run_dir.exists():
        shutil.rmtree(run_dir)
        print(f"Removed existing run directory before forced launch: {run_dir}")


def cuda_available() -> bool:
    try:
        import torch
    except ImportError:
        return False

    return bool(torch.cuda.is_available())


def resolve_torch_device(args: argparse.Namespace) -> str | None:
    if args.torch_device:
        if args.torch_device.startswith("cuda") and not cuda_available():
            raise RuntimeError(
                "CUDA was requested, but PyTorch cannot access a GPU. "
                "Run scripts/check_gpu_training.py for diagnostics."
            )
        if args.torch_device == "mps":
            raise RuntimeError(
                "ML-Agents 1.1.0 is incompatible with Apple MPS in this project "
                "(mixed CPU/MPS tensors during policy evaluation). Use CUDA or explicitly allow CPU training."
            )
        if args.torch_device == "cpu" and not args.allow_cpu:
            raise RuntimeError(
                "CPU training requires explicit consent. Pass --allow-cpu with --torch-device cpu."
            )
        return args.torch_device

    if cuda_available():
        return "cuda"
    if args.allow_cpu:
        return "cpu"

    raise RuntimeError(
        "CUDA is unavailable and ML-Agents 1.1.0 cannot use Apple MPS reliably. "
        "Pass --allow-cpu to opt into slower CPU training."
    )


def build_training_command(args: argparse.Namespace, root: Path) -> list[str]:
    trainer_config = manifest_value(args, "trainer_config")
    run_id = manifest_value(args, "run_id")
    seed = manifest_value(args, "seed")
    torch_device = resolve_torch_device(args)

    if not trainer_config:
        raise ValueError("trainer_config is required, either via --trainer-config or manifest.")
    if not run_id:
        raise ValueError("run_id is required, either via --run-id or manifest.")

    command = [
        "mlagents-learn",
        str(trainer_config),
        "--run-id",
        str(run_id),
        "--results-dir",
        args.results_dir,
    ]

    if seed is not None:
        command.extend(["--seed", str(seed)])
    if args.force:
        command.append("--force")
    if args.resume:
        command.append("--resume")
    initialize_from = manifest_value(args, "initialize_from")
    if initialize_from:
        command.extend(["--initialize-from", str(initialize_from)])
    if args.env:
        command.extend(["--env", args.env])
    if args.no_graphics:
        command.append("--no-graphics")
    if torch_device:
        command.extend(["--torch-device", torch_device])
    if args.timeout_wait is not None:
        command.extend(["--timeout-wait", str(args.timeout_wait)])
    if args.base_port is not None:
        command.extend(["--base-port", str(args.base_port)])
    if args.extra_mlagents_args:
        command.extend(args.extra_mlagents_args)

    return command


def shell_join(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def ensure_training_preflight(base_port: int = 5004) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        if sock.connect_ex(("127.0.0.1", base_port)) == 0:
            raise RuntimeError(f"Preflight failed: port {base_port} is already in use.")

    # The default port remains single-worker for backwards safety. Explicit,
    # non-default ports are reserved for isolated worker roots, where runtime
    # override files and result directories cannot race with another process.
    if base_port != 5004:
        return

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


def write_runtime_stage_override(args: argparse.Namespace, root: Path) -> None:
    stage_value = manifest_value(args, "curriculum_stage")
    if not stage_value:
        return

    override_dir = root / "configs" / "runtime_overrides"
    override_dir.mkdir(parents=True, exist_ok=True)
    override_path = override_dir / "active_stage.txt"
    override_path.write_text(str(stage_value).strip() + "\n", encoding="utf-8")


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
    rule_override = override_dir / "active_rule_config.txt"
    if rule_value:
        rule_path = Path(str(rule_value).strip())
        if not rule_path.is_absolute() and len(rule_path.parts) == 1:
            rule_path = Path("configs/env_configs") / rule_path
        rule_override.write_text(str(rule_path) + "\n", encoding="utf-8")
    else:
        rule_override.write_text("", encoding="utf-8")

    reward_value = manifest_value(args, "reward_config")
    reward_override = override_dir / "active_reward_config.txt"
    if reward_value:
        reward_path = Path(str(reward_value).strip())
        if not reward_path.is_absolute() and len(reward_path.parts) == 1:
            reward_path = Path("configs/reward_configs") / reward_path
        reward_override.write_text(str(reward_path) + "\n", encoding="utf-8")
    else:
        reward_override.write_text("", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest")
    parser.add_argument("--run-id")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--trainer-config")
    parser.add_argument("--env-config")
    parser.add_argument("--reward-config")
    parser.add_argument("--curriculum-config")
    parser.add_argument("--curriculum-stage")
    parser.add_argument("--rule-config")
    parser.add_argument("--scene")
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--notes")
    parser.add_argument("--experiment-family")
    parser.add_argument("--matrix-stage-id")
    parser.add_argument("--matrix-stage-order", type=int)
    parser.add_argument("--matrix-total-stages", type=int)
    parser.add_argument("--extra-config", action="append", default=[])
    parser.add_argument("--torch-device")
    parser.add_argument("--allow-cpu", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--initialize-from")
    parser.add_argument("--env")
    parser.add_argument("--no-graphics", action="store_true")
    parser.add_argument("--timeout-wait", type=int)
    parser.add_argument("--base-port", type=int)
    parser.add_argument("--metadata-only", action="store_true")
    parser.add_argument(
        "--forbid-fallback-log-copy",
        action="store_true",
        help="Fail instead of copying logs from Unity persistentDataPath fallback locations.",
    )
    parser.add_argument("extra_mlagents_args", nargs=argparse.REMAINDER)
    return parser


def write_training_status(
    root: Path,
    run_id: str,
    results_dir: str,
    *,
    exit_code: int | None,
    status: str,
    error: str | None = None,
    logs_dir: Path | None = None,
    missing_logs: list[str] | None = None,
) -> None:
    run_dir = root / results_dir / run_id
    metadata_dir = run_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "status": status,
        "success": status == "completed",
        "exit_code": exit_code,
        "error": error,
        "logs_dir": str(logs_dir) if logs_dir else None,
        "missing_logs": missing_logs or [],
    }
    (metadata_dir / "training_status.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def generate_run_kpis(root: Path, run_id: str, results_dir: str, logs_dir: Path, seed: int) -> int:
    output_dir = root / results_dir / run_id / "kpis"
    command = [
        sys.executable,
        "scripts/summarize_eval_kpis.py",
        "--logs-dir",
        str(logs_dir),
        "--run-id",
        run_id,
        "--seed",
        str(seed),
        "--output",
        str(output_dir / "eval_kpi_summary.json"),
        "--csv-output",
        str(output_dir / "eval_kpi_summary.csv"),
    ]
    return subprocess.run(command, cwd=root).returncode


def main() -> int:
    root = repo_root()
    parser = build_parser()
    args = parser.parse_args()
    args.manifest_data = {}

    manifest_path = resolve(root, args.manifest)
    if manifest_path is not None:
        args.manifest_data = load_yaml(manifest_path)

    try:
        command = build_training_command(args, root)
        ensure_training_preflight(args.base_port or 5004)
        clean_forced_run_directory(args, root)
        write_runtime_stage_override(args, root)
        write_runtime_config_overrides(args, root)
        args.training_command = shell_join(command)
        metadata_path = save_metadata(args)
        run_id = manifest_value(args, "run_id")
        prepare_run_log_routing(root, str(run_id), args.results_dir, mode="training")
    except Exception as exc:
        print(f"Failed to prepare training run: {exc}", file=sys.stderr)
        return 1

    print(f"Saved run metadata: {metadata_path}")
    print(f"Training command: {args.training_command}")

    if args.metadata_only:
        write_training_status(
            root,
            str(manifest_value(args, "run_id")),
            args.results_dir,
            exit_code=0,
            status="metadata_only",
            logs_dir=root / args.results_dir / str(manifest_value(args, "run_id")) / "logs",
        )
        return 0

    write_training_status(
        root,
        str(manifest_value(args, "run_id")),
        args.results_dir,
        exit_code=None,
        status="running",
        logs_dir=root / args.results_dir / str(manifest_value(args, "run_id")) / "logs",
    )

    try:
        process_env = os.environ.copy()
        process_env["LABYRINTH_REPO_ROOT"] = str(root)
        configured_scene = manifest_value(args, "scene")
        if configured_scene:
            process_env["LABYRINTH_SCENE"] = str(configured_scene)
        rc = subprocess.run(command, cwd=root, env=process_env).returncode
    except FileNotFoundError as exc:
        if exc.filename == "mlagents-learn":
            print(
                "Failed to launch training: 'mlagents-learn' was not found in PATH.\n"
                "Activate the project environment first, for example:\n"
                "  source \"/home/code/anaconda3/etc/profile.d/conda.sh\"\n"
                "  conda activate labyrinth-breach\n"
                "Then verify with:\n"
                "  mlagents-learn --help",
                file=sys.stderr,
            )
            write_training_status(
                root,
                str(manifest_value(args, "run_id")),
                args.results_dir,
                exit_code=127,
                status="failed",
                error="mlagents-learn not found in PATH",
            )
            return 127
        raise
    run_id = str(manifest_value(args, "run_id"))
    try:
        sync = collect_run_log_artifacts(
            root,
            run_id,
            args.results_dir,
            strict=rc == 0,
            allow_fallback_copy=not args.forbid_fallback_log_copy,
        )
        copied = ", ".join(sync.copied) if sync.copied else "none"
        missing = ", ".join(sync.missing) if sync.missing else "none"
        print(f"Run log sync target: {sync.logs_dir}")
        print(f"Run log sync copied: {copied}")
        print(f"Run log sync missing: {missing}")
        if rc == 0:
            kpi_rc = generate_run_kpis(
                root,
                run_id,
                args.results_dir,
                sync.logs_dir,
                int(manifest_value(args, "seed")),
            )
            if kpi_rc != 0:
                rc = kpi_rc
                print(f"KPI generation failed with exit code {kpi_rc}.", file=sys.stderr)
        write_training_status(
            root,
            run_id,
            args.results_dir,
            exit_code=rc,
            status="completed" if rc == 0 else "failed",
            logs_dir=sync.logs_dir,
            missing_logs=list(sync.missing),
        )
    except Exception as exc:
        print(f"Run log sync failed: {exc}", file=sys.stderr)
        write_training_status(
            root,
            run_id,
            args.results_dir,
            exit_code=2 if rc == 0 else rc,
            status="failed",
            error=f"run log sync failed: {exc}",
        )
        return 2 if rc == 0 else rc

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
