#!/usr/bin/env python3
"""Validate the Labyrinth Breach foundation scaffold."""

from __future__ import annotations

from pathlib import Path


REQUIRED_DIRECTORIES = [
    "unity",
    "python",
    "configs",
    "experiments",
    "results",
    "scripts",
    "docs",
    "paper",
    "media",
]

REQUIRED_CONFIG_FILES = [
    "configs/trainer_configs/ppo_openarena_3v2.yaml",
    "configs/env_configs/env_openarena_v1.yaml",
    "configs/reward_configs/reward_shared_basic_v1.yaml",
    "configs/curriculum_configs/curriculum_basic_to_maze_v1.yaml",
    "configs/experiment_manifests/exp_openarena_shared_seed42.yaml",
]


def check_directories(root: Path) -> list[str]:
    missing: list[str] = []
    print("Checking required directories:")
    for relative_path in REQUIRED_DIRECTORIES:
        path = root / relative_path
        if path.is_dir():
            print(f"  OK      {relative_path}/")
        else:
            print(f"  MISSING {relative_path}/")
            missing.append(relative_path)
    return missing


def check_config_files(root: Path) -> list[str]:
    missing: list[str] = []
    print("\nChecking required config files:")
    for relative_path in REQUIRED_CONFIG_FILES:
        path = root / relative_path
        if path.is_file():
            print(f"  OK      {relative_path}")
        else:
            print(f"  MISSING {relative_path}")
            missing.append(relative_path)
    return missing


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    missing_directories = check_directories(root)
    missing_config_files = check_config_files(root)

    if not missing_directories and not missing_config_files:
        print("\nSuccess! Required folders and config files are present.")
        return 0

    print("\nSetup validation failed.")
    if missing_directories:
        print("\nMissing folders:")
        for path in missing_directories:
            print(f"  - {path}/")
    if missing_config_files:
        print("\nMissing config files:")
        for path in missing_config_files:
            print(f"  - {path}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
