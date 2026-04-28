# Architecture

## System Overview

Labyrinth Breach is split into three major layers:

- Unity simulation layer
- Python training and evaluation layer
- configuration, logging, and experiment management layer

Unity owns the environment state and agent simulation. Python owns training, evaluation, plotting, and metric calculation. Config files connect both sides so experiments can be repeated and compared.

## Unity Environment

The Unity side simulates the 3v2 pursuit-evasion environment.

Primary responsibilities:

- agent spawning and reset
- episode timing
- capture detection
- win and loss conditions
- maze layout and dynamic wall shifts
- exit zone events
- ray-based sensing
- last-known-position memory
- reward event hooks
- debug visualization
- per-step and per-episode logging hooks

Planned scene progression:

```text
01_Baseline_OpenArena_3v2
02_StaticMaze_3v2
03_DynamicMaze_3v2
04_Eval_UnseenMaze_3v2
```

Main Unity systems:

- `PursuitEvasionEnvController.cs`
- `BaseAgent.cs`
- `SentinelAgent.cs`
- `RunnerAgent.cs`
- `SpawnManager.cs`
- `EpisodeStateTracker.cs`
- `MazeGenerator.cs`
- `DynamicWallController.cs`
- `ExitZoneController.cs`

## Agent Architecture

All agents inherit from `BaseAgent.cs`.

Shared responsibilities:

- movement handling
- alive/dead state
- episode reset
- local memory cache
- debug drawing hooks
- reward event hooks

Specialized subclasses:

- `SentinelAgent.cs` for pursuers
- `RunnerAgent.cs` for evaders

This avoids duplicating lifecycle logic across five separate agents.

## Observation Architecture

Observations are built in layers:

- self state: position, velocity, heading, alive flag
- environment context: time remaining, exit distance, wall proximity, wall shift timer
- visible entities: teammate and opponent relative state
- memory state: last-known target position, time since last seen, validity flag

Key classes:

- `RaySensorBuilder.cs`
- `VisibilityTracker.cs`
- `LastKnownPositionMemory.cs`
- `EntityBufferSensorWriter.cs`
- `ObservationAssembler.cs`

BufferSensors are planned for scalable teammate and opponent observations so the system is not locked to brittle fixed-size arrays.

## Python Backend

Python is used for:

- ML-Agents training with PPO
- optional MA-POCA experiments
- evaluation runners
- log parsing
- metric calculation
- plotting and paper artifact generation

The Python environment is defined by:

- `environment.yml`
- `requirements.txt`

The expected Python version is `3.10.12`, with `mlagents==1.1.0`, `mlagents-envs==1.1.0`, and `torch==2.2.1+cu121`.

## Reward System

Rewards are centralized through `RewardEngine.cs`, not scattered across agents.

Reward design includes:

- terminal team rewards
- individual capture/tag rewards
- survival and exploration rewards
- trap-aware shaping
- penalties for clustering or failed outcomes

Planned reward classes:

- `RewardEngine.cs`
- `RewardEvent.cs`
- `SentinelRewardPolicy.cs`
- `RunnerRewardPolicy.cs`
- `TrapEventDetector.cs`

Each reward event must be named and logged so reward contribution can be audited.

## Training and Evaluation Separation

Training and evaluation must remain separate.

Training mode:

- learning enabled
- curriculum stages active
- randomized seeds and spawn settings when configured
- model checkpoints and TensorBoard outputs generated

Evaluation mode:

- fixed trained policy
- deterministic seeds
- no learning
- seen and unseen maze layouts evaluated separately
- metrics exported to CSV or JSON

This separation is required for reproducibility and paper-ready comparisons.
