#!/bin/sh
# Snapshot tournament, end to end. Run from the repo root on the Mac.
#
#   sh scripts/run_tournament_pipeline.sh            # full pipeline
#   sh scripts/run_tournament_pipeline.sh prep       # stages 1-3 only, no Unity
#   sh scripts/run_tournament_pipeline.sh cross      # primary matrix + analysis
#
# Every stage is resumable. Re-running skips completed work.
# Progress is appended to results/official_summary/tournament/pipeline.log so it
# can be tailed from another shell or read over a remote mount.

set -eu

STAGE=${1:-all}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

PYTHON=${PYTHON:-/opt/anaconda3/envs/labyrinth-breach/bin/python}
ENV_BUILD=${ENV_BUILD:-builds/macos/LabyrinthBreach.app}
OUT=results/official_summary/tournament
LOG=$OUT/pipeline.log
mkdir -p "$OUT"

say() { printf '\n=== %s ===\n' "$1" | tee -a "$LOG"; }
run() { printf '+ %s\n' "$*" | tee -a "$LOG"; "$@" 2>&1 | tee -a "$LOG"; }

printf '\n########## pipeline start %s ##########\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"

if [ ! -x "$PYTHON" ]; then
  echo "Python not found at $PYTHON. Set PYTHON=... or activate the env." >&2
  exit 1
fi

# ---------------------------------------------------------------- 1. materialise
if [ "$STAGE" = all ] || [ "$STAGE" = prep ]; then
  say "1/6 re-materialising evicted checkpoints (iCloud eviction)"
  # Reading a dataless file forces macOS to fetch it. Parallel to keep it quick.
  find results \( -name '*.pt' -o -name '*.onnx' \) -print0 \
    | xargs -0 -P 4 -n 1 -I{} sh -c 'cat "{}" > /dev/null 2>&1 || echo "still unreadable: {}"' \
    | tee -a "$LOG"

  say "2/6 verifying every checkpoint is readable"
  if ! run "$PYTHON" scripts/check_materialized.py --probe \
        --output "$OUT/materialization_report.json"; then
    echo "Checkpoints are still unreadable. Turn off System Settings > Apple Account >" >&2
    echo "iCloud > Optimise Mac Storage, or move this repo out of the synced Documents" >&2
    echo "tree, then re-run. Nothing downstream will work until this is clean." >&2
    exit 2
  fi

  say "3/6 extracting self-play ELO from all runs"
  run "$PYTHON" scripts/extract_selfplay_elo.py --output "$OUT/selfplay_elo.json"
fi

[ "$STAGE" = prep ] && { echo "\nPrep complete. No Unity needed so far."; exit 0; }

# ---------------------------------------------------------------- 4. timing probe
if [ "$STAGE" = all ]; then
  say "4/6 timing one evaluation cell (30 episodes)"
  START=$(date +%s)
  run "$PYTHON" scripts/evaluate_policy.py \
    --manifest configs/experiment_manifests/exp_seen_eval_no_assist_seed42.yaml \
    --source-run-id LB_3v2_official_seed42_stage4 \
    --source-results-dir results \
    --output-dir results/tournament_timing_probe \
    --eval-run-id LBT_TIMING_PROBE \
    --seed 42 --target-episodes 30 --max-runtime-seconds 900 \
    --env "$ENV_BUILD" --allow-cpu --no-graphics --deterministic --force-output
  ELAPSED=$(( $(date +%s) - START ))
  printf 'cell wall clock: %ss for 30 episodes (%.1f s/episode)\n' \
    "$ELAPSED" "$(echo "$ELAPSED / 30" | bc -l)" | tee -a "$LOG"
  printf 'projected: cross-seed 25x300ep ~%s h, within-seed 720x30ep ~%s h (single stream)\n' \
    "$(echo "$ELAPSED / 30 * 300 * 25 / 3600" | bc -l | cut -c1-4)" \
    "$(echo "$ELAPSED * 720 / 3600" | bc -l | cut -c1-4)" | tee -a "$LOG"
fi

# ---------------------------------------------------------------- 5. primary matrix
say "5/6 cross-seed matrix (primary, 25 cells x 300 episodes)"
run "$PYTHON" scripts/run_snapshot_tournament.py \
  --matrix cross-seed --env "$ENV_BUILD" --allow-cpu --no-graphics \
  --resume-completed --base-port 5010

run "$PYTHON" scripts/analyze_tournament.py --matrix cross-seed

[ "$STAGE" = cross ] && { echo "\nPrimary matrix complete. See $OUT/analysis_cross_seed.json"; exit 0; }

# ---------------------------------------------------------------- 6. rest
say "6/6 collapse probe (2 cells) then within-seed matrix (720 cells x 30 episodes)"
run "$PYTHON" scripts/run_snapshot_tournament.py \
  --matrix collapse-probe --env "$ENV_BUILD" --allow-cpu --no-graphics \
  --resume-completed --base-port 5015 || echo "collapse probe failed; continuing"

# Four shards on distinct ports. Each shard is independently resumable.
for i in 1 2 3 4; do
  PORT=$(( 5020 + (i - 1) * 10 ))
  "$PYTHON" scripts/run_snapshot_tournament.py \
    --matrix within-seed --shard "$i/4" --base-port "$PORT" \
    --env "$ENV_BUILD" --allow-cpu --no-graphics --resume-completed \
    >> "$OUT/within_seed_shard$i.log" 2>&1 &
  echo "launched shard $i/4 on port $PORT (log: $OUT/within_seed_shard$i.log)" | tee -a "$LOG"
done
wait

say "aggregating within-seed payoff matrix"
run "$PYTHON" scripts/run_snapshot_tournament.py --matrix within-seed --resume-completed
run "$PYTHON" scripts/analyze_tournament.py --matrix within-seed

say "pipeline complete"
echo "Results in $OUT/" | tee -a "$LOG"
