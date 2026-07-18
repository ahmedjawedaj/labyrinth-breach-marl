#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(dirname -- "$SCRIPT_DIR")
cd "$ROOT"

PATH=/opt/anaconda3/envs/labyrinth-breach/bin:/usr/local/bin:/usr/bin:/bin
export PATH

exec /opt/anaconda3/envs/labyrinth-breach/bin/python \
  scripts/run_multiseed_curriculum.py "$@"
