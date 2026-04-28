# Reward Ablation, Wall Impact, and Role Emergence

## Task 19: Reward configuration ablation

Run:

```bash
python scripts/run_reward_config_ablation.py --no-graphics
```

Per-seed condition outputs:

- `results/seed_<seed>/reward_baseline/`
- `results/seed_<seed>/reward_shared_plus_individual/`
- `results/seed_<seed>/reward_trap_aware/`
- `results/seed_<seed>/reward_dynamicmaze_memory/`

Per-seed comparison:

- `results/seed_<seed>/reward_config_comparison.json`
- `results/seed_<seed>/reward_config_comparison.csv`

## Task 23: Static vs dynamic wall impact

Run:

```bash
python scripts/run_dynamic_wall_impact.py --no-graphics
```

Per-seed condition outputs:

- `results/seed_<seed>/static_maze/`
- `results/seed_<seed>/dynamic_maze/`

Per-seed wall impact comparison:

- `results/seed_<seed>/static_dynamic_wall_impact.json`
- `results/seed_<seed>/static_dynamic_wall_impact.csv`

Includes wall-shift tactical impact proxies:

- pathing change after shift
- stall fraction after shift
- wall-shift event count

## Task 24: Role emergence analysis

Role analysis is automatically produced during ablation/impact scripts:

- `results/seed_<seed>/sentinel_role_analysis/`
- `results/seed_<seed>/runner_role_analysis/`

Role outputs include assignment tables and summary JSON per analyzed stage/split.
