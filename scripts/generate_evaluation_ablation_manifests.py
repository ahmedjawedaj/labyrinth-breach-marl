#!/usr/bin/env python3
"""Generate matched evaluation-only ablation configs and matrix manifests."""

from __future__ import annotations

import copy
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs" / "env_configs"
MANIFEST_DIR = ROOT / "configs" / "experiment_manifests"

SPLITS = [
    ("seen_seed42", "seen", "maze_dynamic_config.yaml", "exp_seen_eval_seed42.yaml"),
    ("unseen_seed101", "unseen", "maze_unseen_eval_config.yaml", "exp_unseen_eval_seed101.yaml"),
    ("unseen_seed202", "unseen", "maze_unseen_eval_seed202.yaml", "exp_unseen_eval_seed202.yaml"),
    ("unseen_seed303", "unseen", "maze_unseen_eval_seed303.yaml", "exp_unseen_eval_seed303.yaml"),
    ("unseen_seed404", "unseen", "maze_unseen_eval_seed404.yaml", "exp_unseen_eval_seed404.yaml"),
    ("unseen_seed505", "unseen", "maze_unseen_eval_seed505.yaml", "exp_unseen_eval_seed505.yaml"),
]


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping in {path}")
    return data


def write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    print(path.relative_to(ROOT))


def config_output_name(base_name: str, condition: str) -> str:
    stem = Path(base_name).stem
    suffix = {
        "action_assist_off": "no_assist",
        "dynamic_wall_off": "wall_off",
        "memory_off": "memory_off",
    }[condition]
    return f"{stem}_{suffix}.yaml"


def transform_config(base: dict, condition: str) -> dict:
    transformed = copy.deepcopy(base)
    transformed["config_id"] = f"{base['config_id']}_{condition}_v1"
    if condition == "action_assist_off":
        transformed["action_assist"]["sentinel_pursuit_strength"] = 0.0
        transformed["action_assist"]["runner_evade_strength"] = 0.0
    elif condition == "dynamic_wall_off":
        transformed["dynamic_walls"]["enabled"] = False
    elif condition == "memory_off":
        transformed["observations"]["use_memory"] = False
    else:  # pragma: no cover
        raise ValueError(f"Unknown condition: {condition}")
    return transformed


def generate_condition(condition: str) -> str:
    matrix_splits = []
    for split_id, group, config_name, manifest_name in SPLITS:
        output_config_name = config_output_name(config_name, condition)
        output_manifest_name = f"exp_{condition}_{split_id}.yaml"

        config = transform_config(load_yaml(CONFIG_DIR / config_name), condition)
        write_yaml(CONFIG_DIR / output_config_name, config)

        manifest = copy.deepcopy(load_yaml(MANIFEST_DIR / manifest_name))
        manifest["run_id"] = f"LB_3v2_{condition}_{split_id}_v1"
        manifest["rule_config"] = output_config_name
        manifest["notes"] = (
            f"Matched evaluation-only {condition} intervention; all other rule "
            "parameters are identical to the canonical split."
        )
        write_yaml(MANIFEST_DIR / output_manifest_name, manifest)
        matrix_splits.append(
            {
                "id": split_id,
                "group": group,
                "manifest": f"configs/experiment_manifests/{output_manifest_name}",
            }
        )

    matrix_name = f"official_{condition}_eval_matrix.yaml"
    matrix = {
        "experiment_family": f"LB_3v2_{condition}_eval_v1",
        "training_matrix_manifest": "configs/experiment_manifests/official_curriculum_matrix.yaml",
        "source_stage_id": "stage4",
        "seeds": [42, 101, 202],
        "duration_minutes": 30,
        "episodes_per_cell": 100,
        "deterministic_inference": True,
        "minimum_unseen_layout_count": 5,
        "intervention": condition,
        "splits": matrix_splits,
    }
    write_yaml(MANIFEST_DIR / matrix_name, matrix)
    return f"configs/experiment_manifests/{matrix_name}"


