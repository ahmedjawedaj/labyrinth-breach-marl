# RL Quality Audit Report - Labyrinth Breach

## 1. Executive Summary

This audit evaluates whether the repository currently provides **empirical evidence** (not architectural intent) for four claims:

1. robust coordination  
2. stable multi-seed learning  
3. clean generalization  
4. trustworthy metrics

High-level conclusion:

- The project has **substantial structural support** for all four claims in code/config design.
- Empirical proof is **insufficient/incomplete** for all four claims at research-grade confidence.
- The current state is best described as: **implementation-ready, evidence-incomplete**.

Strict verdicts:

- Robust coordination: **cannot be confirmed from available evidence**
- Stable multi-seed learning: **contradicted** (for strong claim), at best partially supported structurally
- Clean generalization: **cannot be confirmed from available evidence**
- Trustworthy metrics: **partially supported** structurally, **cannot be confirmed** empirically

---

## 2. Scope of Audit

This audit reviewed:

- Unity runtime logic
- reward and trap logic
- observation/memory logic
- curriculum/env/trainer/reward configs
- training and evaluation orchestration scripts
- experiment manifests
- `results/` artifacts (run metadata, training status, evaluation metadata)
- documentation related to evaluation/reproduction

This audit did **not** infer behavior from class names or docs alone. Where empirical artifacts were missing, conclusions are explicitly marked as unconfirmed.

---

## 3. Evidence Reviewed

## 3.1 Core implementation files

- `unity/Assets/Scripts/Environment/PursuitEvasionEnvController.cs`
- `unity/Assets/Scripts/Agents/BaseAgent.cs`
- `unity/Assets/Scripts/Agents/SentinelAgent.cs`
- `unity/Assets/Scripts/Agents/RunnerAgent.cs`
- `unity/Assets/Scripts/Rewards/RewardEngine.cs`
- `unity/Assets/Scripts/Rewards/TrapEventDetector.cs`
- `unity/Assets/Scripts/Sensors/ObservationAssembler.cs`
- `unity/Assets/Scripts/Sensors/VisibilityTracker.cs`
- `unity/Assets/Scripts/Sensors/LastKnownPositionMemory.cs`
- `unity/Assets/Scripts/Environment/MazeGenerator.cs`
- `unity/Assets/Scripts/Environment/DynamicWallController.cs`
- `unity/Assets/Scripts/Logging/EpisodeLogger.cs`
- `unity/Assets/Scripts/Logging/StepLogger.cs`
- `unity/Assets/Scripts/Logging/ReplayEventExporter.cs`

## 3.2 Config and orchestration files

- `configs/trainer_configs/ppo_dynamicmaze_3v2.yaml`
- `configs/trainer_configs/ppo_openarena_3v2.yaml`
- `configs/reward_configs/reward_shared_plus_individual_v2.yaml`
- `configs/reward_configs/reward_dynamicmaze_memory_v4.yaml`
- `configs/env_configs/maze_static_config.yaml`
- `configs/env_configs/maze_dynamic_config.yaml`
- `configs/curriculum_configs/curriculum_3v2_full_v1.yaml`
- `configs/experiment_manifests/exp_curriculum_stage1_static_fixed_seed42.yaml`
- `configs/experiment_manifests/exp_curriculum_stage2_static_random_seed42.yaml`
- `configs/experiment_manifests/exp_curriculum_stage3_dynamic_low_seed42.yaml`
- `configs/experiment_manifests/exp_curriculum_stage4_dynamic_high_seed42.yaml`
- `configs/experiment_manifests/exp_unseen_eval_seed101.yaml`
- `scripts/train_with_metadata.py`
- `scripts/run_multiseed_curriculum.py`
- `scripts/evaluate_policy.py`
- `scripts/run_fixed_duration_eval_multiseed.py`
- `scripts/summarize_eval_kpis.py`

## 3.3 Empirical artifact files in `results/`

