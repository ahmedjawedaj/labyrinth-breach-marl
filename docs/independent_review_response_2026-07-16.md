# Response to Independent Senior Review

**Review received:** 2026-07-16  
**Response status:** implementation in progress; not submission-ready  
**Canonical manuscript:** `output/pdf/labyrinth_breach_journal.pdf`

## Decision

The review's central verdict is accepted. The repository contains a credible
benchmark and evidence pipeline, but the registered comparative study is not
complete. No curriculum, topology-generalization, coordination, or ablation
claim will be promoted to a finding until its registered evidence is complete.

## Finding-by-finding response

| ID | Status | Response and evidence |
|---|---|---|
| B1 | **In progress** | The official matrix contains five independently trained policy seeds (`42`, `101`, `202`, `606`, `707`), four curriculum stages, one seen plus five generated held-out topologies, and 100 completed episodes per policy-topology cell. The matrix reached 20/20 audited runs, but seed-42 Stage 4 was then invalidated after an inference process overwrote its required player log. A clean replacement is active from the audited Stage 3 checkpoint, so the strict current count is 19/20. The 30 canonical evaluation cells and all five registered ablations remain required, and the RQs remain unanswered. |
| B2 | **Protocol corrected** | Assist-off is now the canonical evaluation. Assist-on is a paired deployment-time intervention. Seen and held-out rule files pass a 10/10 matched-control audit. Every legacy assist-on/v4/single-topology result is in `Legacy Evidence Audit (Excluded from Official Results)` and is barred from RQ1-RQ3 evidence. |
| M1 | **Resolved for protocol; reruns pending** | All official training and evaluation manifests use `reward_v5_active_agents.yaml`. The manuscript now states that the fixed-checkpoint diagnostic actually used v4 and that the v5 reward table does not describe it. Legacy results are excluded, not reconciled into the official study. |
| M2 | **Claim corrected** | The manuscript no longer attributes exit reachability to the inert `ExitGuard` check. It attributes reachability to the seeded spanning-tree invariant and explicitly discloses that the tag check is inert. Source behavior is not being changed mid-matrix because doing so would make the standalone binary inconsistent across policy seeds. A tested guard implementation is deferred to a clean future build. |
| M3 | **Convention justified** | Official stages use equal 1.5M transition samples per role because ML-Agents ghost self-play alternates learning teams in equal wrapped-trainer-step blocks. The paper reports the corresponding 0.5M Sentinel and 0.75M Runner team decision cycles and avoids cross-role sample-efficiency claims. The excluded open-arena stage is identified as legacy and is not part of the official matrix. |
| M4 | **Resolved in design** | Policy replication increased from three to five seeds. The power analysis reports that `n=5` still detects only large paired effects (`|d_z|` about 1.68 at 80% power); conclusions will emphasize raw effects, intervals, and effect-sign consistency. |
| M5 | **Partially resolved** | Legacy three-phase/v4 figures and tables are retained only in an explicitly excluded evidence-audit section. A five-seed TensorBoard export was generated from 28,320 raw scalar rows and 5,790 summary rows, then preserved as invalidated when the seed-42 Stage 4 integrity gate was reopened. It will be regenerated after the clean replacement; ablation figures and the final Results replacement remain pending. |
| M6 | **Partially resolved** | The publication test suite increased from 3 to 16 tests. Added checks cover statistical intervals, KPI semantics, launcher seed selection, matched controls, artifact-aware campaign completion, official v5/topology provenance, and immutable evaluation checkpoint snapshots. All 16 pass. A real isolation smoke also left all 47 source files byte-identical. `.github/workflows/publication-integrity.yml` runs the portable gates, and `docs/implementation_change_log.md` traces each fix. Further Unity-level topology, reward-attribution, and dynamic-wall safety tests remain required for a journal artifact. |
| m1-m4 | **Resolved in manuscript** | Wording now says planar horizontal ray fan; official and legacy trainer hyperparameters are distinguished; official 180-second and legacy 120-second timeouts are separated; Runner timeout wins remain distinct from exits. |
| m5 | **Open, controlled** | Reward YAML fallback remains in the Unity loader. Current official manifests are complete and preflight-audited, but runtime hard-fail semantics require a rebuilt standalone. This will be implemented only before a clean new experiment family, not during the active matrix. |
| m6 | **Resolved** | The ambiguous root PDF was identified as a 23-slide presentation and renamed `labyrinth_breach_presentation.pdf`. The journal PDF has one canonical path: `output/pdf/labyrinth_breach_journal.pdf`. |

