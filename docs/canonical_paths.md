# Canonical Paths

This file lists the active source paths that should be treated as canonical.

## Unity

- `unity/Assets/Scenes/`
- `unity/Assets/Prefabs/`
- `unity/Assets/Scripts/`
- `unity/Assets/Materials/`
- `unity/Assets/ScriptableObjects/`
- `unity/Assets/ML-Agents/`

## Configuration

- `configs/trainer_configs/`
- `configs/env_configs/`
- `configs/reward_configs/`
- `configs/curriculum_configs/`
- `configs/experiment_manifests/`
- `configs/runtime_overrides/`

## Scripts

- `scripts/train_with_metadata.py`
- `scripts/evaluate_policy.py`
- `scripts/build_official_summary_reports.py`
- `scripts/build_paper_ready_outputs.py`
- `scripts/summarize_eval_kpis.py`
- `scripts/validate_run_provenance.py`
- `scripts/seed_completion_tracker.py`

## Results

- raw run artifacts: `results/<run_id>/`
- raw logs: `results/<run_id>/logs/`
- run metadata: `results/<run_id>/metadata/`
- training status: `results/<run_id>/run_logs/`
- checkpoints and ONNX exports: `results/<run_id>/Runner/`, `results/<run_id>/Sentinel/`
- official family aggregate summaries: `results/LB_3v2_seen_unseen_eval_official_v1/`
- compact mirror summaries: `results/official_summary/`

## Noncanonical Paths

- `unity/Scenes/`
- `unity/Prefabs/`
- `unity/Scripts/`
- `unity/Materials/`
- `Labyrinth-Breach/New Unity Project/`

These paths are legacy or archival and should not be treated as the active source of truth.
