#!/usr/bin/env python3
"""Verify that seen and held-out evaluation configs differ only by topology identity."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import yaml


HELD_OUT_CONFIGS = {
    101: "maze_unseen_eval_config_no_assist.yaml",
    202: "maze_unseen_eval_seed202_no_assist.yaml",
    303: "maze_unseen_eval_seed303_no_assist.yaml",
    404: "maze_unseen_eval_seed404_no_assist.yaml",
    505: "maze_unseen_eval_seed505_no_assist.yaml",
}


def load(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def controlled_fields(config: dict) -> dict:
    cleaned = copy.deepcopy(config)
    cleaned.pop("config_id", None)
    cleaned.pop("maze", None)
    randomization = cleaned.get("randomization") or {}
    randomization.pop("seed", None)
    randomization.pop("maze_seed", None)
    return cleaned


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="results/official_summary/evaluation_control_audit.json")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config_dir = root / "configs/env_configs"
    seen = load(config_dir / "maze_dynamic_config_no_assist.yaml")
    seen_controls = controlled_fields(seen)
    checks: list[dict] = []

    def check(name: str, passed: bool, evidence: str) -> None:
        checks.append({"check": name, "status": "PASS" if passed else "FAIL", "evidence": evidence})

    signatures: set[str] = set()
    for seed, filename in HELD_OUT_CONFIGS.items():
        held_out = load(config_dir / filename)
        maze = held_out.get("maze") or {}
        randomization = held_out.get("randomization") or {}
        check(
            f"Matched non-topology controls for seed {seed}",
            controlled_fields(held_out) == seen_controls,
            filename,
        )
        check(
            f"Held-out topology routing for seed {seed}",
            maze.get("layout_split") == "unseen"
            and maze.get("use_unseen_layout") is True
            and int(randomization.get("seed", -1)) == seed
            and int(randomization.get("maze_seed", -1)) == seed,
            f"maze={maze}, randomization_seed={randomization.get('seed')}, maze_seed={randomization.get('maze_seed')}",
        )

    passed = sum(item["status"] == "PASS" for item in checks)
    payload = {
        "schema_version": 1,
        "seen_control": "configs/env_configs/maze_dynamic_config_no_assist.yaml",
        "held_out_configs": {str(seed): f"configs/env_configs/{name}" for seed, name in HELD_OUT_CONFIGS.items()},
        "allowed_differences": ["config_id", "maze", "randomization.seed", "randomization.maze_seed"],
        "passed": passed,
        "failed": len(checks) - passed,
        "checks": checks,
    }
    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Evaluation control audit: {passed}/{len(checks)} checks passed")
    print(f"Wrote: {output}")
    return 0 if passed == len(checks) else 2


if __name__ == "__main__":
    raise SystemExit(main())
