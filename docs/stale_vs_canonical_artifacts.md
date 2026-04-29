# Stale vs Canonical Artifacts

## Canonical Truth

The canonical truth for experiments is the raw run-scoped artifact set:

- `results/<run_id>/metadata/run_metadata.json`
- `results/<run_id>/run_logs/training_status.json`
- `results/<run_id>/logs/*.csv`
- `results/<run_id>/Runner/checkpoint.pt`
- `results/<run_id>/Sentinel/checkpoint.pt`
- `results/<run_id>/Runner.onnx`
- `results/<run_id>/Sentinel.onnx`

For seen/unseen evaluation, the raw truth is:

- `results/seed_<seed>/eval/LB_3v2_seen_unseen_eval_official_v1_seed<seed>_seen_30m/`
- `results/seed_<seed>/eval/LB_3v2_seen_unseen_eval_official_v1_seed<seed>_unseen_30m/`

## Derived Artifacts

Derived artifacts are safe to regenerate from the raw truth. These were regenerated in this cleanup pass and now represent the current canonical derived summaries:

- `results/official_summary/*.csv`
- `results/LB_3v2_seen_unseen_eval_official_v1/eval/final_seen_unseen_summary.*`
- `results/LB_3v2_seen_unseen_eval_official_v1/summary/multiseed_summary.csv`
- paper-ready tables and plots

## Stale or Ambiguous Artifacts Found in the Audit

- `results/official_summary/seen_unseen_comparison.csv`
  - previously blank and not regenerated from current raw evaluation logs
- `results/official_summary/multiseed_kpi_summary.csv`
  - previously referenced missing aggregate files
- top-level Unity mirrors:
  - `unity/Scenes/`
  - `unity/Prefabs/`
  - `unity/Scripts/`
  - `unity/Materials/`

The first two items above were regenerated directly from the raw `results/seed_<seed>/eval/...` logs and KPI files during this pass. The historical note is retained here for audit traceability.

## Canonical vs Archived

- canonical Unity source: `unity/Assets/...`
- archived duplicate mirrors: `unity/_deprecated_duplicate_tree/...`
- accidental nested Unity project: `Labyrinth-Breach/New Unity Project/`

## Safe Regeneration Rule

Only regenerate:

- summary CSV/JSON files
- KPI tables
- plots
- provenance reports

Do not hand-edit raw logs or model artifacts.
