# Labyrinth Breach

**Reinforcement Learning-based Multi-Agent Pursuit-Evasion in Dynamic Maze Environments**

> AI641 -- AI for Robotics | MS AI, LUMS

[![Demo Video](https://img.shields.io/badge/Demo-Video-red?logo=googledrive)](https://drive.google.com/file/d/1uA2Xk7QteroUly8sJsRQaxy1PfJatwN0/view)
[![Paper](https://img.shields.io/badge/Paper-IEEE%20Draft-blue)](/paper/labyrinth_breach_journal.tex)

## Overview

Labyrinth Breach is a Unity ML-Agents environment for asymmetric multi-agent pursuit-evasion. Three **Sentinel** (pursuer) agents cooperatively chase two **Runner** (evader) agents across procedurally generated mazes with dynamic wall shifts, exit zones, and partial observability.

Agents are trained with **PPO** using tactical reward shaping that encourages coordination behaviors such as pincer formations, corridor denial, and exit blocking. Trained policies are evaluated across multiple random seeds on both seen and unseen maze layouts.

### Evidence Status

The current publication draft reports the audited canonical assist-off
evaluation over five trained policy seeds, one seen topology, and five held-out
topologies. Every policy-topology cell targets 100 completed episodes.

| Metric | Seen | Five held-out topologies |
| --- | ---: | ---: |
| Cells / episodes | 5 / 501 | 25 / 2,501 |
| Sentinel win rate | 41.5% +/- 5.0 | 42.2% +/- 8.0 |
| Runner win rate | 58.5% +/- 5.0 | 57.8% +/- 8.0 |
| Escape rate | 52.9% +/- 7.4 | 53.5% +/- 9.5 |
| Pincer episode rate | 22.6% +/- 4.1 | 20.3% +/- 4.5 |
| Exit denial rate | 42.7% +/- 2.9 | 39.2% +/- 4.6 |

The full journal submission evidence pack is still blocked because only two of
five registered paired ablation families are complete. The current paper should
therefore be treated as a strong advisor-review / preprint draft, not as a
finished journal submission package. See
[`docs/publication_pause_conclusion_2026-07-18.md`](docs/publication_pause_conclusion_2026-07-18.md).

## Project Structure

```
labyrinth-breach-marl/
├── unity/                          # Unity project (open with Unity Hub)
│   ├── Assets/Scripts/
│   │   ├── Agents/                 # BaseAgent, SentinelAgent, RunnerAgent
│   │   ├── Environment/            # PursuitEvasionEnvController (episode logic)
│   │   ├── Rewards/                # RewardEngine, RewardConfig, policy classes
│   │   ├── Sensors/                # ObservationAssembler, RaySensorBuilder
│   │   └── Logging/                # StepLogger, CSV output
│   ├── Assets/Models/              # Trained ONNX checkpoints (Git LFS)
│   └── Assets/Scenes/              # 4 scenes (open arena, static, dynamic, unseen)
├── configs/
│   ├── trainer_configs/            # PPO hyperparameters (YAML)
│   ├── reward_configs/             # Reward weights (YAML)
│   └── curriculum_configs/         # 4-stage curriculum definition
├── scripts/                        # Training, evaluation, validation scripts
├── paper/                          # LaTeX source for the final report
└── results/                        # Evaluation logs and metrics
```

## Observation and Action Space

| Component | Sentinel | Runner |
| --- | --- | --- |
| Self state | 10 | 10 |
| Environment context | 7 | 7 |
| Ray perception (6 per ray) | 84 (14 rays) | 96 (16 rays) |
| Last-known-position memory | 6 | 6 |
| Opponent summary (2 nearest) | 10 | 10 |
| **Total observation** | **117** | **129** |
| Action space | 2 continuous | 2 continuous |

## Training Curriculum

| Stage | Sentinel Steps | Runner Steps | Wall Shift |
| --- | ---: | ---: | --- |
| Static maze, fixed spawns | 1,500,000 | 1,500,000 | None |
| Static maze, random spawns | 1,500,000 | 1,500,000 | None |
| Dynamic maze, low frequency | 1,500,000 | 1,500,000 | 20s, intensity 1 |
| Dynamic maze, high frequency | 1,500,000 | 1,500,000 | 8s, intensity 3 |

Episode and win-rate thresholds in the curriculum YAML are post-training audit
targets; ML-Agents termination is controlled by the trainer step budgets above.

## Required Versions

| Component | Version |
| --- | --- |
| Unity Editor | `6000.0.40f1` |
| Unity ML-Agents package | `com.unity.ml-agents@4.0.0` |
| Python | `3.10.12` |
| Python ML-Agents | `mlagents==1.1.0` |
| PyTorch | `torch==2.2.1` |

## Setup

1. Install Unity Hub and Unity Editor `6000.0.40f1`.
2. Open the `unity/` folder with Unity Hub.
3. Create the Python environment:

```bash
# Conda
conda env create -f environment.yml
conda activate labyrinth-breach

# Or venv
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

4. Verify setup:

```bash
python scripts/setup_validation.py
mlagents-learn --help
```

## Running Inference

Open any scene in the Unity Editor (e.g., `03_DynamicMaze_3v2`) and press Play. The agents will run using the trained ONNX models in `unity/Assets/Models/`.

## Training

```bash
python scripts/run_multiseed_curriculum.py \
  --resume-completed \
  --env builds/macos/LabyrinthBreach.app \
  --allow-cpu \
  --no-graphics
```

The launcher transfers both role checkpoints between stages, preserves raw
logs and configuration snapshots, generates KPIs, and fails runs that do not
pass the strict training audit.

## Authors

- Ahmed Jawed (25280040)
- Muhammad Sikander Raheem (25280017)
- Usman Irshad Bhatti (25280099)
