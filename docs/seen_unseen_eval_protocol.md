# Seen vs Unseen Evaluation Protocol (Official)

This project now has an explicit official seen/unseen evaluation protocol:

- `configs/experiment_manifests/official_seen_unseen_eval_matrix.yaml`

## Definitions

- **Seen environment**: layout distribution used during training-style dynamic maze configuration.
  - Manifest: `configs/experiment_manifests/exp_seen_eval_seed42.yaml`
  - Scene/config path: dynamic maze evaluation on trained layout family.
- **Unseen environment**: held-out layout distribution not used in training maps.
  - Manifest: `configs/experiment_manifests/exp_unseen_eval_seed101.yaml`
  - Scene/config path: unseen maze evaluation.

## Deterministic, seed-aligned evaluation

For each official seed (`42`, `101`, `202`), the pipeline runs both:

- `seen`
- `unseen`

using the same:

- evaluation duration (`duration_minutes` in eval matrix manifest)
- deterministic inference setting (`deterministic_inference`)
- inference mode (`--resume --inference`)

## Execution

```bash
python scripts/run_seen_unseen_eval_matrix.py --no-graphics
```

## Result layout

- Per seed:
  - `results/seed_<seed>/eval/<eval_run_id>/...`
  - `results/seed_<seed>/eval/meta_evaluation.json`
  - `results/seed_<seed>/eval/seen_unseen_comparison.json`
  - `results/seed_<seed>/eval/seen_unseen_comparison.csv`
- Family aggregate:
  - `results/LB_3v2_seen_unseen_eval_official_v1/eval/final_seen_unseen_summary.json`
  - `results/LB_3v2_seen_unseen_eval_official_v1/eval/final_seen_unseen_summary.csv`
- Completion tracking:
  - `results/<training_experiment_family>/completion/seed_completion_report.json`
  - `results/<training_experiment_family>/completion/seed_completion_report.csv`

The completion tracker fails if any required metadata/artifact is missing.
