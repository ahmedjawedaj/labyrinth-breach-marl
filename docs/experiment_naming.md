# Experiment Naming

## Purpose

Experiment names must be deterministic, descriptive, and easy to compare. Every training and evaluation run should have a unique run ID that captures the major experimental variables.

## Format

Use this format:

```text
LB_3v2_<environment>_<reward_or_ablation>_seed<seed>_v<version>
```

Example:

```text
LB_3v2_dynamicmaze_memory_seed17_v1
```

## Components

`LB`

- Project prefix for Labyrinth Breach.

`3v2`

- Team setup: 3 Sentinels vs 2 Runners.

`environment`

- Environment or scene family.
- Examples: `open`, `staticmaze`, `dynamicmaze`, `unseen`.

`reward_or_ablation`

- Reward version or experiment condition.
- Examples: `shared`, `trapaware`, `memory`, `nomemory`, `hybrid`.

`seed`

- Random seed used for training or evaluation.
- Example: `seed42`.

`version`

- Experiment definition version.
- Example: `v1`, `v2`.

## Examples

```text
LB_3v2_open_shared_seed42_v1
LB_3v2_staticmaze_shared_seed42_v1
LB_3v2_dynamicmaze_shared_seed42_v1
LB_3v2_dynamicmaze_trapaware_seed42_v1
LB_3v2_dynamicmaze_nomemory_seed42_v1
LB_3v2_unseen_trapaware_seed17_v1
```

## Manifest Requirements

Each experiment manifest should include:

- `run_id`
- `seed`
- `scene`
- `env_config`
- `reward_config`
- `trainer_config`
- `curriculum_stage`
- `commit_hash`
- `artifact_uri`
- `notes`

## Rules

- Do not reuse a run ID for a different experiment.
- Increment the version when the experiment definition changes.
- Keep seed values explicit.
- Store the run ID in logs, checkpoints, metrics, and plots.
- Use the same run ID across training, evaluation, and paper artifacts.

