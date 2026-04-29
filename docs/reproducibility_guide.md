# Reproducibility Guide

This project uses run metadata, config snapshots, and run-scoped logs to make training and evaluation reproducible.

## Canonical Reproducibility Inputs

For every official run, preserve:

- run ID
- seed
- trainer config
- environment config
- reward config
- curriculum config
- scene name
- git commit hash
- exact command used to launch the run
- model or checkpoint reference
- generated KPI files
- generated official summary files

## Training Snapshot Flow

Use:

```bash
python scripts/train_with_metadata.py \
  --manifest configs/experiment_manifests/exp_dynamicmaze_shared_seed42.yaml \
  --force \
  --torch-device cuda
```

This wrapper writes:

- `results/<run_id>/metadata/run_metadata.json`
- `results/<run_id>/metadata/config_snapshots/`
- `results/<run_id>/metadata/reproduce.sh`

The snapshot records:

- config file paths
- SHA256 hashes of copied config snapshots
- git commit hash
- dirty worktree status
- exact launch command

## Evaluation Snapshot Flow

Use:

```bash
python scripts/evaluate_policy.py \
  --manifest configs/experiment_manifests/exp_unseen_eval_seed101.yaml \
  --source-run-id LB_3v2_dynamicmaze_gpu_seed42_v1
```

Evaluation should write:

- `results/seed_<seed>/eval/<run_id>/metadata/run_metadata.json`
- `results/seed_<seed>/eval/<run_id>/metadata/evaluation_metadata.json`
- `results/seed_<seed>/eval/<run_id>/logs/`
- `results/seed_<seed>/eval/<run_id>/kpi/`

Evaluation should remain deterministic and learning-disabled.

## Official Summary Regeneration

Derived summaries should be regenerated from raw run logs and KPI files, not edited manually.

Primary rebuild paths:

- `scripts/build_official_summary_reports.py`
- `scripts/build_paper_ready_outputs.py`
- `scripts/summarize_eval_kpis.py`

The official seen/unseen aggregate should come from:

- `results/seed_42/eval/LB_3v2_seen_unseen_eval_official_v1_seed42_seen_30m/`
- `results/seed_42/eval/LB_3v2_seen_unseen_eval_official_v1_seed42_unseen_30m/`
- `results/seed_101/eval/LB_3v2_seen_unseen_eval_official_v1_seed101_seen_30m/`
- `results/seed_101/eval/LB_3v2_seen_unseen_eval_official_v1_seed101_unseen_30m/`
- `results/seed_202/eval/LB_3v2_seen_unseen_eval_official_v1_seed202_seen_30m/`
- `results/seed_202/eval/LB_3v2_seen_unseen_eval_official_v1_seed202_unseen_30m/`

## Never Edit Manually

- `results/<run_id>/logs/*.csv`
- `results/<run_id>/metadata/*.json`
- `results/<run_id>/Runner/*.onnx`
- `results/<run_id>/Sentinel/*.onnx`
- `results/<run_id>/Runner/checkpoint.pt`
- `results/<run_id>/Sentinel/checkpoint.pt`

## Validation Before Publishing

Run:

```bash
python scripts/validate_run_provenance.py
```

The validator should fail on:

- run ID mismatch
- seed mismatch
- reward config mismatch
- scene mismatch
- behavior name mismatch
- missing config snapshots
- missing official evaluation artifacts