## Verified changes

- `python -m unittest discover -s tests -v`: **16/16 passed**.
- Evaluation matched-control audit: **10/10 passed**.
- Memory-off control audit: **8/8 passed**.
- Action-assist-on control audit: **6/6 passed**.
- Dynamic-wall-off control audit: **6/6 passed**.
- Ablation registration: **5/5 conditions** with **9 directional hypotheses**
  under one `canonical_full_minus_condition` convention.
- Statistics smoke tests export per-policy generalization-gap intervals,
  seed-by-layout variance components, and paired absolute-gap effects.
- KPI smoke test regenerates team-level target-reacquisition delay with explicit
  right-censor counts from raw step logs.
- Training-budget audit: **11/11 passed**.
- Pretraining implementation audit: **25/25 passed**.
- Manuscript: **12 IEEE pages**, 28 cited references, no missing citations,
  undefined references, or overfull boxes after the latest build.
- Publication readiness: **12/16 gates pass** while the seed-42 Stage 4
  replacement and curve regeneration restore the two reopened gates. Official
  evaluation and ablation results are also blocked.

These checks establish protocol and artifact integrity. They do not substitute
for missing empirical results.

## Execution gates

### Gate 1: Complete the minimum credible study

1. Finish all 20 audited curriculum training runs. **Replacement in progress.**
2. Export five-seed learning curves from TensorBoard event files. **Regenerate
   after replacement.**
3. Run the 30-cell assist-off evaluation matrix to 100 completed episodes/cell.
4. Run memory-off, tactical-reward-off, direct-dynamic, assist-on, and
   dynamic-wall-off conditions with the registered paired design.
5. Regenerate every official table and figure from canonical CSV/JSON only.

**Acceptance condition:** the readiness audit reports
`READY_FOR_SUBMISSION_REVIEW`; no result comes from an invalidated or legacy run.

### Gate 2: Raise the work from workshop-grade to journal-grade

1. Expand held-out topology coverage from five to at least ten after the
   five-topology registered matrix is complete; report seed-by-layout variance.
2. Add a matched-compute centralized-critic baseline (MAPPO or MA-POCA). The
   existing draft MA-POCA YAML is not sufficient: Unity team-group registration,
   equal budgets, self-play controls, and a clean baseline matrix are required.
3. Add a recurrent-memory baseline against the explicit last-known-position
   subsystem.
4. Quantify wall-transition collision, clipping, minimum exit-path clearance,
   and post-shift route recovery.
5. Add Unity edit/play-mode tests for topology connectivity, exit safety,
   reward attribution, missing reward keys, and episode reset behavior.
6. Rebuild under strict reward-schema validation and run a clean, versioned
   experiment family if any runtime semantics change.

### Gate 3: Rewrite from completed evidence

1. Replace the excluded legacy evidence section with official curves, balanced
   seen/held-out tables, ablation effects, failure cases, and variance analysis.
2. Answer each RQ with a bounded claim tied to a specific figure or table.
3. Expand Discussion around effect mechanisms, disagreement across seeds and
   layouts, comparison with current baselines, and negative results.
4. Preserve simulation-only limitations and avoid equilibrium, hardware, and
   zero-shot-generalization claims not supported by the experiment.

## Submission decision rule

- **Preprint/workshop candidate:** Gate 1 complete with coherent, reproducible
  effects and no unresolved provenance failures.
- **Journal candidate:** Gates 1-3 complete, including a competitive baseline,
  stronger topology diversity, safety evidence, and a rewritten Results section.
- **Do not submit:** any official run is missing, any table depends on legacy
  artifacts, or the evidence contradicts a central claim without the manuscript
  being reframed around that negative result.
