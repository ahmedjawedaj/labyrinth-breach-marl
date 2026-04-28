# Labyrinth Breach Project Plan

## Project Summary

Labyrinth Breach is a fresh Unity ML-Agents project for a 3v2 asymmetric multi-agent pursuit-evasion environment. The project targets both an AI for Robotics final submission and a research-paper-ready experimental prototype.

The environment contains:

- 3 Sentinels as pursuers.
- 2 Runners as evaders.
- Static and dynamic maze variants.
- Shifting wall topology.
- Partial observability through ray-based sensing.
- Last-known-position memory when line of sight breaks.
- Exit-based Runner success.
- Team rewards plus selective individual and trap-aware shaping.
- PPO-first training, with MA-POCA as an optional stretch path.
- Paper-ready logging, evaluation metrics, ablations, and reproducibility artifacts.

The project must be treated as a fresh production-grade build. Older code may only be reused when it is stable, correct, modular, and directly useful.

## Research Direction

The central research question is:

Can standard team-reward multi-agent reinforcement learning learn meaningful trap formation and tactical cooperation in dynamic maze pursuit-evasion, or are trap-aware shaping, last-known-position memory, and dynamic topology needed to produce stronger coordination?

The system should support experiments that compare:

- Open arena vs static maze vs dynamic maze.
- Shared basic reward vs trap-aware reward.
- Memory enabled vs memory disabled.
- Seen maze seeds vs unseen maze seeds.
- PPO vs MA-POCA, if MA-POCA support is feasible.

## Planning Adjustments

The active execution plan follows the updated week-by-week structure, with several additions needed for the full project scope:

- Keep Phases 8, 9, 10, and the final release phase. The project cannot be paper-ready without debugging, logging, evaluation, metric generation, experiment artifacts, and reproducibility checks.
- Treat PPO as required and MA-POCA as optional. MA-POCA should not block the final course deliverable.
- Start logging, metrics, reward event naming, and config loading in Phase 2. Waiting until late phases makes debugging and evidence collection much harder.
- Add tests from the beginning, including Unity EditMode or PlayMode tests and Python validation tests for configs and metrics.
- Keep train and evaluation workflows separate. Evaluation must use fixed policies, deterministic seeds, and held-out maze layouts.
- Track artifact policy early. Large model checkpoints, videos, raw logs, and TensorBoard outputs should not be committed directly unless handled through Git LFS or external artifact storage.

## Repository Structure

The repository should use this top-level structure:

```text
README.md
LICENSE
.gitignore
unity/
python/
configs/
experiments/
results/
scripts/
docs/
paper/
media/
```

Recommended Unity structure:

```text
unity/
  Assets/
    Scenes/
    Scripts/
      Agents/
      Environment/
      Sensors/
      Rewards/
      Logging/
      Utils/
    ScriptableObjects/
      Configs/
    Prefabs/
    Materials/
    Gizmos/
    Tests/
      EditMode/
      PlayMode/
  Packages/
  ProjectSettings/
```

If the project keeps the currently requested direct folders under `unity/`, maintain them consistently:

```text
unity/Scenes/
unity/Scripts/Agents/
unity/Scripts/Environment/
unity/Scripts/Sensors/
unity/Scripts/Rewards/
unity/Scripts/Logging/
unity/ScriptableObjects/Configs/
unity/Prefabs/
unity/Materials/
unity/Gizmos/
unity/Tests/
```

Python structure:

```text
python/
  training_helpers/
  log_parsers/
  metrics_calculators/
  plotting_scripts/
  evaluation_runners/
  tests/
```

Config structure:

```text
configs/
  env_configs/
  reward_configs/
  curriculum_configs/
  trainer_configs/
  experiment_manifests/
```

Initial config files:

```text
configs/trainer_configs/ppo_openarena_3v2.yaml
configs/trainer_configs/ppo_staticmaze_3v2.yaml
configs/trainer_configs/ppo_dynamicmaze_3v2.yaml
configs/trainer_configs/mapoca_dynamicmaze_3v2.yaml
configs/env_configs/env_openarena_v1.yaml
configs/env_configs/env_staticmaze_v1.yaml
configs/env_configs/env_dynamicmaze_v1.yaml
configs/env_configs/env_unseen_eval_v1.yaml
configs/reward_configs/reward_shared_basic_v1.yaml
configs/reward_configs/reward_shared_plus_individual_v2.yaml
configs/reward_configs/reward_trap_aware_v3.yaml
configs/reward_configs/reward_dynamicmaze_memory_v4.yaml
configs/curriculum_configs/curriculum_basic_to_maze_v1.yaml
configs/curriculum_configs/curriculum_maze_to_dynamic_v2.yaml
configs/experiment_manifests/exp_openarena_shared_seed42.yaml
configs/experiment_manifests/exp_staticmaze_shared_seed42.yaml
configs/experiment_manifests/exp_dynamicmaze_shared_seed42.yaml
configs/experiment_manifests/exp_dynamicmaze_trapaware_seed42.yaml
configs/experiment_manifests/exp_dynamicmaze_memory_ablation_seed42.yaml
```

