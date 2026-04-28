# implementation_audit_summary

## actual implemented scope
- Unity ML-Agents environment with 3 Sentinels vs 2 Runners.
- Scenes for open arena, static maze, dynamic maze, and unseen eval.
- Core gameplay systems implemented: capture, exits, episode lifecycle, spawn/reset, dynamic wall shifts.
- Observation stack implemented with vector observations, custom ray observations, visibility/LOS, and last-known-position memory.
- Reward system implemented with terminal rewards, shaping terms, penalties, and optional trap-aware tactical rewards (pincer/enclosure/corridor/exit denial).
- Logging and evaluation pipeline implemented with run-scoped logs and KPI summarization scripts.

## biggest problems
- Duplicate Unity trees (`unity/Assets/...` and `unity/...`) create maintenance and drift risk.
- Extra nested Unity project artifacts (`Labyrinth-Breach/New Unity Project`) add ambiguity.
- Aggregate summary artifacts in `results` appear stale/inconsistent with per-run artifacts.
- Reward provenance consistency risk between metadata-config references and observed run logs in some artifacts.
- Buffer sensor path appears partially implemented but not clearly active in final ML-Agents sensor pipeline.

## biggest strengths
- Strong config-driven pipeline (`configs` + orchestration scripts) for training/eval.
- Clear multi-seed seen/unseen evaluation structure.
- Rich runtime logging (`episode_log`, `step_log`, `reward_audit`, `replay_events`) and KPI generation.
- Tactical coordination logic exists in code (trap event detection and reward hooks).
- Reproducibility scaffolding exists (run metadata, model hashes, eval metadata).

## publication readiness
- Current status: suitable for final semester submission.
- Paper direction: viable for student/workshop-style paper after consistency cleanup.
- Strongest angle: coordination under dynamic topology and partial observability (memory/LOS) in 3v2 pursuit-evasion.

## must-fix items
- Canonicalize Unity source/asset tree and remove duplication ambiguity.
- Regenerate official aggregate summaries directly from current raw run artifacts.
- Add automated checks that metadata reward config aligns with runtime episode/reward logs.
- Validate and document active observation pipeline (especially buffer sensor intent vs actual usage).
- Add sanity checks for KPI parsing/proxy metrics and publish a reproducibility snapshot script.
