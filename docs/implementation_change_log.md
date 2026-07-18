# Implementation Change Log

This log records publication-relevant behavioral and analysis changes that
predate or are not isolated in a dedicated Git commit. It supplements, but does
not replace, repository history and run-level config snapshots.

## 2026-07-16

### Episode-keyed path and survival aggregation

- **Problem:** path integration could connect the final position of one episode
  to the initial position of the next; Runner survival used an aggregate maximum
  rather than a mean over Runner episodes.
- **Change:** `scripts/summarize_eval_kpis.py` keys previous positions and
  survival clocks by `(episode_id, agent_id)` and averages Runner survival over
  Runner-episode records.
- **Regression evidence:**
  `test_path_survival_and_route_change_do_not_cross_episode_resets` in
  `tests/test_publication_metrics.py`.

### Dynamic-wall route response and spatial coordination

- **Problem:** path length had been labeled as a route-change metric, and team
  spread was not formally episode-balanced.
- **Change:** route response now measures the angle between one-second Runner
  displacement windows before and after logged wall shifts. Sentinel spread and
  Runner separation average pairwise distances within snapshots, then episodes.
- **Regression evidence:** the episode-reset/route-change test above and
  `test_team_spread_is_episode_balanced`.

### Target reacquisition delay

- **Problem:** the registered memory ablation named reacquisition delay, but the
  canonical KPI exporter did not compute it.
- **Change:** `summarize_target_reacquisition` measures elapsed time from loss of
  all Sentinel-team visible targets to renewed team visibility. Initial target
  acquisition is excluded; terminal open gaps are counted as right-censored.
- **Regression evidence:**
  `test_reacquisition_excludes_initial_acquisition_and_reports_censoring`.

### Controlled topology evaluation

- **Problem:** legacy unseen seeds changed placements/events on one hard-coded
  topology, and legacy seen/unseen files also changed movement and wall rules.
- **Change:** generated topology seeds `101`, `202`, `303`, `404`, and `505` use
  matched non-topology controls; topology identity and seed are logged per
  episode. The publication matrix is assist-off and uses five policy seeds.
- **Regression/audit evidence:** `validate_evaluation_controls.py` (10/10) and
  `test_official_evaluation_uses_v5_and_distinct_topology_seeds`.

### Ablation integrity

- **Problem:** deployment interventions could silently include unrelated rule
  changes.
- **Change:** condition-specific control audits whitelist only the registered
  fields for memory off, action assist on, and dynamic walls off. Audit outputs
  have stable condition-specific paths consumed by publication readiness.
- **Regression evidence:**
  `test_ablation_control_audit_rejects_unregistered_field_change`.

### Statistical outputs

- **Problem:** the manuscript specified generalization gaps and requested a
  seed-by-layout analysis, but the canonical exporter did not emit them.
- **Change:** `analyze_publication_statistics.py` exports per-policy
  seen-minus-layout-balanced-held-out gaps with bootstrap intervals and a
  balanced two-way variance decomposition. `analyze_paired_ablation.py` exports
  full-minus-condition absolute-gap effects.
- **Regression evidence:**
  `test_generalization_gap_and_seed_layout_variance_are_exportable` plus smoke
  outputs under `tmp/statistics_smoke/` and `tmp/paired_smoke/`.

### Manuscript evidence quarantine

- **Problem:** legacy v4/assist-on/single-topology artifacts could be mistaken
  for official v5 comparative results.
- **Change:** `paper/labyrinth_breach_journal.tex` labels the complete legacy
  section, every table, and every figure as excluded from official Results.
  Official claims remain blocked until the readiness audit passes.

### Curriculum launcher seed selection

- **Problem:** the default matrix path took precedence over explicit
  `--stage-manifest` and `--seeds` arguments, so a targeted launch could silently
  continue into other registered seeds.
- **Change:** stage-manifest mode now has explicit precedence, matrix mode
  validates the five official seeds, and an optional seed subset is checked and
  honored.
- **Regression evidence:**
  `test_curriculum_launcher_honors_registered_seed_subset`.

### Isolated publication workers

- **Problem:** the complete registered study contains 65 training runs across
  the baseline and retraining conditions, followed by 180 evaluation cells;
  one sequential Unity process would make the evidence campaign unnecessarily
  slow. Direct parallel launches were unsafe because ML-Agents used one port
  and Unity runtime overrides were repository-global.
- **Change:** training and evaluation launchers now support explicit unique base
  ports, registered seed subsets, worker-local matrix status, and evaluation
  shards that defer shared aggregation. Five detached workers use isolated
  worktree roots while writing disjoint seed run IDs to one canonical results
  directory. `run_remaining_publication_gates.sh` waits for all shards before
  curves, aggregates, paired analyses, readiness, and evidence-pack generation.
- **Regression evidence:**
  `test_isolated_training_worker_forwards_unique_base_port` and
  `test_evaluation_shard_honors_registered_seed_subset`; the full portable suite
  passes 16/16 tests.

### Immutable evaluation checkpoint snapshots

- **Problem:** ML-Agents `--resume --inference` creates TensorBoard events and
  a Unity player log under `--results-dir`. The first canonical-evaluation
  launch therefore overwrote the required player log in the official seed-42
  Stage 4 training directory before the process was stopped. That run and its
  curve export were preserved as invalidated artifacts, and a clean Stage 4
  replacement was started from the audited Stage 3 checkpoint.
- **Change:** `evaluate_policy.py` now copies each behavior's fixed
  `checkpoint.pt` into an ephemeral per-cell inference workspace. ML-Agents
  writes only there, while evaluation metadata records hashes from the official
  source checkpoints. The workspace is removed at process exit. The updated
  evaluator was copied to all five isolated campaign workers.
- **Regression evidence:**
  `test_inference_uses_checkpoint_snapshot_without_mutating_source`; a real
  one-episode seed-101 smoke run loaded both staged checkpoints, produced all
  required logs and KPI outputs, removed its workspace, and left a 47-file
  source SHA-256 manifest byte-identical before and after evaluation.

### Artifact-aware campaign completion

- **Problem:** exact-target status alone did not prove that a completed cell
  retained every required raw log, KPI output, checkpoint hash, and immutable
  inference provenance field.
- **Change:** live campaign accounting now requires all core training or
  evaluation artifacts to be non-empty. Training also requires a 33/33 audit;
  evaluation requires at least the registered episode count, two source
  checkpoint hashes, and immutable-source/ephemeral-workspace flags.
- **Regression evidence:**
  `test_campaign_evaluation_completion_requires_artifact_integrity` rejects an
  exact-target status with missing artifacts and accepts the same status only
  after the full artifact contract is present.

### Campaign completion accounting

- **Problem:** a training or evaluation status file exists as soon as a run
  starts, so directory or file-presence counts can misclassify active or failed
  work as completed evidence.
- **Change:** `summarize_publication_campaign.py` enumerates the registered 65
  training runs and 180 evaluation cells from their manifests. Training counts
  require `status=completed`, `success=true`, and exit code zero; evaluation
  counts additionally require the exact 100-episode target. It writes canonical
  JSON and Markdown status artifacts under `results/orchestration/`.
- **Regression evidence:**
  `test_campaign_status_requires_success_and_episode_target` exercises running,
  failed, under-target, and target-complete boundaries.

## Required traceability going forward

1. Behavioral Unity changes require a clean standalone build manifest.
2. Runtime semantic changes require a new experiment family; do not mix builds
   within a policy-seed matrix.
3. Every reported table must identify its raw aggregate index and analysis
   script version.
4. Every bug fix affecting a metric requires a negative or boundary regression
   test before official evaluation is regenerated.
