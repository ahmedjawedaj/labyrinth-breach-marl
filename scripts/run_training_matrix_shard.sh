#!/bin/sh
set -eu

if [ "$#" -lt 4 ]; then
  echo "usage: $0 LABEL MATRIX_MANIFEST BASE_PORT SEED [SEED ...]" >&2
  exit 2
fi

LABEL=$1
MATRIX=$2
BASE_PORT=$3
shift 3

case "$LABEL" in
  *[!A-Za-z0-9_]*)
    echo "LABEL may contain only letters, digits, and underscores" >&2
    exit 2
    ;;
esac

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(dirname -- "$SCRIPT_DIR")
PYTHON=/opt/anaconda3/envs/labyrinth-breach/bin/python
ENV_PATH=builds/macos/LabyrinthBreach.app
STATUS_DIR="worker_status/shards/$LABEL"
STATUS_FILE="$ROOT/results/orchestration/training_shard_${LABEL}.status"
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
mkdir -p "$STATUS_DIR" results/orchestration
printf 'running\n' > "$STATUS_FILE"

"$PYTHON" scripts/run_multiseed_curriculum.py \
  --matrix-manifest "$MATRIX" \
  --seeds "$@" \
  --results-dir results \
  --matrix-status-dir "$STATUS_DIR" \
  --base-port "$BASE_PORT" \
  --resume-completed \
  --force \
  --env "$ENV_PATH" \
  --allow-cpu \
  --no-graphics

COMPLETED=1
exit 0