- `results/LB_3v2_curriculum_seed42_stage1/run_logs/training_status.json`
- `results/LB_3v2_curriculum_seed42_stage2/run_logs/training_status.json`
- `results/LB_3v2_curriculum_seed42_stage3/run_logs/training_status.json`
- `results/LB_3v2_curriculum_seed42_stage4/run_logs/training_status.json`
- `results/LB_3v2_curriculum_seed101_stage1/run_logs/training_status.json`
- `results/LB_3v2_curriculum_seed101_stage2/run_logs/training_status.json`
- `results/LB_3v2_curriculum_seed42_stage4/metadata/run_metadata.json`
- `results/LB_3v2_curriculum_seed42_stage2/metadata/run_metadata.json`
- `results/LB_3v2_curriculum_seed42_stage4_eval_seed42_30m/metadata/run_metadata.json`
- `results/LB_3v2_curriculum_seed42_stage4_eval_seed42_30m/metadata/evaluation_metadata.json`
- `results/LB_3v2_curriculum_seed42_stage4_eval_seed101_30m/metadata/run_metadata.json`
- `results/LB_3v2_curriculum_seed42_stage4_eval_seed101_30m/metadata/evaluation_metadata.json`

Not found in repository results:

- `results/**/logs/episode_log.csv`
- `results/**/logs/agent_step_log.csv`
- `results/**/eval_kpi_summary.json`

---

## 4. Structural Assessment

## 4.1 Coordination support in code

Structural support exists:

- Trap/coordination event detectors implemented (`TrapEventDetector.cs`):
  - pincer
  - enclosure
  - dead-end forcing
  - corridor control
  - exit denial
  - cluster penalty
- Reward pathways for these events are implemented (`RewardEngine.cs`) and configurable (`reward_dynamicmaze_memory_v4.yaml`).
- Sentinel chase shaping and anti-teammate-focus penalties exist in environment controller.

Assessment: **Strong structural support**.

## 4.2 Multi-seed support in scripts

Structural support exists:

- `run_multiseed_curriculum.py` supports staged training across arbitrary seed lists.
- `run_fixed_duration_eval_multiseed.py` supports seed sweeps for evaluation.

Assessment: **Strong structural support**.

## 4.3 Generalization support

Structural support exists:

- explicit unseen evaluation scene/config/manifest (`exp_unseen_eval_seed101.yaml`).
- held-out seed concept declared (`held_out_seeds` in manifest).
- deterministic evaluation mode implemented in `evaluate_policy.py`.

Assessment: **Moderate-to-strong structural support**.

## 4.4 Metrics/logging support

Structural support exists:

- per-step logging (`StepLogger.cs`)
- per-episode logging (`EpisodeLogger.cs`)
- replay/reward-event logging (`ReplayEventExporter.cs`, reward audit in `RewardEngine.cs`)
- KPI summarization script (`summarize_eval_kpis.py`)

Important structural caveat:

- Unity loggers write to `Application.persistentDataPath`, not directly to `results/`.
- evaluation wrapper and KPI script do not automatically move/collect those CSVs into run folders.

Assessment: **Moderate structural support with integration gap**.

---

## 5. Empirical Evidence Assessment

This section separates evidence actually present in artifacts from design intent.

## 5.1 Training artifacts

Observed:

- Completed/partially completed stage artifacts exist for seed 42 (`stage1..stage4`).
- `training_status.json` includes checkpoint rewards over time.
- Example instability in stage trajectories:
  - `stage4` sentinel rewards swing across checkpoints (positive -> negative -> positive).
- Seed 101 appears incomplete:
  - `LB_3v2_curriculum_seed101_stage1` has early checkpoint only.
  - `LB_3v2_curriculum_seed101_stage2/run_logs/training_status.json` contains metadata only (no behavior checkpoints).
- No seed 202 training status for curriculum stages in `results/`.

