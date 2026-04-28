# Labyrinth Breach - Complete Project Implementation Reference

This document is a full implementation reference for the current `Labyrinth-Breach` project. It is written to be operational, not just conceptual: what exists, how it is wired, how to run it, what to check in Unity, what changed over time, and where common failures come from.

---

## 1) Project Goal and Core Scenario

The project implements a multi-agent pursuit-evasion environment in Unity ML-Agents:

- Team A: **Sentinels** (pursuers), typically 3 agents.
- Team B: **Runners** (evaders), typically 2 agents.
- Environment types:
  - Open arena baseline.
  - Static mazes.
  - Dynamic mazes with shifting walls.
  - Unseen evaluation maze for generalization checks.

Primary objective of the implementation:

- Sentinels should actively track and capture runners.
- Runners should evade sentinels and reach exits when available.
- Policies should generalize beyond one fixed map and not collapse into local loops.

---

## 2) Repository Components

### 2.1 Unity runtime (`unity/Assets/Scripts`)

- Agents
  - `Agents/BaseAgent.cs`
  - `Agents/SentinelAgent.cs`
  - `Agents/RunnerAgent.cs`
- Environment and control
  - `Environment/PursuitEvasionEnvController.cs`
  - `Environment/SpawnManager.cs`
  - `Environment/MazeGenerator.cs`
  - `Environment/DynamicWallController.cs`
  - `Environment/DynamicWallPillar.cs`
  - `Environment/ExitZoneController.cs`
  - `Environment/EpisodeStateTracker.cs`
  - `Environment/EnvRuleConfigLoader.cs`
  - `Environment/CurriculumConfigLoader.cs`
- Rewards
  - `Rewards/RewardEngine.cs`
  - `Rewards/RewardConfig.cs`
  - `Rewards/RewardEvent.cs`
  - `Rewards/SentinelRewardPolicy.cs`
  - `Rewards/RunnerRewardPolicy.cs`
  - `Rewards/TrapEventDetector.cs`
- Sensors and observations
  - `Sensors/ObservationAssembler.cs`
  - `Sensors/VisibilityTracker.cs`
  - `Sensors/RaySensorBuilder.cs`
  - `Sensors/LastKnownPositionMemory.cs`
  - `Sensors/EntityBufferSensorWriter.cs`
- Logging and debug
  - `Logging/StepLogger.cs`
  - `Logging/EpisodeLogger.cs`
  - `Logging/ReplayEventExporter.cs`
  - `DebugDrawUtils.cs`

### 2.2 Python orchestration (`scripts/`)

- Training and metadata
  - `train_with_metadata.py`
  - `save_run_metadata.py`
- Evaluation
  - `evaluate_policy.py`
  - `run_fixed_duration_eval_multiseed.py`
  - `summarize_eval_kpis.py`
- Curriculum orchestration
  - `run_multiseed_curriculum.py`
- Diagnostics/helpers
  - `check_gpu_training.py`
  - `setup_validation.py`
  - `check_large_artifacts.py`

### 2.3 Config layer (`configs/`)

- Trainer configs
  - `trainer_configs/ppo_openarena_3v2.yaml`
  - `trainer_configs/ppo_staticmaze_3v2.yaml`
  - `trainer_configs/ppo_dynamicmaze_3v2.yaml`
  - `trainer_configs/mapoca_dynamicmaze_3v2.yaml`
- Env configs
  - `env_configs/env_staticmaze_v1.yaml`
  - `env_configs/env_dynamicmaze_v1.yaml`
  - `env_configs/env_openarena_v1.yaml`
  - `env_configs/env_unseen_eval_v1.yaml`
  - `env_configs/maze_static_config.yaml`
  - `env_configs/maze_dynamic_config.yaml`
  - `env_configs/maze_unseen_eval_config.yaml`
  - `env_configs/asymmetry_config.yaml`
  - `env_configs/randomization_training_v1.yaml`
- Reward configs
  - `reward_configs/reward_shared_basic_v1.yaml`
  - `reward_configs/reward_shared_plus_individual_v2.yaml`
  - `reward_configs/reward_dynamicmaze_memory_v4.yaml`
  - `reward_configs/reward_trap_aware_v3.yaml`
- Curriculum configs
  - `curriculum_configs/curriculum_3v2_full_v1.yaml`
  - `curriculum_configs/curriculum_basic_to_maze_v1.yaml`
  - `curriculum_configs/curriculum_maze_to_dynamic_v2.yaml`
- Experiment manifests
  - Stage and eval manifests under `experiment_manifests/`

---

## 3) Runtime Control Flow

At runtime in Unity:

1. `PursuitEvasionEnvController.BeginEpisode()` is entry point.
2. It loads env rules and curriculum stage (`EnvRuleConfigLoader` + `CurriculumConfigLoader`).
3. It applies randomization controls and dynamic wall config.
4. `SpawnManager` resets/spawns all agents.
5. Agent overrides are applied (capture radius, dynamics).
6. Rewards/loggers are initialized.
7. Episode loop updates:
   - movement and observations
   - capture detection
   - exit detection
   - shaping rewards/penalties
   - wall-loop/orbit penalties
   - dynamic wall shifts
   - logs and KPI data

---

## 4) Agent Implementation Details

## 4.1 `BaseAgent`

- Handles:
  - movement step (`Move`)
  - observation collection
  - action consumption (`OnActionReceived`)
  - ML-Agents component setup
- Important implementation notes:
  - `decisionPeriod` target is 2 for responsive movement.
  - Uses `ResolveConstrainedMovement` from environment controller.
  - Team-specific assist blending:
    - Sentinel pursuit assist (toward runner target)
    - Runner evade assist (away from nearest visible threat)
  - Behavior type is now selected safely:
    - communicator on or no model -> `Default`
    - model assigned and no communicator -> `InferenceOnly`

## 4.2 `SentinelAgent`

- Capture checks via distance against capture radius.
- `TryCaptureRunner()` marks runner captured if within radius.
- Capture radius receives runtime override from env config.

## 4.3 `RunnerAgent`

- Tracks `isCaptured` and `hasEscaped`.
- On capture/escape, deactivates gameplay state.
- Designed to become non-participating once terminal local state is reached.

---

## 5) Environment and Collision Implementation

## 5.1 `PursuitEvasionEnvController`

This is the central orchestrator. It includes:

- episode lifecycle
- config loading
- curriculum stage application
- travel metrics and terminal arming gates
- reward and shaping evaluation
- logging and replay hooks
- wall and confinement handling

Key safeguards implemented:

- minimum terminal grace and movement before terminal checks are armed
- start separation and initial overlap resolution
- wall-loop penalties with repeat scaling
- orbit-stall penalties
- pursuit and evade delta shaping
- maze coverage metrics by team
- runtime stage override file support

## 5.2 Wall pass-through prevention

Core behavior:

- movement sphere-cast and overlap correction
- hit filtering by collider properties and `Wall` tag
- slide-along-wall logic when direct movement is blocked
- post-dynamic-shift sanitation to unstick overlapped agents

Recent hardening:

- wall casts/overlap queries no longer rely only on a potentially incorrect layer mask path
- generated walls explicitly enforce non-trigger colliders

## 5.3 Dynamic walls

`DynamicWallController`:

- toggles wall pillars at configured interval/intensity
- avoids unsafe shifts near agents
- records shift stats
- requests global sanitize pass after shifts

---

## 6) Reward and Penalty System

Reward signals are implemented by `RewardEngine` + `RewardPolicy` wrappers and loaded from YAML.

Sentinel events:

- team full capture
- individual capture bonus
- chase progress bonus / chase regression penalty
- wall-loop and orbit-stall penalties
- cluster penalty
- trap-aware bonuses (when enabled)

Runner events:

- exit success reward
- capture penalties
- survival reward
- evade progress / threat approach penalty
- wall-loop and orbit-stall penalties
- exploration bonuses

Shaping stability controls added in code:

- chase/evade deadzones
- delta scaling to reduce noisy micro-updates

This avoids unstable oscillatory learning and improves pairwise behavior consistency.

---

## 7) Observation Pipeline

Observation stack combines:

- self state
- environment context
- memory features (last known target)
- ray perception
- opponent summary

Team observation config is controlled by env/rule configs.
In recent tuning, teammate inclusion was disabled in key maze configs to reduce teammate fixation in sentinels.

---

## 8) Curriculum and Stage Control

Primary curriculum progression used:

1. `static_maze_fixed_spawn_easy` (scene `02_StaticMaze_3v2`)
2. `static_maze_random_spawn` (scene `02_StaticMaze_3v2`)
3. `dynamic_maze_low_frequency` (scene `03_DynamicMaze_3v2`)
4. `dynamic_maze_high_frequency_tactical` (scene `03_DynamicMaze_3v2`)

Important implementation detail:

- `train_with_metadata.py` writes runtime stage override:
  - `configs/runtime_overrides/active_stage.txt`
- `PursuitEvasionEnvController` reads this and chooses stage by `stage_id`.

This prevents wrong-stage loading when multiple stages share same scene.

---

## 9) Training/Evaluation CLI Workflow

### 9.1 Training command style

- Main launcher:
  - `python scripts/train_with_metadata.py ...`
- It records run metadata + command snapshot before launching trainer.