Experiment and result structure:

```text
experiments/
  manifests/
  runs/
  notes/
  templates/

results/
  metrics/
  figures/
  tables/
  videos/
```

Script structure:

```text
scripts/
  setup_python_env.sh
  train_openarena.sh
  train_staticmaze.sh
  train_dynamicmaze.sh
  evaluate_policy.sh
  generate_plots.sh
  export_results.sh
```

Scripts should be thin wrappers around documented commands. They must not hide critical configuration choices; run ID, trainer config, environment config, reward config, seed, and output path should stay explicit.

## Naming Standards

Use project-specific names in code:

- `SentinelAgent.cs` for pursuers.
- `RunnerAgent.cs` for evaders.
- `BaseAgent.cs` for shared agent functionality.

Academic writing may still refer to Sentinels as pursuers and Runners as evaders.

Experiment IDs must be deterministic and descriptive:

```text
LB_3v2_open_shared_seed42_v1
LB_3v2_staticmaze_hybrid_seed42_v1
LB_3v2_dynamicmaze_memory_seed17_v2
```

Each experiment manifest should include:

- `run_id`
- `seed`
- `scene`
- `env_config`
- `reward_config`
- `trainer_config`
- `curriculum_stage`
- `commit_hash`
- `notes`

## Scene and Class Inventory

The Unity project should create scenes in this order:

```text
01_Baseline_OpenArena_3v2
02_StaticMaze_3v2
03_DynamicMaze_3v2
04_Eval_UnseenMaze_3v2
```

The planned class inventory is:

Agents:

- `BaseAgent.cs`
- `SentinelAgent.cs`
- `RunnerAgent.cs`

Environment:

- `PursuitEvasionEnvController.cs`
- `MazeGenerator.cs`
- `DynamicWallController.cs`
- `ExitZoneController.cs`
- `EpisodeStateTracker.cs`
- `SpawnManager.cs`

Sensors and observations:

- `RaySensorBuilder.cs`
- `EntityBufferSensorWriter.cs`
- `LastKnownPositionMemory.cs`
- `VisibilityTracker.cs`
- `ObservationAssembler.cs`

Rewards:

- `RewardEngine.cs`
- `RewardEvent.cs`
- `SentinelRewardPolicy.cs`
- `RunnerRewardPolicy.cs`
- `TrapEventDetector.cs`

Logging and metrics:

- `EpisodeLogger.cs`
- `StepLogger.cs`
- `MetricsCollector.cs`
- `ReplayEventExporter.cs`

Config and utilities:

- `EnvConfigSO.cs`
- `RewardConfigSO.cs`
- `CurriculumConfigSO.cs`
- `ExperimentConfigSO.cs`
- `MathUtils.cs`
- `DebugDrawUtils.cs`

Class names may change only when there is a clear architectural reason. Name changes should be reflected in docs and configs immediately.

## Phase 1: Repo and Project Foundations (Week 1)

Objective: create the clean foundation for development, documentation, reproducibility, and collaboration.

Tasks:

- Create or prepare the GitHub repository.
- Add the top-level project structure.
- Add `scripts/` for reproducible command-line workflows.
- Add `configs/experiment_manifests/`.
- Add `.gitignore`, `LICENSE`, and initial `README.md`.
- Add Python environment management with `requirements.txt`, `environment.yml`, or `pyproject.toml`.
- Record Unity, ML-Agents, Python, and PyTorch versions.
- Define an artifact policy for large files.
- Add initial documentation.
- Add a basic test and validation plan.
- Add initial setup checks for Unity and Python dependencies.
- Add placeholder tests for config validation and repository setup.

Documentation to create:

- `docs/project_overview.md`
- `docs/architecture_notes.md`
- `docs/environment_rules.md`
- `docs/reward_philosophy.md`
- `docs/experiment_naming_convention.md`
- `docs/evaluation_protocol.md`
- `docs/contribution_guide.md`
- `docs/reproduction_guide.md`

Deliverables:

- Clean repository scaffold.
- Initial documentation.
- Standard experiment ID format.
- `.gitignore` covering Unity, Python, ML outputs, logs, and local editor files.
- Initial dependency and version policy.
- Artifact policy for checkpoints, videos, raw logs, and large result files.
- Initial test plan for Unity setup, Python setup, config loading, and folder validation.

Acceptance criteria:

- Required folders exist.
- Documentation files exist.
- Empty directories are tracked with placeholders where needed.
- Unity-generated folders such as `Library/`, `Temp/`, `Obj/`, `Build/`, `Logs/`, and `UserSettings/` are ignored.
- Python virtual environments, caches, checkpoints, and large training outputs are ignored or handled through an artifact strategy.
- Basic repository setup checks can be run and documented.

