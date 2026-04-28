# Runner Roles, Metadata Integrity, and Paper Outputs

## Task 25: Runner role emergence analysis

Run role analysis on any completed run:

```bash
python scripts/analyze_role_emergence.py \
  --run-root results/seed_42/eval/<run_id> \
  --seed 42 \
  --stage-label seen \
  --output-base results
```

Primary outputs (required path):

- `results/<seed>/runner_role_analysis/role_summary.csv`
- `results/<seed>/runner_role_analysis/role_episode_breakdown.csv`

Compatibility outputs are also written under `results/seed_<seed>/runner_role_analysis/`.

## Task 26: Metadata snapshot integrity

Metadata generation now fails if any required snapshot/config is missing.

Required metadata coverage includes:

- run_id, seed, stage_id, scene
- trainer/env/reward/curriculum/rule configs
- manifest snapshot
- git metadata and timestamp

Evaluation metadata includes:

- eval environment type (`layout_split`)
- deterministic flag
- duration/timeout settings
- model paths
- source model run id

## Task 28: Paper-ready analysis outputs

Generate report tables and plots:

```bash
python scripts/build_paper_ready_outputs.py \
  --experiment-family LB_3v2_seen_unseen_eval_official_v1
```

Outputs:

- `results/<experiment_family>/summary/multiseed_summary.csv`
- `results/<experiment_family>/summary/generalization_comparison.csv`
- `results/<experiment_family>/summary/ablation_comparison.csv`
- `results/<experiment_family>/plots/reward/`
- `results/<experiment_family>/plots/coordination/`
- `results/<experiment_family>/plots/path/`