Implication:

- Multi-seed curriculum completion and comparability are not demonstrated.

## 5.2 Evaluation artifacts

Observed:

- Evaluation metadata exists for:
  - `stage4_eval_seed42_30m`
  - `stage4_eval_seed101_30m`
- No artifact found for corresponding `seed202` shard.
- No KPI JSON files found under `results/`.
- No `episode_log.csv` / `agent_step_log.csv` found under `results/`.

Implication:

- Reported fixed-duration pipeline is structurally present, but **evaluation outputs needed for research claims are not in available evidence**.
- Based on available repository artifacts alone, final unseen-generalization claims cannot be validated.

## 5.3 Metrics integrity evidence

Observed:

- `summarize_eval_kpis.py` computes some KPIs but uses proxies:
  - “wall_collision_recovery_time_proxy” explicitly marked as proxy (stall fraction), not direct collision recovery measurement.
  - no explicit coordination KPIs (pincer/corridor/exit denial rates) computed there.
- Docs request richer metrics (`docs/evaluation_protocol.md`) than currently computed by script.

Implication:

- Metrics layer is partially implemented but not sufficient to support strong research claims without additional computed outputs and artifact capture.

---

## 6. Claim-by-Claim Findings

## 6.1 Claim: robust coordination

### A) Structural support

**Yes (high)**:

- Coordination-like events are formally encoded in `TrapEventDetector.cs`.
- Rewards for coordination events are wired in `RewardEngine.cs` and reward configs.

### B) Empirical evidence

**Cannot be confirmed from available evidence**:

- No coordination metric outputs found (e.g., pincer success rates across runs).
- No episode/replay CSVs found in repository results for quantitative confirmation.
- No seed-level coordination analysis artifacts found.

### Verdict

**cannot be confirmed**

---

## 6.2 Claim: stable multi-seed learning

### A) Structural support

**Yes (high)**:

- Multi-seed scripts exist for training and evaluation.

### B) Empirical evidence

Evidence does not support a stable multi-seed claim:

- Seed42 has staged artifacts.
- Seed101 appears incomplete/inconsistent at curriculum level.
- Seed202 curriculum artifacts absent in reviewed results.
- Evaluation seed coverage appears incomplete (missing seed202 eval artifacts for the cited run family).

### Verdict

**contradicted** (for “stable multi-seed learning” as a demonstrated claim)

---

## 6.3 Claim: clean generalization

### A) Structural support

**Yes (medium-high)**:

- Unseen eval scene/manifest and held-out seed intent are present.

### B) Empirical evidence

**Cannot be confirmed from available evidence**:

- No summarized seen-vs-unseen comparison outputs found.
- No KPI JSONs and no eval CSVs in results tree to quantify generalization.
- Evaluation metadata exists, but metadata alone is not performance proof.

### Verdict

**cannot be confirmed**

---

## 6.4 Claim: trustworthy metrics

### A) Structural support

**Partially yes (medium)**:

- Logging components and KPI script exist.
- Reward audit by category/event exists in code.

### B) Empirical evidence

**Insufficient for strong trustworthiness claim**:

- Required raw logs for KPI script are not found in reviewed `results/` structure.
- KPI script includes proxy metrics and lacks explicit coordination metrics from `evaluation_protocol.md`.
- No evidence of robust handling/reporting of missing eval shards in final KPI outputs.

### Verdict

**partially supported** (structurally) / **cannot be confirmed** (empirically)

---

## 7. Gaps and Risks

## Gap 1 - Missing empirical KPI artifacts in results

- Severity: **critical**
- Why it matters: without generated KPI outputs and raw eval CSVs, claims cannot be validated.
- Missing evidence: `episode_log.csv`, `agent_step_log.csv`, `eval_kpi_summary.json` for target runs.
- Validation step: persist/copy Unity logs into run-specific `results/<eval_run_id>/logs/` and generate KPI JSON for each seed.

