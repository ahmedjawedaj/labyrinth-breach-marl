# Retraining and Results Report

## 1. Executive Summary

- Scope executed: full pre-training implementation audit, full 3-seed/4-stage training pipeline launch attempt, evaluation launch prerequisites, artifact/KPI validation, and summary export generation.
- Outcome: **NOT COMPLETE / NOT RESEARCH-READY**.
- Primary blocker: ML-Agents consistently waits for Unity runtime connection (`Listening on port 5004. Start training by pressing the Play button in the Unity Editor.`), and no standalone Unity executable is present in repository for headless automation.
- Result: official matrix did not complete; required seen/unseen evaluation outputs and KPI summaries are missing.

## 2. Implementation Check Result

- Audit output: `results/official_summary/pretraining_implementation_audit.json`
- Audit table: `results/official_summary/pretraining_implementation_audit.csv`
- Check result: **19 PASS / 1 FAIL**
  - PASS: required scenes, Sentinel/Runner behavior names, team IDs, behavior type, decision requester period, stale model null refs in prefabs, reset/capture/exit/dynamic-wall/observation wiring, memory toggle config support, reward/trap/logging/metadata/artifact/KPI script presence.
  - FAIL: Unity CLI discoverability from shell (`Unity`/`unity-editor` not found in `PATH`), preventing batchmode compile/run verification from this environment.

## 3. Training Matrix Status

- Matrix manifest: `configs/experiment_manifests/official_curriculum_matrix.yaml`
- Official run-id template verified in manifest: `LB_3v2_official_seed{seed}_{stage_id}`
- Attempted pipeline launch command:
  - `python scripts/run_full_remediation.py --allow-cpu --no-graphics --timeout-wait 120`
- Runtime evidence:
  - ML-Agents reached wait state for Unity connection on port 5004.
  - One partial training metadata entry exists for `seed42_stage1`; status reports interrupted termination (`exit_code=-15`).
- Strict matrix completion report:
  - `results/LB_3v2_curriculum_official_v1/completion/seed_completion_report.json`
  - `results/LB_3v2_curriculum_official_v1/completion/seed_completion_report.csv`

## 4. Seed Completion Table

Source: `results/official_summary/training_completion_matrix.csv`

- Seed 42: stage1 failed (`training_status exit_code=-15`), stage2-4 missing artifacts, eval seen/unseen missing, meta-evaluation missing.
- Seed 101: stage1-4 missing artifacts, eval seen/unseen missing, meta-evaluation missing.
- Seed 202: stage1-4 missing artifacts, eval seen/unseen missing, meta-evaluation missing.

## 5. Seen vs Unseen Evaluation Table

Source: `results/official_summary/seen_unseen_comparison.csv`

- All official seeds have empty rows (no seen/unseen completed runs).
- Missing aggregate eval artifact:
  - `results/LB_3v2_seen_unseen_eval_official_v1/eval/final_seen_unseen_summary.csv`

## 6. Core KPI Summary

Source: `results/official_summary/multiseed_kpi_summary.csv`

- No computed rows (file header only).
- Reason: evaluation KPI generation did not occur due incomplete evaluations.

## 7. Coordination KPI Summary

Source: `results/official_summary/coordination_kpi_summary.csv`

- No rows produced.
- Reason: no completed eval run roots with `kpi/eval_kpi_summary.json` available.

## 8. Reward Breakdown Summary

Source: `results/official_summary/reward_breakdown_summary.csv`

- No rows produced.
- Reason: no completed eval run roots with `logs/reward_breakdown.csv` available.

## 9. Memory/Observation Notes

- Static implementation audit confirms memory-related components/configs exist:
  - `unity/Assets/Scripts/Sensors/LastKnownPositionMemory.cs`
  - memory-off config files under `configs/env_configs/*_memory_off.yaml` with `use_memory: false`.
- Runtime validation for memory ablation is **not available** because training/evaluation runs did not complete.

## 10. Dynamic Wall Impact Notes

- Static implementation audit confirms dynamic wall wiring in controller/scripts.
- Runtime dynamic-wall tactical impact metrics are **not available** (no successful stage/eval completion).

## 11. Role Emergence Notes

- Role analysis scripts exist in codebase but no new official evaluation outputs were generated for this retraining attempt.
- Therefore, sentinel/runner role KPI outputs are **not confirmed for this run**.

## 12. Missing Artifacts or Failed Runs

Canonical missing/failure list:
- `results/official_summary/missing_artifacts_report.csv`

Highlights:
- Missing stage artifacts for official run IDs `LB_3v2_official_seed{seed}_stage{1..4}` (all seeds, except partial seed42 stage1 metadata).
- Missing eval artifacts for official IDs:
  - `LB_3v2_seen_unseen_eval_official_v1_seed42_seen_30m`
  - `LB_3v2_seen_unseen_eval_official_v1_seed42_unseen_30m`
  - `LB_3v2_seen_unseen_eval_official_v1_seed101_seen_30m`
  - `LB_3v2_seen_unseen_eval_official_v1_seed101_unseen_30m`
  - `LB_3v2_seen_unseen_eval_official_v1_seed202_seen_30m`
  - `LB_3v2_seen_unseen_eval_official_v1_seed202_unseen_30m`
- Missing per-seed `meta_evaluation.json` for all official seeds.
- Seed42 stage1 recorded failure status: `training_status exit_code=-15`.

## 13. Result Quality Judgment

- Judgment: **NOT RESEARCH-READY**.
- Rationale:
  - Official 3-seed matrix incomplete.
  - Seen/unseen evaluation not completed.
  - Required KPI outputs absent.
  - No defensible multi-seed generalization or coordination claim can be made.

## 14. Next Fixes Required

1. Provide a runnable Unity environment path for CLI-driven training/eval (`--env`), or keep Unity Editor running in Play mode continuously during ML-Agents runs.
2. Re-run official matrix end-to-end after Unity runtime connectivity is guaranteed.
3. Re-run strict completion tracker and verify all required logs/KPIs exist and are non-empty.
4. Regenerate summary tables only after successful eval completion.

---

## Commands Used (for reproducibility)

```bash
python scripts/pretraining_implementation_audit.py --results-dir results --output results/official_summary/pretraining_implementation_audit.json
python scripts/run_full_remediation.py --allow-cpu --no-graphics --timeout-wait 120
python scripts/seed_completion_tracker.py --training-matrix-manifest configs/experiment_manifests/official_curriculum_matrix.yaml --eval-matrix-manifest configs/experiment_manifests/official_seen_unseen_eval_matrix.yaml --results-dir results --output-dir results
python scripts/build_official_summary_reports.py --results-dir results --training-family LB_3v2_curriculum_official_v1 --eval-family LB_3v2_seen_unseen_eval_official_v1
```
