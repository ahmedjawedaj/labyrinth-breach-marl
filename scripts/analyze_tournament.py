#!/usr/bin/env python3
"""Coevolutionary analysis of the snapshot tournament payoff matrices.

Implements Phase 2 of TASK_snapshot_tournament.md:

  2.1  Monotonic progress against archive-position offset
  2.2  Bradley-Terry transitive fit and residual, with a parametric bootstrap null
  2.3  Nash averaging (two-population zero-sum), support concentration
  2.4  Cycle detection, reported against a sampling-noise null
  2.5  Self-play ELO versus archive-based Bradley-Terry rating
  2.6  Cross-stage curriculum dominance

Two notes on method, both deliberate.

First, this is a two-population asymmetric game. Sentinels and Runners are
separate populations and the payoff matrix is bipartite, so single-population
intransitivity measures do not transfer. The Bradley-Terry residual is the
primary intransitivity measure here: Bradley-Terry *is* the rank-1 transitive
model, so deviation from it is exactly what "no single scalar strength ordering
explains the outcomes" means. Cycle counts are reported because the task asks
for them, but they are secondary.

Second, every dispersion statistic on a payoff matrix is positive under sampling
noise alone. At n episodes per cell the standard error on a win rate near 0.5 is
sqrt(0.25/n), which at n=30 is about 9 percentage points; thresholding such a
matrix into a dominance relation produces cycles in a perfectly transitive game.
So residual and cycle count are both reported against a parametric bootstrap
null simulated from the fitted transitive model at the observed episode counts.
A raw count without its null is not interpretable and is not printed alone.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from save_run_metadata import repo_root  # noqa: E402

MATRIX_DIR = Path("results") / "official_summary" / "tournament"
RNG_SEED = 20260805


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------


def load_matrix(root: Path, matrix_name: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = root / MATRIX_DIR / f"payoff_matrix_{matrix_name.replace('-', '_')}.json"
    if not path.is_file():
        raise SystemExit(f"Payoff matrix not found: {path}\nRun scripts/run_snapshot_tournament.py first.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["cells"], payload.get("meta", {})


def checkpoint_key(side: dict[str, Any]) -> str:
    return f"seed{side['seed']}-stage{side['stage']}-step{side['step']}"


def parse_key(key: str) -> tuple[int, int, int]:
    seed, stage, step = (int(v) for v in re.findall(r"\d+", key))
    return seed, stage, step


def to_arrays(cells: list[dict[str, Any]]) -> tuple[list[str], list[str], np.ndarray, np.ndarray]:
    """Return (sentinel keys, runner keys, win-rate matrix, episode-count matrix)."""
    key = checkpoint_key
    sentinels = sorted({key(c["sentinel"]) for c in cells}, key=parse_key)
    runners = sorted({key(c["runner"]) for c in cells}, key=parse_key)
    s_index = {k: i for i, k in enumerate(sentinels)}
    r_index = {k: i for i, k in enumerate(runners)}

    payoff = np.full((len(sentinels), len(runners)), np.nan)
    counts = np.zeros((len(sentinels), len(runners)))
    for cell in cells:
        i, j = s_index[key(cell["sentinel"])], r_index[key(cell["runner"])]
        rate = cell.get("sentinel_win_rate")
        if rate is None:
            continue
        payoff[i, j] = float(rate)
        counts[i, j] = float(cell.get("episodes") or 0)
    return sentinels, runners, payoff, counts


# ---------------------------------------------------------------------------
# 2.2 Bradley-Terry
# ---------------------------------------------------------------------------


def fit_bradley_terry(payoff: np.ndarray, counts: np.ndarray, iterations: int = 500) -> tuple[np.ndarray, np.ndarray]:
    """MLE for P(sentinel i beats runner j) = sigmoid(a_i - b_j) by gradient ascent.

    Returns (a, b). Identifiable only up to a shared additive constant, so `a` is
    centred on zero.
    """
    observed = np.nan_to_num(payoff)
    mask = (~np.isnan(payoff)) & (counts > 0)
    wins = observed * counts
    a = np.zeros(payoff.shape[0])
    b = np.zeros(payoff.shape[1])
    step = 0.5

    for _ in range(iterations):
        predicted = 1.0 / (1.0 + np.exp(-(a[:, None] - b[None, :])))
        residual = np.where(mask, wins - counts * predicted, 0.0)
        denom_a = np.maximum(np.where(mask, counts, 0.0).sum(axis=1), 1e-9)
        denom_b = np.maximum(np.where(mask, counts, 0.0).sum(axis=0), 1e-9)
        a += step * residual.sum(axis=1) / denom_a
        b -= step * residual.sum(axis=0) / denom_b
        a -= a.mean()
    return a, b


def bt_predicted(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-(a[:, None] - b[None, :])))


def residual_statistic(payoff: np.ndarray, predicted: np.ndarray, mask: np.ndarray) -> float:
    """Root-mean-square deviation of observed payoffs from the transitive fit."""
    diff = (payoff - predicted)[mask]
    return float(np.sqrt(np.mean(diff**2))) if diff.size else float("nan")


# ---------------------------------------------------------------------------
# 2.4 cycles
# ---------------------------------------------------------------------------


def count_cycles(payoff: np.ndarray, mask: np.ndarray, threshold: float = 0.5) -> dict[str, Any]:
    """Three-cycles in the bipartite dominance relation.

    A Sentinel and a Runner are linked when their cell exists. Sentinel i
    dominates Runner j when the win rate exceeds `threshold`, otherwise j
    dominates i. A 3-cycle in the bipartite orientation is a length-4 alternating
    cycle: i beats j, k beats j is false... so cycles here are counted over
    Sentinel pairs that disagree in their ordering of a Runner pair, which is the
    bipartite analogue of intransitivity.
    """
    rows, cols = payoff.shape
    disagreements = 0
    comparable = 0
    for i, k in combinations(range(rows), 2):
        for j, m in combinations(range(cols), 2):
            if not (mask[i, j] and mask[i, m] and mask[k, j] and mask[k, m]):
                continue
            comparable += 1
            # Does Sentinel i rank Runners j,m in the same order as Sentinel k?
            first = payoff[i, j] - payoff[i, m]
            second = payoff[k, j] - payoff[k, m]
            if first * second < 0:
                disagreements += 1
    return {
        "comparable_quadruples": comparable,
        "order_disagreements": disagreements,
        "disagreement_rate": (disagreements / comparable) if comparable else float("nan"),
    }


# ---------------------------------------------------------------------------
# null model
# ---------------------------------------------------------------------------


def bootstrap_null(
    a: np.ndarray, b: np.ndarray, counts: np.ndarray, mask: np.ndarray, draws: int
) -> dict[str, Any]:
    """Simulate payoff matrices from the fitted transitive model.

    Answers: how large a residual, and how many order disagreements, would this
    design produce if the game were perfectly transitive and the only source of
    deviation were binomial sampling at the observed episode counts?
    """
    rng = np.random.default_rng(RNG_SEED)
    truth = bt_predicted(a, b)
    safe_counts = np.where(counts > 0, counts, 1)

    residuals, disagreement_rates = [], []
    for _ in range(draws):
        simulated = rng.binomial(safe_counts.astype(int), truth) / safe_counts
        simulated = np.where(mask, simulated, np.nan)
        sim_a, sim_b = fit_bradley_terry(simulated, counts, iterations=200)
        residuals.append(residual_statistic(simulated, bt_predicted(sim_a, sim_b), mask))
        disagreement_rates.append(count_cycles(np.nan_to_num(simulated), mask)["disagreement_rate"])

    return {
        "draws": draws,
        "residual_mean": float(np.nanmean(residuals)),
        "residual_p95": float(np.nanpercentile(residuals, 95)),
        "disagreement_rate_mean": float(np.nanmean(disagreement_rates)),
        "disagreement_rate_p95": float(np.nanpercentile(disagreement_rates, 95)),
        "_residuals": residuals,
        "_disagreements": disagreement_rates,
    }


def empirical_p(observed: float, null_samples: list[float]) -> float:
    clean = [v for v in null_samples if not math.isnan(v)]
    if not clean or math.isnan(observed):
        return float("nan")
    exceed = sum(1 for v in clean if v >= observed)
    return (exceed + 1) / (len(clean) + 1)


# ---------------------------------------------------------------------------
# 2.3 Nash averaging
# ---------------------------------------------------------------------------


def nash_averaging(payoff: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    """Maximum-entropy Nash for the two-population zero-sum game.

    The antisymmetric payoff is (win rate - 0.5). Solves the LP for the game
    value and one equilibrium, then maximises entropy over the equilibrium
    polytope. Falls back to the LP vertex if the entropy step does not converge.

    Balduzzi et al. (2018) is the reference. Verify against that paper's worked
    examples before publishing numbers from this function.
    """
    try:
        from scipy.optimize import linprog, minimize
    except ImportError:
        return {"available": False, "reason": "scipy is required for Nash averaging"}

    matrix = np.where(mask, payoff - 0.5, 0.0)
    rows, cols = matrix.shape

    # Row player: maximise v subject to p^T A >= v, p in simplex.
    c = np.zeros(rows + 1)
    c[-1] = -1.0
    A_ub = np.hstack([-matrix.T, np.ones((cols, 1))])
    b_ub = np.zeros(cols)
    A_eq = np.zeros((1, rows + 1))
    A_eq[0, :rows] = 1.0
    bounds = [(0.0, None)] * rows + [(None, None)]
    row_lp = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=[1.0], bounds=bounds, method="highs")
    if not row_lp.success:
        return {"available": False, "reason": f"row LP failed: {row_lp.message}"}
    p_lp, value = row_lp.x[:rows], row_lp.x[-1]

    # Column player: minimise w subject to A q <= w, q in simplex.
    c2 = np.zeros(cols + 1)
    c2[-1] = 1.0
    A_ub2 = np.hstack([matrix, -np.ones((rows, 1))])
    b_ub2 = np.zeros(rows)
    A_eq2 = np.zeros((1, cols + 1))
    A_eq2[0, :cols] = 1.0
    bounds2 = [(0.0, None)] * cols + [(None, None)]
    col_lp = linprog(c2, A_ub=A_ub2, b_ub=b_ub2, A_eq=A_eq2, b_eq=[1.0], bounds=bounds2, method="highs")
    q_lp = col_lp.x[:cols] if col_lp.success else np.full(cols, 1.0 / cols)

    def max_entropy(dist_lp: np.ndarray, constraint: np.ndarray, target: float, sense: str) -> np.ndarray:
        n = dist_lp.size
        tol = 1e-7

        def negative_entropy(x: np.ndarray) -> float:
            safe = np.clip(x, 1e-12, None)
            return float(np.sum(safe * np.log(safe)))

        cons = [{"type": "eq", "fun": lambda x: np.sum(x) - 1.0}]
        if sense == "ge":
            cons.append({"type": "ineq", "fun": lambda x: x @ constraint - (target - tol)})
        else:
            cons.append({"type": "ineq", "fun": lambda x: (target + tol) - constraint @ x})
        result = minimize(
            negative_entropy, dist_lp, method="SLSQP", bounds=[(0.0, 1.0)] * n,
            constraints=cons, options={"maxiter": 500, "ftol": 1e-10},
        )
        return result.x / result.x.sum() if result.success else dist_lp

    p = max_entropy(p_lp, matrix, value, "ge")
    q = max_entropy(q_lp, matrix, value, "le")

    def support(dist: np.ndarray, floor: float = 1e-4) -> dict[str, Any]:
        active = np.where(dist > floor)[0]
        safe = np.clip(dist, 1e-12, None)
        entropy = float(-np.sum(safe * np.log(safe)))
        return {
            "support_size": int(active.size),
            "support_indices": active.tolist(),
            "entropy_nats": entropy,
            "entropy_ratio_vs_uniform": entropy / math.log(dist.size) if dist.size > 1 else float("nan"),
        }

    return {
        "available": True,
        "game_value": float(value),
        "sentinel_distribution": p.tolist(),
        "runner_distribution": q.tolist(),
        "sentinel_support": support(p),
        "runner_support": support(q),
        "maxent_applied": True,
        "caveat": "Verify against Balduzzi et al. (2018) worked examples before publication.",
    }


# ---------------------------------------------------------------------------
# 2.1 / 2.6
# ---------------------------------------------------------------------------


def monotonic_progress(cells: list[dict[str, Any]]) -> dict[str, Any]:
    """Mean Sentinel win rate against archive-position offset, per seed.

    Offset is the Sentinel's position in its seed's ordered checkpoint list minus
    the Runner's. Positive offset means the Sentinel is later in training than
    the opponent it faces. Monotone increasing is progress; flat or non-monotone
    is cycling.
    """
    order: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for cell in cells:
        for side in ("sentinel", "runner"):
            entry = (cell[side]["stage"], cell[side]["step"])
            if entry not in order[cell[side]["seed"]]:
                order[cell[side]["seed"]].append(entry)
    positions = {seed: {v: i for i, v in enumerate(sorted(items))} for seed, items in order.items()}

    per_seed: dict[str, dict[str, Any]] = {}
    buckets: dict[int, list[float]] = defaultdict(list)
    for cell in cells:
        seed = cell["sentinel"]["seed"]
        if seed != cell["runner"]["seed"]:
            continue
        rate = cell.get("sentinel_win_rate")
        if rate is None:
            continue
        s_pos = positions[seed][(cell["sentinel"]["stage"], cell["sentinel"]["step"])]
        r_pos = positions[seed][(cell["runner"]["stage"], cell["runner"]["step"])]
        buckets[s_pos - r_pos].append(float(rate))
        per_seed.setdefault(str(seed), {"offsets": defaultdict(list)})["offsets"][s_pos - r_pos].append(float(rate))

    pooled = {
        str(offset): {"mean": float(np.mean(v)), "n": len(v), "sd": float(np.std(v, ddof=1)) if len(v) > 1 else None}
        for offset, v in sorted(buckets.items())
    }
    seeds_out = {}
    for seed, payload in per_seed.items():
        seeds_out[seed] = {
            str(offset): {"mean": float(np.mean(v)), "n": len(v)}
            for offset, v in sorted(payload["offsets"].items())
        }

    offsets = sorted(buckets)
    means = [float(np.mean(buckets[o])) for o in offsets]
    spearman = float("nan")
    if len(offsets) > 2:
        rank_x = np.argsort(np.argsort(offsets)).astype(float)
        rank_y = np.argsort(np.argsort(means)).astype(float)
        if rank_x.std() > 0 and rank_y.std() > 0:
            spearman = float(np.corrcoef(rank_x, rank_y)[0, 1])

    return {
        "pooled_by_offset": pooled,
        "per_seed_by_offset": seeds_out,
        "spearman_offset_vs_winrate": spearman,
        "interpretation": (
            "Positive and strong: later Sentinels beat earlier Runners, i.e. genuine progress. "
            "Near zero or non-monotone: cycling, later policies are differently specialised rather than better. "
            "Do not pool this across seeds for policy-level claims."
        ),
    }


def curriculum_dominance(cells: list[dict[str, Any]]) -> dict[str, Any]:
    grid: dict[str, list[float]] = defaultdict(list)
    for cell in cells:
        rate = cell.get("sentinel_win_rate")
        if rate is None:
            continue
        grid[f"S_stage{cell['sentinel']['stage']}_vs_R_stage{cell['runner']['stage']}"].append(float(rate))
    return {
        "mean_sentinel_win_rate": {k: float(np.mean(v)) for k, v in sorted(grid.items())},
        "cell_counts": {k: len(v) for k, v in sorted(grid.items())},
        "caveat": (
            "Cross-stage dominance is weaker evidence than the matched-budget direct-dynamic control. "
            "State that explicitly in the write-up; do not present it as equivalent."
        ),
    }


# ---------------------------------------------------------------------------
# 2.5 ELO
# ---------------------------------------------------------------------------


def load_elo(root: Path, source_results_dir: str) -> dict[str, Any]:
    try:
        from tensorboard.backend.event_processing import event_accumulator
    except ImportError:
        return {"available": False, "reason": "tensorboard not importable; run inside the labyrinth-breach env"}

    series: dict[str, list[tuple[int, float]]] = {}
    missing: list[str] = []
    base = root / source_results_dir
    for run_dir in sorted(base.glob("LB_3v2_official_seed*_stage*")):
        for behavior in ("Sentinel", "Runner"):
            events = sorted((run_dir / behavior).glob("events.out.tfevents.*"))
            key = f"{run_dir.name}/{behavior}"
            found = False
            for event_file in events:
                acc = event_accumulator.EventAccumulator(str(event_file), size_guidance={"scalars": 0})
                acc.Reload()
                tags = [t for t in acc.Tags().get("scalars", []) if "elo" in t.lower()]
                if not tags:
                    continue
                series[key] = [(e.step, e.value) for e in acc.Scalars(tags[0])]
                found = True
                break
            if not found:
                missing.append(key)
    return {
        "available": True,
        "series_found": sorted(series),
        "series_missing": missing,
        "series": {k: v for k, v in series.items()},
        "note": (
            "team_change is 100000, so the ghost trainer alternates the learning team and each behavior's "
            "series is expected to have gaps. Total absence for one behavior across all runs is a logging "
            "artifact, not evidence; report Spearman for the behavior that has ELO and say why the other is missing."
        ),
    }


def elo_correlation(elo: dict[str, Any], ratings: dict[str, float]) -> dict[str, Any]:
    if not elo.get("available"):
        return {"available": False, "reason": elo.get("reason")}
    paired: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for key, points in elo.get("series", {}).items():
        run_id, behavior = key.rsplit("/", 1)
        match = [m for m in ratings if m.startswith(f"{behavior}:")]
        for rating_key in match:
            _, seed, stage, step = rating_key.split(":")
            if f"seed{seed}_stage{stage}" not in run_id:
                continue
            nearest = min(points, key=lambda p: abs(p[0] - int(step)), default=None)
            if nearest is not None:
                paired[f"{behavior}/seed{seed}"].append((nearest[1], ratings[rating_key]))

    out = {}
    for group, pairs in sorted(paired.items()):
        if len(pairs) < 3:
            out[group] = {"n": len(pairs), "spearman": None, "note": "too few points"}
            continue
        x = np.array([p[0] for p in pairs], dtype=float)
        y = np.array([p[1] for p in pairs], dtype=float)
        rx = np.argsort(np.argsort(x)).astype(float)
        ry = np.argsort(np.argsort(y)).astype(float)
        rho = float(np.corrcoef(rx, ry)[0, 1]) if rx.std() > 0 and ry.std() > 0 else float("nan")
        out[group] = {"n": len(pairs), "spearman": rho}
    return {"available": True, "per_group": out}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--matrix", default="cross-seed",
                        choices=("cross-seed", "within-seed", "collapse-probe"))
    parser.add_argument("--source-results-dir", default="results")
    parser.add_argument("--bootstrap-draws", type=int, default=500)
    parser.add_argument("--skip-elo", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()

    root = repo_root()
    cells, meta = load_matrix(root, args.matrix)
    sentinels, runners, payoff, counts = to_arrays(cells)
    mask = (~np.isnan(payoff)) & (counts > 0)

    median_n = float(np.median(counts[mask])) if mask.any() else float("nan")
    resolvable = 2.8 * math.sqrt(0.25 / median_n) if median_n and median_n > 0 else float("nan")

    a, b = fit_bradley_terry(payoff, counts)
    predicted = bt_predicted(a, b)
    observed_residual = residual_statistic(payoff, predicted, mask)
    observed_cycles = count_cycles(np.nan_to_num(payoff), mask)

    null = bootstrap_null(a, b, counts, mask, args.bootstrap_draws)

    ratings = {}
    for index, key in enumerate(sentinels):
        seed, stage, step = parse_key(key)
        ratings[f"Sentinel:{seed}:{stage}:{step}"] = float(a[index])
    for index, key in enumerate(runners):
        seed, stage, step = parse_key(key)
        ratings[f"Runner:{seed}:{stage}:{step}"] = float(-b[index])

    elo = {"available": False, "reason": "skipped"} if args.skip_elo else load_elo(root, args.source_results_dir)

    report = {
        "matrix": args.matrix,
        "matrix_meta": meta,
        "design": {
            "sentinels": len(sentinels),
            "runners": len(runners),
            "cells_with_data": int(mask.sum()),
            "median_episodes_per_cell": median_n,
            "resolvable_win_rate_difference_80pct_power": resolvable,
            "note": (
                "Differences smaller than the resolvable threshold are sampling noise. "
                "Do not threshold this matrix into a dominance relation below that resolution."
            ),
        },
        "bradley_terry": {
            "sentinel_ratings": {k: float(v) for k, v in zip(sentinels, a)},
            "runner_ratings": {k: float(-v) for k, v in zip(runners, b)},
            "residual_rms": observed_residual,
            "null_residual_mean": null["residual_mean"],
            "null_residual_p95": null["residual_p95"],
            "p_value": empirical_p(observed_residual, null["_residuals"]),
            "interpretation": (
                "A residual above the null p95 is evidence that no single scalar strength ordering "
                "explains the outcomes. A residual inside the null is consistent with a transitive game."
            ),
        },
        "cycles": {
            **observed_cycles,
            "null_disagreement_rate_mean": null["disagreement_rate_mean"],
            "null_disagreement_rate_p95": null["disagreement_rate_p95"],
            "p_value": empirical_p(observed_cycles["disagreement_rate"], null["_disagreements"]),
            "interpretation": (
                "Secondary to the Bradley-Terry residual. Report only alongside the null; a raw "
                "disagreement count is uninterpretable at these episode counts."
            ),
        },
        "nash_averaging": nash_averaging(payoff, mask),
        "monotonic_progress": monotonic_progress(cells),
        "curriculum_dominance": curriculum_dominance(cells),
        "elo_validation": elo_correlation(elo, ratings),
        "elo_inventory": {k: v for k, v in elo.items() if k != "series"},
    }

    output = Path(args.output) if args.output else root / MATRIX_DIR / f"analysis_{args.matrix.replace('-', '_')}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    print(f"Matrix:                  {args.matrix}  ({len(sentinels)} x {len(runners)}, {int(mask.sum())} cells)")
    print(f"Median episodes/cell:    {median_n:.0f}")
    print(f"Resolvable difference:   {resolvable * 100:.1f} pp at 80% power")
    print(f"BT residual (RMS):       {observed_residual:.4f}  (null mean {null['residual_mean']:.4f}, "
          f"p95 {null['residual_p95']:.4f}, p = {report['bradley_terry']['p_value']:.3f})")
    print(f"Order disagreement rate: {observed_cycles['disagreement_rate']:.4f}  "
          f"(null mean {null['disagreement_rate_mean']:.4f}, p = {report['cycles']['p_value']:.3f})")
    print(f"Progress Spearman:       {report['monotonic_progress']['spearman_offset_vs_winrate']:.4f}")
    nash = report["nash_averaging"]
    if nash.get("available"):
        print(f"Nash support:            Sentinel {nash['sentinel_support']['support_size']}/{len(sentinels)}, "
              f"Runner {nash['runner_support']['support_size']}/{len(runners)}")
    print(f"\nReport: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
