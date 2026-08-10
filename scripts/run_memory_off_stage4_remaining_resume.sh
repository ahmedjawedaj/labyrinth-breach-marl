#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"
export PATH="/opt/anaconda3/envs/labyrinth-breach/bin:${PATH}"

wait_for_training_slot() {
  while pgrep -f "mlagents-learn|LabyrinthBreach.app|MacOS/Labyrinth Breach|scripts/train_with_metadata.py" >/dev/null
  do
    date -u +"%Y-%m-%dT%H:%M:%SZ waiting for active ML-Agents job to finish"
    sleep 300
  done
}

run_seed() {
  local seed="$1"
  local run_id="LB_3v2_memory_off_seed${seed}_stage4"
  local init_id="LB_3v2_memory_off_seed${seed}_stage3"

  wait_for_training_slot
  date -u +"%Y-%m-%dT%H:%M:%SZ starting ${run_id}"
  /opt/anaconda3/envs/labyrinth-breach/bin/python scripts/train_with_metadata.py \
    --manifest configs/experiment_manifests/exp_memory_off_stage4_aligned.yaml \
    --seed "${seed}" \
    --run-id "${run_id}" \
    --results-dir results \
    --experiment-family LB_3v2_memory_off_official_v2 \
    --matrix-stage-id stage4 \
    --matrix-stage-order 4 \
    --matrix-total-stages 4 \
    --initialize-from "${init_id}" \
    --resume \
    --no-graphics \
    --env builds/macos/LabyrinthBreach.app \
    --allow-cpu
  date -u +"%Y-%m-%dT%H:%M:%SZ finished ${run_id}"
}

run_seed 202
run_seed 606
run_seed 707
