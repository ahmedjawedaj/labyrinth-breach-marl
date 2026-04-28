#!/usr/bin/env python3
"""Check whether this machine can run ML-Agents training on the GPU."""

from __future__ import annotations

import subprocess


def run_command(command: list[str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except FileNotFoundError as exc:
        return 127, str(exc)

    return completed.returncode, completed.stdout.strip()


def main() -> int:
    print("Checking NVIDIA driver with nvidia-smi...")
    smi_code, smi_output = run_command(["nvidia-smi"])
    print(smi_output or "nvidia-smi produced no output")
    print()

    print("Checking PyTorch CUDA access...")
    try:
        import torch
    except ImportError:
        print("PyTorch is not installed in this Python environment.")
        return 1

    print(f"torch: {torch.__version__}")
    print(f"torch.version.cuda: {torch.version.cuda}")
    print(f"torch.cuda.is_available(): {torch.cuda.is_available()}")
    print(f"torch.cuda.device_count(): {torch.cuda.device_count()}")
    if torch.cuda.is_available():
        print(f"GPU 0: {torch.cuda.get_device_name(0)}")
        tensor = torch.ones((1024, 1024), device="cuda")
        print(f"CUDA tensor check: {float(tensor.sum().item()):.1f}")
        print()
        print("GPU training is available. Use --torch-device cuda or scripts/train_with_metadata.py default behavior.")
        return 0

    print()
    print("GPU training is not available in this environment.")
    print("If nvidia-smi failed, fix the NVIDIA driver/session first; project code cannot bypass that.")
    print("If nvidia-smi worked but PyTorch failed, reinstall the CUDA PyTorch wheel pinned by requirements.txt.")
    return 1 if smi_code == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
