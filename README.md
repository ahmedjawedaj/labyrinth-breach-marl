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
| PyTorch | `torch==2.2.1+cu121` |
| NumPy | `numpy==1.23.5` |
| Setuptools | `setuptools==70.0.0` |

No HDRP or URP dependency is required at this stage. Use the default render pipeline unless a later scene milestone explicitly changes that.

## Setup

The recommended setup is the same on Windows, Linux, and macOS:

1. Install Unity Hub.
2. Install Unity Editor `6000.0.40f1`.
3. Open the repository root folder with Unity Hub.
4. In Unity Package Manager, install:

```text
com.unity.ml-agents@4.0.0
```

5. Create the Python environment using Conda or `venv`.
6. Verify `mlagents-learn` starts correctly.

### Windows

Use PowerShell or Command Prompt for Python setup.

**Conda**

```powershell
conda env create -f environment.yml
conda activate labyrinth-breach
```

**venv**

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Linux

Use Bash or Zsh for Python setup.

**Conda**

```bash
conda env create -f environment.yml
conda activate labyrinth-breach
```

**venv**

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### macOS

Use Bash or Zsh for Python setup.

**Conda**

```bash
conda env create -f environment.yml
conda activate labyrinth-breach
```

**venv**

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Verify Python and ML-Agents

Run:

```bash
python --version
python -m pip show mlagents mlagents-envs torch numpy setuptools
mlagents-learn --help
```

The default dependency files install the CUDA 12.1 PyTorch wheel. That is the current project baseline for GPU training. If a machine does not have CUDA-capable hardware, use the `--allow-cpu` path only for intentional smoke tests.

## Setup Validation

Validate the repository scaffold from the project root:

```bash
python scripts/setup_validation.py
```

The script checks required top-level folders and the initial open-arena config files. It prints `Success!` when the required setup is present and lists missing folders or config files otherwise.

For detailed reproduction steps, see [docs/reproduction_guide.md](docs/reproduction_guide.md).