## Phase 2: Open Arena Baseline (Weeks 2-3)

Objective: build the simplest 3v2 environment to validate lifecycle, reset, capture, reward plumbing, and basic training.

Scene:

```text
01_Baseline_OpenArena_3v2
```

Tasks:

- Create a flat open arena.
- Spawn 3 Sentinels and 2 Runners at fixed spawn points.
- Implement basic movement.
- Implement capture and survival logic.
- Implement the central environment controller.
- Add minimal reward engine support.
- Add early logging and metrics from the start.
- Add initial config loading.
- Confirm training can start with the initial PPO config.

Core classes:

- `BaseAgent.cs`
- `SentinelAgent.cs`
- `RunnerAgent.cs`
- `PursuitEvasionEnvController.cs`
- `SpawnManager.cs`
- `EpisodeStateTracker.cs`
- `RewardEngine.cs`
- `RewardEvent.cs`
- `EpisodeLogger.cs`
- `MetricsCollector.cs`

Minimum logs:

- `episode_id`
- `step_id`
- `agent_id`
- `team`
- `position`
- `alive_flag`
- `capture_event`
- `episode_result`
- `reward_delta`

Deliverables:

- Working open arena.
- Correct 3 Sentinel and 2 Runner spawn.
- Episode reset.
- Capture event.
- Episode termination.
- Basic reward event naming.
- Basic logs and metrics.

Acceptance criteria:

- 3 Sentinels and 2 Runners spawn correctly.
- Reset restores all agents and environment state.
- Capture works and fires once per Runner.
- Episode ends correctly.
- Basic training can start.
- Logs show episode outcome and reward events.
- Training starts with initial configuration and logging.

## Phase 3: Agent Dynamics and Game Rules (Week 4)

Objective: centralize game rules and encode configurable asymmetry.

Tasks:

- Define Sentinel win condition: both Runners captured before timeout.
- Define Runner win condition: at least one Runner reaches an exit or timeout survival condition is met, depending on config.
- Implement spherical capture proximity.
- Freeze or deactivate captured Runners cleanly.
- Prevent duplicate capture reward.
- Centralize rules in environment-level systems.
- Add configurable asymmetry.

Configurable asymmetry:

- Sentinel speed.
- Runner speed.
- Capture radius.
- Blocking/trap shaping weight.
- Timeout.
- Exit success behavior.

Validation tests:

- Both Runners captured produces Sentinel win.
- One Runner reaches exit produces Runner win.
- Timeout behavior follows config.
- Capture event fires once.
- Captured Runner cannot continue producing capture rewards.
- Episode reset clears alive flags, memory, rewards, walls, exits, and logs.

Deliverables:

- Central game rules.
- Configurable asymmetric agent setup.
- Reliable reset and terminal-state handling.

## Phase 4: Observations and Sensing (Weeks 5-6)

Objective: implement modular observations, ray perception, entity observations, and memory.

Observation layers:

- Self state: position, velocity, heading, alive flag.
- Environment context: time remaining, nearest exit distance, wall proximity, time until wall shift.
- Visible entities: teammate and opponent relative positions and velocities.
- Memory state: last-known target position, time since last seen, validity flag.

Tasks:

- Implement ray-based perception.
- Use 12 to 14 rays for Sentinels.
- Use 16 rays for Runners.
- Detect walls, exits, teammates, and opponents.
- Implement `LastKnownPositionMemory.cs`.
- Implement `VisibilityTracker.cs`.
- Implement `ObservationAssembler.cs`.
- Add BufferSensor-ready entity observations.
- Add observation ablation toggles.

Observation ablation toggles:

- `use_memory`
- `use_rays`
- `use_buffer_sensors`
- `include_teammates`
- `include_opponents`
- `include_exit_vector`

Deliverables:

- Modular observation stack.
- Ray perception for both teams.
- Last-known-position memory.
- BufferSensor-ready entity observations.

Acceptance criteria:

- Visible targets update memory.
- Broken line of sight preserves stale target location.
- Time since last seen increments correctly.
- Memory clears on target death and episode reset.
- Observations support future ablations.

## Phase 5: Maze System (Weeks 7-8)

Objective: add static and dynamic maze environments.

### Phase 5A: Static Maze

Scene:

```text
02_StaticMaze_3v2
```

Tasks:

- Create fixed corridor maze layout.
- Add exits.
- Add spawn-safe zones.
- Add exit-safe zones.
- Define junctions, corridors, and dead ends for metrics.

Deliverables:

- Static maze with exits.
- Spawn-safe and exit-safe placement.
- Corridor movement validation.

### Phase 5B: Dynamic Maze

Scene:

```text
03_DynamicMaze_3v2
```

Tasks:

