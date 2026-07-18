#!/bin/sh
set -eu

if [ "$#" -lt 3 ]; then
  echo "usage: $0 LABEL BASE_PORT SEED [SEED ...]" >&2
  exit 2
fi

LABEL=$1
BASE_PORT=$2
shift 2

case "$LABEL" in
  *[!A-Za-z0-9_]*)
    echo "LABEL may contain only letters, digits, and underscores" >&2
    exit 2
    ;;
esac

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(dirname -- "$SCRIPT_DIR")
PYTHON=/opt/anaconda3/envs/labyrinth-breach/bin/python
STATUS_FILE="$ROOT/results/orchestration/canonical_eval_${LABEL}.status"
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
mkdir -p results/orchestration
printf 'running\n' > "$STATUS_FILE"

"$PYTHON" scripts/run_publication_eval_matrix.py \
  --matrix configs/experiment_manifests/official_publication_eval_matrix.yaml \
  --seeds "$@" \
  --source-results-dir results \
  --results-dir results/publication_eval_official \
  --base-port "$BASE_PORT" \
  --resume-completed \
  --skip-finalize \
  --env builds/macos/LabyrinthBreach.app \
  --allow-cpu \
  --no-graphics

COMPLETED=1
exit 0
