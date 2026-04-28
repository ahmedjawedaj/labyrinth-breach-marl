#!/usr/bin/env python3
"""Build a seen-vs-unseen generalization drop table from metric summaries."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MetricDefinition:
    name: str
    path: tuple[str, ...]
    higher_is_better: bool


CORE_METRICS: tuple[MetricDefinition, ...] = (
    MetricDefinition("sentinel_win_rate", ("win_rate", "sentinel_win_rate"), True),
    MetricDefinition("runner_win_rate", ("win_rate", "runner_win_rate"), True),
    MetricDefinition("exit_success_rate", ("exit_success", "exit_success_rate"), True),
    MetricDefinition("avg_runner_survival_time_seconds", ("survival_time", "avg_runner_survival_time_seconds"), True),
    MetricDefinition("avg_first_capture_time_seconds", ("capture_times", "avg_first_capture_time_seconds"), False),
    MetricDefinition("avg_full_capture_time_seconds", ("capture_times", "avg_full_capture_time_seconds"), False),
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing JSON file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected top-level JSON object in {path}")
    return data


def get_nested(data: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    if current is None:
        return None
    try:
        return float(current)
    except (TypeError, ValueError):
        return None


def _abs_drop(seen: float, unseen: float, higher_is_better: bool) -> float:
    # Positive drop means unseen is worse.
    if higher_is_better:
        return seen - unseen
    return unseen - seen


def _pct_drop(abs_drop: float, seen: float) -> float | None:
    if abs(seen) < 1e-12:
        return None
    return (abs_drop / abs(seen)) * 100.0


def build_drop_rows(seen: dict[str, Any], unseen: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for metric in CORE_METRICS:
        seen_value = get_nested(seen, metric.path)
        unseen_value = get_nested(unseen, metric.path)
        if seen_value is None or unseen_value is None:
            rows.append(
                {
                    "metric": metric.name,
                    "seen_value": seen_value,
                    "unseen_value": unseen_value,
                    "absolute_drop": None,
                    "relative_drop_percent": None,
                    "higher_is_better": metric.higher_is_better,
                    "status": "missing_value",
                }
            )
            continue

        absolute_drop = _abs_drop(seen_value, unseen_value, metric.higher_is_better)
        relative_drop = _pct_drop(absolute_drop, seen_value)
        rows.append(
            {
                "metric": metric.name,
                "seen_value": seen_value,
                "unseen_value": unseen_value,
                "absolute_drop": absolute_drop,
                "relative_drop_percent": relative_drop,
                "higher_is_better": metric.higher_is_better,
                "status": "ok",
            }
        )

    return rows


def summarize(rows: list[dict[str, Any]], seen_label: str, unseen_label: str) -> dict[str, Any]:
    valid = [row for row in rows if row["status"] == "ok"]
    degraded = [row for row in valid if row["absolute_drop"] > 0]
    improved = [row for row in valid if row["absolute_drop"] < 0]
    unchanged = [row for row in valid if row["absolute_drop"] == 0]

    return {
        "schema_version": 1,
        "comparison": {
            "seen_label": seen_label,
            "unseen_label": unseen_label,
        },
        "metric_count": len(rows),
        "valid_metric_count": len(valid),
        "degraded_metric_count": len(degraded),
        "improved_metric_count": len(improved),
        "unchanged_metric_count": len(unchanged),
        "generalization_drop_table": rows,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "metric",
                "seen_value",
                "unseen_value",
                "absolute_drop",
                "relative_drop_percent",
                "higher_is_better",
                "status",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seen-core-metrics",
        type=Path,
        required=True,
        help="Path to core metrics JSON for seen mazes.",
    )
    parser.add_argument(
        "--unseen-core-metrics",
        type=Path,
        required=True,
        help="Path to core metrics JSON for unseen mazes.",
    )
    parser.add_argument("--seen-label", default="seen", help="Display label for seen set.")
    parser.add_argument("--unseen-label", default="unseen", help="Display label for unseen set.")
    parser.add_argument("--output-json", type=Path, required=True, help="Output JSON path for drop summary.")
    parser.add_argument("--output-csv", type=Path, required=True, help="Output CSV path for drop table.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    seen = load_json(args.seen_core_metrics)
    unseen = load_json(args.unseen_core_metrics)
    rows = build_drop_rows(seen, unseen)
    summary = summarize(rows, args.seen_label, args.unseen_label)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_csv(args.output_csv, rows)

    print(f"Wrote seen-vs-unseen summary: {args.output_json}")
    print(f"Wrote generalization drop table: {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
