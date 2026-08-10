#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"
export PATH="/opt/anaconda3/envs/labyrinth-breach/bin:${PATH}"

exec /opt/anaconda3/envs/labyrinth-breach/bin/python scripts/train_with_metadata.py \
  --manifest configs/experiment_manifests/exp_memory_off_stage4_aligned.yaml \
  --seed 101 \
  --run-id LB_3v2_memory_off_seed101_stage4 \
  --results-dir results \
  --experiment-family LB_3v2_memory_off_official_v2 \
  --matrix-stage-id stage4 \
  --matrix-stage-order 4 \
  --matrix-total-stages 4 \
  --initialize-from LB_3v2_memory_off_seed101_stage3 \
  --resume \
  --no-graphics \
  --env builds/macos/LabyrinthBreach.app \
  --allow-cpu