## Gap 2 - Incomplete multi-seed execution

- Severity: **critical**
- Why it matters: stability claim requires comparable complete seed set.
- Missing evidence: complete stage1-4 training + eval for seeds 42/101/202.
- Validation step: rerun multi-seed pipeline with strict completion matrix and produce per-seed summary table.

## Gap 3 - Coordination metrics not operationalized in final reports

- Severity: **high**
- Why it matters: robust coordination requires quantitative proof, not reward hooks only.
- Missing evidence: pincer/corridor/exit-denial rates per seed from run logs.
- Validation step: add metric extraction script from replay/audit logs and publish aggregated coordination tables.

## Gap 4 - Metric-definition mismatch between docs and scripts

- Severity: **high**
- Why it matters: “trustworthy metrics” requires consistency between protocol and computation.
- Missing evidence: computed metrics for all items described in `docs/evaluation_protocol.md`.
- Validation step: align KPI script with protocol, include schema versioning/tests, and generate reproducible report outputs.

## Gap 5 - Reproducibility metadata has unresolved snapshot entries

- Severity: **medium**
- Why it matters: unresolved config snapshot paths reduce confidence in exact reproducibility.
- Missing evidence: all source config references resolved and archived.
- Validation step: fix snapshot-source resolution in metadata tooling and verify all `exists=false` entries are eliminated for official runs.

---

## 8. What Can Be Claimed Safely Right Now

- The project implements a sophisticated RL environment and reward architecture for pursuit-evasion.
- Coordination-relevant detectors and reward terms are implemented in runtime code.
- Curriculum, fixed-duration evaluation, and metadata capture tooling exist.
- At least one full seed42 curriculum sequence produced training artifacts and checkpoints.

---

## 9. What Cannot Be Claimed Yet

- Robust coordination is demonstrated empirically across seeds.
- Multi-seed learning is stable.
- Clean generalization to unseen layouts is quantitatively established.
- Metrics are research-grade trustworthy for publication-level claims.

For each of these, current status is: **cannot be confirmed from available evidence** (or contradicted for stable multi-seed claim).

---

## 10. Recommended Validation Plan

1. **Lock evaluation artifact pathing**
   - Ensure Unity logs (`episode_log.csv`, `agent_step_log.csv`, `replay_events.csv`, `reward_audit.csv`) are copied into `results/<eval_run_id>/logs/`.
2. **Complete a strict 3-seed matrix**
   - Train stage1-4 for seeds 42/101/202 with identical stop conditions.
3. **Run complete fixed-duration unseen eval**
   - All 3 seeds with identical duration and deterministic inference settings.
4. **Produce required KPI suite**
   - Include win rates, capture times, path metrics, and explicit coordination metrics.
5. **Publish a seed-level summary table**
   - mean/std/confidence intervals, pass/fail checks, and missing-shard handling.
6. **Add consistency tests**
   - Unit/integration tests that fail if required logs or KPI files are absent.
7. **Run ablation matrix**
   - trap-aware on/off, memory on/off, dynamic walls low/high to show causal contribution.

---

## 11. Final Scorecard

| Claim | Structural support | Empirical evidence | Confidence level | Verdict | Key evidence | Main blockers |
|---|---|---|---|---|---|---|
| robust coordination | High | Low | Very low | cannot be confirmed | `TrapEventDetector.cs`, trap rewards in `RewardEngine.cs` | no coordination KPI outputs, no replay-derived summary artifacts |
| stable multi-seed learning | High | Low/negative | Very low | contradicted | multi-seed scripts exist; seed42 staged runs exist | incomplete seed coverage (101 partial, 202 absent), missing comparable summaries |
| clean generalization | Medium-high | Low | Very low | cannot be confirmed | unseen eval manifest + evaluation metadata for seeds 42/101 | no seen-vs-unseen KPI tables, missing seed202 eval shard and KPI artifacts |
| trustworthy metrics | Medium | Low | Low | partially supported (structure), cannot be confirmed (proof) | step/episode/replay/reward loggers + KPI script | logs not present in results, proxy metrics, protocol-script mismatch |

