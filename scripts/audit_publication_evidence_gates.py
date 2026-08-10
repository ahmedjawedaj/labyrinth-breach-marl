#!/usr/bin/env python3
"""Strict audit for the four hostile-review publication evidence gates."""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "results" / "official_summary" / "evidence_gates"
MINIMUM_AUDIT_CHECKS = 33


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def nonempty(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def safe_name(tag: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", tag.lower()).strip("_")


def run_id_from_matrix(matrix: dict[str, Any], seed: int, stage: dict[str, Any]) -> str:
    return str(matrix["run_id_template"]).format(
        experiment_family=matrix["experiment_family"],
        seed=seed,
        stage_id=stage["id"],
        stage_order=stage.get("order"),
    )


def training_run_complete(run_dir: Path) -> tuple[bool, str]:
    status_path = run_dir / "metadata" / "training_status.json"
    audit_path = run_dir / "metadata" / "training_audit.json"
    metadata_path = run_dir / "metadata" / "run_metadata.json"
    required_logs = [
        run_dir / "logs" / "episode_log.csv",
        run_dir / "logs" / "agent_step_log.csv",
        run_dir / "logs" / "reward_audit.csv",
        run_dir / "logs" / "replay_events.csv",
    ]
    missing = [
        str(path.relative_to(ROOT))
        for path in [status_path, audit_path, metadata_path, *required_logs]
        if not nonempty(path)
    ]
    if missing:
        return False, "missing or empty: " + ", ".join(missing[:4])
    status = load_json(status_path)
    audit = load_json(audit_path)
    if status.get("success") is not True or status.get("exit_code") != 0:
        return False, f"status={status.get('status')} success={status.get('success')} exit={status.get('exit_code')}"
    if int(audit.get("failed", 1)) != 0 or len(audit.get("checks") or []) < MINIMUM_AUDIT_CHECKS:
        return False, f"audit failed={audit.get('failed')} checks={len(audit.get('checks') or [])}"
    return True, "complete"


def audit_training_matrix(matrix_path: Path, results_root: Path) -> dict[str, Any]:
    matrix = load_yaml(matrix_path)
    rows: list[dict[str, Any]] = []
    for seed in [int(seed) for seed in matrix.get("seeds") or []]:
        for stage in matrix.get("stages") or []:
            run_id = run_id_from_matrix(matrix, seed, stage)
            complete, evidence = training_run_complete(results_root / run_id)
            rows.append(
                {
                    "seed": seed,
                    "stage": stage.get("id"),
                    "run_id": run_id,
                    "complete": complete,
                    "evidence": evidence,
                }
            )
    complete_count = sum(row["complete"] for row in rows)
    return {
        "matrix": str(matrix_path.relative_to(ROOT)),
        "experiment_family": matrix.get("experiment_family"),
        "expected_runs": len(rows),
        "complete_runs": complete_count,
        "passed": bool(rows) and complete_count == len(rows),
        "incomplete": [row for row in rows if not row["complete"]],
    }


def audit_official_training() -> dict[str, Any]:
    return audit_training_matrix(
        ROOT / "configs" / "experiment_manifests" / "official_curriculum_matrix.yaml",
        ROOT / "results",
    )


def audit_learning_curves() -> dict[str, Any]:
    output_dir = ROOT / "results" / "official_summary" / "training_curves"
    manifest_path = output_dir / "training_curve_manifest.json"
    raw_csv = output_dir / "official_training_curves_raw.csv"
    summary_csv = output_dir / "official_training_curves_summary.csv"
    if not nonempty(manifest_path):
        return {"passed": False, "evidence": f"missing {manifest_path.relative_to(ROOT)}"}
    manifest = load_json(manifest_path)
    matrix = load_yaml(ROOT / "configs" / "experiment_manifests" / "official_curriculum_matrix.yaml")
    expected_seeds = [int(seed) for seed in matrix.get("seeds") or []]
    missing_files = [
        str(path.relative_to(ROOT))
        for path in [raw_csv, summary_csv]
        if not nonempty(path)
    ]
    tags = [str(tag) for tag in manifest.get("tags") or []]
    for tag in tags:
        stem = output_dir / f"training_curve_{safe_name(tag)}"
        for suffix in (".pdf", ".png"):
            path = stem.with_suffix(suffix)
            if not nonempty(path):
                missing_files.append(str(path.relative_to(ROOT)))
    passed = (
        manifest.get("include_running") is False
        and manifest.get("policy_seeds_observed") == expected_seeds
        and not manifest.get("missing_or_incomplete")
        and int(manifest.get("raw_row_count", 0)) > 0
        and int(manifest.get("summary_row_count", 0)) > 0
        and not missing_files
    )
    return {
        "passed": passed,
        "manifest": str(manifest_path.relative_to(ROOT)),
        "policy_seeds_observed": manifest.get("policy_seeds_observed"),
        "raw_row_count": manifest.get("raw_row_count"),
        "summary_row_count": manifest.get("summary_row_count"),
        "missing_or_incomplete": manifest.get("missing_or_incomplete"),
        "missing_files": missing_files,
    }


def audit_canonical_evaluation() -> dict[str, Any]:
    audit_path = ROOT / "results" / "publication_eval_official" / "aggregate" / "publication_eval_audit.json"
    summary_csv = ROOT / "results" / "publication_eval_official" / "aggregate" / "publication_eval_summary.csv"
    summary_json = ROOT / "results" / "publication_eval_official" / "aggregate" / "publication_eval_summary.json"
    if not nonempty(audit_path):
        return {"passed": False, "evidence": f"missing {audit_path.relative_to(ROOT)}"}
    audit = load_json(audit_path)
    runs = audit.get("runs") or []
    passed = (
        audit.get("valid") is True
        and int(audit.get("expected_matrix_rows", 0)) == 30
        and int(audit.get("observed_matrix_rows", -1)) == 30
        and int(audit.get("episode_target_per_cell", 0)) == 100
        and not audit.get("problems")
        and len(runs) == 30
        and all(run.get("valid") is True and int(run.get("completed_episodes", 0)) >= 100 for run in runs)
        and nonempty(summary_csv)
        and nonempty(summary_json)
    )
    return {
        "passed": passed,
        "audit": str(audit_path.relative_to(ROOT)),
        "observed_matrix_rows": audit.get("observed_matrix_rows"),
        "expected_matrix_rows": audit.get("expected_matrix_rows"),
        "episode_target_per_cell": audit.get("episode_target_per_cell"),
        "problem_count": len(audit.get("problems") or []),
        "run_count": len(runs),
    }


def audit_ablation_condition(condition: dict[str, Any], suite: dict[str, Any]) -> dict[str, Any]:
    condition_id = str(condition["id"])
    expected_cells = len(suite.get("seeds") or []) * len(suite.get("evaluation_topologies") or [])
    effects_path = ROOT / "results" / "official_summary" / "ablations" / condition_id / "paired_effects.json"
    eval_audit_path = ROOT / "results" / "ablations" / condition_id / "aggregate" / "publication_eval_audit.json"
    result: dict[str, Any] = {
        "id": condition_id,
        "type": condition.get("type"),
        "expected_cells": expected_cells,
        "paired_effects": str(effects_path.relative_to(ROOT)),
        "evaluation_audit": str(eval_audit_path.relative_to(ROOT)),
    }
    if condition.get("training_matrix"):
        result["training"] = audit_training_matrix(ROOT / str(condition["training_matrix"]), ROOT / "results")
    if nonempty(eval_audit_path):
        eval_audit = load_json(eval_audit_path)
        result["evaluation_valid"] = (
            eval_audit.get("valid") is True
            and int(eval_audit.get("observed_matrix_rows", -1)) == expected_cells
            and not eval_audit.get("problems")
        )
        result["evaluation_rows"] = eval_audit.get("observed_matrix_rows")
        result["evaluation_problem_count"] = len(eval_audit.get("problems") or [])
    else:
        result["evaluation_valid"] = False
        result["evaluation_rows"] = 0
        result["evaluation_problem_count"] = None
    if nonempty(effects_path):
        effects = load_json(effects_path)
        result["matched_cell_count"] = effects.get("matched_cell_count")
        result["effect_count"] = len(effects.get("effects") or [])
        result["effects_valid"] = (
            int(effects.get("matched_cell_count", 0)) == expected_cells
            and len(effects.get("effects") or []) > 0
        )
    else:
        result["matched_cell_count"] = 0
        result["effect_count"] = 0
        result["effects_valid"] = False
    result["passed"] = (
        result.get("effects_valid") is True
        and result.get("evaluation_valid") is True
        and (not result.get("training") or result["training"]["passed"] is True)
    )
    return result


def audit_ablation_studies() -> dict[str, Any]:
    suite = load_yaml(ROOT / "configs" / "experiment_manifests" / "official_ablation_suite.yaml")
    conditions = [audit_ablation_condition(condition, suite) for condition in suite.get("conditions") or []]
    complete = sum(condition["passed"] for condition in conditions)
    return {
        "passed": bool(conditions) and complete == len(conditions),
        "suite": "configs/experiment_manifests/official_ablation_suite.yaml",
        "complete_conditions": complete,
        "expected_conditions": len(conditions),
        "conditions": conditions,
    }


def audit_readiness_artifacts() -> dict[str, Any]:
    readiness_path = ROOT / "results" / "official_summary" / "publication_readiness.json"
    if not nonempty(readiness_path):
        return {"passed": False, "evidence": f"missing {readiness_path.relative_to(ROOT)}"}
    readiness = load_json(readiness_path)
    required_passed = readiness.get("required_passed_gates")
    total_required = readiness.get("total_required_gates")
    return {
        "passed": readiness.get("status") == "READY_FOR_SUBMISSION_REVIEW" and required_passed == total_required,
        "status": readiness.get("status"),
        "required_passed_gates": required_passed,
        "total_required_gates": total_required,
        "registered_extension_gate_ids": readiness.get("registered_extension_gate_ids") or [],
        "source": str(readiness_path.relative_to(ROOT)),
    }


def write_csv_rows(path: Path, gate_rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["gate", "passed", "evidence"])
        writer.writeheader()
        writer.writerows(gate_rows)


def build_report() -> dict[str, Any]:
    gate_payloads = {
        "official_training_matrix": audit_official_training(),
        "audited_five_seed_learning_curves": audit_learning_curves(),
        "canonical_30_cell_evaluation": audit_canonical_evaluation(),
        "five_paired_ablation_studies": audit_ablation_studies(),
        "final_readiness_verification": audit_readiness_artifacts(),
    }
    gate_rows: list[dict[str, Any]] = []
    for gate_id, payload in gate_payloads.items():
        gate_rows.append(
            {
                "gate": gate_id,
                "passed": bool(payload.get("passed")),
                "evidence": summarize_gate(gate_id, payload),
            }
        )
    all_passed = all(row["passed"] for row in gate_rows)
    return {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "COMPLETE" if all_passed else "INCOMPLETE",
        "passed_gates": sum(row["passed"] for row in gate_rows),
        "total_gates": len(gate_rows),
        "gates": gate_rows,
        "details": gate_payloads,
    }


def summarize_gate(gate_id: str, payload: dict[str, Any]) -> str:
    if gate_id == "official_training_matrix":
        return f"{payload.get('complete_runs')}/{payload.get('expected_runs')} audited official training runs complete"
    if gate_id == "audited_five_seed_learning_curves":
        return (
            f"seeds={payload.get('policy_seeds_observed')} raw_rows={payload.get('raw_row_count')} "
            f"missing_files={len(payload.get('missing_files') or [])}"
        )
    if gate_id == "canonical_30_cell_evaluation":
        return (
            f"rows={payload.get('observed_matrix_rows')}/{payload.get('expected_matrix_rows')} "
            f"target_episodes={payload.get('episode_target_per_cell')} problems={payload.get('problem_count')}"
        )
    if gate_id == "five_paired_ablation_studies":
        return f"{payload.get('complete_conditions')}/{payload.get('expected_conditions')} paired ablation studies complete"
    if gate_id == "final_readiness_verification":
        return (
            f"submission_readiness={payload.get('status')} "
            f"required={payload.get('required_passed_gates')}/{payload.get('total_required_gates')} "
            f"extensions={payload.get('registered_extension_gate_ids')}"
        )
    return json.dumps(payload, sort_keys=True)


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Publication Evidence Gates",
        "",
        f"Status: **{report['status']}**",
        f"Gates passed: **{report['passed_gates']}/{report['total_gates']}**",
        "",
        "| Gate | Passed | Evidence |",
        "|---|---:|---|",
    ]
    for gate in report["gates"]:
        lines.append(f"| {gate['gate']} | {gate['passed']} | {gate['evidence']} |")
    lines.extend(["", "## Blocking Next Actions", ""])
    for gate in report["gates"]:
        if gate["passed"]:
            continue
        lines.append(f"- `{gate['gate']}`: {gate['evidence']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    report = build_report()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "publication_evidence_gates.json"
    md_path = args.output_dir / "publication_evidence_gates.md"
    csv_path = args.output_dir / "publication_evidence_gates.csv"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(md_path, report)
    write_csv_rows(csv_path, report["gates"])
    print(f"Publication evidence gates: {report['passed_gates']}/{report['total_gates']} passed")
    print(f"Status: {report['status']}")
    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")
    print(f"Wrote: {csv_path}")
    return 0 if report["status"] == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
