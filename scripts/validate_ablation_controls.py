#!/usr/bin/env python3
"""Verify evaluation ablations differ from canonical configs only as intended."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs" / "env_configs"
BASE_CONFIGS = [
    "maze_dynamic_config.yaml",
    "maze_unseen_eval_config.yaml",
    "maze_unseen_eval_seed202.yaml",
    "maze_unseen_eval_seed303.yaml",
    "maze_unseen_eval_seed404.yaml",
    "maze_unseen_eval_seed505.yaml",
]
NO_ASSIST_BASE_CONFIGS = [
    "maze_dynamic_config_no_assist.yaml",
    "maze_unseen_eval_config_no_assist.yaml",
    "maze_unseen_eval_seed202_no_assist.yaml",
    "maze_unseen_eval_seed303_no_assist.yaml",
    "maze_unseen_eval_seed404_no_assist.yaml",
    "maze_unseen_eval_seed505_no_assist.yaml",
]


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping in {path}")
    return data


def flatten(data, prefix: str = "") -> dict[str, object]:
    if isinstance(data, list):
        result = {}
        for index, value in enumerate(data):
            path = f"{prefix}.{index}" if prefix else str(index)
            result.update(flatten(value, path))
        return result
    if not isinstance(data, dict):
        return {prefix: data}
    result = {}
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        result.update(flatten(value, path))
    return result


def variant_name(base_name: str, condition: str) -> str:
    if condition == "action_assist_on":
        return f"{Path(base_name).stem.removesuffix('_no_assist')}.yaml"
    suffix = {
        "action_assist_off": "no_assist",
        "dynamic_wall_off": "wall_off",
        "memory_off": "memory_off",
    }[condition]
    return f"{Path(base_name).stem}_{suffix}.yaml"


def allowed_changes(condition: str) -> set[str]:
    common = {"config_id"}
    if condition in {"action_assist_off", "action_assist_on"}:
        return common | {
            "action_assist.sentinel_pursuit_strength",
            "action_assist.runner_evade_strength",
        }
    if condition == "dynamic_wall_off":
        return common | {"dynamic_walls.enabled"}
    return common | {"observations.use_memory"}


def expected_values(condition: str) -> dict[str, object]:
    if condition == "action_assist_on":
        return {
            "action_assist.sentinel_pursuit_strength": 0.15,
            "action_assist.runner_evade_strength": 0.0,
        }
    if condition == "action_assist_off":
        return {
            "action_assist.sentinel_pursuit_strength": 0.0,
            "action_assist.runner_evade_strength": 0.0,
        }
    if condition == "dynamic_wall_off":
        return {"dynamic_walls.enabled": False}
    return {"observations.use_memory": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--condition",
        choices=["action_assist_off", "action_assist_on", "dynamic_wall_off", "memory_off"],
        required=True,
    )
    parser.add_argument(
        "--output",
        help="Output JSON path (defaults to a condition-specific readiness artifact)",
    )
    args = parser.parse_args()

    checks = []
    if args.condition == "action_assist_on":
        base_configs = NO_ASSIST_BASE_CONFIGS
    else:
        base_configs = (["maze_static_config.yaml"] if args.condition == "memory_off" else []) + BASE_CONFIGS
    for base_name in base_configs:
        variant = variant_name(base_name, args.condition)
        base_flat = flatten(load_yaml(CONFIG_DIR / base_name))
        variant_flat = flatten(load_yaml(CONFIG_DIR / variant))
        keys = set(base_flat) | set(variant_flat)
        changed = {key for key in keys if base_flat.get(key) != variant_flat.get(key)}
        unexpected = sorted(changed - allowed_changes(args.condition))
        expected = expected_values(args.condition)
        values_ok = all(variant_flat.get(key) == value for key, value in expected.items())
        passed = not unexpected and values_ok
        checks.append(
            {
                "base": base_name,
                "variant": variant,
                "passed": passed,
                "changed_paths": sorted(changed),
                "unexpected_paths": unexpected,
            }
        )

    if args.condition == "memory_off":
        full_curriculum = flatten(
            load_yaml(ROOT / "configs/curriculum_configs/curriculum_3v2_full_v1.yaml")
        )
        memory_curriculum = flatten(
            load_yaml(ROOT / "configs/curriculum_configs/curriculum_memory_off_aligned_v2.yaml")
        )
        keys = set(full_curriculum) | set(memory_curriculum)
        changed = {key for key in keys if full_curriculum.get(key) != memory_curriculum.get(key)}
        allowed = {"curriculum_id"} | {key for key in changed if key.endswith(".rule_config")}
        unexpected = sorted(changed - allowed)
        rule_paths_ok = all(
            str(memory_curriculum[key]).endswith("_memory_off.yaml")
            for key in changed
            if key.endswith(".rule_config")
        )
        checks.append(
            {
                "base": "curriculum_3v2_full_v1.yaml",
                "variant": "curriculum_memory_off_aligned_v2.yaml",
                "passed": not unexpected and rule_paths_ok and len(changed - {"curriculum_id"}) == 4,
                "changed_paths": sorted(changed),
                "unexpected_paths": unexpected,
            }
        )

    output_name = args.output or (
        f"results/official_summary/{args.condition}_control_audit.json"
    )
    output = ROOT / output_name
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "condition": args.condition,
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
    }
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    passed_count = sum(check["passed"] for check in checks)
    print(f"{args.condition} control audit: {passed_count}/{len(checks)} checks passed")
    print(f"Wrote: {output}")
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
