#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(dirname -- "$SCRIPT_DIR")
PYTHON=/opt/anaconda3/envs/labyrinth-breach/bin/python
STATUS_FILE="$ROOT/results/orchestration/seed42_stage4_recovery.status"
COMPLETED=0
PATH=/opt/anaconda3/envs/labyrinth-breach/bin:/usr/local/bin:/usr/bin:/bin
export PATH

finish() {
  rc=$?
  trap - EXIT
  if [ "$rc" -eq 0 ] && [ "$COMPLETED" -eq 1 ]; then
    printf 'complete\n' > "$STATUS_FILE"
  else
    printf 'interrupted_or_failed:%s\n' "$rc" > "$STATUS_FILE"
  fi
  exit "$rc"
}
trap finish EXIT

cd "$ROOT"
mkdir -p results/orchestration worker_status/recovery_seed42
printf 'running\n' > "$STATUS_FILE"

"$PYTHON" scripts/run_multiseed_curriculum.py \
  --matrix-manifest configs/experiment_manifests/official_curriculum_matrix.yaml \
  --seeds 42 \
  --results-dir results \
  --matrix-status-dir worker_status/recovery_seed42 \
  --base-port 5074 \
  --resume-completed \
  --force \
  --env builds/macos/LabyrinthBreach.app \
  --allow-cpu \
  --no-graphics

"$PYTHON" scripts/analyze_official_training_curves.py
"$PYTHON" scripts/summarize_publication_campaign.py

COMPLETED=1
exit 0
