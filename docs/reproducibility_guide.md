# Reproducibility Guide

This is the canonical path for regenerating the publication evidence. Commands
are run from the repository root. Do not edit generated CSV, JSON, ONNX, or
checkpoint files manually.

## 1. Environment

- macOS standalone built with Unity `6000.0.40f1`
- Unity ML-Agents package `com.unity.ml-agents@4.0.0`
- Python `3.10.12`, `mlagents==1.1.0`, and `torch==2.2.1`
- Official policy seeds: `42`, `101`, `202`, `606`, `707`
- Held-out topology seeds: `101`, `202`, `303`, `404`, `505`

Create the Python environment from `environment.yml`, then build the player:

```bash
conda env create -f environment.yml
conda activate labyrinth-breach
python scripts/build_unity_player.py
```

The build must create `builds/macos/LabyrinthBreach.app` and a build manifest.

## 2. Prelaunch Gates

```bash
python scripts/setup_validation.py
python scripts/pretraining_implementation_audit.py
python scripts/validate_training_budgets.py
python scripts/validate_reward_ablation.py
python scripts/validate_evaluation_controls.py
python scripts/validate_ablation_controls.py --condition memory_off
python scripts/validate_ablation_controls.py --condition action_assist_on \
  --output results/official_summary/action_assist_on_control_audit.json
python scripts/validate_ablation_controls.py --condition dynamic_wall_off
python -m unittest discover -s tests -v
python scripts/analyze_experiment_power.py
```

Expected pass counts are 25/25 implementation checks, 8/8 reward checks, 11/11
training-budget checks, 10/10
seen/held-out control checks, 8/8 memory checks, and 6/6 checks for each
evaluation-only rule intervention. A failed gate invalidates a launch rather
than merely generating a warning.

## 3. Official Training

```bash
python scripts/run_multiseed_curriculum.py \
  --resume-completed \
  --env builds/macos/LabyrinthBreach.app \
  --allow-cpu \
  --no-graphics
```

The matrix contains 20 runs: four transferred stages for each of five policy
seeds. Stage completion is determined by the fixed ML-Agents trainer-step budget,
not the YAML episode or win-rate audit thresholds. The launcher transfers both
role checkpoints with `--initialize-from`, generates KPIs, and runs a strict
33-check audit before allowing the next stage to start.

Both role trainers use asymmetric snapshot self-play. One role learns at a
time, the learning team changes every 100,000 behavior steps, opponent
snapshots are saved every 20,000 steps, and the deployed opponent changes every
2,000 steps. Each opponent draw is 50% the latest policy and 50% uniform over a
ten-snapshot window. Static, dynamic, and matched direct-dynamic trainer files
must use the same self-play schedule; `validate_training_budgets.py` audits
these values as well as the equal 1.5M per-role transition-sample budgets. Equal
`max_steps` is required because ML-Agents alternates the learning team after an
equal number of wrapped-trainer steps.

After all 20 runs pass, export the official learning-curve evidence:

```bash
PATH=/opt/anaconda3/envs/labyrinth-breach/bin:$PATH \
python scripts/analyze_official_training_curves.py
```

The exporter refuses incomplete matrices. It writes raw per-seed TensorBoard
reward, episode-length, ELO, entropy, and loss scalars; matched-step means and
Student-t intervals; and PDF/PNG figures under
`results/official_summary/training_curves/`.

## 4. Official Evaluation

```bash
python scripts/run_publication_eval_matrix.py \
  --results-dir results/publication_eval_official \
  --resume-completed \
  --env builds/macos/LabyrinthBreach.app \
  --allow-cpu \
  --no-graphics
```

This evaluates every Stage 4 policy on one seen and five held-out topologies.
Every policy-topology cell must reach 100 completed episodes; the 30-minute cap
marks failure if the target is unmet. The launcher automatically runs artifact,
provenance, topology, and statistical audits after aggregation.

## 5. Ablation Suite

```bash
python scripts/run_publication_ablation_suite.py \
  --env builds/macos/LabyrinthBreach.app \
  --allow-cpu \
  --no-graphics \
  --resume-completed
```

The suite executes five registered conditions:

1. Memory off: retrain all seeds and stages with the six memory inputs zeroed,
   target-memory updates stopped, and assist fallback to remembered targets disabled.
2. Tactical reward off: retrain all seeds and stages.
3. Direct dynamic training: retrain each seed with the matched total step budget.
4. Action assist on: paired hybrid-controller intervention against the canonical
   assist-off policy evaluation.
5. Dynamic walls off: paired intervention on the full policies.

Every condition is evaluated on the same six topologies and 100-episode cells.
`scripts/analyze_paired_ablation.py` exports full-minus-ablated cell deltas,
paired effect sizes, sign consistency, and hierarchical bootstrap intervals.
The analyzer includes outcome/timing metrics plus tactical-event prevalence and
intensity, spread/separation, path efficiency, stall fraction, and wall-shift
route response from KPI schema v3.

The same canonical workflow can be invoked end to end with:

```bash
python scripts/run_full_remediation.py \
  --env builds/macos/LabyrinthBreach.app \
  --allow-cpu \
  --no-graphics
```

## 6. Required Run Artifacts

Each publication run must contain non-empty copies of:

- `metadata/run_metadata.json`
- `metadata/training_status.json` or `metadata/evaluation_status.json`
- `metadata/config_snapshots/`
- `logs/episode_log.csv`
- `logs/agent_step_log.csv`
- `logs/reward_audit.csv`
- `logs/replay_events.csv`
- `kpi/*.json`
- `kpi/*.csv`

Training runs additionally contain Sentinel and Runner checkpoints and ONNX
exports. Every episode row records the run ID, seed, effective Unity scene,
rule/reward configuration, curriculum stage, layout ID, and topology seed. Runs
using `unknown_run`, `seed_unknown`, fallback log copying, or mismatched observed
provenance are excluded.

## 7. Readiness and Manuscript

```bash
python scripts/audit_publication_readiness.py
python scripts/build_current_evidence_snapshot.py
cd paper
latexmk -pdf -interaction=nonstopmode -halt-on-error \
  labyrinth_breach_journal.tex
cp labyrinth_breach_journal.pdf labyrinth_breach_revised_publication_report.pdf
```

The readiness audit must report `READY_FOR_SUBMISSION_REVIEW`. A manuscript PDF
alone is not readiness: official training, fixed-count evaluation, and all five
paired ablation analyses must also pass. The final PDF is
`paper/labyrinth_breach_revised_publication_report.pdf`. The current
no-retraining snapshot is generated under
`results/official_summary/current_evidence_snapshot.*`.

After all gates pass, build the hashed evidence pack:

```bash
python scripts/build_publication_evidence_pack.py
```

The pack preserves canonical configs, scripts, manuscript sources, audits,
training checkpoints, raw logs, evaluation outputs, and paired analyses under
`output/evidence/labyrinth_breach_publication/`. `artifact_manifest.json` and
`SHA256SUMS` make every included file independently verifiable. The command
refuses to create a submission pack while readiness is blocked.
