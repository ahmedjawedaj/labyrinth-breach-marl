#!/usr/bin/env python3
"""Validate equal-sample self-play and matched curriculum/ablation budgets."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_MATRIX = ROOT / "configs/experiment_manifests/official_curriculum_matrix.yaml"
DIRECT_MANIFEST = ROOT / "configs/experiment_manifests/exp_direct_dynamic_matched.yaml"
OUTPUT_JSON = ROOT / "results/official_summary/training_budget_audit.json"
OUTPUT_CSV = ROOT / "results/official_summary/training_budget_audit.csv"
TEAM_SIZE = {"Sentinel": 3, "Runner": 2}
SELF_PLAY_EXPECTED = {
    "save_steps": 20000,
    "team_change": 100000,
    "swap_steps": 2000,
    "window": 10,
    "play_against_latest_model_ratio": 0.5,
    "initial_elo": 1200.0,
}


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def manifest_budgets(manifest_path: Path) -> dict[str, int]:
    manifest = load_yaml(manifest_path)
    trainer = load_yaml(ROOT / manifest["trainer_config"])
    return {role: int(trainer["behaviors"][role]["max_steps"]) for role in TEAM_SIZE}


def add(checks: list[dict], name: str, passed: bool, evidence: str) -> None:
    checks.append({"check": name, "status": "PASS" if passed else "FAIL", "evidence": evidence})


def main() -> int:
    matrix = load_yaml(OFFICIAL_MATRIX)
    checks: list[dict] = []
    stage_budgets: list[dict[str, int]] = []

    for stage in matrix["stages"]:
        budgets = manifest_budgets(ROOT / stage["manifest"])
        stage_budgets.append(budgets)
        add(
            checks,
            f"{stage['id']} self-play samples synchronize",
            budgets["Sentinel"] == budgets["Runner"],
            f"Sentinel={budgets['Sentinel']} samples, Runner={budgets['Runner']} samples",
        )

    curriculum_totals = {
        role: sum(stage[role] for stage in stage_budgets)
        for role in TEAM_SIZE
    }
    add(
        checks,
        "curriculum self-play totals synchronize",
        curriculum_totals["Sentinel"] == curriculum_totals["Runner"],
        f"sample totals={curriculum_totals}",
    )

    direct_budgets = manifest_budgets(DIRECT_MANIFEST)
    for role in TEAM_SIZE:
        add(
            checks,
            f"direct dynamic matches {role} curriculum samples",
            direct_budgets[role] == curriculum_totals[role],
            f"expected={curriculum_totals[role]}, actual={direct_budgets[role]}",
        )
    add(
        checks,
        "direct dynamic self-play samples synchronize",
        direct_budgets["Sentinel"] == direct_budgets["Runner"],
        f"sample budgets={direct_budgets}",
    )

    trainer_paths = {
        "static curriculum": ROOT / "configs/trainer_configs/ppo_staticmaze_3v2.yaml",
        "dynamic curriculum": ROOT / "configs/trainer_configs/ppo_dynamicmaze_3v2.yaml",
        "direct dynamic": ROOT / "configs/trainer_configs/ppo_direct_dynamic_matched_3v2.yaml",
    }
    for label, trainer_path in trainer_paths.items():
        trainer = load_yaml(trainer_path)
        role_settings = {
            role: (trainer.get("behaviors", {}).get(role, {}).get("self_play") or {})
            for role in TEAM_SIZE
        }
        add(
            checks,
            f"{label} asymmetric self-play synchronized",
            all(settings == SELF_PLAY_EXPECTED for settings in role_settings.values()),
            f"roles={role_settings}",
        )

    passed = sum(item["status"] == "PASS" for item in checks)
    payload = {
        "schema_version": 1,
        "team_sizes": TEAM_SIZE,
        "curriculum_totals": curriculum_totals,
        "direct_dynamic_budgets": direct_budgets,
        "self_play_expected": SELF_PLAY_EXPECTED,
        "passed": passed,
        "failed": len(checks) - passed,
        "checks": checks,
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("check", "status", "evidence"))
        writer.writeheader()
        writer.writerows(checks)
    print(f"Training budget audit: {passed}/{len(checks)} checks passed")
    print(f"Curriculum samples: {curriculum_totals}; direct dynamic: {direct_budgets}")
    return 0 if passed == len(checks) else 2


if __name__ == "__main__":
    raise SystemExit(main())
