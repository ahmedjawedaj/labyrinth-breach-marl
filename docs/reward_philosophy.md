# Reward Philosophy

## Purpose

The reward system should encourage useful multi-agent tactics without turning the environment into a scripted behavior demo. Rewards must support learning, evaluation, and ablation studies.

The main design principle is:

Terminal outcomes should matter most, while shaping rewards should be small, named, measurable, and auditable.

## Centralized Reward Engine

Rewards must be applied through a centralized reward system.

Planned classes:

- `RewardEngine.cs`
- `RewardEvent.cs`
- `SentinelRewardPolicy.cs`
- `RunnerRewardPolicy.cs`
- `TrapEventDetector.cs`

Agents should not scatter raw `AddReward` calls across unrelated scripts. Reward events should be named and logged.

## Sentinel Reward Direction

Sentinels should be rewarded for:

- capturing Runners
- capturing both Runners before timeout
- forming pincer pressure
- blocking exits
- forcing Runners into dead ends
- controlling corridors and junctions

Sentinels may be penalized for:

- failing to capture before timeout
- allowing exit success
- clustering too tightly when spreading would help
- reward-hacking noisy proximity signals

## Runner Reward Direction

Runners should be rewarded for:

- reaching exits
- surviving longer
- exploring maze space
- splitting pressure between Sentinels
- maintaining useful separation

Runners may be penalized for:

- being captured
- both Runners being captured
- remaining trapped without progress
- ignoring exits when exit mode is active

## Trap-Aware Shaping

Trap-aware shaping is the main research differentiator. It should detect intermediate tactical events, not random movement patterns.

Target events:

- pincer formation
- opposite-side enclosure
- dead-end forcing
- exit denial pressure
- multi-Sentinel corridor control
- blocker-at-junction behavior

These rewards should be small enough that terminal success remains the primary objective.

## Reward Versions

Initial reward versions:

```text
reward_shared_basic_v1.yaml
reward_shared_plus_individual_v2.yaml
reward_trap_aware_v3.yaml
reward_dynamicmaze_memory_v4.yaml
```

Use these versions for ablations:

- shared basic reward vs trap-aware reward
- memory enabled vs memory disabled
- static maze vs dynamic maze
- seen maze vs unseen maze

## Reward Audit

Each episode should report reward totals by group:

- terminal reward total
- capture reward total
- survival reward total
- trap-aware reward total
- exploration reward total
- penalty total

This prevents one reward term from silently dominating training.