- Implement modular wall pillars.
- Raise and lower wall pillars through `DynamicWallController.cs`.
- Avoid runtime NavMesh rebaking as the main dependency.
- Add configurable shift intervals.
- Add low-frequency and high-frequency shift modes.
- Prevent invalid wall placement unless explicitly allowed by experiment config.

Validation:

- No agent spawns inside geometry.
- Wall shifts do not break physics.
- Line of sight changes after wall shifts.
- Maze seed reproduces the same layout.
- Exits are not impossible to reach unless explicitly configured.

Deliverables:

- Dynamic wall-shifting maze.
- Configurable topology changes.
- Safe wall-shift rules.

## Phase 6: Reward System (Week 9)

Objective: build a centralized reward engine with versioned configs and trap-aware shaping.

Tasks:

- Centralize rewards in `RewardEngine.cs`.
- Use named `RewardEvent` values.
- Avoid scattered `AddReward` calls across random scripts.
- Implement Sentinel and Runner reward policies.
- Add reward audit trails.
- Add versioned reward config files.

Reward config versions:

```text
reward_shared_basic_v1.yaml
reward_shared_plus_individual_v2.yaml
reward_trap_aware_v3.yaml
reward_dynamicmaze_memory_v4.yaml
```

Sentinel reward terms:

- Team reward when both Runners are captured.
- Escape or timeout penalty.
- Individual tag bonus.
- Encirclement bonus.
- Cluster penalty.
- Exit denial shaping.

Runner reward terms:

- Team reward when at least one Runner reaches an exit.
- Both-captured penalty.
- Tagged penalty.
- Per-step survival bonus.
- Exploration bonus.
- Team separation shaping.

Trap-aware events:

- Pincer formation.
- Opposite-side enclosure.
- Dead-end forcing.
- Exit denial pressure.
- Multi-Sentinel corridor control.

Reward audit fields:

- `terminal_reward_total`
- `capture_reward_total`
- `survival_reward_total`
- `trap_reward_total`
- `exploration_reward_total`
- `penalty_total`

Deliverables:

- Central reward engine.
- Configurable reward policies.
- Trap-aware shaping.
- Reward audit output.

Acceptance criteria:

- Reward components are logged by name.
- Trap-aware events trigger only when conditions are met.
- Terminal rewards remain dominant over shaping rewards.
- Reward configs can be swapped without code rewrites.

## Phase 7: Training Strategy (Weeks 10-11)

Objective: support PPO-first training with curriculum stages and optional MA-POCA path.

Tasks:

- Configure PPO as the primary training path.
- Use separate behavior names for Sentinels and Runners where appropriate.
- Add trainer configs for open arena, static maze, and dynamic maze.
- Add optional MA-POCA config if feasible.
- Implement curriculum stages.
- Add randomization controls.

Trainer configs:

```text
ppo_openarena_3v2.yaml
ppo_staticmaze_3v2.yaml
ppo_dynamicmaze_3v2.yaml
mapoca_dynamicmaze_3v2.yaml
```

Curriculum stages:

- Stage 1: open arena, no exits, no shifting, fixed spawns.
- Stage 2: static maze, exits enabled, random spawns.
- Stage 3: dynamic maze with low-frequency wall shifts.
- Stage 4: dense dynamic maze with higher shift frequency.

Randomization controls:

- Spawn randomness.
- Maze seed.
- Shift frequency.
- Exit count and positions.
- Speed asymmetry.
- Timeout.
- Ray count.
- Observation ablations.

Deliverables:

- PPO training pipeline.
- Curriculum configs.
- Randomization controls.
- Optional MA-POCA path documented as stretch scope.

Acceptance criteria:

- PPO training runs for open arena, static maze, and dynamic maze configs.
- Curriculum stage parameters are loaded from config.
- Spawn randomness, maze seed, exit positions, and speed asymmetry can be controlled.
- Training artifacts save run ID, seed, config snapshots, and commit hash.
- MA-POCA is documented as optional and does not block the PPO pipeline.

## Phase 8: Debugging and Observability (Week 12)

Objective: provide in-editor visibility and reliable event logging.

Tasks:

- Implement debug overlays.
- Visualize raycasts.
- Visualize capture radius.
- Visualize current visible target.
- Visualize last-known target point.
- Visualize exit zones.
- Visualize wall shift timer.
- Display reward events.
- Expand per-step and per-episode logs.

Per-step logs:

- `episode_id`
- `step_id`
- `agent_id`
- `team`
- `position`
- `velocity`
- `target_visible`
- `last_known_used`
- `reward_delta`
- `reward_event_name`
- `alive_flag`

Per-episode logs:

- `run_id`
- `map_id`
- `seed`
- `trainer`
- `reward_config`
- `curriculum_stage`
- `winner`
- `timeout_flag`
- `both_captured_flag`
- `exit_success_flag`
- `first_capture_time`
- `second_capture_time`
- `total_team_rewards`
- `pincer_count`
- `trap_count`
- `exploration_count`

