# Publication Upgrade Status

## Pause state on 2026-07-18

The campaign was intentionally paused after the strict status reached 47/65
training runs and 90/180 evaluation cells. See
`docs/publication_pause_conclusion_2026-07-18.md` for the current conclusion,
completed evidence, remaining gates, and resume instructions.

At pause time, official five-seed curriculum training, audited five-seed
learning curves, canonical 30-cell evaluation, action-assist paired analysis,
and dynamic-wall paired analysis were complete. The remaining publication gates
are memory-off evaluation/analysis, tactical-reward-off completion/analysis,
direct-dynamic completion/analysis, and final evidence-pack regeneration.

## Completed in this upgrade pass

- Built and verified the macOS Unity standalone player.
- Added a strict publication protocol for 5 policy seeds and 5 unseen layout seeds.
- Added held-out unseen layout configs for seeds 202, 303, 404, and 505.
- Added action-assist config support and an assist-off evaluation manifest.
- Tightened log collection so publication runs can forbid fallback log copying.
- Corrected coordination metric semantics from ambiguous event-count rates to episode rates plus event counts per episode.
- Updated the manuscript framing from final-result claims to a defensible benchmark/protocol paper.
- Fixed standalone repository-root, scene, rule-config, and reward-config routing.
- Fixed replay capture-time parsing (`time_seconds` instead of the nonexistent `time` field).
- Added episode-level scene/rule/reward provenance fields and a strict matrix audit.
- Completed a validated 18-cell legacy-checkpoint diagnostic with 118 completed episodes.
- Passed all 25 pretraining implementation, topology, budget, hash-resume, clean-retry, and local toolchain audit checks.
- Read and critically synthesized thirteen full primary papers from 2020-2026;
  recorded their seed counts, evaluation budgets, ablations, hardware evidence,
  and implications in `docs/literature_review_2020_2026.md`.
- Expanded the manuscript into a separate IEEE journal draft with a formal POSG,
  reward equations, dynamic-topology model, metric definitions, hierarchical
  statistical plan, recent related work, and a pre-registered ablation table.
- Fixed missing checkpoint transfer between curriculum stages.
- Aligned Stage 1 and Stage 2 on a normalized static-maze network configuration,
  retaining network compatibility with Stages 3 and 4.
- Fixed curriculum scene activation, curriculum-over-rule randomization priority,
  and reset-integrity validation ordering.
- Added automatic per-training-run KPI generation and a strict 33-check training
  audit. Verified fixed Stage 1 routing and Stage 1-to-Stage 2 transfer with two
  independent 5,000-step smoke runs.
- Replaced wall-clock-only official evaluation with 100 completed episodes per
  policy-layout cell; the 30-minute cap now marks an incomplete run as failed.
- Added a canonical statistics tool that exports cell tables, equal-layout
  estimates, per-policy sample variation, Wilson intervals, and hierarchical
  policy/layout/episode bootstrap intervals. On legacy data it correctly refuses
  policy-level inference because no independent policy seed exists.
- Found and corrected a hidden generalization flaw: the old five unseen seeds
  reused one hard-coded topology. The upgraded generator now creates a distinct,
  connected topology per held-out seed, separates topology from per-episode
  placement randomness, and adds layout ID/topology seed to every episode row.
- Added paired ablation statistics: matched policy/topology deltas, paired
  standardized effect size, sign consistency, and hierarchical bootstrap
  intervals with a fixed `full_minus_ablated` convention.
- Detected a second legacy evaluation confound: seen and unseen rule files
  changed movement and wall dynamics together with scene identity. Standardized
  those controls and added a 10-check prelaunch comparison that now passes.
- Added complete action-assist-off and dynamic-wall-off evaluation matrices over
  all six topologies. Each intervention passes 6/6 structural checks and may
  change only its registered rule field.
- Added one machine-readable five-condition ablation suite that distinguishes
  retraining ablations from paired evaluation-time interventions.
- Replaced unsupported headline results and threshold-based training claims in
  the repository README with the audited legacy diagnostic and fixed trainer
  step budgets.
- Added an executable publication-readiness audit. It treats audited official
  training curves as a separate blocking artifact in addition to official
  training, evaluation, and completed paired ablation analyses.
- Added a TensorBoard evidence exporter that preserves per-policy-seed scalar
  rows, computes matched-step Student-t intervals, and writes publication PDF
  figures. Strict mode refuses incomplete or pre-audit training matrices.
- Added asymmetric opponent-snapshot self-play to both behaviors in every
  official trainer configuration. The canonical exporter now includes
  `Self-play/ELO`, and the budget audit checks snapshot cadence, team switching,
  window size, latest-policy ratio, and initial ELO.
- Corrected a KPI aggregation defect that had allowed episode-reset teleports
  into path length and had reported maximum rather than mean runner-episode
  survival. KPI schema v3 keys trajectories by episode and agent.
- Replaced the path-length ``route change'' label with measured one-second
  pre/post wall-shift Runner deflection, including mean angle and the fraction
  of turns at least 45 degrees. Added episode-balanced Sentinel spread and
  Runner separation.