### 9.2 Evaluation command style

- Inference-only evaluation:
  - `python scripts/evaluate_policy.py ...`
- Fixed duration multi-seed wrapper:
  - `python scripts/run_fixed_duration_eval_multiseed.py ...`
- KPI summarization:
  - `python scripts/summarize_eval_kpis.py ...`

### 9.3 Common operational requirement

- Use one active ML-Agents run at a time on default port.
- If `UnityWorkerInUseException` occurs, free port 5004 and restart.

---

## 10) Unity Configuration Modes

## 10.1 Training mode

For both Sentinel and Runner:

- Behavior Name: `Sentinel` / `Runner`
- Team Id: `0` / `1`
- Behavior Type: `Default`
- Model: `None`
- Configure ML Agents Components: checked
- Decision Period: 2

Scene per stage:

- Stage 1/2 -> `02_StaticMaze_3v2`
- Stage 3/4 -> `03_DynamicMaze_3v2`
- final generalization eval scene -> `04_Eval_UnseenMaze_3v2`

## 10.2 Inference mode (play only)

For both teams:

- Behavior Type: `Inference Only`
- Assign matching model pair from same run id:
  - Sentinel model for sentinels
  - Runner model for runners
- Keep Decision Period 2
- No Python trainer required in pure inference play

---

## 11) Pairwise Accuracy and BON Process

Current implemented pipeline:

1. Run fixed-duration evaluation for target run(s) over seeds.
2. Produce KPI JSON files from episode/step logs.
3. Compute comparison metrics externally (BON/pairwise).

Minimum required for fair comparison:

- same evaluation scene
- same duration
- same seed list
- deterministic inference setting

If one seed fails (for example worker/port collision), pairwise/BON is incomplete and should be rerun for missing shards.

---

## 12) Known Failure Modes and Resolutions

## 12.1 `UnityWorkerInUseException`

Cause:

- Existing `mlagents-learn` still bound to port 5004.

Resolution:

- kill stale trainer process
- free port
- restart Unity + trainer in correct order

## 12.2 Agents not moving in inference

Typical causes:

- Behavior Type wrong (`Default` instead of `InferenceOnly`)
- Model not assigned
- behavior name mismatch
- DecisionRequester missing/wrong period

## 12.3 Agents spawn issues / empty scene in Play

Mitigations in code:

- spawn reference auto-recovery
- spawn validation and explicit error log when no agents spawned

## 12.4 Wall clipping / vibration

Mitigations in code:

- strict wall blocking logic and depenetration
- post-shift sanitation
- non-wall collider filtering in movement blocking tests

## 12.5 Stale model picker entries in Unity

Cause:

- old `.onnx.meta` entries and Unity cache.

Resolution:

- remove model assets/meta from `Assets`
- clear prefab model refs (`m_Model: {fileID: 0}`)
- close Unity, clear `Library`, reopen and reimport

---

## 13) Files Most Critical to Behavior Quality

1. `unity/Assets/Scripts/Environment/PursuitEvasionEnvController.cs`
2. `unity/Assets/Scripts/Agents/BaseAgent.cs`
3. `unity/Assets/Scripts/Rewards/RewardEngine.cs`
4. `unity/Assets/Scripts/Environment/MazeGenerator.cs`
5. `configs/reward_configs/reward_dynamicmaze_memory_v4.yaml`
6. `configs/reward_configs/reward_shared_plus_individual_v2.yaml`
7. `configs/trainer_configs/ppo_dynamicmaze_3v2.yaml`
8. `configs/env_configs/maze_dynamic_config.yaml`
9. `configs/env_configs/maze_static_config.yaml`
10. `scripts/train_with_metadata.py`

---

## 14) Current Recommended Execution Sequence

1. Stage 1 train (static fixed) on `02_StaticMaze_3v2`
2. Stage 2 train (static random) on `02_StaticMaze_3v2`
3. Stage 3 train (dynamic low shift) on `03_DynamicMaze_3v2`
4. Stage 4 train (dynamic high shift) on `03_DynamicMaze_3v2`
5. Fixed-duration multi-seed eval on `04_Eval_UnseenMaze_3v2`
6. KPI summarize
7. Pairwise/BON compare

Operational order per run:

- start trainer command
- wait for listener log
- press Play in Unity

---

## 15) Notes About Completeness

This file captures the complete implementation structure and all major runtime/training decisions currently present in the repository and active workflow.

For absolute reproducibility, pair this file with:

- `docs/project_plan.md`
- `docs/reproduction_guide.md`
- saved run metadata under each `results/<run_id>/metadata/`

These metadata snapshots contain the exact command, config references, and run-id-level provenance for each experiment.