Deliverables:

- Debug mode.
- Comprehensive logs.
- Reward audit trail.

Acceptance criteria:

- Debug overlays can be enabled and disabled without changing training behavior.
- Capture radius, raycasts, visible targets, last-known target positions, exit zones, and wall shift timer are visible in editor debug mode.
- Per-step and per-episode logs are written in a stable machine-readable format.
- Reward audit totals can identify whether terminal, shaping, trap-aware, or penalty terms dominate an episode.

## Phase 9: Evaluation and Metrics (Week 13)

Objective: evaluate trained policies with fixed protocols and paper-ready metrics.

Scene:

```text
04_Eval_UnseenMaze_3v2
```

Tasks:

- Separate training mode from evaluation mode.
- Run deterministic evaluation seeds.
- Evaluate seen and unseen mazes.
- Export metrics to CSV or JSON.
- Generate summary tables.

Core metrics:

- Sentinel win rate.
- Runner win rate.
- Average time to first capture.
- Average time to full capture.
- Exit success rate.
- Survival time per Runner.

Coordination metrics:

- Pincer success rate.
- Trap frequency.
- Average Sentinel spread.
- Average Runner separation.
- Corridor block event count.
- Exit denial event count.

Generalization metrics:

- Seen maze win rate.
- Unseen maze win rate.
- Performance drop on unseen maps.

Path metrics:

- Path efficiency to exit.
- Shortest path vs actual path ratio.

Deliverables:

- Evaluation runner.
- Metrics scripts.
- Seen and unseen maze evaluation.
- Tables and plots for experiments.

Acceptance criteria:

- Evaluation runs without learning enabled.
- Evaluation uses deterministic seeds and fixed trained policies.
- Seen and unseen maze results are reported separately.
- Metrics export includes win rate, time-to-capture, exit success, pincer rate, trap frequency, path efficiency, and generalization drop.
- Evaluation outputs can be regenerated from saved configs and model artifacts.

## Phase 10: Paper-Ready Experiments and Finalization (Weeks 14-15)

Objective: run the minimum experiment matrix and generate paper artifacts.

Minimum experiment matrix:

- Experiment 1: open arena, PPO, shared basic reward.
- Experiment 2: static maze, PPO, shared basic reward.
- Experiment 3: dynamic maze, PPO, shared basic reward.
- Experiment 4: dynamic maze, PPO, trap-aware reward.
- Experiment 5: dynamic maze, PPO, trap-aware reward, memory disabled.
- Experiment 6: dynamic maze, PPO, unseen maze evaluation.
- Experiment 7: dynamic maze, MA-POCA, trap-aware reward, if feasible.

Required ablations:

- Memory vs no memory.
- Shared basic reward vs trap-aware reward.
- Static maze vs dynamic maze.
- Seen maze vs unseen maze.
- PPO vs MA-POCA if feasible.

Paper artifacts:

- Training curves.
- Win-rate tables.
- Seen vs unseen generalization table.
- Ablation table.
- Coordination metrics table.
- Qualitative screenshots.
- Demo video clips.

Deliverables:

- Paper-ready experiment results.
- Figures, tables, and plots.
- Reproducible run manifests.

Acceptance criteria:

- At least four core experiments are completed and documented.
- Memory and trap-aware reward ablations are included.
- Seen and unseen maze comparisons are included.
- Plots and tables are generated by scripts, not manual editing.
- Every reported result is traceable to a run manifest, seed, config snapshot, and commit hash.

## Final Phase: Project Quality and Release (Week 16)

Objective: make the repository public-ready and reproducible.

Tasks:

- Maintain clean Git history.
- Use feature branches and clean commits.
- Tag releases by milestone.
- Finalize README.
- Finalize reproduction guide.
- Ensure experiment outputs save config snapshots, seed, and commit hash.
- Verify training, inference, evaluation, and plot generation workflows.

Release tags:

```text
v0.1-open-arena
v0.2-static-maze
v0.3-dynamic-maze
v0.4-memory-rewards
v1.0-paper-ready
```

Reproducibility checklist:

- A new user can install dependencies.
- A new user can open the Unity project.
- Baseline training can be started from documented commands.
- Evaluation can be run from a saved model.
- Plots and tables can be regenerated.
- Reported results can be traced to configs and commit hashes.

Deliverables:

- Clean GitHub-ready repository.
- Final README.
- Reproduction package.
- Tagged release.

Acceptance criteria:

- A clean checkout can follow the README to set up dependencies.
- The Unity project opens without missing packages or broken references.
- Training, inference, evaluation, and plot generation commands are documented.
- Large artifacts are either excluded, stored through Git LFS, or documented as external downloads.
- Release tags match completed milestones.

## Implementation Task Breakdown

This section divides the project into small implementation tasks. Each task should be small enough to complete, review, and test independently.

