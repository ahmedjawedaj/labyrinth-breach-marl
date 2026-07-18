#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(dirname -- "$SCRIPT_DIR")
WORKER_BASE=${LABYRINTH_WORKER_BASE:-"$(dirname -- "$ROOT")/labyrinth-breach-workers"}
STATUS_FILE="$ROOT/results/orchestration/seed42_stage4_recovery.status"
ORCHESTRATION_DIR="$ROOT/results/orchestration"

cd "$ROOT"
mkdir -p "$ORCHESTRATION_DIR"
printf 'waiting_for_seed42_recovery\n' > "$ORCHESTRATION_DIR/seed42_eval_handoff.status"

while :; do
  if [ -f "$STATUS_FILE" ] && [ "$(tail -n 1 "$STATUS_FILE")" = "complete" ]; then
    break
  fi
  sleep 300
done

launch_eval() {
  label=$1
  worker=$2
  port=$3
  matrix=$4
  results_dir=$5
  screen_name=$6
  log="$ORCHESTRATION_DIR/eval_shard_${label}.log"
  screen -dmS "$screen_name" sh -lc "cd '$worker' && /bin/sh scripts/run_eval_matrix_shard.sh '$label' '$port' '$matrix' '$results_dir' 42 > '$log' 2>&1"
}

printf 'launching_seed42_evals\n' > "$ORCHESTRATION_DIR/seed42_eval_handoff.status"

launch_eval \
  canonical42 \
  "$WORKER_BASE/eval42canon" \
  5124 \
  configs/experiment_manifests/official_publication_eval_matrix.yaml \
  results/publication_eval_official \
  labyrinth-eval-seed42-canonical

launch_eval \
  assist42 \
  "$WORKER_BASE/eval42assist" \
  5134 \
  configs/experiment_manifests/official_action_assist_on_eval_matrix.yaml \
  results/ablations/action_assist_on \
  labyrinth-eval-seed42-assist

launch_eval \
  wall42 \
  "$WORKER_BASE/eval42wall" \
  5144 \
  configs/experiment_manifests/official_dynamic_wall_off_eval_matrix.yaml \
  results/ablations/dynamic_wall_off \
  labyrinth-eval-seed42-wall

printf 'launched_seed42_evals\n' > "$ORCHESTRATION_DIR/seed42_eval_handoff.status"
