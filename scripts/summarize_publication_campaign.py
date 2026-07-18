#!/usr/bin/env python3
"""Summarize strict completion state for the full publication campaign."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]

TRAINING_MATRICES = [
    "configs/experiment_manifests/official_curriculum_matrix.yaml",
    "configs/experiment_manifests/official_memory_off_aligned_matrix.yaml",
    "configs/experiment_manifests/official_tactical_off_aligned_matrix.yaml",
    "configs/experiment_manifests/official_direct_dynamic_matrix.yaml",
]

EVALUATION_MATRICES = [
    (
        "configs/experiment_manifests/official_publication_eval_matrix.yaml",
        "results/publication_eval_official",
    ),
    (
        "configs/experiment_manifests/official_memory_off_eval_matrix.yaml",
        "results/ablations/memory_off",
    ),
    (
        "configs/experiment_manifests/official_tactical_reward_off_eval_matrix.yaml",
        "results/ablations/tactical_reward_off",
    ),
    (
        "configs/experiment_manifests/official_direct_dynamic_training_eval_matrix.yaml",
        "results/ablations/direct_dynamic_training",
    ),
    (
        "configs/experiment_manifests/official_action_assist_on_eval_matrix.yaml",
        "results/ablations/action_assist_on",
    ),
    (
        "configs/experiment_manifests/official_dynamic_wall_off_eval_matrix.yaml",
        "results/ablations/dynamic_wall_off",
    ),
]

TRAINING_REQUIRED_ARTIFACTS = (
    "metadata/run_metadata.json",
    "metadata/training_audit.json",
    "logs/episode_log.csv",
    "logs/agent_step_log.csv",
    "logs/reward_audit.csv",
    "logs/replay_events.csv",
    "Sentinel.onnx",
    "Runner.onnx",
)

EVALUATION_REQUIRED_ARTIFACTS = (
    "metadata/run_metadata.json",
    "metadata/evaluation_metadata.json",
    "logs/episode_log.csv",
    "logs/agent_step_log.csv",
    "logs/reward_audit.csv",
    "logs/replay_events.csv",
    "kpi/eval_kpi_summary.json",
    "kpi/eval_kpi_summary.csv",
)


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def classify_training_status(status: dict, artifacts_valid: bool = True) -> str:
    if (
        status.get("success") is True
        and status.get("exit_code") == 0
        and status.get("status") == "completed"
        and artifacts_valid
    ):
        return "completed"
    if status.get("status") == "running":
        return "running"
    if status:
        return "failed_or_incomplete"
    return "missing"


def classify_evaluation_status(status: dict, target_episodes: int, artifacts_valid: bool = True) -> str:
    if (
        status.get("success") is True
        and int(status.get("completed_episodes") or 0) >= target_episodes
        and int(status.get("target_episodes") or 0) == target_episodes
        and artifacts_valid
    ):
        return "completed"
    if status.get("status") == "running":
        return "running"
    if status:
        return "failed_or_incomplete"
    return "missing"


def missing_or_empty(run_root: Path, relative_paths: tuple[str, ...]) -> list[str]:
    return [
        f"missing_or_empty:{relative_path}"
        for relative_path in relative_paths
        if not (run_root / relative_path).is_file() or (run_root / relative_path).stat().st_size == 0
    ]


def training_artifact_problems(run_root: Path) -> list[str]:
    problems = missing_or_empty(run_root, TRAINING_REQUIRED_ARTIFACTS)
    if (run_root / "INVALIDATED.md").exists() or (run_root / "metadata/INVALIDATED.md").exists():
        problems.append("run_marked_invalidated")
    audit = load_json(run_root / "metadata/training_audit.json")
    if int(audit.get("passed") or 0) < 33 or int(audit.get("failed") or 0) != 0:
        problems.append("training_audit_not_33_of_33")
    return sorted(set(problems))


def evaluation_artifact_problems(run_root: Path, target_episodes: int) -> list[str]:
    problems = missing_or_empty(run_root, EVALUATION_REQUIRED_ARTIFACTS)
    if (run_root / "INVALIDATED.md").exists() or (run_root / "metadata/INVALIDATED.md").exists():
        problems.append("run_marked_invalidated")

    episode_path = run_root / "logs/episode_log.csv"
    if episode_path.is_file():
        try:
            with episode_path.open(encoding="utf-8") as handle:
                completed_rows = max(0, sum(1 for _ in handle) - 1)
        except OSError:
            completed_rows = 0
        if completed_rows < target_episodes:
            problems.append(f"episode_rows_below_target:{completed_rows}/{target_episodes}")

    metadata = load_json(run_root / "metadata/evaluation_metadata.json")
    if metadata.get("source_training_artifacts_immutable") is not True:
        problems.append("immutable_source_flag_missing")
    if metadata.get("inference_workspace_ephemeral") is not True:
        problems.append("ephemeral_workspace_flag_missing")
    checkpoints = metadata.get("checkpoints") or []
    if len(checkpoints) != 2 or any(not item.get("exists") or not item.get("sha256") for item in checkpoints):
        problems.append("checkpoint_hash_provenance_incomplete")
    return sorted(set(problems))


def count_states(records: list[dict]) -> dict[str, int]:
    states = {"completed": 0, "running": 0, "failed_or_incomplete": 0, "missing": 0}
    for record in records:
        states[record["state"]] += 1
    return states


def training_records(root: Path, results_root: Path, matrix_path: str) -> tuple[dict, list[dict]]:
    matrix = load_yaml(root / matrix_path)
    records = []
    for seed in matrix["seeds"]:
        for stage in matrix["stages"]:
            run_id = matrix["run_id_template"].format(
                experiment_family=matrix["experiment_family"],
                seed=int(seed),
                stage_id=stage["id"],
                stage_order=int(stage.get("order", 1)),
            )
            status_path = results_root / run_id / "metadata" / "training_status.json"
            status = load_json(status_path)
            run_root = results_root / run_id
            artifact_problems = training_artifact_problems(run_root) if status else []
            records.append(
                {
                    "seed": int(seed),
                    "stage_id": stage["id"],
                    "run_id": run_id,
                    "state": classify_training_status(status, not artifact_problems),
                    "status_path": str(status_path),
                    "artifact_problems": artifact_problems,
                }
            )
    return matrix, records


def evaluation_records(root: Path, matrix_path: str, output_path: str) -> tuple[dict, list[dict]]:
    matrix = load_yaml(root / matrix_path)
    target = int(matrix["episodes_per_cell"])
    output_root = root / output_path
    records = []
    for seed in matrix["seeds"]:
        for split in matrix["splits"]:
            run_id = f"{matrix['experiment_family']}_policyseed{seed}_{split['id']}_{target}ep"
            status_path = output_root / f"policy_seed_{seed}" / run_id / "metadata" / "evaluation_status.json"
            status = load_json(status_path)
            run_root = output_root / f"policy_seed_{seed}" / run_id
            artifact_problems = evaluation_artifact_problems(run_root, target) if status else []
            records.append(
                {
                    "policy_seed": int(seed),
                    "split_id": split["id"],
                    "run_id": run_id,
                    "state": classify_evaluation_status(status, target, not artifact_problems),
                    "status_path": str(status_path),
                    "artifact_problems": artifact_problems,
                }
            )
    return matrix, records


def build_summary(root: Path, results_root: Path) -> dict:
    training = []
    for matrix_path in TRAINING_MATRICES:
        matrix, records = training_records(root, results_root, matrix_path)
        training.append(
            {
                "experiment_family": matrix["experiment_family"],
                "matrix": matrix_path,
                "counts": count_states(records),
                "total": len(records),
                "records": records,
            }
        )

    evaluations = []
    for matrix_path, output_path in EVALUATION_MATRICES:
        matrix, records = evaluation_records(root, matrix_path, output_path)
        evaluations.append(
            {
                "experiment_family": matrix["experiment_family"],
                "matrix": matrix_path,
                "results_dir": output_path,
                "counts": count_states(records),
                "total": len(records),
                "records": records,
            }
        )

    return {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "training": training,
        "evaluations": evaluations,
        "training_total": sum(item["total"] for item in training),
        "training_completed": sum(item["counts"]["completed"] for item in training),
        "evaluation_total": sum(item["total"] for item in evaluations),
        "evaluation_completed": sum(item["counts"]["completed"] for item in evaluations),
    }


def write_markdown(summary: dict, path: Path) -> None:
    lines = [
        "# Publication Campaign Status",
        "",
        f"Generated: `{summary['generated_utc']}`",
        "",
        f"Training: **{summary['training_completed']}/{summary['training_total']}** strict runs complete.",
        f"Evaluation: **{summary['evaluation_completed']}/{summary['evaluation_total']}** target-complete cells.",
        "",
        "## Training",
        "",
        "| Family | Complete | Running | Failed/incomplete | Missing | Total |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in summary["training"]:
        counts = item["counts"]
        lines.append(
            f"| `{item['experiment_family']}` | {counts['completed']} | {counts['running']} | "
            f"{counts['failed_or_incomplete']} | {counts['missing']} | {item['total']} |"
        )
    lines.extend(
        [
            "",
            "## Evaluation",
            "",
            "| Family | Complete | Running | Failed/incomplete | Missing | Total |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for item in summary["evaluations"]:
        counts = item["counts"]
        lines.append(
            f"| `{item['experiment_family']}` | {counts['completed']} | {counts['running']} | "
            f"{counts['failed_or_incomplete']} | {counts['missing']} | {item['total']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", default="results")
    parser.add_argument("--output-dir", default="results/orchestration")
    args = parser.parse_args()

    results_root = Path(args.results_root)
    if not results_root.is_absolute():
        results_root = ROOT / results_root
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = build_summary(ROOT, results_root)
    json_path = output_dir / "publication_campaign_status.json"
    markdown_path = output_dir / "publication_campaign_status.md"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(summary, markdown_path)
    print(
        f"Training {summary['training_completed']}/{summary['training_total']}; "
        f"evaluation {summary['evaluation_completed']}/{summary['evaluation_total']}"
    )
    print(f"Wrote: {json_path}")
    print(f"Wrote: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
