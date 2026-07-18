# Publication Upgrade Pause and Conclusion

Generated: 2026-07-18

## Decision

This campaign is paused intentionally. The current repository contains a
substantially upgraded publication pipeline, manuscript draft, reproducibility
protocol, canonical evaluation data, audited five-seed training curves, and two
completed paired ablation analyses. It is not yet a complete journal evidence
pack because three ablation families remain unfinished.

The honest conclusion is: the project is now much stronger than the earlier
six-page report, but the full publication-grade experiment matrix should not be
claimed complete.

## Current Strict Status

- Training: 47/65 strict runs complete.
- Evaluation: 90/180 target-complete cells.
- Publication readiness: 14/16 gates passed.
- Disk at pause: approximately 74 GB free.
- Detached training/evaluation workers were stopped after the pause snapshot.
- The generated campaign status may still label interrupted in-progress stages
  as `running` because that field comes from run metadata, not live OS process
  inspection. At the pause point, no `mlagents-learn`, Unity player, or
  Labyrinth worker process remained active.
- Official five-seed curriculum training: 20/20 audited runs complete.
- Audited five-seed learning curves: complete.
- Canonical 30-cell evaluation: complete.
- Paired ablations complete: action assist on/off and dynamic wall on/off.

## Completed Evidence

- Built and used the macOS Unity standalone player for reproducible runs.
- Added strict run metadata, seed tracking, raw log validation, KPI exports, and
  provenance checks.
- Expanded held-out evaluation to one seen topology and five held-out topology
  seeds per policy seed.
- Added canonical fixed-count evaluation with 100 completed episodes per cell.
- Added official statistical outputs: policy/layout/episode bootstrap intervals,
  Wilson intervals, per-seed summaries, and paired ablation effect tables.
- Generated audited five-seed learning curves from TensorBoard scalar exports.
- Added recent 2020-2026 literature review material and upgraded the manuscript
  into a 12-page IEEE-style draft.
- Added protocol, control, reward, topology, training-budget, and publication
  readiness audits.

## Current Empirical Results Available

Available result families:

- Canonical assist-off evaluation:
  `results/publication_eval_official/aggregate/publication_eval_summary.csv`
- Action-assist paired ablation:
  `results/official_summary/ablations/action_assist_on/paired_effects.csv`
- Dynamic-wall paired ablation:
  `results/official_summary/ablations/dynamic_wall_off/paired_effects.csv`
- Learning curves:
  `results/official_summary/training_curves/`
- Readiness report:
  `results/official_summary/publication_readiness.md`
- Campaign status:
  `results/orchestration/publication_campaign_status.md`

## Remaining Work

The unfinished gates are:

1. Memory-off evaluation and paired analysis.
2. Tactical-reward-off training/evaluation and paired analysis.
3. Direct-dynamic training/evaluation and paired analysis.
4. Final aggregate/evidence-pack regeneration after all five ablations are
   complete.

Estimated remaining wall time at the observed machine load was 32-64 hours,
mostly because direct-dynamic training uses a much larger step budget.

## Recommendation

For a near-term advisor review, use the current state as a strong partial
evidence package and frame the manuscript honestly:

- The environment, metrics, audits, and canonical evaluation are now
  publication-style.
- The completed results support a simulation benchmark/preprint or workshop
  submission path.
- A journal submission should wait until all five ablation families and the
  final evidence pack are complete.

Do not claim that the full five-ablation publication plan is complete. Do not
claim direct-dynamic or memory-off/tactical-off ablation conclusions from the
paused state.

## Resume Notes

Do not delete `results/`, `worker_status/`, or the worker folders under
`../labyrinth-breach-workers/` if continuation is desired. They contain
checkpoints, logs, metadata, and completion markers used by the resume-aware
scripts.

Primary resume command:

```bash
screen -L -Logfile results/orchestration/remaining_gates.log -dmS labyrinth-publication-gates /bin/sh scripts/run_remaining_publication_gates.sh
```

After resume completion, rerun:

```bash
/opt/anaconda3/envs/labyrinth-breach/bin/python scripts/summarize_publication_campaign.py
/opt/anaconda3/envs/labyrinth-breach/bin/python scripts/audit_publication_readiness.py
/opt/anaconda3/envs/labyrinth-breach/bin/python scripts/build_publication_evidence_pack.py --force
```
