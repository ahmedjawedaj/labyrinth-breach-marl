#!/usr/bin/env python3
"""Round-robin tournament over saved self-play checkpoints.

Plays Sentinel checkpoints against Runner checkpoints using the existing
fixed-policy inference path (scripts/evaluate_policy.py). No training, no GPU.

Three matrices:

  cross-seed      Stage-4 final checkpoint from each policy seed, all pairings.
                  Primary result: unaffected by checkpoint granularity, and every
                  cell is individually load-bearing, so it runs at high episode
                  counts.
  within-seed     All deduplicated checkpoints within each policy seed. Feeds the
                  monotonic-progress trend, which averages over archive-position
                  offsets, so a lower per-cell episode count is acceptable.
  collapse-probe  Surviving checkpoints from the invalidated latest-policy
                  cycling run.

Each cell stages two checkpoints into a synthetic run directory and invokes
evaluate_policy.py unmodified, so the strict publication-evaluation gate, KPI
summarization, and artifact validation all apply without weakening.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from save_run_metadata import repo_root  # noqa: E402
from check_materialized import is_dataless, verify_readable  # noqa: E402


BEHAVIORS = ("Sentinel", "Runner")
OFFICIAL_RUN = re.compile(r"^LB_3v2_official_seed(?P<seed>\d+)_stage(?P<stage>\d+)$")
CHECKPOINT = re.compile(r"^(?P<behavior>Sentinel|Runner)-(?P<step>\d+)\.pt$")
COLLAPSE_RUN = "LB_3v2_official_seed42_stage1_latest_policy_cycling_invalidated_20260716"
STAGE_DIR = Path("tmp") / "snapshot_tournament_stage"
MATRIX_OUTPUT = Path("results") / "official_summary" / "tournament"

MATRIX_DEFAULTS = {
    "cross-seed": {"episodes": 300, "results_dir": "results/snapshot_tournament/cross_seed"},
    "within-seed": {"episodes": 30, "results_dir": "results/snapshot_tournament/within_seed"},
    "collapse-probe": {"episodes": 30, "results_dir": "results/snapshot_tournament/collapse_probe"},
}


@dataclass(frozen=True)
class Checkpoint:
    behavior: str
    seed: int
    stage: int
    step: int
    run_id: str
    checkpoint_path: str
    onnx_path: str | None

    @property
    def code(self) -> str:
        return f"{self.seed}s{self.stage}c{self.step}"


# ---------------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------------


def scan_run(root: Path, run_dir: Path, seed: int, stage: int) -> dict[str, list[Checkpoint]]:
    found: dict[str, list[Checkpoint]] = {behavior: [] for behavior in BEHAVIORS}
    for behavior in BEHAVIORS:
        behavior_dir = run_dir / behavior
        if not behavior_dir.is_dir():
            continue
        for candidate in sorted(behavior_dir.glob(f"{behavior}-*.pt")):
            match = CHECKPOINT.match(candidate.name)
            if match is None:
                continue
            onnx = candidate.with_suffix(".onnx")
            found[behavior].append(
                Checkpoint(
                    behavior=behavior,
                    seed=seed,
                    stage=stage,
                    step=int(match.group("step")),
                    run_id=run_dir.name,
                    checkpoint_path=str(candidate.relative_to(root)),
                    onnx_path=str(onnx.relative_to(root)) if onnx.is_file() else None,
                )
            )
    for behavior in BEHAVIORS:
        found[behavior].sort(key=lambda c: (c.seed, c.stage, c.step))
    return found


def discover_official(
    root: Path, source_results_dir: Path, seeds: list[int], stages: list[int]
) -> dict[str, list[Checkpoint]]:
    found: dict[str, list[Checkpoint]] = {behavior: [] for behavior in BEHAVIORS}
    for run_dir in sorted(source_results_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        match = OFFICIAL_RUN.match(run_dir.name)
        if match is None:
            continue
        seed, stage = int(match.group("seed")), int(match.group("stage"))
        if seeds and seed not in seeds:
            continue
        if stages and stage not in stages:
            continue
        for behavior, items in scan_run(root, run_dir, seed, stage).items():
            found[behavior].extend(items)
    for behavior in BEHAVIORS:
        found[behavior].sort(key=lambda c: (c.seed, c.stage, c.step))
    return found


def dedupe(checkpoints: list[Checkpoint], window: int) -> list[Checkpoint]:
    """Collapse checkpoints within `window` steps of each other.

    ML-Agents writes an end-of-run export a few thousand steps after the last
    interval checkpoint. Those two policies are separated by under 0.3% of the
    training budget. Keeping both would seed the payoff matrix with a redundant
    row and column, which matters for Nash averaging in particular.
    """
    if window <= 0:
        return list(checkpoints)
    kept: list[Checkpoint] = []
    for checkpoint in checkpoints:
        if kept:
            previous = kept[-1]
            if (
                previous.seed == checkpoint.seed
                and previous.stage == checkpoint.stage
                and checkpoint.step - previous.step <= window
            ):
                kept[-1] = checkpoint
                continue
        kept.append(checkpoint)
    return kept


def latest_per_group(checkpoints: list[Checkpoint], stage: int) -> list[Checkpoint]:
    """Highest-step checkpoint of the given stage, one per seed."""
    best: dict[int, Checkpoint] = {}
    for checkpoint in checkpoints:
        if checkpoint.stage != stage:
            continue
        current = best.get(checkpoint.seed)
        if current is None or checkpoint.step > current.step:
            best[checkpoint.seed] = checkpoint
    return [best[seed] for seed in sorted(best)]


# ---------------------------------------------------------------------------
# matrices
# ---------------------------------------------------------------------------


def build_matrix(
    root: Path, source_results_dir: Path, args: argparse.Namespace
) -> tuple[list[tuple[Checkpoint, Checkpoint]], dict[str, Any]]:
    if args.matrix == "collapse-probe":
        run_dir = source_results_dir / COLLAPSE_RUN
        if not run_dir.is_dir():
            raise SystemExit(
                f"Collapse-probe run not found: {run_dir}\n"
                "Task section 2.7 says not to reconstruct or estimate. Skip this matrix."
            )
        found = scan_run(root, run_dir, seed=42, stage=1)
        sentinels, runners = found["Sentinel"], found["Runner"]
        note = "Surviving checkpoints only; report as an N-cell probe in text, not as a figure."
    else:
        found = discover_official(root, source_results_dir, args.seeds, args.stages)
        sentinels = dedupe(found["Sentinel"], args.dedupe_window)
        runners = dedupe(found["Runner"], args.dedupe_window)
        if args.matrix == "cross-seed":
            sentinels = latest_per_group(sentinels, args.cross_seed_stage)
            runners = latest_per_group(runners, args.cross_seed_stage)
            note = f"Stage-{args.cross_seed_stage} final checkpoint per seed; independent policies."
        else:
            note = "Within-seed pairings only; checkpoints are a correlated trajectory, not independent policies."

    if not sentinels or not runners:
        raise SystemExit("No checkpoints discovered. Check --source-results-dir, --seeds, --stages.")

    pairs = [
        (sentinel, runner)
        for sentinel in sentinels
        for runner in runners
        if args.matrix != "within-seed" or sentinel.seed == runner.seed
    ]
    meta = {
        "matrix": args.matrix,
        "note": note,
        "sentinel_count": len(sentinels),
        "runner_count": len(runners),
        "cells": len(pairs),
        "episodes_per_cell": args.episodes,
        "dedupe_window": args.dedupe_window,
    }
    return pairs, meta


def pair_id(sentinel: Checkpoint, runner: Checkpoint) -> str:
    return f"LBT_S{sentinel.code}_R{runner.code}"


def preflight_materialization(root: Path, pairs: list[tuple[Checkpoint, Checkpoint]]) -> list[str]:
    """Refuse to start when any required checkpoint has been evicted from disk.

    macOS iCloud "Optimise Mac Storage" leaves st_size intact while dropping the
    blocks, so an evicted checkpoint looks present until something tries to read
    it. Discovering that at cell 300 of 720 wastes hours, so it is checked once
    up front against the exact set this run needs.
    """
    required: set[Path] = set()
    for sentinel, runner in pairs:
        for checkpoint in (sentinel, runner):
            required.add(root / checkpoint.checkpoint_path)
            if checkpoint.onnx_path:
                required.add(root / checkpoint.onnx_path)

    problems: list[str] = []
    for path in sorted(required):
        if not path.exists():
            problems.append(f"missing: {path}")
        elif is_dataless(path):
            problems.append(f"evicted: {path}")
        else:
            readable, reason = verify_readable(path)
            if not readable:
                problems.append(f"unreadable: {path}  [{reason}]")
    return problems


# ---------------------------------------------------------------------------
# execution
# ---------------------------------------------------------------------------


def stage_pair(root: Path, sentinel: Checkpoint, runner: Checkpoint, run_id: str) -> Path:
    """Materialise a synthetic run directory holding the two chosen policies.

    evaluate_policy.py copies `<results>/<run_id>/<behavior>/checkpoint.pt` into
    its own ephemeral workspace, so an arbitrary pairing is expressible purely as
    a directory layout. Training artifacts are never touched.
    """
    stage_root = root / STAGE_DIR / run_id
    if stage_root.exists():
        shutil.rmtree(stage_root)
    for behavior, checkpoint in (("Sentinel", sentinel), ("Runner", runner)):
        target = stage_root / behavior
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / checkpoint.checkpoint_path, target / "checkpoint.pt")
        if checkpoint.onnx_path:
            shutil.copy2(root / checkpoint.onnx_path, stage_root / f"{behavior}.onnx")
    (stage_root / "pairing.json").write_text(
        json.dumps({"run_id": run_id, "Sentinel": asdict(sentinel), "Runner": asdict(runner)}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return stage_root


def cell_is_complete(run_root: Path, episodes: int) -> bool:
    status_path = run_root / "metadata" / "evaluation_status.json"
    kpi_path = run_root / "kpi" / "eval_kpi_summary.json"
    if not (status_path.is_file() and kpi_path.is_file()):
        return False
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return status.get("success") is True and int(status.get("completed_episodes") or 0) >= episodes


def read_cell(run_root: Path) -> dict[str, Any]:
    kpi = json.loads((run_root / "kpi" / "eval_kpi_summary.json").read_text(encoding="utf-8"))
    coordination = kpi.get("coordination") or {}
    return {
        "episodes": kpi.get("episodes"),
        "sentinel_win_rate": kpi.get("sentinel_win_rate"),
        "runner_win_rate": kpi.get("runner_win_rate"),
        "escape_rate": kpi.get("escape_rate"),
        "mean_time_to_full_capture_seconds": kpi.get("mean_time_to_full_capture_seconds"),
        "mean_time_to_first_capture_seconds": kpi.get("mean_time_to_first_capture_seconds"),
        "runner_survival_time_seconds_mean": kpi.get("runner_survival_time_seconds_mean"),
        "stall_step_fraction": (kpi.get("wall_collision_recovery_time_proxy") or {}).get("value"),
        "pincer_episode_rate": coordination.get("pincer_episode_rate"),
        "exit_denial_episode_rate": coordination.get("exit_denial_episode_rate"),
        "trap_episode_rate": coordination.get("trap_episode_rate"),
    }


def build_command(args: argparse.Namespace, run_id: str, output_dir: Path) -> list[str]:
    command = [
        sys.executable,
        "scripts/evaluate_policy.py",
        "--manifest", args.manifest,
        "--source-run-id", run_id,
        "--source-results-dir", str(STAGE_DIR),
        "--output-dir", str(output_dir),
        "--eval-run-id", run_id,
        "--seed", str(args.eval_seed),
        "--target-episodes", str(args.episodes),
        "--max-runtime-seconds", str(args.max_runtime_seconds),
        "--timeout-wait", str(args.timeout_wait),
        "--forbid-fallback-log-copy",
        "--deterministic",
    ]
    if args.env:
        command.extend(["--env", args.env])
    if args.allow_cpu:
        command.append("--allow-cpu")
    if args.no_graphics:
        command.append("--no-graphics")
    if args.base_port is not None:
        command.extend(["--base-port", str(args.base_port)])
    if args.dry_run:
        command.append("--dry-run")
    return command


# ---------------------------------------------------------------------------
# payoff matrix output
# ---------------------------------------------------------------------------


def write_payoff_matrix(root: Path, matrix_name: str, records: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    out_dir = root / MATRIX_OUTPUT
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"payoff_matrix_{matrix_name.replace('-', '_')}"

    (out_dir / f"{stem}.json").write_text(
        json.dumps({"meta": meta, "cells": records}, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    columns = [
        "run_id",
        "sentinel_seed", "sentinel_stage", "sentinel_step", "sentinel_run_id",
        "runner_seed", "runner_stage", "runner_step", "runner_run_id",
        "manifest", "eval_seed", "episodes",
        "sentinel_win_rate", "runner_win_rate", "escape_rate",
        "mean_time_to_first_capture_seconds", "mean_time_to_full_capture_seconds",
        "runner_survival_time_seconds_mean", "stall_step_fraction",
        "pincer_episode_rate", "exit_denial_episode_rate", "trap_episode_rate",
    ]
    with (out_dir / f"{stem}.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            flat = dict(record)
            for side in ("sentinel", "runner"):
                for field in ("seed", "stage", "step", "run_id"):
                    flat[f"{side}_{field}"] = record[side][field]
            writer.writerow(flat)

    print(f"Payoff matrix: {out_dir / f'{stem}.csv'}")
    print(f"Payoff matrix: {out_dir / f'{stem}.json'}")


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--matrix", choices=tuple(MATRIX_DEFAULTS), default="cross-seed")
    parser.add_argument("--source-results-dir", default="results")
    parser.add_argument("--results-dir", help="Defaults per matrix.")
    parser.add_argument(
        "--manifest",
        default="configs/experiment_manifests/exp_seen_eval_no_assist_seed42.yaml",
        help="Held constant across every cell so the policy pair is the only varying factor.",
    )
    parser.add_argument("--eval-seed", type=int, default=42)
    parser.add_argument("--seeds", type=int, nargs="*", default=[42, 101, 202, 606, 707])
    parser.add_argument("--stages", type=int, nargs="*", default=[1, 2, 3, 4])
    parser.add_argument("--cross-seed-stage", type=int, default=4)
    parser.add_argument("--episodes", type=int, help="Defaults per matrix.")
    parser.add_argument("--dedupe-window", type=int, default=10000)
    parser.add_argument("--max-runtime-seconds", type=int, default=5400)
    parser.add_argument("--timeout-wait", type=int, default=120)
    parser.add_argument("--env")
    parser.add_argument("--allow-cpu", action="store_true")
    parser.add_argument("--no-graphics", action="store_true")
    parser.add_argument("--base-port", type=int)
    parser.add_argument("--shard", help="INDEX/TOTAL, 1-based, for parallel workers on distinct base ports.")
    parser.add_argument("--resume-completed", action="store_true")
    parser.add_argument("--keep-stage-dirs", action="store_true")
    parser.add_argument("--skip-materialization-check", action="store_true",
                        help="Skip the evicted-checkpoint preflight. Not recommended.")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def parse_shard(value: str | None, total_pairs: int) -> tuple[int, int]:
    if not value:
        return 1, 1
    try:
        index_text, total_text = value.split("/", 1)
        index, total = int(index_text), int(total_text)
    except ValueError as exc:
        raise SystemExit(f"--shard must look like 2/8, got {value!r}") from exc
    if total < 1 or not 1 <= index <= total:
        raise SystemExit(f"--shard out of range: {value!r}")
    if total > total_pairs:
        raise SystemExit(f"--shard total {total} exceeds the {total_pairs} available cells")
    return index, total


def main() -> int:
    args = build_parser().parse_args()
    defaults = MATRIX_DEFAULTS[args.matrix]
    if args.episodes is None:
        args.episodes = defaults["episodes"]
    if args.results_dir is None:
        args.results_dir = defaults["results_dir"]

    root = repo_root()
    source_results_dir = root / args.source_results_dir
    if not source_results_dir.is_dir():
        print(f"Source results directory not found: {source_results_dir}", file=sys.stderr)
        return 1

    pairs, meta = build_matrix(root, source_results_dir, args)
    shard_index, shard_total = parse_shard(args.shard, len(pairs))
    shard_pairs = [pair for offset, pair in enumerate(pairs) if offset % shard_total == shard_index - 1]

    print(f"Matrix:            {args.matrix}")
    print(f"Note:              {meta['note']}")
    print(f"Sentinels x Runners: {meta['sentinel_count']} x {meta['runner_count']}")
    print(f"Cells:             {meta['cells']}")
    print(f"This shard:        {len(shard_pairs)} ({shard_index}/{shard_total})")
    print(f"Episodes per cell: {args.episodes}")
    print(f"Manifest:          {args.manifest}")

    if args.plan_only:
        print(json.dumps(
            [{"run_id": pair_id(s, r), "sentinel": asdict(s), "runner": asdict(r)} for s, r in shard_pairs],
            indent=2,
        ))
        return 0

    if not args.skip_materialization_check:
        problems = preflight_materialization(root, shard_pairs)
        if problems:
            print(f"\nPreflight failed: {len(problems)} required checkpoint files cannot be read.\n", file=sys.stderr)
            for problem in problems[:40]:
                print(f"  {problem}", file=sys.stderr)
            if len(problems) > 40:
                print(f"  ... and {len(problems) - 40} more", file=sys.stderr)
            print(
                "\nThese files stat as present but have no blocks allocated locally, which is what\n"
                "macOS iCloud 'Optimise Mac Storage' does when it evicts file contents.\n"
                "Re-materialise them on the Mac before running:\n"
                "  find results -name '*.pt' -o -name '*.onnx' | xargs -n1 -P4 cat > /dev/null\n"
                "then rerun. Full survey: python scripts/check_materialized.py --probe\n",
                file=sys.stderr,
            )
            return 2
        print("Preflight: all required checkpoints readable.")

    output_dir = Path(args.results_dir)
    records: list[dict[str, Any]] = []

    for position, (sentinel, runner) in enumerate(shard_pairs, start=1):
        run_id = pair_id(sentinel, runner)
        run_root = root / output_dir / run_id
        label = f"[{position}/{len(shard_pairs)}] {run_id}"

        if args.resume_completed and cell_is_complete(run_root, args.episodes):
            print(f"{label}: reusing completed cell")
        else:
            stage_pair(root, sentinel, runner, run_id)
            command = build_command(args, run_id, output_dir)
            if run_root.exists():
                command.append("--force-output")
            print(f"\n=== {label} ===")
            print(" ".join(command))
            rc = subprocess.run(command, cwd=root).returncode
            if not args.keep_stage_dirs:
                shutil.rmtree(root / STAGE_DIR / run_id, ignore_errors=True)
            if rc != 0:
                print(f"{label}: failed with exit code {rc}. Rerun with --resume-completed.", file=sys.stderr)
                return rc
            if args.dry_run:
                continue

        records.append({
            "run_id": run_id,
            "sentinel": asdict(sentinel),
            "runner": asdict(runner),
            "manifest": args.manifest,
            "eval_seed": args.eval_seed,
            **read_cell(run_root),
        })
        (root / output_dir / "cells.json").write_text(
            json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    if args.dry_run:
        return 0

    if shard_total > 1:
        print(f"\nShard {shard_index}/{shard_total} complete: {len(records)} cells.")
        print("Payoff matrix is written once all shards finish; rerun without --shard using")
        print("--resume-completed to aggregate.")
        return 0

    write_payoff_matrix(root, args.matrix, records, meta)
    print(f"\nCompleted {len(records)} cells.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
