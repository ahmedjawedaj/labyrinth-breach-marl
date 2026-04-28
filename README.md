# Labyrinth Breach

Labyrinth Breach is a Unity ML-Agents project for multi-agent pursuit-evasion in dynamic mazes. It features 3 Sentinels and 2 Runners, focusing on cooperative trapping, route denial, configurable rewards, memory under broken line of sight, and PPO-first training.

## Required Versions

Use these versions for reproducible setup:

| Component | Required version |
| --- | --- |
| Unity Editor | `6000.0.40f1` |
| Unity ML-Agents package | `com.unity.ml-agents@4.0.0` |
| Python | `3.10.12` |
| Python ML-Agents | `mlagents==1.1.0` |
| ML-Agents environment API | `mlagents-envs==1.1.0` |
| PyTorch | `torch==2.2.1+cpu` |
| NumPy | `numpy==1.23.5` |
| Setuptools | `setuptools==70.0.0` |

No HDRP or URP dependency is required at this stage. Use the default render pipeline unless a later scene milestone explicitly changes that.

## Setup

Install Unity Editor `6000.0.40f1` through Unity Hub. After opening the Unity project, install the ML-Agents Unity package through Package Manager using:

```text
com.unity.ml-agents@4.0.0
```

Create the Python environment with Conda:

```bash
conda env create -f environment.yml
conda activate labyrinth-breach
```

Or use `venv` and pip:

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Verify the Python training CLI:

```bash
python --version
python -m pip show mlagents mlagents-envs torch numpy setuptools
mlagents-learn --help
```

The default dependency files install the CPU-only PyTorch wheel. This avoids downloading the multi-gigabyte CUDA dependency stack during initial setup. CUDA can be added later for long training runs if the machine has a compatible GPU and enough disk space.

## Setup Validation

Validate the repository scaffold from the project root:

```bash
python scripts/setup_validation.py
```

The script checks required top-level folders and the initial open-arena config files. It prints `Success!` when the required setup is present and lists missing folders or config files otherwise.

For detailed reproduction steps, see [docs/reproduction_guide.md](docs/reproduction_guide.md).
