#!/usr/bin/env python3
"""Create a machine-readable publication readiness report without hiding blockers."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = ROOT / "results" / "official_summary" / "publication_readiness.json"
OUTPUT_MD = ROOT / "results" / "official_summary" / "publication_readiness.md"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def audit_passed(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, f"missing {path.relative_to(ROOT)}"
    data = load_json(path)
    if "failed" in data:
        passed = int(data.get("failed", 1)) == 0
        return passed, f"{data.get('passed', 0)} passed, {data.get('failed', 0)} failed"
    passed = data.get("passed") is True
    checks = data.get("checks") or []
    return passed, f"{sum(item.get('passed') is True for item in checks)}/{len(checks)} checks passed"


def pdf_pages(path: Path) -> int:
    if not path.is_file():
        return 0
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo is None:
        for candidate in (Path("/opt/anaconda3/bin/pdfinfo"), Path("/opt/homebrew/bin/pdfinfo")):
            if candidate.is_file():
                pdfinfo = str(candidate)
                break
    if pdfinfo is None:
        return 0
    result = subprocess.run([pdfinfo, str(path)], capture_output=True, text=True, check=False)
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    return 0


def expected_training_runs() -> tuple[int, int]:
    matrix = load_yaml(ROOT / "configs/experiment_manifests/official_curriculum_matrix.yaml")
    expected = 0
    completed = 0
    for seed in matrix["seeds"]:
        for stage in matrix["stages"]:
            expected += 1
            run_id = matrix["run_id_template"].format(
                experiment_family=matrix["experiment_family"],
                seed=seed,
                stage_id=stage["id"],
                stage_order=stage["order"],
            )
            status_path = ROOT / "results" / run_id / "metadata" / "training_status.json"
            audit_path = ROOT / "results" / run_id / "metadata" / "training_audit.json"
            if not status_path.is_file() or not audit_path.is_file():
                continue
            status = load_json(status_path)
            audit = load_json(audit_path)
            if (
                status.get("success") is True
                and int(audit.get("failed", 1)) == 0
                and len(audit.get("checks") or []) >= 33
            ):
                completed += 1
    return completed, expected


def add_gate(gates: list[dict], gate_id: str, passed: bool, evidence: str, blocking: bool = True) -> None:
    gates.append(
        {
            "id": gate_id,
            "status": "PASS" if passed else "BLOCKED",
            "blocking": blocking,
            "evidence": evidence,
        }
    )


def main() -> int:
    gates: list[dict] = []
    for gate_id, relative in [
        ("implementation_audit", "results/official_summary/pretraining_implementation_audit.json"),
        ("training_budget_audit", "results/official_summary/training_budget_audit.json"),
        ("evaluation_control_audit", "results/official_summary/evaluation_control_audit.json"),
        ("reward_control_audit", "results/official_summary/reward_ablation_audit.json"),
        ("memory_control_audit", "results/official_summary/memory_off_control_audit.json"),
        ("assist_control_audit", "results/official_summary/action_assist_on_control_audit.json"),
        ("wall_control_audit", "results/official_summary/dynamic_wall_off_control_audit.json"),
    ]:
        passed, evidence = audit_passed(ROOT / relative)
        add_gate(gates, gate_id, passed, evidence)

    paper_path = ROOT / "output/pdf/labyrinth_breach_journal.pdf"
    pages = pdf_pages(paper_path)
    add_gate(gates, "journal_manuscript", pages >= 10, f"{pages} rendered IEEE pages")

    literature = (ROOT / "docs/literature_review_2020_2026.md").read_text(encoding="utf-8")
    full_reviews = sum(
        line.startswith("|") and "(**full review**" in line
        for line in literature.splitlines()
    )
    add_gate(gates, "recent_literature", full_reviews >= 13, f"{full_reviews} full primary-paper reviews")

    suite = load_yaml(ROOT / "configs/experiment_manifests/official_ablation_suite.yaml")
    condition_count = len(suite.get("conditions") or [])
    hypothesis_count = sum(
        len(condition.get("directional_hypotheses") or [])
        for condition in suite.get("conditions") or []
    )
    conditions_with_hypotheses = sum(
        bool(condition.get("directional_hypotheses"))
        for condition in suite.get("conditions") or []
    )
    ablation_protocol_ready = (
        condition_count == 5
        and conditions_with_hypotheses == condition_count
        and suite.get("effect_convention") == "canonical_full_minus_condition"
    )
    add_gate(
        gates,
        "ablation_protocol",
        ablation_protocol_ready,
        f"{condition_count}/5 conditions and {hypothesis_count} directional hypotheses registered",
    )

    metric_script = (ROOT / "scripts/summarize_eval_kpis.py").read_text(encoding="utf-8")
    statistics_script = (ROOT / "scripts/analyze_publication_statistics.py").read_text(encoding="utf-8")
    metric_protocol_ready = all(
        token in metric_script
        for token in [
            'PROTOCOL_VERSION = "evaluation_protocol.md@v2"',
            "path_by_agent_episode",
            "summarize_route_changes",
            "summarize_target_reacquisition",
            "mean_team_spread",
        ]
    ) and all(
        token in statistics_script
        for token in ["bootstrap_policy_generalization_gap", "seed_layout_variance_components"]
    )
    add_gate(
        gates,
        "metric_protocol_v2",
        metric_protocol_ready,
        "episode-keyed paths, survival, reacquisition, spatial/route response, gaps, and variance",
    )

    power_path = ROOT / "results/official_summary/power_analysis/minimum_detectable_effects.json"
    power_ready = False
    power_evidence = f"missing {power_path.relative_to(ROOT)}"
    if power_path.is_file():
        power_rows = load_json(power_path).get("rows") or []
        observed_sizes = [int(row.get("paired_policy_seeds", 0)) for row in power_rows]
        power_ready = observed_sizes == [3, 5, 10] and all(
            float(row.get("minimum_detectable_abs_dz", 0.0)) > 0.0 for row in power_rows
        )
        power_evidence = ", ".join(
            f"n={row['paired_policy_seeds']}: |dz|={row['minimum_detectable_abs_dz']:.3f}"
            for row in power_rows
        )
    add_gate(gates, "statistical_power_audit", power_ready, power_evidence)

    completed, expected = expected_training_runs()
    add_gate(gates, "official_training", completed == expected, f"{completed}/{expected} audited runs complete")

    curriculum_matrix = load_yaml(
        ROOT / "configs/experiment_manifests/official_curriculum_matrix.yaml"
    )
    expected_policy_seeds = [int(seed) for seed in curriculum_matrix.get("seeds") or []]
    curve_manifest_path = ROOT / "results/official_summary/training_curves/training_curve_manifest.json"
    curve_ready = False
    curve_evidence = f"missing {curve_manifest_path.relative_to(ROOT)}"
    if curve_manifest_path.is_file():
        curve_manifest = load_json(curve_manifest_path)
        curve_ready = (
            curve_manifest.get("include_running") is False
            and curve_manifest.get("policy_seeds_observed") == expected_policy_seeds
            and not curve_manifest.get("missing_or_incomplete")
            and int(curve_manifest.get("raw_row_count", 0)) > 0
        )
        curve_evidence = (
            f"seeds={curve_manifest.get('policy_seeds_observed')}, "
            f"raw_rows={curve_manifest.get('raw_row_count', 0)}, "
            f"diagnostic_mode={curve_manifest.get('include_running')}"
        )
    add_gate(gates, "official_training_curves", curve_ready, curve_evidence)

    official_eval_audit = ROOT / "results/publication_eval_official/aggregate/publication_eval_audit.json"
    passed, evidence = audit_passed(official_eval_audit)
    add_gate(gates, "official_evaluation", passed, evidence)

    completed_ablation_analyses = 0
    for condition in suite.get("conditions") or []:
        effects = ROOT / "results/official_summary/ablations" / condition["id"] / "paired_effects.json"
        if effects.is_file() and load_json(effects).get("matched_cell_count", 0) > 0:
            completed_ablation_analyses += 1
    add_gate(
        gates,
        "ablation_results",
        completed_ablation_analyses == condition_count,
        f"{completed_ablation_analyses}/{condition_count} paired analyses complete",
    )

    blocking = [gate for gate in gates if gate["blocking"] and gate["status"] != "PASS"]
    payload = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "READY_FOR_SUBMISSION_REVIEW" if not blocking else "BLOCKED",
        "passed_gates": sum(gate["status"] == "PASS" for gate in gates),
        "total_gates": len(gates),
        "gates": gates,
        "blocking_gate_ids": [gate["id"] for gate in blocking],
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Publication Readiness",
        "",
        f"Status: **{payload['status']}**",
        "",
        "| Gate | Status | Evidence |",
        "|---|---|---|",
    ]
    lines.extend(f"| {gate['id']} | {gate['status']} | {gate['evidence']} |" for gate in gates)
    if blocking:
        lines.extend(["", "## Blocking Gates", ""])
        lines.extend(f"- `{gate['id']}`: {gate['evidence']}" for gate in blocking)
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Publication readiness: {payload['passed_gates']}/{payload['total_gates']} gates passed")
    print(f"Status: {payload['status']}")
    print(f"Wrote: {OUTPUT_JSON}")
    print(f"Wrote: {OUTPUT_MD}")
    return 0 if not blocking else 2


if __name__ == "__main__":
    raise SystemExit(main())
