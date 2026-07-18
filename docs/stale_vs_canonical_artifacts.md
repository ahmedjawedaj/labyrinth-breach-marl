# Stale vs Canonical Artifacts

## Canonical Manuscript

- Source: `paper/labyrinth_breach_journal.tex`
- Rendered PDF: `output/pdf/labyrinth_breach_journal.pdf`
- Evidence status: `results/official_summary/publication_readiness.json`
- Current factual boundary: `docs/current_empirical_truth.md`

`paper/labyrinth_breach_final.tex` is the superseded six-page course report.
`paper/viva_cheatsheet.tex` is a legacy May 2025 study aid. Both now contain
visible superseded labels and must not be submitted as the publication paper.

## Canonical Raw Evidence

Training truth is stored under `results/<run_id>/` and requires:

- `metadata/run_metadata.json`
- `metadata/training_status.json`
- `metadata/training_audit.json`
- `logs/episode_log.csv`
- `logs/agent_step_log.csv`
- `logs/reward_audit.csv`
- `logs/replay_events.csv`
- `kpis/eval_kpi_summary.json`
- `kpis/eval_kpi_summary.csv`
- Sentinel and Runner checkpoints/ONNX exports

Official evaluation truth is under `results/publication_eval_official/`.
Ablation truth is under `results/ablations/<condition>/`. Derived statistics are
valid only when regenerated from those run-scoped logs by the canonical scripts.

## Explicitly Invalidated Evidence

- `results/publication_eval/`: standalone scene/config routing was incorrect.
- `results/LB_3v2_official_seed42_stage1_mixed_log_restart_invalidated_20260716/`:
  mixed legacy and V5 append-only rows after a forced retry.
- `results/LB_3v2_official_seed42_stage1_asymmetric_budget_invalidated_20260716/`:
  interrupted after detecting unsynchronized 3v2 role budgets.
- Any run with `INVALIDATED.md`, `unknown_run`, `seed_unknown`, fallback-copied
  logs, missing artifacts, or observed scene/rule/reward mismatch.

The historical one-checkpoint diagnostic in `results/publication_eval_v2/` may
be discussed only as pipeline and configuration-shift evidence. Its five unseen
seed configurations reused one hard-coded topology and changed other dynamics;
it is not topology-generalization evidence.

## Safe Regeneration Rule

Regenerate summaries, statistics, plots, audits, and the manuscript from raw
run artifacts. Never hand-edit raw logs, model files, or completed-run metadata.