- Expanded paired ablation analysis from four outcome metrics to outcome,
  timing, tactical-event prevalence/intensity, spatial coordination, path,
  stall, and dynamic-response metrics loaded from canonical KPI artifacts.
- Added eleven regression and protocol-integrity tests covering episode-reset
  path isolation, runner-level survival, 90-degree shift response,
  episode-balanced spread, Wilson intervals, bootstrap suppression, matched
  evaluation controls, ablation-field rejection, and official reward/topology
  provenance, generalization-gap intervals, seed-by-layout variance output, and
  target-reacquisition semantics and launcher seed selection; all tests pass.
- Added a reproducible noncentral-t power audit. At alpha 0.05 and 80% power,
  three paired policy seeds detect only |dz| about 3.26 (five: 1.68; ten: 1.00).
- Updated the strict completion tracker to the 20 training runs plus 30
  fixed-count publication-evaluation cells, with snapshot SHA-256 validation
  and distinct running/failed/invalidated status reporting.

## Current evidence status

The replacement matrix in `results/publication_eval_v2/` passes all 18 run audits,
all 108 required artifact checks, and all episode-level provenance checks. It
contains 12 seen and 106 unseen completed episodes.

This is still diagnostic evidence from one legacy checkpoint pair. The three
seeds are evaluation seeds, not independent training seeds. The official
five-policy-seed training/evaluation matrix remains incomplete.

An initial partial Stage 1 run was interrupted and explicitly invalidated after
590 episodes because the old manifests changed reward definitions between
static and dynamic stages. Its first V5 retry was invalidated when a live
provenance check found legacy and V5 rows mixed in append-only Unity logs. A
clean retry then exposed a role-budget inconsistency: equal Sentinel/Runner
limits freeze the three-agent Sentinel policy before the two-agent Runner
policy finishes. That run was stopped and invalidated. A subsequent
corrected-budget run exposed latest-policy cycling: Sentinel wins dropped from
92% in the first 100 episodes to 8% in the last 100 while both current policies
learned simultaneously. It was also stopped and invalidated. Forced training
now removes the complete target directory, all official stages use the
same 1.5M per-policy sample budget, and both roles train through alternating
opponent-snapshot self-play. An intermediate self-play run with 1.5M/1.0M
limits was stopped at approximately 200k/110k after source inspection confirmed
that unequal limits would create a 500k frozen-Runner tail. Partial progress is
not reported as a result; a run enters the evidence pack only after model
export, KPI generation, and a 33/33 audit.

The earlier `results/publication_eval/` matrix is explicitly invalidated because
it was generated before standalone scene/config routing was corrected.

The registered baseline matrix reached 20/20 audited runs and produced an
audited five-seed learning-curve export on 2026-07-17. That gate was then
reopened after an inference launch overwrote the required seed-42 Stage 4
player log by using the official training directory as its ML-Agents results
directory. The affected run and curve export are preserved as invalidated
artifacts, and a clean seed-42 Stage 4 replacement is training from its audited
Stage 3 checkpoint on port 5074. The current strict state is 19/20 baseline and
23/65 total training runs. Evaluation now stages checkpoints in ephemeral
workspaces, and the tested fix is installed in all five workers. Publication
readiness is temporarily 12/16 until the replacement and curve regeneration
restore the two gates; canonical evaluation and all paired ablations remain
pending.

## Current blocker

The immediate work is the clean seed-42 Stage 4 replacement plus aligned
ablation training, followed by fixed-count canonical and paired evaluations.
Build, routing, transfer, raw-log, KPI, and run-audit gates remain operational.

## Low-effort baseline pass on 2026-07-24

A non-training baseline pass was completed using the refreshed macOS Unity
standalone. The runtime now supports `learned`, `random`, and `heuristic`
evaluation policies through `LABYRINTH_BASELINE_POLICY` and the matching
runtime override file written by `scripts/evaluate_policy.py`.

The diagnostic matrix ran 12/12 cells: random and geometric-heuristic action
overrides across one seen split and five held-out splits, one evaluation seed,
and 25 target episodes per split. The retained evidence level is KPI/metadata
summaries plus aggregate CSV/JSON outputs; raw baseline CSV logs should be
rerun and retained before using these rows in a formal evidence pack. The
aggregate outputs are:

- `results/lightweight_baselines/aggregate/baseline_eval_summary.csv`
- `results/lightweight_baselines/aggregate/baseline_eval_summary.json`

Held-out Sentinel win rate was 27.2% +/- 4.4 for random actions and 68.3% +/-
9.7 for the geometric heuristic. The canonical learned PPO row remains 42.2% +/-
8.2 over five trained policy seeds and 100 target episodes per cell. These
baselines should be reported as diagnostic controls only; they do not replace a
matched-compute learned MARL comparison such as MAPPO or MA-POCA.

## Active command

```bash
screen -r labyrinth-publication-gates
```

The detached supervisor runs `scripts/run_remaining_publication_gates.sh`. It
will not generate shared aggregates or paired analyses unless every seed shard
completes successfully.