### Foundation Tasks

FND-01: Create required top-level directories.

- Output: `unity/`, `python/`, `configs/`, `experiments/`, `results/`, `scripts/`, `docs/`, `paper/`, and `media/`.
- Validation: all required directories exist and empty ones have placeholders if they must be tracked by Git.

FND-02: Create Unity project folders.

- Output: scene, script, prefab, material, gizmo, ScriptableObject config, and test folders.
- Validation: folder names match the plan exactly.

FND-03: Create Python project folders.

- Output: training helpers, log parsers, metric calculators, plotting scripts, evaluation runners, and tests.
- Validation: Python structure is ready for package or script development.

FND-04: Create config folders and initial empty config files.

- Output: trainer, environment, reward, curriculum, and experiment manifest config files.
- Validation: every initial config file listed in this plan exists.

FND-05: Add dependency management.

- Output: `requirements.txt`, `environment.yml`, or `pyproject.toml`.
- Validation: Python dependencies and versions are documented.

FND-06: Add Unity and ML-Agents version notes.

- Output: setup section in README or reproduction guide.
- Validation: a new developer can identify the required Unity, ML-Agents, Python, and PyTorch versions.

FND-07: Add `.gitignore`.

- Output: ignore rules for Unity, Python, logs, model outputs, build outputs, and local editor files.
- Validation: Unity `Library/`, `Temp/`, `Obj/`, `Build/`, `Logs/`, and Python cache files are ignored.

FND-08: Add artifact policy.

- Output: documentation explaining where checkpoints, videos, raw logs, and large result files belong.
- Validation: large artifacts are not committed accidentally.

FND-09: Create required docs.

- Output: overview, architecture, rules, reward, evaluation, naming, contribution, and reproduction docs.
- Validation: each document exists and contains initial project-specific content.

FND-10: Add basic setup validation.

- Output: simple Python or shell checks for folder existence and config file presence.
- Validation: setup validation can be run locally.

### Open Arena Tasks

OA-01: Create baseline open arena scene.

- Output: `01_Baseline_OpenArena_3v2`.
- Validation: scene opens with a flat arena and no maze or dynamic walls.

OA-02: Create placeholder Sentinel and Runner prefabs.

- Output: basic prefabs for 3 Sentinels and 2 Runners.
- Validation: prefabs can be spawned into the scene.

OA-03: Implement `BaseAgent.cs`.

- Output: shared movement, reset state, alive flag, and debug hooks.
- Validation: Sentinel and Runner classes can inherit from it without duplicate lifecycle code.

OA-04: Implement `SentinelAgent.cs`.

- Output: Sentinel-specific movement parameters and team identity.
- Validation: Sentinels move and report team state correctly.

OA-05: Implement `RunnerAgent.cs`.

- Output: Runner-specific movement parameters and team identity.
- Validation: Runners move and report team state correctly.

OA-06: Implement `SpawnManager.cs`.

- Output: fixed spawn positions for 3 Sentinels and 2 Runners.
- Validation: all agents spawn at expected positions on episode start and reset.

OA-07: Implement `EpisodeStateTracker.cs`.

- Output: episode timer, alive counts, capture state, and winner state.
- Validation: episode state resets cleanly.

OA-08: Implement `PursuitEvasionEnvController.cs`.

- Output: single source of truth for episode lifecycle, reset, capture, terminal outcomes, and hooks.
- Validation: no game outcome logic is scattered across agents.

OA-09: Implement basic capture detection.

- Output: spherical proximity capture rule.
- Validation: capture fires once per Runner and cannot repeat for inactive Runners.

OA-10: Add basic reward events.

- Output: capture, survival, timeout, and terminal reward events.
- Validation: each reward event has a stable name and is logged.

OA-11: Add basic episode logging.

- Output: episode result and capture logs.
- Validation: running an episode writes machine-readable logs.

OA-12: Add initial PPO smoke test config.

- Output: minimal trainer config for open arena.
- Validation: ML-Agents training can start without config errors.

### Game Rule Tasks

RULE-01: Implement Sentinel win condition.

- Output: Sentinels win when both Runners are captured before timeout.
- Validation: correct terminal result is recorded.

RULE-02: Implement Runner win conditions.

- Output: Runners win by exit success or configured timeout survival.
- Validation: config controls timeout survival behavior.

RULE-03: Implement captured Runner state.

- Output: captured Runner becomes inactive or frozen cleanly.
- Validation: captured Runner does not move, emit duplicate capture events, or receive invalid rewards.

RULE-04: Implement configurable asymmetry.

- Output: Sentinel speed, Runner speed, capture radius, timeout, and exit behavior loaded from config.
- Validation: changing config changes runtime behavior without code edits.

RULE-05: Add reset integrity check.

- Output: reset verifies alive flags, memory, reward totals, wall state, exits, and logs.
- Validation: repeated episodes do not leak state.

