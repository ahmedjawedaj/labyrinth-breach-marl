# Publication Upgrade Guide

This guide is the canonical execution path for upgrading Labyrinth Breach from a course report to a publication-ready simulation benchmark submission.

## 1. Build the Unity player

Close any Unity Editor instance that has this project open, then run:

```bash
python scripts/build_unity_player.py
```

Expected output:

- `builds/macos/LabyrinthBreach.app`
- `builds/macos/build_manifest.json`
- `builds/macos/unity_build.log`

If the build fails because another Unity instance is open, close Unity and rerun the command. Use `--server-build` only after installing Unity's macOS Dedicated Server module; the normal player supports automated `--no-graphics` evaluation.

## 2. Run a checkpoint smoke evaluation

Use the existing `v5_dynamicmaze` checkpoint family for a quick evidence pass:

```bash
python scripts/run_publication_eval_matrix.py \
  --source-run-id v5_dynamicmaze \
  --skip-training-status-check \
  --results-dir results/publication_eval_v2 \
  --env builds/macos/LabyrinthBreach.app \
  --allow-cpu \
  --no-graphics \
  --target-episodes 10 \
  --max-runtime-seconds 600
```

This runs one legacy policy pair across three evaluation seeds, one seen
topology, and five generated held-out topologies. It is a pipeline smoke test,
not three independently trained policy seeds and not a paper result. The command
fails if a ten-episode cell is incomplete, Unity logs are missing, or provenance
is routed through fallback locations.

Audit the diagnostic matrix:

```bash
python scripts/audit_publication_eval_matrix.py \
  --aggregate results/publication_eval_v2/aggregate/publication_eval_summary.json \
  --results-dir results/publication_eval_v2 \
  --output results/publication_eval_v2/aggregate/publication_eval_audit.json \
  --enforce-episode-target \
  --expected-episodes 10 \
  --enforce-topology-provenance
```

The audit requires 18 matrix cells, 108 raw/KPI artifacts, and correct episode-level scene/rule/reward provenance.

## 3. Run official retraining

After the standalone player works, run the official curriculum matrix:

```bash
python scripts/run_multiseed_curriculum.py \
  --resume-completed \
  --env builds/macos/LabyrinthBreach.app \
  --allow-cpu \
  --no-graphics
```

Then run the strict fixed-count official evaluation:

```bash
python scripts/run_publication_eval_matrix.py \
  --results-dir results/publication_eval_official \
  --resume-completed \
  --env builds/macos/LabyrinthBreach.app \
  --allow-cpu \
  --no-graphics
```

Run all five registered ablations and paired analyses with:

```bash
python scripts/run_publication_ablation_suite.py \
  --env builds/macos/LabyrinthBreach.app \
  --allow-cpu \
  --no-graphics \
  --resume-completed
```

## 4. Required artifacts

Every run used in the paper must contain:

- `metadata/run_metadata.json`
- `logs/episode_log.csv`
- `logs/agent_step_log.csv`
- `logs/reward_audit.csv`
- `logs/replay_events.csv`
- `kpi/eval_kpi_summary.json`
- `kpi/eval_kpi_summary.csv`

Do not use runs containing `seed_unknown`, `unknown_run`, missing logs, or fallback-copied logs.

## 5. Publication claim rules

- Use legacy results only as preliminary motivation.
- Report final results only from canonical KPI outputs.
- Include confidence intervals or at least mean/std across seeds.
- Include action-assist-off results before claiming learned coordination.
- Include at minimum memory, tactical reward, dynamic wall, curriculum, and action-assist ablations.
- Disclose simulation-only status and absence of physical robot validation.
