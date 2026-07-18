#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(dirname -- "$SCRIPT_DIR")
WORKER_BASE=${LABYRINTH_WORKER_BASE:-"$(dirname -- "$ROOT")/labyrinth-breach-workers"}
PYTHON=/opt/anaconda3/envs/labyrinth-breach/bin/python
ORCHESTRATION_DIR="$ROOT/results/orchestration"

cd "$ROOT"
mkdir -p "$ORCHESTRATION_DIR"

pids=""
for assignment in 42:5014 101:5024 202:5034 606:5044 707:5054; do
  seed=${assignment%%:*}
  port=${assignment##*:}
  worker="$WORKER_BASE/seed${seed}"
  log="$ORCHESTRATION_DIR/publication_seed_${seed}.log"
  (
    cd "$worker"
    /bin/sh scripts/run_publication_seed_worker.sh "$seed" "$port"
  ) > "$log" 2>&1 &
  pid=$!
  pids="$pids $pid:$seed"
  printf '%s\n' "$pid" > "$ORCHESTRATION_DIR/publication_seed_${seed}.pid"
  printf 'running\n' > "$ORCHESTRATION_DIR/publication_seed_${seed}.status"
done

failed=0
for item in $pids; do
  pid=${item%%:*}
  seed=${item##*:}
  if wait "$pid"; then
    printf 'complete\n' > "$ORCHESTRATION_DIR/publication_seed_${seed}.status"
  else
    printf 'failed\n' > "$ORCHESTRATION_DIR/publication_seed_${seed}.status"
    failed=1
  fi
done

if [ "$failed" -ne 0 ]; then
  echo "At least one publication worker failed; finalization was not run." >&2
  exit 1
fi

"$PYTHON" scripts/analyze_official_training_curves.py

finalize_eval() {
  matrix=$1
  output=$2
  "$PYTHON" scripts/run_publication_eval_matrix.py \
    --matrix "$matrix" \
    --source-results-dir results \
    --results-dir "$output" \
    --aggregate-only
}

finalize_eval \
  configs/experiment_manifests/official_publication_eval_matrix.yaml \
  results/publication_eval_official
finalize_eval \
  configs/experiment_manifests/official_memory_off_eval_matrix.yaml \
  results/ablations/memory_off
finalize_eval \
  configs/experiment_manifests/official_tactical_reward_off_eval_matrix.yaml \
  results/ablations/tactical_reward_off
finalize_eval \
  configs/experiment_manifests/official_direct_dynamic_training_eval_matrix.yaml \
  results/ablations/direct_dynamic_training
finalize_eval \
  configs/experiment_manifests/official_action_assist_on_eval_matrix.yaml \
  results/ablations/action_assist_on
finalize_eval \
  configs/experiment_manifests/official_dynamic_wall_off_eval_matrix.yaml \
  results/ablations/dynamic_wall_off

FULL_AGGREGATE=results/publication_eval_official/aggregate/publication_eval_summary.csv
for condition in memory_off tactical_reward_off direct_dynamic_training action_assist_on dynamic_wall_off; do
  "$PYTHON" scripts/analyze_paired_ablation.py \
    --full-aggregate "$FULL_AGGREGATE" \
    --full-results-dir results/publication_eval_official \
    --ablated-aggregate "results/ablations/$condition/aggregate/publication_eval_summary.csv" \
    --ablated-results-dir "results/ablations/$condition" \
    --ablation-id "$condition" \
    --output-dir "results/official_summary/ablations/$condition"
done

"$PYTHON" scripts/seed_completion_tracker.py
"$PYTHON" scripts/summarize_publication_campaign.py
"$PYTHON" scripts/audit_publication_readiness.py
"$PYTHON" scripts/build_publication_evidence_pack.py --force
printf 'status=complete\n' > "$ORCHESTRATION_DIR/remaining_gates.status"
