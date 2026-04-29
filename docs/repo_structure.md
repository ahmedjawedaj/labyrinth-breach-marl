# Repository Structure

This repository is organized around a single canonical Unity source tree:

- `unity/Assets/...`

That tree contains the active scenes, prefabs, scripts, materials, scriptable objects, and ML-Agents assets used by training and evaluation.

## Canonical Layout

- `unity/Assets/Scenes/`
  - active Unity scenes
  - includes `01_Baseline_OpenArena_3v2`, `02_StaticMaze_3v2`, `03_DynamicMaze_3v2`, `04_Eval_UnseenMaze_3v2`
- `unity/Assets/Prefabs/`
  - active Sentinel and Runner prefabs
- `unity/Assets/Scripts/`
  - runtime agents, environment, sensing, rewards, logging, debug visuals
- `unity/Assets/Materials/`
  - active scene and agent materials
- `configs/`
  - trainer, environment, reward, curriculum, and experiment manifests
- `scripts/`
  - training, evaluation, validation, summary, and provenance helpers
- `results/`
  - run-scoped metadata, logs, checkpoints, KPI outputs, and derived summaries
- `docs/`
  - project, reproduction, evaluation, cleanup, and audit documentation
- `paper/`
  - paper assets and draft material
- `media/`
  - screenshots, figures, demo captures, and presentation assets
- `experiments/`
  - reserved for experiment organization notes and future manifests

## Deprecated or Noncanonical Paths

- `unity/_deprecated_duplicate_tree/`
  - legacy mirrors of pre-cleanup top-level Unity folders
  - not part of the active runtime source tree
- `Labyrinth-Breach/New Unity Project/`
  - accidental nested Unity project artifact
  - isolated from the active repo flow and should not be used as the canonical project root

## What Should Not Be Edited Manually

- raw run artifacts under `results/<run_id>/logs/`
- run metadata under `results/<run_id>/metadata/`
- ONNX exports and checkpoints under `results/<run_id>/`
- summary CSV/JSON files under `results/official_summary/` unless regenerating them from the scripts

## What Can Be Regenerated

- official summary CSV/JSON outputs
- derived KPI tables and plots
- provenance validation reports
- evaluation summaries generated from raw logs and KPI JSON files

## Canonical Workflow

1. edit sources under `unity/Assets/...`
2. edit configs under `configs/...`
3. run training or evaluation through `scripts/train_with_metadata.py` or `scripts/evaluate_policy.py`
4. collect run-scoped logs into `results/<run_id>/...`
5. regenerate derived summaries with the reporting scripts
6. validate provenance before publishing or citing results