### Observation and Sensing Tasks

OBS-01: Implement self-state observations.

- Output: position, velocity, heading, and alive flag.
- Validation: observation values update every decision step.

OBS-02: Implement environment-context observations.

- Output: time remaining, nearest exit distance, wall proximity, and wall shift timer.
- Validation: values normalize correctly and reset each episode.

OBS-03: Implement `RaySensorBuilder.cs`.

- Output: configurable ray generation for Sentinels and Runners.
- Validation: rays detect walls, exits, teammates, and opponents.

OBS-04: Implement `VisibilityTracker.cs`.

- Output: line-of-sight checks for visible entities.
- Validation: visibility changes when walls or distance block sight.

OBS-05: Implement `LastKnownPositionMemory.cs`.

- Output: current target ID, last known position, time since last seen, and validity flag.
- Validation: memory updates on visibility and decays when line of sight breaks.

OBS-06: Implement `EntityBufferSensorWriter.cs`.

- Output: BufferSensor-ready teammate and opponent entity encoding.
- Validation: observations support variable entity counts.

OBS-07: Implement `ObservationAssembler.cs`.

- Output: layered observation builder combining self, environment, entities, and memory.
- Validation: observation shape is stable for ML-Agents.

OBS-08: Add observation ablation toggles.

- Output: config flags for memory, rays, BufferSensors, teammates, opponents, and exit vector.
- Validation: toggles can disable features without code edits.

### Maze Tasks

MAZE-01: Create static maze sceen.

- Output: `02_StaticMaze_3v2`.
- Validation: scene contains corridors, junctions, exits, and spawn-safe zones.

MAZE-02: Implement `MazeGenerator.cs`.

- Output: configurable static or seeded maze layout generation.
- Validation: same seed produces same layout.

MAZE-03: Implement exit zones.

- Output: trigger-based exit zones for active Runners.
- Validation: Runner entering exit triggers the correct team event once.

MAZE-04: Implement spawn-safe and exit-safe placement.

- Output: safe placement rules for agents and exits.
- Validation: agents do not spawn inside walls or unreachable cells.

MAZE-05: Implement dynamic wall prefab.

- Output: modular wall pillar prefab that can raise and lower.
- Validation: wall state changes are visible and collision state is correct.

MAZE-06: Implement `DynamicWallController.cs`.

- Output: wall shift scheduling and safe wall state changes.
- Validation: wall shifts change routes without breaking physics.

MAZE-07: Add wall shift config.

- Output: shift interval, shift intensity, safe buffer, and allowed blocking rules.
- Validation: dynamic behavior changes through config.

MAZE-08: Add dynamic maze scene.

- Output: `03_DynamicMaze_3v2`.
- Validation: agents continue functioning after wall shifts.

### Reward Tasks

RWD-01: Implement `RewardEvent.cs`.

- Output: stable names for all reward events.
- Validation: logs use event names consistently.

RWD-02: Implement `RewardEngine.cs`.

- Output: centralized reward application and audit totals.
- Validation: agents do not call scattered reward logic directly.

RWD-03: Implement `SentinelRewardPolicy.cs`.

- Output: Sentinel terminal, capture, trap, cluster, and exit-denial rewards.
- Validation: Sentinel rewards match active config.

RWD-04: Implement `RunnerRewardPolicy.cs`.

- Output: Runner terminal, survival, exploration, tagged, and separation rewards.
- Validation: Runner rewards match active config.

RWD-05: Implement reward config loading.

- Output: versioned reward config files.
- Validation: reward version can change without code edits.

RWD-06: Implement `TrapEventDetector.cs`.

- Output: pincer, enclosure, dead-end forcing, exit denial, and corridor control detection.
- Validation: trap-aware events trigger only under meaningful conditions.

RWD-07: Add reward audit export.

- Output: per-episode reward totals grouped by term.
- Validation: terminal, shaping, trap, exploration, and penalty totals are visible.

### Training Tasks

TRN-01: Create PPO open arena config.

- Output: `ppo_openarena_3v2.yaml`.
- Validation: training starts in open arena.

TRN-02: Create PPO static maze config.

- Output: `ppo_staticmaze_3v2.yaml`.
- Validation: training starts in static maze.

TRN-03: Create PPO dynamic maze config.

- Output: `ppo_dynamicmaze_3v2.yaml`.
- Validation: training starts in dynamic maze.

TRN-04: Create optional MA-POCA config.

- Output: `mapoca_dynamicmaze_3v2.yaml`.
- Validation: config exists but does not block PPO progress.

TRN-05: Implement curriculum config loading.

- Output: curriculum stages loaded from config.
- Validation: stage parameters affect scene behavior.

TRN-06: Implement randomization controls.

- Output: spawn randomness, maze seed, exit position, shift frequency, speed asymmetry, timeout, and ray count controls.
- Validation: randomization can be enabled, disabled, and seeded.