def generate_retrained_evaluation(
    condition: str,
    training_matrix: str,
    source_stage_id: str,
    *,
    reward_config: str | None = None,
    transform_rules: bool = False,
) -> str:
    matrix_splits = []
    for split_id, group, config_name, manifest_name in SPLITS:
        manifest = copy.deepcopy(load_yaml(MANIFEST_DIR / manifest_name))
        if transform_rules:
            output_config_name = config_output_name(config_name, condition)
            write_yaml(CONFIG_DIR / output_config_name, transform_config(load_yaml(CONFIG_DIR / config_name), condition))
            manifest["rule_config"] = output_config_name
        if reward_config:
            manifest["reward_config"] = reward_config
        output_manifest_name = f"exp_{condition}_{split_id}.yaml"
        manifest["run_id"] = f"LB_3v2_{condition}_{split_id}_v1"
        manifest["notes"] = (
            f"Evaluation for the independently retrained {condition} condition "
            "under matched topology and non-ablated controls."
        )
        write_yaml(MANIFEST_DIR / output_manifest_name, manifest)
        matrix_splits.append(
            {
                "id": split_id,
                "group": group,
                "manifest": f"configs/experiment_manifests/{output_manifest_name}",
            }
        )

    matrix_name = f"official_{condition}_eval_matrix.yaml"
    matrix = {
        "experiment_family": f"LB_3v2_{condition}_eval_v1",
        "training_matrix_manifest": training_matrix,
        "source_stage_id": source_stage_id,
        "seeds": [42, 101, 202],
        "duration_minutes": 30,
        "episodes_per_cell": 100,
        "deterministic_inference": True,
        "minimum_unseen_layout_count": 5,
        "splits": matrix_splits,
    }
    if transform_rules:
        matrix["intervention"] = condition
    if condition == "tactical_reward_off":
        matrix["reward_intervention"] = condition
    write_yaml(MANIFEST_DIR / matrix_name, matrix)
    return f"configs/experiment_manifests/{matrix_name}"


def main() -> int:
    assist_matrix = generate_condition("action_assist_off")
    wall_matrix = generate_condition("dynamic_wall_off")
    memory_training = "configs/experiment_manifests/official_memory_off_aligned_matrix.yaml"
    tactical_training = "configs/experiment_manifests/official_tactical_off_aligned_matrix.yaml"
    direct_training = "configs/experiment_manifests/official_direct_dynamic_matrix.yaml"
    memory_eval = generate_retrained_evaluation(
        "memory_off",
        memory_training,
        "stage4",
        transform_rules=True,
    )
    tactical_eval = generate_retrained_evaluation(
        "tactical_reward_off",
        tactical_training,
        "stage4",
        reward_config="reward_v5_tactical_off.yaml",
    )
    direct_eval = generate_retrained_evaluation(
        "direct_dynamic_training",
        direct_training,
        "direct_dynamic",
    )
    suite = {
        "suite_id": "LB_3v2_publication_ablation_suite_v1",
        "seeds": [42, 101, 202],
        "evaluation_topologies": [42, 101, 202, 303, 404, 505],
        "conditions": [
            {
                "id": "memory_off",
                "type": "retrain",
                "training_matrix": memory_training,
                "evaluation_matrix": memory_eval,
            },
            {
                "id": "tactical_reward_off",
                "type": "retrain",
                "training_matrix": tactical_training,
                "evaluation_matrix": tactical_eval,
            },
            {
                "id": "direct_dynamic_training",
                "type": "retrain",
                "training_matrix": direct_training,
                "evaluation_matrix": direct_eval,
            },
            {"id": "action_assist_off", "type": "evaluation_intervention", "evaluation_matrix": assist_matrix},
            {"id": "dynamic_wall_off", "type": "evaluation_intervention", "evaluation_matrix": wall_matrix},
        ],
    }
    write_yaml(MANIFEST_DIR / "official_ablation_suite.yaml", suite)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
