# Run-Scoped Unity Log Routing

Raw Unity artifacts are now routed per run to:

- `results/<run_id>/logs/episode_log.csv`
- `results/<run_id>/logs/agent_step_log.csv`
- `results/<run_id>/logs/reward_audit.csv`
- `results/<run_id>/logs/replay_events.csv`

## How it works

- `scripts/train_with_metadata.py` and `scripts/evaluate_policy.py` now write `configs/runtime_overrides/active_run_context.json` before launching ML-Agents.
- Unity log writers (`EpisodeLogger`, `StepLogger`, `ReplayEventExporter`, `RewardEngine`, and `EpisodeStateTracker`) resolve output paths from that run context first.
- If run context is unavailable, Unity falls back to `Application.persistentDataPath/LabyrinthBreachLogs` (legacy behavior preserved).
- After each run, Python automatically collects missing required logs from known Unity fallback locations into `results/<run_id>/logs/`.

## Failure behavior

- On successful training runs (`exit code 0`) and fixed-duration/successful evaluation runs (`exit code 0` or `124`), missing required artifacts cause the script to fail with a clear error.
- On failed runs, log collection still executes best-effort and reports missing files without masking the original failure.
- Evaluation now performs strict KPI validation:
  - `evaluate_policy.py` runs `summarize_eval_kpis.py` after raw log collection (unless explicitly skipped).
  - KPI outputs must exist and be non-empty in `results/<run_id>/kpi/`:
    - `eval_kpi_summary.json`
    - `eval_kpi_summary.csv`
  - `run_fixed_duration_eval_multiseed.py` re-validates raw logs and KPI outputs per seed before reporting overall success.
