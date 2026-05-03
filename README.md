# Labyrinth Breach

**Reinforcement Learning-based Multi-Agent Pursuit-Evasion in Dynamic Maze Environments**

> AI641 -- AI for Robotics | MS AI, LUMS

[![Demo Video](https://img.shields.io/badge/Demo-Video-red?logo=googledrive)](https://drive.google.com/file/d/1uA2Xk7QteroUly8sJsRQaxy1PfJatwN0/view)
[![Paper](https://img.shields.io/badge/Paper-LaTeX-blue)](/paper/labyrinth_breach_final.tex)

## Overview

Labyrinth Breach is a Unity ML-Agents environment for asymmetric multi-agent pursuit-evasion. Three **Sentinel** (pursuer) agents cooperatively chase two **Runner** (evader) agents across procedurally generated mazes with dynamic wall shifts, exit zones, and partial observability.

Agents are trained with **PPO** using tactical reward shaping that encourages coordination behaviors such as pincer formations, corridor denial, and exit blocking. Trained policies are evaluated across multiple random seeds on both seen and unseen maze layouts.

### Key Results

| Metric | Seen | Unseen |
| --- | --- | --- |
| Sentinel win rate | 0.620 | 0.603 |
| Time to first capture (s) | 17.15 | 9.68 |
| Time to second capture (s) | 37.84 | 24.55 |

Policies transfer to unseen layouts with only a 1.7 percentage point drop in win rate while capture timing shifts substantially, indicating topology-sensitive rather than memorized behavior.

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

| Stage | Min Episodes | Wall Shift | Win Rate Threshold |
| --- | --- | --- | --- |
| Static maze, fixed spawns | 1,200 | None | >= 0.62 |
| Static maze, random spawns | 2,200 | None | >= 0.55 |
| Dynamic maze, low frequency | 3,200 | 20s | >= 0.50 |
| Dynamic maze, high frequency | 3,000 | 8s | >= 0.45 |

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
mlagents-learn configs/trainer_configs/ppo_openarena_3v2.yaml --run-id=baseline_run
```

Then press Play in the Unity Editor to begin training.

## Authors

- Muhammad Sikander Raheem (25280017)
- Usman Irshad Bhatti (25280099)
- Ahmed Jawed (25280040)
