#!/usr/bin/env python3
"""Build a concise publication evidence snapshot for submission review."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "results" / "official_summary"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def pct(value: float) -> str:
    return f"{100.0 * value:.1f}%"


def mean(rows: list[dict[str, str]], key: str) -> float:
    values = [float(row[key]) for row in rows]
    return sum(values) / len(values) if values else 0.0


def summarize_baselines(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    summary = []
    for policy in sorted({row["baseline_policy"] for row in rows}):
        for group in ("seen", "unseen"):
            subset = [
                row
                for row in rows
                if row["baseline_policy"] == policy and row["group"] == group
            ]
            if not subset:
                continue
            summary.append(
                {
                    "controller": policy,
                    "group": group,
                    "cells": len(subset),
                    "episodes": sum(int(float(row["episodes"])) for row in subset),
                    "sentinel_win_rate_mean": mean(subset, "sentinel_win_rate"),
                    "escape_rate_mean": mean(subset, "escape_rate"),
                    "full_capture_seconds_mean": mean(
                        subset,
                        "mean_time_to_full_capture_seconds",
                    ),
                    "pincer_episode_rate_mean": mean(subset, "pincer_episode_rate"),
                }
            )
    return summary


def effect_lookup(path: Path, group: str, metric: str) -> dict[str, float | int | str]:
    data = read_json(path)
    for row in data.get("effects") or []:
        if row.get("group") == group and row.get("metric") == metric:
            return {
                "ablation_id": data.get("ablation_id", path.parent.name),
                "group": group,
                "metric": metric,
                "matched_cells": int(row.get("matched_cells", 0)),
                "delta": float(row.get("mean_full_minus_ablated", 0.0)),
                "paired_effect_dz": float(row.get("paired_effect_dz", 0.0)),
                "bootstrap_low": float(row.get("hierarchical_bootstrap_low", 0.0)),
                "bootstrap_high": float(row.get("hierarchical_bootstrap_high", 0.0)),
            }
    raise KeyError(f"Missing effect {metric} for {group} in {path}")


def main() -> int:
    readiness = read_json(OUTPUT_DIR / "publication_readiness.json")
    official_eval = read_json(
        ROOT / "results" / "publication_eval_official" / "aggregate" / "publication_eval_audit.json"
    )
    baseline_rows = read_csv(
        ROOT / "results" / "lightweight_baselines" / "aggregate" / "baseline_eval_summary.csv"
    )
    action_effects = OUTPUT_DIR / "ablations" / "action_assist_on" / "paired_effects.json"
    wall_effects = OUTPUT_DIR / "ablations" / "dynamic_wall_off" / "paired_effects.json"

    key_effects = [
        effect_lookup(action_effects, "unseen", "sentinel_win"),
        effect_lookup(action_effects, "unseen", "escape"),
        effect_lookup(action_effects, "unseen", "sentinel_spread_meters"),
        effect_lookup(wall_effects, "unseen", "sentinel_win"),
        effect_lookup(wall_effects, "unseen", "pincer_episode_rate"),
        effect_lookup(wall_effects, "unseen", "exit_denial_episode_rate"),
        effect_lookup(wall_effects, "unseen", "trap_episode_rate"),
        effect_lookup(wall_effects, "unseen", "stall_step_fraction"),
    ]

    payload = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "readiness_status": readiness["status"],
        "passed_gates": readiness["passed_gates"],
        "total_gates": readiness["total_gates"],
        "required_passed_gates": readiness.get("required_passed_gates", readiness["passed_gates"]),
        "total_required_gates": readiness.get("total_required_gates", readiness["total_gates"]),
        "registered_extension_count": readiness.get("registered_extension_count", 0),
        "pending_evidence_gate_ids": readiness.get("pending_evidence_gate_ids", readiness.get("blocking_gate_ids", [])),
        "registered_extension_gate_ids": readiness.get("registered_extension_gate_ids", []),
        "official_evaluation": official_eval["group_summary"],
        "lightweight_baselines": summarize_baselines(baseline_rows),
        "completed_ablation_effects": key_effects,
        "submission_polish_without_retraining": [
            "tighten claims and threat framing",
            "strengthen literature synthesis",
            "keep random and heuristic controls as diagnostic only",
            "maintain script-to-table traceability",
        ],
        "registered_retraining_extensions": [
            "memory off paired retraining",
            "tactical reward off paired retraining",
            "direct dynamic training paired retraining",
        ],
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / "current_evidence_snapshot.json"
    csv_path = OUTPUT_DIR / "current_evidence_snapshot.csv"
    md_path = OUTPUT_DIR / "current_evidence_snapshot.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    csv_rows = []
    for group, values in payload["official_evaluation"].items():
        csv_rows.append(
            {
                "section": "official_evaluation",
                "item": group,
                "cells": "",
                "episodes": values["episodes"],
                "sentinel_win_rate": values["sentinel_win_rate"],
                "escape_rate": values["escape_rate"],
                "detail": "canonical assist-off",
            }
        )
    for row in payload["lightweight_baselines"]:
        csv_rows.append(
            {
                "section": "lightweight_baseline",
                "item": f"{row['controller']}_{row['group']}",
                "cells": row["cells"],
                "episodes": row["episodes"],
                "sentinel_win_rate": row["sentinel_win_rate_mean"],
                "escape_rate": row["escape_rate_mean"],
                "detail": "evaluation-only action override",
            }
        )

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "section",
                "item",
                "cells",
                "episodes",
                "sentinel_win_rate",
                "escape_rate",
                "detail",
            ],
        )
        writer.writeheader()
        writer.writerows(csv_rows)

    lines = [
        "# Current Evidence Snapshot",
        "",
        f"Generated UTC: `{payload['generated_utc']}`",
        "",
        f"Readiness: **{payload['readiness_status']}**",
        f"Required checks: **{payload['required_passed_gates']}/{payload['total_required_gates']}**",
        f"All tracked checks: **{payload['passed_gates']}/{payload['total_gates']}**",
        f"Required evidence gates: `{', '.join(payload['pending_evidence_gate_ids']) or 'none'}`",
        f"Registered extension gates: `{', '.join(payload['registered_extension_gate_ids']) or 'none'}`",
        "",
        "## Canonical Evaluation",
        "",
        "| Split | Episodes | Sentinel win | Escape |",
        "| --- | ---: | ---: | ---: |",
    ]
    for group, values in payload["official_evaluation"].items():
        lines.append(
            f"| {group} | {values['episodes']} | {pct(values['sentinel_win_rate'])} | {pct(values['escape_rate'])} |"
        )

    lines.extend(
        [
            "",
            "## Lightweight Baselines",
            "",
            "| Controller | Split | Cells | Episodes | Sentinel win | Escape | Full capture | Pincer |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in payload["lightweight_baselines"]:
        lines.append(
            "| "
            f"{row['controller']} | {row['group']} | {row['cells']} | {row['episodes']} | "
            f"{pct(row['sentinel_win_rate_mean'])} | {pct(row['escape_rate_mean'])} | "
            f"{row['full_capture_seconds_mean']:.2f} s | {pct(row['pincer_episode_rate_mean'])} |"
        )

    lines.extend(
        [
            "",
            "## Completed Ablations",
            "",
            "| Ablation | Split | Metric | Matched cells | Delta | dz | Bootstrap interval |",
            "| --- | --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in key_effects:
        lines.append(
            "| "
            f"{row['ablation_id']} | {row['group']} | {row['metric']} | {row['matched_cells']} | "
            f"{row['delta']:.4f} | {row['paired_effect_dz']:.2f} | "
            f"[{row['bootstrap_low']:.4f}, {row['bootstrap_high']:.4f}] |"
        )

    lines.extend(
        [
            "",
            "## Registered Extensions",
            "",
            "The current submission evidence is limited to the reported canonical evaluation, control policies, and paired deployment interventions.",
            "Memory-off, tactical-reward-off, and direct-dynamic conditions are registered retraining extensions.",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
