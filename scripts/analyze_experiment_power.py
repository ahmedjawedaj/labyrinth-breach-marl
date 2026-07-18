#!/usr/bin/env python3
"""Export paired-seed minimum detectable effects for the registered study."""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from scipy.optimize import brentq
from scipy.stats import nct, t


def paired_t_power(effect_size: float, sample_size: int, alpha: float) -> float:
    degrees_of_freedom = sample_size - 1
    critical_value = t.ppf(1.0 - alpha / 2.0, degrees_of_freedom)
    noncentrality = effect_size * sample_size**0.5
    return float(
        nct.cdf(-critical_value, degrees_of_freedom, noncentrality)
        + 1.0
        - nct.cdf(critical_value, degrees_of_freedom, noncentrality)
    )


def minimum_detectable_effect(sample_size: int, alpha: float, target_power: float) -> float:
    upper_bound = 0.25
    while upper_bound <= 8.0:
        candidate_power = paired_t_power(upper_bound, sample_size, alpha)
        if math.isfinite(candidate_power) and candidate_power >= target_power:
            break
        upper_bound += 0.25
    else:
        raise ValueError(
            f"Target power {target_power} is not reached by |dz|=8 for n={sample_size}."
        )
    return float(
        brentq(
            lambda effect: paired_t_power(effect, sample_size, alpha) - target_power,
            0.0,
            upper_bound,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-sizes", nargs="+", type=int, default=[3, 5, 10])
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--target-power", type=float, default=0.80)
    parser.add_argument("--output-dir", default="results/official_summary/power_analysis")
    args = parser.parse_args()

    if any(sample_size < 2 for sample_size in args.sample_sizes):
        raise ValueError("Every paired-seed sample size must be at least two.")
    if not 0.0 < args.alpha < 1.0 or not 0.0 < args.target_power < 1.0:
        raise ValueError("alpha and target power must lie strictly between zero and one.")

    rows = [
        {
            "paired_policy_seeds": sample_size,
            "degrees_of_freedom": sample_size - 1,
            "alpha_two_sided": args.alpha,
            "target_power": args.target_power,
            "minimum_detectable_abs_dz": minimum_detectable_effect(
                sample_size, args.alpha, args.target_power
            ),
        }
        for sample_size in args.sample_sizes
    ]

    root = Path(__file__).resolve().parents[1]
    output_dir = root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "test": "two-sided paired t test over independent policy-seed deltas",
        "effect_size": "dz = mean paired delta / sample standard deviation of paired deltas",
        "assumptions": [
            "policy seeds are independent replicates",
            "paired seed-level deltas are approximately normal",
            "episode count does not increase policy-level sample size",
        ],
        "rows": rows,
    }
    json_path = output_dir / "minimum_detectable_effects.json"
    csv_path = output_dir / "minimum_detectable_effects.csv"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote: {json_path}")
    print(f"Wrote: {csv_path}")
    for row in rows:
        print(
            f"n={row['paired_policy_seeds']}: "
            f"minimum detectable |dz|={row['minimum_detectable_abs_dz']:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
