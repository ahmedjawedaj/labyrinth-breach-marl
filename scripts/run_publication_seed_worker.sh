#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: $0 SEED BASE_PORT" >&2
  exit 2
fi

SEED=$1
BASE_PORT=$2
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(dirname -- "$SCRIPT_DIR")
PYTHON=/opt/anaconda3/envs/labyrinth-breach/bin/python
ENV_PATH=builds/macos/LabyrinthBreach.app
STATUS_DIR=worker_status/seed${SEED}
PATH=/opt/anaconda3/envs/labyrinth-breach/bin:/usr/local/bin:/usr/bin:/bin
export PATH

cd "$ROOT"
mkdir -p "$STATUS_DIR"

run_training_matrix() {
  matrix=$1
  "$PYTHON" scripts/run_multiseed_curriculum.py \
    --matrix-manifest "$matrix" \
    --seeds "$SEED" \
    --results-dir results \
    --matrix-status-dir "$STATUS_DIR" \
    --base-port "$BASE_PORT" \
    --resume-completed \
    --force \
    --env "$ENV_PATH" \
    --allow-cpu \
    --no-graphics
}

run_eval_shard() {
  matrix=$1
  output=$2
  "$PYTHON" scripts/run_publication_eval_matrix.py \
    --matrix "$matrix" \
    --seeds "$SEED" \
    --source-results-dir results \
    --results-dir "$output" \
    --base-port "$BASE_PORT" \
    --resume-completed \
    --skip-finalize \
    --env "$ENV_PATH" \
    --allow-cpu \
    --no-graphics
}

run_training_matrix configs/experiment_manifests/official_curriculum_matrix.yaml
run_training_matrix configs/experiment_manifests/official_memory_off_aligned_matrix.yaml
run_training_matrix configs/experiment_manifests/official_tactical_off_aligned_matrix.yaml
run_training_matrix configs/experiment_manifests/official_direct_dynamic_matrix.yaml

run_eval_shard \
  configs/experiment_manifests/official_publication_eval_matrix.yaml \
  results/publication_eval_official
run_eval_shard \
  configs/experiment_manifests/official_memory_off_eval_matrix.yaml \
  results/ablations/memory_off
run_eval_shard \
  configs/experiment_manifests/official_tactical_reward_off_eval_matrix.yaml \
  results/ablations/tactical_reward_off
run_eval_shard \
  configs/experiment_manifests/official_direct_dynamic_training_eval_matrix.yaml \
  results/ablations/direct_dynamic_training
run_eval_shard \
  configs/experiment_manifests/official_action_assist_on_eval_matrix.yaml \
  results/ablations/action_assist_on
run_eval_shard \
  configs/experiment_manifests/official_dynamic_wall_off_eval_matrix.yaml \
  results/ablations/dynamic_wall_off

printf 'seed=%s\nbase_port=%s\nstatus=complete\n' "$SEED" "$BASE_PORT" > "$STATUS_DIR/COMPLETE"