---

## 12. Appendix: Evidence References

Implementation:

- `unity/Assets/Scripts/Environment/PursuitEvasionEnvController.cs`
- `unity/Assets/Scripts/Agents/BaseAgent.cs`
- `unity/Assets/Scripts/Rewards/RewardEngine.cs`
- `unity/Assets/Scripts/Rewards/TrapEventDetector.cs`
- `unity/Assets/Scripts/Sensors/ObservationAssembler.cs`
- `unity/Assets/Scripts/Sensors/VisibilityTracker.cs`
- `unity/Assets/Scripts/Sensors/LastKnownPositionMemory.cs`
- `unity/Assets/Scripts/Environment/MazeGenerator.cs`
- `unity/Assets/Scripts/Environment/DynamicWallController.cs`
- `unity/Assets/Scripts/Logging/EpisodeLogger.cs`
- `unity/Assets/Scripts/Logging/StepLogger.cs`
- `unity/Assets/Scripts/Logging/ReplayEventExporter.cs`

Configs and manifests:

- `configs/trainer_configs/ppo_dynamicmaze_3v2.yaml`
- `configs/trainer_configs/ppo_openarena_3v2.yaml`
- `configs/reward_configs/reward_shared_plus_individual_v2.yaml`
- `configs/reward_configs/reward_dynamicmaze_memory_v4.yaml`
- `configs/env_configs/maze_static_config.yaml`
- `configs/env_configs/maze_dynamic_config.yaml`
- `configs/curriculum_configs/curriculum_3v2_full_v1.yaml`
- `configs/experiment_manifests/exp_curriculum_stage1_static_fixed_seed42.yaml`
- `configs/experiment_manifests/exp_curriculum_stage2_static_random_seed42.yaml`
- `configs/experiment_manifests/exp_curriculum_stage3_dynamic_low_seed42.yaml`
- `configs/experiment_manifests/exp_curriculum_stage4_dynamic_high_seed42.yaml`
- `configs/experiment_manifests/exp_unseen_eval_seed101.yaml`

Scripts:

- `scripts/train_with_metadata.py`
- `scripts/run_multiseed_curriculum.py`
- `scripts/evaluate_policy.py`
- `scripts/run_fixed_duration_eval_multiseed.py`
- `scripts/summarize_eval_kpis.py`

Empirical artifacts:

- `results/LB_3v2_curriculum_seed42_stage1/run_logs/training_status.json`
- `results/LB_3v2_curriculum_seed42_stage2/run_logs/training_status.json`
- `results/LB_3v2_curriculum_seed42_stage3/run_logs/training_status.json`
- `results/LB_3v2_curriculum_seed42_stage4/run_logs/training_status.json`
- `results/LB_3v2_curriculum_seed101_stage1/run_logs/training_status.json`
- `results/LB_3v2_curriculum_seed101_stage2/run_logs/training_status.json`
- `results/LB_3v2_curriculum_seed42_stage4/metadata/run_metadata.json`
- `results/LB_3v2_curriculum_seed42_stage2/metadata/run_metadata.json`
- `results/LB_3v2_curriculum_seed42_stage4_eval_seed42_30m/metadata/run_metadata.json`
- `results/LB_3v2_curriculum_seed42_stage4_eval_seed42_30m/metadata/evaluation_metadata.json`
- `results/LB_3v2_curriculum_seed42_stage4_eval_seed101_30m/metadata/run_metadata.json`
- `results/LB_3v2_curriculum_seed42_stage4_eval_seed101_30m/metadata/evaluation_metadata.json`

Protocol/docs referenced:

- `docs/evaluation_protocol.md`
- `docs/reproduction_guide.md`

