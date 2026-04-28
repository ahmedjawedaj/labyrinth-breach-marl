# Reproduction Guide

This guide defines the required versions and setup steps for reproducing Labyrinth Breach development, training, and evaluation.

## Version Matrix

| Component | Required version | Notes |
| --- | --- | --- |
| Unity Editor | `6000.0.40f1` | Install through Unity Hub. |
| Unity ML-Agents package | `com.unity.ml-agents@4.0.0` | Install through Unity Package Manager. |
| Python | `3.10.12` | Required by `mlagents==1.1.0`. |
| Python ML-Agents trainer | `mlagents==1.1.0` | Provides `mlagents-learn`. |
| ML-Agents environment API | `mlagents-envs==1.1.0` | Python interface for Unity environments. |
| PyTorch | `torch==2.2.1+cu121` | CUDA 12.1 wheel pinned in `requirements.txt` and `environment.yml`. |
| NumPy | `numpy==1.23.5` | Matches ML-Agents 1.1.0 constraints. |
| Protobuf | `protobuf==3.20.3` | Matches ML-Agents 1.1.0 constraints. |
| Setuptools | `setuptools==70.0.0` | Provides `pkg_resources`, which ML-Agents 1.1.0 imports. |

No HDRP or URP dependency is required for the current project plan. Use the default render pipeline unless a later milestone explicitly introduces a render pipeline requirement.

## Unity Setup

1. Install Unity Hub.
2. Install Unity Editor `6000.0.40f1`.
3. Open the project from the `unity/` directory once the Unity project files are created.
4. Open Unity Package Manager.
5. Add the ML-Agents package:

```text
com.unity.ml-agents@4.0.0
```

When the Unity project is generated, commit the following Unity metadata:

```text
unity/Packages/manifest.json
unity/Packages/packages-lock.json
unity/ProjectSettings/ProjectVersion.txt
unity/ProjectSettings/
```

Do not commit generated Unity cache folders such as:

```text
unity/Library/
unity/Temp/
unity/Obj/
unity/Build/
unity/Logs/
unity/UserSettings/
```

## Python Setup With Conda

Create the environment:

```bash
conda env create -f environment.yml
conda activate labyrinth-breach
```

Verify the environment:

```bash
python --version
python -m pip show mlagents mlagents-envs torch numpy protobuf setuptools
mlagents-learn --help
```

Expected core versions:

```text
Python 3.10.12
mlagents 1.1.0
mlagents-envs 1.1.0
torch 2.2.1+cu121
numpy 1.23.5
protobuf 3.20.3
setuptools 70.0.0
```

## Python Setup With venv

Use this path if Conda is unavailable:

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## PyTorch GPU Notes

The project pins:

```text
torch==2.2.1+cu121
```

The default dependency files install the CUDA 12.1 PyTorch wheel from:

```text
https://download.pytorch.org/whl/cu121
```

After installing, verify both the NVIDIA driver and PyTorch CUDA access:

```bash
python scripts/check_gpu_training.py
```

If `nvidia-smi` fails, fix the NVIDIA driver/session first. If `nvidia-smi`
works but `torch.cuda.is_available()` is false, reinstall the CUDA PyTorch
wheel from the pinned dependency files.

## ML-Agents Notes

The Python packages are pinned together:

```text
mlagents==1.1.0
mlagents-envs==1.1.0
```

Keep these versions aligned. Do not upgrade one without checking the matching Unity package and retesting training startup.

## Setup Validation Checklist

A new developer should be able to run:

```bash
python --version
python -m pip show mlagents mlagents-envs torch numpy protobuf setuptools
mlagents-learn --help
```

The Unity editor should open the project using Unity `6000.0.40f1`, and the Package Manager should show `com.unity.ml-agents@4.0.0`.

## Repository Setup Validation

Run the scaffold validation script from the repository root:

```bash
python scripts/setup_validation.py
```

The script checks:

- required top-level folders
- initial open-arena trainer config
- initial open-arena environment config
- initial shared-basic reward config
- initial curriculum config
- initial open-arena experiment manifest

Expected success message:

```text
Success! Required folders and config files are present.
```

If setup is incomplete, the script prints each missing folder or config file and exits with a nonzero status.

## Run Metadata Saving

Use the metadata wrapper for training runs that need to be reproducible:

```bash
python scripts/train_with_metadata.py \
  --manifest configs/experiment_manifests/exp_dynamicmaze_shared_seed42.yaml \
  --force \
  --torch-device cuda
```

`scripts/train_with_metadata.py` defaults to `--torch-device cuda` when CUDA is
available and fails fast when CUDA is unavailable. Add `--allow-cpu` only for an
intentional CPU smoke test.

For direct `mlagents-learn` commands, pass the device explicitly:

```bash
mlagents-learn configs/trainer_configs/ppo_dynamicmaze_3v2.yaml \
  --run-id LB_3v2_dynamicmaze_gpu_seed42_v1 \
  --force \
  --torch-device cuda
```

The wrapper saves metadata before launching `mlagents-learn`. Each run gets:

- `results/<run-id>/metadata/run_metadata.json`
- `results/<run-id>/metadata/config_snapshots/`
- `results/<run-id>/metadata/reproduce.sh`

The metadata includes run ID, seed, trainer config, reward config, environment config, curriculum config, config file hashes, commit hash, dirty worktree status, and the exact training command.

To save metadata without launching training:

