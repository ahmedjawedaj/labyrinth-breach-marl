# Reward Breakdown and Memory Ablation

## Per-episode reward breakdown export

Each episode now exports team-level reward breakdown rows with:

- `episode_id`
- `team`
- `total_reward`
- `terminal_reward`
- `shaping_reward`
- `trap_aware_reward`
- `exploration_reward`
- `penalties`
- `reward_breakdown` (JSON string by reward event)

Output files:

- Run-scoped: `results/<run_id>/logs/reward_breakdown.csv`
- Seed-scoped aggregate: `results/seed_<seed>/logs/reward_breakdown.csv`

## Memory on/off ablation

Official matrix manifest:

- `configs/experiment_manifests/official_memory_ablation_matrix.yaml`

Conditions:

- `memory_on`
- `memory_off`

Stages (per seed):

1. open arena fixed spawn
2. static maze random spawn
3. dynamic maze low-frequency wall shifts
4. dynamic maze high-frequency wall shifts

Outputs:

- `results/seed_<seed>/memory_on/...`
- `results/seed_<seed>/memory_off/...`
- Per-seed comparison:
  - `results/seed_<seed>/memory_ablation_comparison.json`
  - `results/seed_<seed>/memory_ablation_comparison.csv`
- Global summary:
  - `results/LB_memory_ablation_official_v1/memory_ablation_summary.json`

Run command:

```bash
python scripts/run_memory_ablation.py --no-graphics
```
