# Repository Cleanup Report

This report summarizes the controlled cleanup and consistency pass.

## Completed Changes

1. Moved duplicate Unity root mirrors out of the active source path:
   - `unity/Scenes/` -> `unity/_deprecated_duplicate_tree/Scenes/`
   - `unity/Prefabs/` -> `unity/_deprecated_duplicate_tree/Prefabs/`
   - `unity/Scripts/` -> `unity/_deprecated_duplicate_tree/Scripts/`
   - `unity/Materials/` -> `unity/_deprecated_duplicate_tree/Materials/`

2. Added canonical structure documentation:
   - `docs/repo_structure.md`
   - `docs/canonical_paths.md`

3. Added reproducibility guidance:
   - `docs/reproducibility_guide.md`

4. Added cleanup/reference documentation:
   - `docs/canonical_repo_map.md`
   - `docs/stale_vs_canonical_artifacts.md`

5. Added a provenance validation helper:
   - `scripts/validate_run_provenance.py`

6. Regeneration path updated for official summaries:
   - `scripts/build_official_summary_reports.py`
   - regenerated derived aggregates under:
     - `results/LB_3v2_seen_unseen_eval_official_v1/eval/final_seen_unseen_summary.csv`
     - `results/LB_3v2_seen_unseen_eval_official_v1/eval/final_seen_unseen_summary.json`
     - `results/LB_3v2_seen_unseen_eval_official_v1/summary/multiseed_summary.csv`
     - `results/official_summary/seen_unseen_comparison.csv`
     - `results/official_summary/multiseed_kpi_summary.csv`
     - `results/official_summary/training_completion_matrix.csv`
     - `results/official_summary/coordination_kpi_summary.csv`
     - `results/official_summary/reward_breakdown_summary.csv`
     - `results/official_summary/missing_artifacts_report.csv`

7. Added a placeholder for repository experiment organization:
   - `experiments/README.md`

8. Added an archive note for the deprecated Unity mirrors:
   - `unity/_deprecated_duplicate_tree/README.md`

9. Added a strict provenance validator:
   - `scripts/validate_run_provenance.py`
   - currently fails on real metadata/log mismatches, which is intentional so provenance gaps are not hidden

## Untouched by Design

- trained model files
- run artifacts under `results/`
- ONNX exports
- checkpoints
- Unity runtime logic under `unity/Assets/...`
- reward logic
- observation logic
- training configs
- evaluation configs

## Remaining Uncertainty

- the nested `Labyrinth-Breach/New Unity Project/` directory remains present as an ignored accidental Unity project artifact and was not moved in this pass
- some older docs still refer to legacy Unity mirror paths for historical context

## Cleanup Intent

The repository now has a clearer separation between:

- canonical source
- deprecated mirrors
- raw run truth
- derived summaries
- reproducibility metadata
