# Canonical Repository Map

## Canonical Active Tree

- Unity runtime source: `unity/Assets/...`
- Configuration source: `configs/...`
- Training and evaluation scripts: `scripts/...`
- Documentation: `docs/...`

## Deprecated or Legacy Mirrors

- `unity/Scenes/`
- `unity/Prefabs/`
- `unity/Scripts/`
- `unity/Materials/`

These were duplicated root-level mirrors and are now isolated under:

- `unity/_deprecated_duplicate_tree/`

## Accidental / Noncanonical Project

- `Labyrinth-Breach/New Unity Project/`

This is a nested Unity project artifact and is not the canonical project root.

## Results Classification

- raw run artifacts: `results/<run_id>/`
- raw logs: `results/<run_id>/logs/`
- metadata: `results/<run_id>/metadata/`
- training status: `results/<run_id>/metadata/training_status.json`
- publication eval runs: `results/publication_eval_official/policy_seed_<seed>/<eval_run_id>/`
- official derived summaries: `results/official_summary/`
- publication evaluation aggregates: `results/publication_eval_official/aggregate/`
- strict completion tracker: `results/LB_3v2_curriculum_official_v1/completion/`

## Documentation Alignment

The canonical path references are described in:

- `docs/repo_structure.md`
- `docs/canonical_paths.md`
- `docs/reproducibility_guide.md`
