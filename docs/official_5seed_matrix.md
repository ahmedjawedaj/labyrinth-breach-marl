# Official 5-Seed Curriculum Matrix

The official training stability family is defined in:

- `configs/experiment_manifests/official_curriculum_matrix.yaml`

It encodes:

- Seeds: `42`, `101`, `202`, `606`, `707`
- Stages: `stage1`, `stage2`, `stage3`, `stage4`
- Deterministic run naming: `{experiment_family}_seed{seed}_{stage_id}`
- Fixed trainer-step budgets (`stop_condition_policy: fixed_trainer_step_budget`)
- Checkpoint transfer for both role policies between consecutive stages

## Run the official matrix

```bash
python scripts/run_multiseed_curriculum.py \
  --resume-completed \
  --env builds/macos/LabyrinthBreach.app \
  --allow-cpu \
  --no-graphics
```

Do not run metadata-only mode while a training player is active because runtime
override files are process-global for the standalone.

## Outputs for audit

- Per-run metadata:
  - `results/<run_id>/metadata/run_metadata.json`
  - `results/<run_id>/metadata/training_status.json`
  - `results/<run_id>/metadata/training_audit.json`
  - includes `experiment_family`, `matrix_stage_id`, `matrix_stage_order`, `matrix_total_stages`
- Matrix completion tracker:
  - `results/<experiment_family>/matrix/matrix_status.json`
  - `results/<experiment_family>/matrix/matrix_status.csv`

If any run fails, execution stops immediately and `matrix_status` is written
with completed, failed, and pending runs.
