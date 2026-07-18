#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(dirname -- "$SCRIPT_DIR")
PYTHON=/opt/anaconda3/envs/labyrinth-breach/bin/python
STATUS_FILE="$ROOT/results/orchestration/canonical_eval.status"
COMPLETED=0
ENV_PATH=builds/macos/LabyrinthBreach.app
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
mkdir -p results/orchestration
printf 'running\n' > "$STATUS_FILE"

"$PYTHON" scripts/run_publication_eval_matrix.py \
  --matrix configs/experiment_manifests/official_publication_eval_matrix.yaml \
  --source-results-dir results \
  --results-dir results/publication_eval_official \
  --base-port 5064 \
  --resume-completed \
  --env "$ENV_PATH" \
  --allow-cpu \
  --no-graphics

COMPLETED=1
exit 0
