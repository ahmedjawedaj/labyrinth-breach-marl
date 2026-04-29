# Labyrinth Breach Review, Testing, and Reporting Guide

This guide provides:

- complete-project review status against `docs/project_plan.md`
- required updates before final evaluation/publication
- end-to-end testing commands (setup -> training -> evaluation -> metrics -> reports)
- reporting template for final project submission

---

## 1) Complete Project Review and Verification

### 1.1 Implemented and Present

- **Scenes**
  - `unity/Assets/Scenes/01_Baseline_OpenArena_3v2.unity`
  - `unity/Assets/Scenes/02_StaticMaze_3v2.unity`
  - `unity/Assets/Scenes/03_DynamicMaze_3v2.unity`
  - `unity/Assets/Scenes/04_Eval_UnseenMaze_3v2.unity`
- **Core Unity systems**
  - agents: `BaseAgent`, `SentinelAgent`, `RunnerAgent`
  - environment: `PursuitEvasionEnvController`, `SpawnManager`, `MazeGenerator`, `DynamicWallController`, `ExitZoneController`, `EpisodeStateTracker`
  - sensing: `RaySensorBuilder`, `ObservationAssembler`, `VisibilityTracker`, `LastKnownPositionMemory`, `EntityBufferSensorWriter`
  - rewards: `RewardEngine`, `RewardConfig`, `RewardEvent`, `SentinelRewardPolicy`, `RunnerRewardPolicy`, `TrapEventDetector`
  - logging/debug: `StepLogger`, `EpisodeLogger`, `ReplayEventExporter`, `DebugDrawUtils`
- **Training configs**
  - PPO: open arena, static maze, dynamic maze
  - MA-POCA: optional dynamic maze config
  - curriculum and environment rule configs present
- **Evaluation runner**
  - `scripts/evaluate_policy.py` launches with `--resume --inference --deterministic`
  - unseen manifest present: `configs/experiment_manifests/exp_unseen_eval_seed101.yaml`
- **Metrics and reporting tooling**
  - core metrics: `python/metrics_calculators/core_metrics.py`
  - coordination metrics: `python/metrics_calculators/coordination_metrics.py`
  - path metrics: `python/metrics_calculators/path_metrics.py`
  - seen vs unseen drop: `python/metrics_calculators/seen_vs_unseen_comparison.py`
  - plots/tables generator: `python/plotting_scripts/generate_evaluation_reports.py`

### 1.2 Verified by Commands

- `python scripts/setup_validation.py` -> required folders/configs pass
- `python scripts/check_gpu_training.py` -> CUDA available (`torch.cuda.is_available() == True`)
- `python scripts/train_with_metadata.py --metadata-only --manifest ...` -> training command includes `--torch-device cuda`
- `python scripts/evaluate_policy.py --dry-run --source-run-id ... --skip-checkpoint-check` -> evaluation command includes fixed-policy flags and deterministic seed
- `python -m compileall scripts python/metrics_calculators python/plotting_scripts` -> scripts syntactically valid

### 1.3 Gaps / Updates Needed

1. **Duplicate Unity code trees are diverged**
   - the canonical runtime tree is `unity/Assets/Scripts`
   - legacy mirrors have been isolated under `unity/_deprecated_duplicate_tree/`
   - keep `unity/Assets/Scripts` as the sole active source of truth to avoid regressions

2. **Automated tests are not yet implemented**
   - currently no substantive Python/Unity unit test suite
   - add tests for reward logic, event parsing, and metric calculators

3. **README dependency text is inconsistent**
   - `README.md` still says CPU-only torch, but dependency files pin CUDA wheel
   - update README to match actual GPU-first setup

4. **Evaluation metrics pipeline is script-based, not yet auto-attached to runner**
   - metrics/report generation works, but not yet chained automatically from `evaluate_policy.py`

---

## 2) End-to-End Testing Plan (Execution Guide)

Run from repository root: `/home/code/Labyrinth-Breach`

### 2.1 Environment and Prerequisites

```bash
conda activate labyrinth-breach
python --version
python scripts/setup_validation.py
python scripts/check_gpu_training.py
mlagents-learn --help
```

Expected:

- setup validation success
- GPU check passes with CUDA tensor test

### 2.2 Unity Scene Sanity Checks

Open `unity/` in Unity 6000.0.40f1.

For each scene:

- `01_Baseline_OpenArena_3v2`
- `02_StaticMaze_3v2`
- `03_DynamicMaze_3v2`
- `04_Eval_UnseenMaze_3v2`

Check:

- no red errors in Console
- `Sentinel` and `Runner` behavior names are present and Behavior Type is `Default`
- episodes reset repeatedly without null references
- in dynamic scene, wall shift events occur and agents continue stepping

### 2.3 Training Smoke Tests (PPO + MA-POCA)

```bash
# Open arena PPO
python scripts/train_with_metadata.py --manifest configs/experiment_manifests/exp_openarena_shared_seed42.yaml --force

# Static maze PPO
python scripts/train_with_metadata.py --manifest configs/experiment_manifests/exp_staticmaze_shared_seed42.yaml --force

# Dynamic maze PPO
python scripts/train_with_metadata.py --manifest configs/experiment_manifests/exp_dynamicmaze_shared_seed42.yaml --force

# Optional MA-POCA dynamic run (explicit config path)
python scripts/train_with_metadata.py \
  --run-id LB_3v2_dynamicmaze_mapoca_smoke_v1 \
  --trainer-config configs/trainer_configs/mapoca_dynamicmaze_3v2.yaml \
  --env-config configs/env_configs/env_dynamicmaze_v1.yaml \
  --reward-config configs/reward_configs/reward_shared_basic_v1.yaml \
  --curriculum-config configs/curriculum_configs/curriculum_maze_to_dynamic_v2.yaml \
  --seed 42 \
  --force
```

