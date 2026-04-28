# Official 3-Seed Curriculum Matrix

The official training stability family is defined in:

- `configs/experiment_manifests/official_curriculum_matrix.yaml`

It encodes:

- Seeds: `42`, `101`, `202`
- Stages: `stage1`, `stage2`, `stage3`, `stage4`
- Deterministic run naming: `{experiment_family}_seed{seed}_{stage_id}`
- Shared stop-condition logic via stage manifests (`stop_condition_policy: stage-manifest-defined`)

## Run the official matrix

```bash
python scripts/run_multiseed_curriculum.py --force
```

Metadata-only matrix audit run (no training launch):

```bash
python scripts/run_multiseed_curriculum.py --metadata-only --force
```

## Outputs for audit

- Per-run metadata:
  - `results/<run_id>/metadata/run_metadata.json`
  - includes `experiment_family`, `matrix_stage_id`, `matrix_stage_order`, `matrix_total_stages`
- Matrix completion tracker:
  - `results/<experiment_family>/matrix/matrix_status.json`
  - `results/<experiment_family>/matrix/matrix_status.csv`

If any run fails, execution stops immediately and `matrix_status` is written with completed/failed/pending runs.