TRN-07: Save run metadata.

- Output: run ID, seed, config snapshots, trainer config, reward config, environment config, and commit hash.
- Validation: every training run can be traced and reproduced.

### Debugging and Logging Tasks

DBG-01: Implement `DebugDrawUtils.cs`.

- Output: reusable debug drawing helpers.
- Validation: debug visuals can be toggled.

DBG-02: Add agent debug labels.

- Output: ID, team, alive state, and current target labels.
- Validation: labels update during play mode.

DBG-03: Visualize sensing.

- Output: raycasts, visible targets, and line-of-sight state.
- Validation: visuals match actual observation behavior.

DBG-04: Visualize memory.

- Output: last-known target point and time since last seen.
- Validation: stale memory is visible after line of sight breaks.

DBG-05: Visualize environment state.

- Output: exit zones, capture radius, and wall shift timer.
- Validation: debug mode explains current episode state.

LOG-01: Implement `StepLogger.cs`.

- Output: per-step logs for agent state, visibility, reward delta, and alive flag.
- Validation: log schema is stable.

LOG-02: Implement `EpisodeLogger.cs`.

- Output: per-episode logs for outcome, captures, rewards, trap counts, and config IDs.
- Validation: every episode produces one complete episode record.

LOG-03: Implement `ReplayEventExporter.cs`.

- Output: compact replay/event timeline for demos and paper review.
- Validation: capture, exit, wall shift, and reward events are exportable.

### Evaluation and Metrics Tasks

EVAL-01: Create unseen evaluation scene.

- Output: `04_Eval_UnseenMaze_3v2`.
- Validation: scene uses held-out seeds or layouts.

EVAL-02: Implement evaluation runner.

- Output: script or Python runner that loads fixed policies and deterministic seeds.
- Validation: evaluation runs without learning enabled.

EVAL-03: Implement core metric calculators.

- Output: win rate, survival time, exit success, first capture time, and full capture time.
- Validation: metrics are exported from evaluation logs.

EVAL-04: Implement coordination metrics.

- Output: pincer rate, trap frequency, Sentinel spread, Runner separation, corridor block count, and exit denial count.
- Validation: metrics are computed consistently across runs.

EVAL-05: Implement path metrics.

- Output: path efficiency and shortest path vs actual path ratio.
- Validation: metrics are valid for static and dynamic maze variants.

EVAL-06: Implement seen vs unseen comparison.

- Output: generalization drop table.
- Validation: seen and unseen results are separated.

EVAL-07: Generate plots and tables.

- Output: figures, CSVs, and summary tables under `results/`.
- Validation: plots are generated by scripts from raw metrics.

### Paper and Release Tasks

PAPER-01: Define final experiment matrix.

- Output: manifests for open arena, static maze, dynamic maze, trap-aware, memory ablation, unseen eval, and optional MA-POCA.
- Validation: each experiment has a complete manifest.

PAPER-02: Run required ablations.

- Output: memory vs no memory, shared vs trap-aware reward, static vs dynamic, seen vs unseen.
- Validation: ablation results are saved with configs and seeds.

PAPER-03: Generate paper artifacts.

- Output: training curves, win-rate tables, ablation tables, coordination metric tables, screenshots, and videos.
- Validation: artifacts are reproducible from scripts.

REL-01: Finalize README.

- Output: setup, training, inference, evaluation, reproduction, project structure, and limitations.
- Validation: README can guide a new user through the project.

REL-02: Finalize reproduction guide.

- Output: exact commands and expected outputs for key experiments.
- Validation: another user can reproduce at least the baseline and one evaluation.

REL-03: Tag milestone releases.

- Output: `v0.1-open-arena`, `v0.2-static-maze`, `v0.3-dynamic-maze`, `v0.4-memory-rewards`, and `v1.0-paper-ready`.
- Validation: tags correspond to completed milestone states.

REL-04: Final repository audit.

- Output: clean public-ready repo.
- Validation: no large accidental artifacts, stale configs, broken docs, or hidden prototype assumptions remain.

## Success Criteria

The project is successful only if:

- Training and inference work reliably.
- The environment supports 3 Sentinels vs 2 Runners.
- Dynamic maze shifts change routes and tactics.
- Last-known-position memory is implemented.
- Trap-aware coordination can be measured.
- Results are reproducible.
- Evaluation includes seen and unseen mazes.
- Metrics go beyond win rate.
- Repo structure and documentation are public-ready.
- Experiments are strong enough to support a paper draft.

## Main Risks

The highest-risk areas are:

- Dynamic maze stability.
- Multi-agent training convergence.
- Trap-aware reward balancing.
- BufferSensor integration.
- Paper-quality experiment runtime.
- Optional MA-POCA support.

MA-POCA should remain a stretch goal. PPO is the required primary training path.