GPU validation during training:

```bash
nvidia-smi -l 2
```

Expect:

- python process appears with non-trivial GPU memory use
- run logs under `results/<run-id>/run_logs/`
- metadata under `results/<run-id>/metadata/`

### 2.4 Evaluation (Fixed Policies, Deterministic)

```bash
python scripts/evaluate_policy.py \
  --manifest configs/experiment_manifests/exp_unseen_eval_seed101.yaml \
  --source-run-id LB_3v2_dynamicmaze_shared_seed42_v1 \
  --deterministic
```

Expect:

- command includes `--resume --inference --deterministic`
- `evaluation_metadata.json` created under evaluation run metadata

### 2.5 Metrics Calculation

Use exported Unity logs (typically under `Application.persistentDataPath/LabyrinthBreachLogs`) copied to an evaluation artifact folder.

```bash
# Core
python python/metrics_calculators/core_metrics.py \
  --episode-log "<LOG_DIR>/episode_log.csv" \
  --replay-log "<LOG_DIR>/replay_events.csv" \
  --expected-runners 2 \
  --output-json results/metrics/unseen_core_metrics_summary.json \
  --output-csv results/metrics/unseen_core_metrics_per_episode.csv

# Coordination
python python/metrics_calculators/coordination_metrics.py \
  --episode-log "<LOG_DIR>/episode_log.csv" \
  --replay-log "<LOG_DIR>/replay_events.csv" \
  --step-log "<LOG_DIR>/agent_step_log.csv" \
  --output-json results/metrics/unseen_coordination_metrics_summary.json \
  --output-csv results/metrics/unseen_coordination_metrics_per_episode.csv

# Path
python python/metrics_calculators/path_metrics.py \
  --episode-log "<LOG_DIR>/episode_log.csv" \
  --step-log "<LOG_DIR>/agent_step_log.csv" \
  --replay-log "<LOG_DIR>/replay_events.csv" \
  --output-json results/metrics/unseen_path_metrics_summary.json \
  --output-csv results/metrics/unseen_path_metrics_per_episode.csv
```

Repeat similarly for seen-evaluation logs, producing `seen_*` metric files.

### 2.6 Seen vs Unseen Generalization Drop

```bash
python python/metrics_calculators/seen_vs_unseen_comparison.py \
  --seen-core-metrics results/metrics/seen_core_metrics_summary.json \
  --unseen-core-metrics results/metrics/unseen_core_metrics_summary.json \
  --seen-label seen \
  --unseen-label unseen \
  --output-json results/metrics/generalization_drop_summary.json \
  --output-csv results/metrics/generalization_drop_table.csv
```

### 2.7 Plot and Table Generation

```bash
python python/plotting_scripts/generate_evaluation_reports.py \
  --seen-core results/metrics/seen_core_metrics_summary.json \
  --unseen-core results/metrics/unseen_core_metrics_summary.json \
  --seen-coordination results/metrics/seen_coordination_metrics_summary.json \
  --unseen-coordination results/metrics/unseen_coordination_metrics_summary.json \
  --seen-path results/metrics/seen_path_metrics_summary.json \
  --unseen-path results/metrics/unseen_path_metrics_summary.json \
  --generalization-drop results/metrics/generalization_drop_summary.json \
  --results-dir results
```

Expected outputs:

- CSV tables in `results/tables/`
- plots in `results/figures/`
- report manifest in `results/metrics/evaluation_report_manifest.json`

---

## 3) Training Configuration Verification Checklist

Before long runs:

- trainer config matches target environment (`ppo_openarena_3v2.yaml`, `ppo_staticmaze_3v2.yaml`, `ppo_dynamicmaze_3v2.yaml`, optional `mapoca_dynamicmaze_3v2.yaml`)
- scene + env config alignment checked (`env_*` + `maze_*` configs)
- reward config selected intentionally (`reward_shared_basic_v1` or trap-aware variants)
- randomization fields verified for each experiment (spawns, maze seed, exit positions, wall shifts, speed asymmetry)
- `--torch-device cuda` present (or wrapper default used)

---

## 4) Project Report Template (Use for Final Submission)

Create `paper/project_report.md` with:

1. **Overview**
   - project objective
   - 3v2 setup
   - research question

2. **Implementation Details**
   - environment and maze systems
   - agent/observation architecture
   - reward system and trap-aware events
   - logging and replay export

3. **Training Setup**
   - config matrix (PPO + optional MA-POCA)
   - seeds, curriculum, randomization controls
   - hardware and GPU utilization evidence

4. **Testing and Validation**
   - setup checks
   - scene/runtime checks
   - training smoke and long-run checks
   - evaluation determinism checks

5. **Evaluation Results**
   - core metrics (seen vs unseen)
   - coordination metrics
   - path metrics
   - generalization drop table
   - plots/tables references from `results/`

6. **Conclusion**
   - strengths
   - current limitations
   - prioritized future improvements

---

## 5) Final Readiness Criteria

Project is ready for evaluation when all are true:

- training wrapper launches successfully for target manifests
- evaluation runs with `--resume --inference --deterministic`
- logs are exported and all metrics calculators succeed
- seen vs unseen drop table is generated
- figures/tables are generated under `results/`
- high-priority gaps are resolved:
  - duplicate Unity script tree divergence
  - missing automated test suite
  - README dependency mismatch