```bash
python scripts/train_with_metadata.py \
  --manifest configs/experiment_manifests/exp_dynamicmaze_shared_seed42.yaml \
  --run-id LB_metadata_check \
  --metadata-only \
  --force \
  --torch-device cuda
```

## Fixed Policy Evaluation

Use the evaluation runner to load existing checkpoints with learning disabled:

```bash
python scripts/evaluate_policy.py \
  --manifest configs/experiment_manifests/exp_unseen_eval_seed101.yaml \
  --source-run-id LB_3v2_dynamicmaze_gpu_seed42_v1
```

The runner launches `mlagents-learn` with `--resume --inference --deterministic`.
The `--source-run-id` must point to a completed training run that contains
`Sentinel/checkpoint.pt` and `Runner/checkpoint.pt`.

For a command preview without launching ML-Agents:

```bash
python scripts/evaluate_policy.py \
  --manifest configs/experiment_manifests/exp_unseen_eval_seed101.yaml \
  --source-run-id LB_3v2_dynamicmaze_gpu_seed42_v1 \
  --dry-run
```

Each evaluation run writes:

- `results/<eval-run-id>/metadata/run_metadata.json`
- `results/<eval-run-id>/metadata/evaluation_metadata.json`
- `results/<eval-run-id>/metadata/config_snapshots/`

## Artifact Management

Large generated artifacts must not be committed directly to normal Git history. This keeps the repository small, cloneable, and suitable for public release.

### Files Excluded From Normal Git

The following files and folders are generated artifacts and should stay out of normal Git commits:

- Unity generated folders: `Library/`, `Temp/`, `Obj/`, `Build/`, `Builds/`, `Logs/`, and `UserSettings/`.
- Python generated files: `__pycache__/`, `*.pyc`, `*.pyo`, `.pytest_cache/`, and `.ruff_cache/`.
- Training outputs: `results/`, `summaries/`, `models/`, `checkpoints/`, `runs/`, `wandb/`, and `mlruns/`.
- Model files: `*.pth`, `*.pt`, `*.ckpt`, `*.h5`, and `*.onnx`.
- TensorBoard files: `*.tfevents*` and `events.out.tfevents.*`.
- Build artifacts: `*.exe`, `*.apk`, `*.aab`, `*.ipa`, `*.xcodeproj`, `*.xcworkspace`, `*.xcarchive`, and `*.unitypackage`.
- Local editor files: `.vscode/`, `.idea/`, `.vs/`, `.DS_Store`, `*.swp`, and `*.swo`.

### Git LFS Policy

Curated model artifacts that must be versioned may use Git LFS. The repository tracks these file types through `.gitattributes`:

```text
*.ckpt
*.pth
*.h5
*.zip
*.onnx
*.pt
*.mp4
*.mov
*.avi
```

Because model outputs are also ignored by `.gitignore`, intentionally adding one requires an explicit force add:

```bash
git lfs install
git add .gitattributes
git add -f path/to/model_or_demo_file.pth
```

Only use Git LFS for small, curated release artifacts. Do not store every training checkpoint in Git LFS.

### External Storage Policy

Use external storage for large or raw artifacts:

| Artifact type | Preferred storage |
| --- | --- |
| Full training checkpoints | Cloud storage such as AWS S3, Google Cloud Storage, Azure Blob Storage, or institutional storage. |
| Selected release checkpoints | Git LFS if needed, otherwise cloud storage. |
| Training videos and demo videos | YouTube, Vimeo, cloud storage, or institutional storage. |
| Raw training logs | Cloud storage, Google Drive, S3, or logging platforms such as ELK/Splunk. |
| Paper-ready figures and small CSV summaries | May be committed under `paper/` or a curated results folder if small. |

When external storage is used, record the storage location, access requirements, run ID, seed, config snapshots, and commit hash in the experiment manifest.

### Upload Process

1. Save raw training outputs outside Git-tracked paths or under ignored folders such as `results/`, `models/`, or `checkpoints/`.
2. Upload large artifacts to the approved external storage location.
3. Record the artifact URI in the corresponding experiment manifest.
4. Commit only the manifest, config snapshots, small metrics summaries, and selected paper-ready figures.

Example manifest fields:

```yaml
artifact_uri: "s3://labyrinth-breach/runs/LB_3v2_dynamicmaze_trapaware_seed42_v1/"
checkpoint_uri: "s3://labyrinth-breach/checkpoints/LB_3v2_dynamicmaze_trapaware_seed42_v1/"
video_uri: "https://example.com/demo-video"
```

Replace these example links with the team's real storage locations when storage is provisioned.

### Pre-Commit Artifact Check

The repository includes a local pre-commit hook configuration that blocks staged files larger than 25 MB unless they are tracked by Git LFS. It also checks that known artifact extensions use Git LFS attributes.

Install and enable it from the active Python environment:

```bash
python -m pip install pre-commit
pre-commit install
```

Run the check manually:

```bash
pre-commit run check-large-artifacts --all-files
```

If `pre-commit` is not installed, the checker can still be run directly:

```bash
python scripts/check_large_artifacts.py
```

CI should run the same check before accepting pull requests.

## References

- Unity ML-Agents release table: https://github.com/Unity-Technologies/ml-agents
- Unity ML-Agents Python trainer docs: https://unity-technologies.github.io/ml-agents/ml-agents/
- ML-Agents PyPI package: https://pypi.org/project/mlagents/
- ML-Agents environment API package: https://pypi.org/project/mlagents-envs/
