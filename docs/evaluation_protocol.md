# Evaluation Protocol

## Purpose

Evaluation measures whether trained policies learned robust pursuit-evasion tactics or only memorized specific layouts and reward shortcuts.

Evaluation must be separate from training. Policies are fixed during evaluation and no learning should occur.

## Evaluation Sets

Run evaluations on:

- open arena baseline
- seen static maze
- seen dynamic maze
- unseen maze seeds
- harder maze density variants
- memory-disabled ablation
- trap-reward-disabled ablation

The key comparison is seen versus unseen maze performance.

## Core Metrics

Core outcome metrics:

- Sentinel win rate
- Runner win rate
- average time to first capture
- average time to full capture
- exit success rate
- survival time per Runner

## Coordination Metrics

Coordination metrics:

- pincer success rate
- trap frequency
- average Sentinel spread
- average Runner separation
- corridor block event count
- exit denial event count

These metrics are required because win rate alone does not prove coordinated behavior.

## Path Metrics

Path metrics:

- path efficiency to exit
- shortest path vs actual path ratio
- route changes after wall shifts

For dynamic mazes, path metrics should account for wall shifts changing available routes.

## Generalization Metrics

Generalization metrics:

- seen maze win rate
- unseen maze win rate
- performance drop on unseen maps

The goal is to identify whether policies learn tactics that transfer or simply memorize training layouts.

## Evaluation Procedure

For each evaluation run:

1. Load trained policy.
2. Disable learning.
3. Set deterministic seed.
4. Select evaluation scene and environment config.
5. Run the configured number of episodes.
6. Export per-step logs and per-episode summaries.
7. Calculate metrics.
8. Generate tables and plots.

Each evaluation output must record:

- run ID
- model checkpoint or policy identifier
- environment config
- reward config
- trainer config
- seed
- maze ID
- commit hash

## Required Outputs

Evaluation should produce:

- metric CSV or JSON files
- summary tables
- plots for paper figures
- selected qualitative screenshots or videos
- experiment manifests linking results to configs
