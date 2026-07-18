#!/bin/sh
set -eu

if [ "$#" -lt 5 ]; then
  echo "usage: $0 LABEL BASE_PORT MATRIX RESULTS_DIR SEED [SEED ...]" >&2
  exit 2
fi

LABEL=$1
BASE_PORT=$2
MATRIX=$3
RESULTS_DIR=$4
shift 4

case "$LABEL" in
  *[!A-Za-z0-9_]*)
    echo "LABEL may contain only letters, digits, and underscores" >&2
    exit 2
    ;;
esac

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(dirname -- "$SCRIPT_DIR")
PYTHON=/opt/anaconda3/envs/labyrinth-breach/bin/python
STATUS_FILE="$ROOT/results/orchestration/eval_shard_${LABEL}.status"
PATH=/opt/anaconda3/envs/labyrinth-breach/bin:/usr/local/bin:/usr/bin:/bin
COMPLETED=0
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
  --matrix "$MATRIX" \
  --seeds "$@" \
  --source-results-dir results \
  --results-dir "$RESULTS_DIR" \
  --base-port "$BASE_PORT" \
  --resume-completed \
  --skip-finalize \
  --env builds/macos/LabyrinthBreach.app \
  --allow-cpu \
  --no-graphics

COMPLETED=1
exit 0
