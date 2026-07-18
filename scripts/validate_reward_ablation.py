#!/usr/bin/env python3
"""Verify that the tactical-reward ablation changes no non-tactical weights."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import yaml


OFFICIAL_STAGE_MANIFESTS = (
    "exp_curriculum_stage1_static_fixed_seed42.yaml",
    "exp_curriculum_stage2_static_random_seed42.yaml",
    "exp_curriculum_stage3_dynamic_low_seed42.yaml",
    "exp_curriculum_stage4_dynamic_high_seed42.yaml",
)
CANONICAL_REWARD = "configs/reward_configs/reward_v5_active_agents.yaml"


def load(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def without_tactical_identity(config: dict) -> dict:
    cleaned = copy.deepcopy(config)
    cleaned.pop("reward_id", None)
    cleaned.pop("description", None)
    cleaned.pop("trap_aware", None)
    return cleaned


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="results/official_summary/reward_ablation_audit.json")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    full_path = root / "configs/reward_configs/reward_v5_active_agents.yaml"
    off_path = root / "configs/reward_configs/reward_v5_tactical_off.yaml"
    full = load(full_path)
    off = load(off_path)

    checks: list[dict] = []

    def check(name: str, passed: bool, evidence: str) -> None:
        checks.append({"check": name, "status": "PASS" if passed else "FAIL", "evidence": evidence})

    check(
        "Non-tactical reward fields are identical",
        without_tactical_identity(full) == without_tactical_identity(off),
        "All fields outside reward_id, description, and trap_aware",
    )
    full_trap = full.get("trap_aware") or {}
    off_trap = off.get("trap_aware") or {}
    check("Full tactical layer enabled", full_trap.get("enabled") is True, str(full_trap))
    check("Ablated tactical layer disabled", off_trap.get("enabled") is False, str(off_trap))
    off_bonuses = [value for key, value in off_trap.items() if key != "enabled"]
    check("Ablated tactical bonuses are zero", all(float(value) == 0.0 for value in off_bonuses), str(off_trap))

    manifest_dir = root / "configs/experiment_manifests"
    for filename in OFFICIAL_STAGE_MANIFESTS:
        manifest = load(manifest_dir / filename)
        check(
            f"Canonical reward in {filename}",
            manifest.get("reward_config") == CANONICAL_REWARD,
            str(manifest.get("reward_config")),
        )

    passed = sum(item["status"] == "PASS" for item in checks)
    payload = {
        "schema_version": 1,
        "canonical_reward": str(full_path.relative_to(root)),
        "tactical_off_reward": str(off_path.relative_to(root)),
        "passed": passed,
        "failed": len(checks) - passed,
        "checks": checks,
    }
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Reward ablation audit: {passed}/{len(checks)} checks passed")
    print(f"Wrote: {output}")
    return 0 if passed == len(checks) else 2


if __name__ == "__main__":
    raise SystemExit(main())
