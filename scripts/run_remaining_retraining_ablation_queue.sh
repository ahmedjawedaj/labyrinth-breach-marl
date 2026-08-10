#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(dirname -- "$SCRIPT_DIR")
PYTHON=/opt/anaconda3/envs/labyrinth-breach/bin/python
ENV_PATH=builds/macos/LabyrinthBreach.app
FULL_EVAL_DIR=results/publication_eval_official
ABLATION_ROOT=results/ablations
SUMMARY_ROOT=results/official_summary/ablations
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/remaining_retraining_ablation_queue.log"

mkdir -p "$LOG_DIR" "$ROOT/results/orchestration"
cd "$ROOT"

log() {
  printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "$LOG_FILE"
}

run_cmd() {
  log "running: $*"
  "$@" 2>&1 | tee -a "$LOG_FILE"
}

memory_repair_screens_active() {
  /opt/homebrew/bin/screen -ls 2>/dev/null | grep -Eq 'lb_memory101|lb_memory_rest'
}

mlagents_jobs_active() {
  pgrep -fl 'mlagents-learn|LabyrinthBreach\.app|scripts/train_with_metadata\.py|run_memory_off_stage4' >/dev/null 2>&1
}

wait_for_current_memory_repairs() {
  log "waiting for active memory-off repair screens and ML-Agents jobs"
  while memory_repair_screens_active || mlagents_jobs_active
  do
    "$PYTHON" scripts/monitor_publication_evidence_gates.py 2>&1 | tee -a "$LOG_FILE" || true
    sleep 900
  done
  log "no active memory-off repair screen or ML-Agents job detected"
  sleep 60
  if memory_repair_screens_active || mlagents_jobs_active
  then
    log "training restarted during settle window, returning to wait"
    wait_for_current_memory_repairs
  fi
}

track_condition() {
  condition_id=$1
  training_matrix=$2
  eval_matrix=$3
  run_cmd "$PYTHON" scripts/seed_completion_tracker.py \
    --training-matrix-manifest "$training_matrix" \
    --eval-matrix-manifest "$eval_matrix" \
    --results-dir results \
    --eval-results-dir "$ABLATION_ROOT/$condition_id" \
    --output-dir "$SUMMARY_ROOT/${condition_id}_tracker"
}

evaluate_condition() {
  condition_id=$1
  eval_matrix=$2
  base_port=$3
  run_cmd "$PYTHON" scripts/run_publication_eval_matrix.py \
    --matrix "$eval_matrix" \
    --source-results-dir results \
    --results-dir "$ABLATION_ROOT/$condition_id" \
    --env "$ENV_PATH" \
    --allow-cpu \
    --no-graphics \
    --resume-completed \
    --base-port "$base_port"
}

analyze_condition() {
  condition_id=$1
  run_cmd "$PYTHON" scripts/analyze_paired_ablation.py \
    --full-aggregate "$FULL_EVAL_DIR/aggregate/publication_eval_summary.csv" \
    --full-results-dir "$FULL_EVAL_DIR" \
    --ablated-aggregate "$ABLATION_ROOT/$condition_id/aggregate/publication_eval_summary.csv" \
    --ablated-results-dir "$ABLATION_ROOT/$condition_id" \
    --ablation-id "$condition_id" \
    --output-dir "$SUMMARY_ROOT/$condition_id"
}

train_condition() {
  condition_id=$1
  training_matrix=$2
  base_port=$3
  log "starting retraining ablation: $condition_id"
  run_cmd "$PYTHON" scripts/run_multiseed_curriculum.py \
    --matrix-manifest "$training_matrix" \
    --results-dir results \
    --base-port "$base_port" \
    --resume-completed \
    --force \
    --env "$ENV_PATH" \
    --allow-cpu \
    --no-graphics
}

run_retrain_condition() {
  condition_id=$1
  training_matrix=$2
  eval_matrix=$3
  train_port=$4
  eval_port=$5
  train_condition "$condition_id" "$training_matrix" "$train_port"
  evaluate_condition "$condition_id" "$eval_matrix" "$eval_port"
  analyze_condition "$condition_id"
  track_condition "$condition_id" "$training_matrix" "$eval_matrix"
}

log "remaining retraining ablation queue started"
wait_for_current_memory_repairs

evaluate_condition \
  memory_off \
  configs/experiment_manifests/official_memory_off_eval_matrix.yaml \
  5110
analyze_condition memory_off
track_condition \
  memory_off \
  configs/experiment_manifests/official_memory_off_aligned_matrix.yaml \
  configs/experiment_manifests/official_memory_off_eval_matrix.yaml

run_retrain_condition \
  tactical_reward_off \
  configs/experiment_manifests/official_tactical_off_aligned_matrix.yaml \
  configs/experiment_manifests/official_tactical_reward_off_eval_matrix.yaml \
  5210 \
  5220

run_retrain_condition \
  direct_dynamic_training \
  configs/experiment_manifests/official_direct_dynamic_matrix.yaml \
  configs/experiment_manifests/official_direct_dynamic_training_eval_matrix.yaml \
  5310 \
  5320

run_cmd "$PYTHON" scripts/audit_publication_evidence_gates.py
log "remaining retraining ablation queue completed"
