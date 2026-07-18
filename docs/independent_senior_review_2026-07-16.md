# Independent Senior Review — *Labyrinth Breach*

**Reviewer stance:** strict senior reviewer for a robotics/MARL journal or top-tier conference.
**Date:** 2026-07-16. **Basis:** both manuscripts (`labyrinth_breach_final.tex`, `labyrinth_breach_journal.tex`), the source repository, configs, raw evaluation logs, the 2020–2026 literature review, and `docs/current_empirical_truth.md`. Claims were verified against code and logs; nothing below is taken on trust from the manuscript.

**Evidence legend:** **[V]** = verified against code/logs by this review · **[I]** = reasonable inference · **[U]** = unavailable / cannot be verified because the experiment is incomplete.

---

## 0. One-paragraph verdict

This is an unusually honest, well-engineered, and carefully scoped piece of *infrastructure* with a genuinely auditable evaluation pipeline — but it is **not yet a scientific paper**, because the experiments that would answer its own research questions have not been run. Every quantitative result currently in the manuscript comes from a **single legacy checkpoint pair**, evaluated on **one hard-coded "unseen" topology**, under a **compound rule-shift confound**, with a **15%-strength scripted pursuit-assist switched on**, and — as I confirmed from the raw logs — under a **different reward file (`v4`) than the reward table (`v5`) printed in the same paper**. The pipeline, statistics, and provenance auditing are real and correct (the headline diagnostic table regenerates from raw logs *exactly*, Wilson intervals and the noncentral-t power analysis check out). The framing is scrupulously scoped and rarely overclaims. But a reviewer scores completed science, not intentions: RQ1 (curriculum) and RQ3 (ablations) have **zero** completed evidence, and RQ2 has only "the checkpoint executes." As submitted to a journal today: **reject** (as a completed study) / at best **major revision**. After the registered matrix completes: a credible **workshop or benchmark-track / preprint** contribution.

---

## 1. Original (6-page) vs. Upgraded (journal) manuscript

### Materially improved (real gains, not page-filler)

- **Honest re-scoping of the central results.** The original (`final.tex` §V-H, l.303) wrote "held-out **geometry** matters… evidence against a layout-invariant claim." The upgrade (`journal.tex` §VI-A/B, l.477, 497, 522–524) corrects this to: all five configs **reused one hard-coded topology**, and seen/unseen also changed speeds/capture-radius/wall-timing, so the contrast is a "**compound configuration shift, not a controlled topology effect**." This is the single most important improvement — the original made a topology-generalization insinuation the data cannot support; the upgrade retracts it. **[V]**
- **Formalization added.** The upgrade introduces a proper POSG tuple with observation/opponent-mixture notation, a self-play operator `μ = 0.5·δ(latest) + 0.5·Unif(H)`, explicit terminal-outcome function, Wilson estimator, dynamic-topology graph `E_{t+1}=E_t △ ΔE_t`, seeded-generator description, metric definitions (spread, path length, route-response deflection), and a full **Statistical Analysis Plan** with hierarchical bootstrap, paired effects, `d_z`, and a **noncentral-t power analysis** (§IV, §V-D–G). The original had a one-line POSG tuple and no statistics plan. Substantial depth gain. **[V]**
- **Related work upgraded from name-dropping to a critical comparison.** The upgrade expands to five themes, adds 2025–2026 comparators (ViPER, EPG, R2PS, MA2MB, Akinmolayan hybrid, MACA), and a feature-comparison table (Table I) that honestly states what the system *does not* do (no hardware, weaker partial-observability than belief-based baselines). The `literature_review_2020_2026.md` behind it is genuinely critical (records seed counts, eval budgets, ablations per paper) and explicitly positions the project **below** the strongest comparators. This is above the bar for the original. **[V]**
- **Confounds promoted to first-class citizens.** Action-assist (ρ_S=0.15), the non-potential shaping caveat, the trainer-step vs decision-cycle asymmetry, and the self-play instability history are now disclosed in the body, not hidden. **[V]**
- **Curriculum description corrected.** Original: 3-phase (open→static→dynamic). Upgrade: the *implemented* 4-stage curriculum (fixed→random→dynamic-low→dynamic-high) read from the canonical YAML, with disclosed budget accounting. **[V]**

### Still shallow / unsupported / unchanged

- **No new empirical contribution.** The upgrade extends *rigor and honesty*, not *evidence*. Both papers rest on the same legacy diagnostic + legacy figures. The research contribution (a completed comparative study) did **not** advance. **[V]**
- **Legacy figures carried over unchanged.** Figs 1–6 (reward curves, breakdown, win-rate, penalty reduction, shaping, phase summary) and Table (phase results: 3,228 / 2,492 / 30 episodes) are legacy artifacts from a **different (3-phase) curriculum and a different reward config** than the paper's official 4-stage/v5 protocol. They are presented as the paper's figures. **[V/I]**
- **Reward table still describes v5** while the only results ran v4 (see M1). Unchanged and now internally contradictory. **[V]**
- **Discussion is still thin** — three bold-headed hypotheses, each immediately deferred to future work. Reads like a registered-report intro, not a Discussion. **[I]**

**Net:** the upgrade is a real improvement in scholarship and self-awareness, and genuinely deepens the *methodological* contribution. It does **not** extend the *empirical* research contribution.

---

## 2. Publication-readiness evaluation

**Novelty / contribution.** The niche — asymmetric 3v2, continuous-planar, within-episode topology change, exit-directed evasion, event-level reward provenance, in one configurable Unity benchmark — is a defensible but **incremental** combination. The authors correctly disclaim algorithmic novelty (`journal.tex` §II-B, l.71; lit review l.66). As an *algorithm* paper: not novel. As a *benchmark/infrastructure* paper: modestly novel, contingent on a completed study. **[I]**

**Technical correctness (verified against code):**
- POSG / PPO-clip / GAE / self-play operator / Wilson / power formulations are **correct and match the implementation**. **[V]**
- Observation dimensions (Sentinel 117 = 10+7+84+6+10; Runner 129 = 10+7+96+6+10; 14/16 rays × 6 floats) **add up exactly in code** (`BaseAgent.cs:264-279`, `ObservationAssembler.cs:23-26`, `RaySensorBuilder.cs:23,42`). **[V]**
- Self-play/trainer config (window 10, latest-ratio 0.5, save 20k, swap 2k, team-change 100k, 1.5M/role, lr/batch/buffer/β/λ/γ/epochs/horizon) **all match** `configs/trainer_configs/ppo_dynamicmaze_3v2.yaml` and `ppo_staticmaze_3v2.yaml`. **[V]**
- Reward math (gated distance shaping, terminal ± 1.0) and action-assist blending (`ã=(1-α)a+αh`, c_S=0.35, c_R=0.30, ρ_S=0.15) **match code** (`BaseAgent.cs:205`, `PursuitEvasionEnvController.cs:1397-1398,1446`). **[V]**
- Topology metric/statistics: hierarchical bootstrap is **genuinely 3-level nested** and **correctly returns NaN / suppresses policy-level intervals** for a single checkpoint (`analyze_publication_statistics.py:113-139`; output JSON `inference_warning`). Power analysis is a **real noncentral-t inversion** (`analyze_experiment_power.py`), independently reproduced (Monte-Carlo power at d_z=3.264, n=3 → 0.800). **[V]**

**Adequacy of experiments — the fatal gap.** Seeds: 1 policy pair (target 3, ideally 5–10). Held-out topologies: 1 hard-coded (target ≥5 distinct). Episodes/cell: 12–31 from a 30-s wall-clock cap (target 100 fixed-count). Baselines: none beyond in-house PPO. Ablations: 0 of 5 completed. **The study that the paper is *about* has not been run.** **[V/U]**

**Claim scoping.** Generally excellent — the manuscript repeatedly separates "benchmark," "validated diagnostic," and "completed study," and reports a failure case (seed 505 reverses the advantage). This restraint is the paper's strongest feature and should be preserved. **[V]**

**Reproducibility / artifact quality.** Strong for what exists: run-scoped raw logs + SHA-256 + config snapshots + git state; control-audit scripts are **real, not stubs**, and enforce single-field diffs; invalidated runs excluded via an **explicit index CSV**, not tree-globbing; the headline table **regenerates exactly** from raw logs. Weaknesses: only 3 policy seeds, only 3 unit tests, the integrity scripts themselves are **untested**, and a claimed path/survival bug-fix is **not traceable** in the 13-commit history. **[V]**

**Related work (2020–2026).** Relevant, recent, and critically read; primary records re-checked July 2026. Above bar. **[V]**

**Venue suitability.** Not journal or main-track conference now. Realistic target **after** the registered matrix: a benchmark/datasets track (e.g., NeurIPS D&B if scaled up), an AAMAS/CoRL/robotics **workshop**, or a **preprint**. A hardware-robotics venue is out of reach (simulation-only). **[I]**

---

## 3. Code & experiment-design audit (verified)

- **Observation pipeline** — correct; "360-degree" is a **planar horizontal fan** at fixed height, not spherical. Clarify wording. **[V]**
- **Reward system** — v5 weights match `reward_v5_active_agents.yaml`; loaded from YAML at runtime (not hardcoded). **But the reported eval ran `reward_dynamicmaze_memory_v4.yaml`** — confirmed directly in the raw `episode_log.csv` rows (`results/publication_eval_v2/.../maze_unseen_eval_seed404.yaml → reward_dynamicmaze_memory_v4`). v4 differs materially (capture 0.32 vs 0.25, cluster −0.02 vs −0.015, survival 0.0007 vs 0.0001, **no** idle/exit-approach terms). See **M1**. **[V]**
- **Action-assist confound** — ρ_S=0.15 is the canonical default *and is ON* in the reported eval configs (`maze_unseen_eval_config.yaml:26`, etc.); assist-off configs exist but those results are not yet produced. The reported "learned" behavior is blended with up to 15% scripted geometric pursuit. See **B2**. **[V]**
- **Topology generation** — code is correct: 13×13 grid, 6×6=36 cells, seeded DFS spanning tree, +4 loops, ≤5 dynamic edges, **construction-level connectivity guarantee** (tree passages never converted to dynamic) *plus* a BFS solvability check. Capable of distinct per-seed topologies — **but the reported results did not use it** (one hard-coded unseen layout). See **B1/B2**. **[V]**
- **Dynamic walls** — genuinely change traversability mid-episode; safe-buffer-around-agents is real; `dynamic_walls.enabled` isolates cleanly. **The exit-non-blocking safeguard is inert**: the guard checks `wall.CompareTag("ExitGuard")` (`DynamicWallController.cs:136`) but dynamic pillars are tagged `"Wall"` and **no code ever assigns `ExitGuard`** (verified: the tag string appears only in the check, never in an assignment). Exits stay reachable only via the spanning-tree guarantee. See **M2**. **[V]**
- **Budget fairness** — 1.5M trainer samples/role ⇒ **0.5M Sentinel vs 0.75M Runner** team-decision-cycles (3v2 parameter sharing). Disclosed. But the **open-arena stage balances roles** (750k/500k → 250k cycles each) while maze stages do **not** — an internal inconsistency. Direct-dynamic baseline uses 6M/role = matched aggregate. See **M3**. **[V]**
- **Train/eval leakage** — none illegitimate: "seen" = training seed 42 (in-distribution by design, correctly labeled); unseen seeds 101/202/303/404/505 do not appear in any training config. **[V]**
- **Provenance / invalidation** — invalidated runs carry explicit `INVALIDATED.md`; analysis reads an explicit index, cannot silently aggregate them. **[V]**
- **Missing tests** — no tests for: Wilson CI, bootstrap suppression, the **control-audit scripts** (the backbone of the integrity argument), self-play stability, reward attribution, topology connectivity. Only 3 unit tests total. See **M6**. **[V]**

---

## 4. Mathematics & statistics audit (verified)

- **Notation / estimators** — consistent and correctly defined (episode-weighted vs layout-balanced estimators, prevalence `P̂_m` vs intensity `C̄_m`, conditional trap→win, generalization gap `G_s`). **[V]**
- **Wilson intervals** — formula correct; 9/12 → [46.8, 91.1]%, 73/106 → [59.5, 76.9]% reproduced to the printed decimal. **[V]**
- **Hierarchical bootstrap** — genuinely nested (seed→layout→episode); **correctly suppressed to NaN** for one checkpoint. Exemplary handling. **[V]**
- **Power / pseudoreplication** — the paper *correctly* states the unit of replication is the **policy seed**, that episodes are not independent policy replicates, and that n=3 detects only `|d_z|≈3.26` (reproduced). This pre-empts the classic MARL pseudoreplication critique. **[V]**
- **Residual statistical weakness** — n=3 is honestly disclosed but is still **below the field standard** (Gorsane et al. recommend 10). At n=3, essentially no ablation short of a massive effect will be resolvable; the paper will be forced to argue from raw effects + sign-consistency, which is weak for a journal. Recommend **≥5** seeds, and where an ablation is central, more. **[V/I]**
- **Recommended additional analysis:** (a) report per-topology **and** aggregate with the layout-balanced estimator as primary (episode-weighting over-weights fast-terminating layouts — the paper notes this but should make balanced the headline); (b) add bootstrap CIs on the generalization gap `G_s` per seed; (c) pre-register the ablation directions/effect signs (the design table is a good start) to avoid post-hoc sign-picking; (d) report a seed×layout variance decomposition once ≥5 seeds exist.

---

## 5. Findings ordered by severity

### BLOCKER — prevents credible submission

**B1. No completed empirical study; the paper's own RQs are unanswered.**
*Where:* `journal.tex` §I (RQ statement, l.51–53), §VI (l.452, 520–524); `docs/current_empirical_truth.md:6-7, 87-96`.
*Evidence [V/U]:* 1 policy pair (not 3), 1 hard-coded unseen topology (not ≥5 distinct), 12–31 episodes/cell (not 100 fixed-count), 0/5 ablations. RQ1 (curriculum) and RQ3 (ablations) have no data; RQ2 has only "executable transfer."
*Why it matters:* a journal/conference paper is judged on completed experiments. As-is, this is a benchmark + registered plan, not a study.
*Correction:* run the official 3-seed (≥5 preferred) × {1 seen + 5 generated distinct topologies} × 100-episode matrix with matched controls, plus all five ablations, then rewrite Results around them.

**B2. The one results table cannot support any "learned coordination / generalization" claim.**
*Where:* `journal.tex` Tables IV–VI (§VI-A), §V-C.
*Evidence [V]:* action-assist ρ_S=0.15 is **ON** (`maze_unseen_eval_config.yaml:26`); all cells share **one** checkpoint and **one** hard-coded topology; seen/unseen also differ in speed/capture-radius/wall-timing (`current_empirical_truth.md:46-47`). So the numbers reflect a hybrid (15% scripted) controller under a compound environment shift — not learned policy behavior, and not topology generalization.
*Why it matters:* the assist-on, single-topology, single-checkpoint diagnostic is being used as the paper's empirical spine.
*Correction:* make **assist-off** the canonical evaluation (or report the assist-on/off pair side by side), and derive all coordination/generalization statements only from the multi-seed, multi-topology, matched-control matrix.

### MAJOR — likely reviewer-rejection issues

**M1. Reward-config provenance contradiction (table ≠ run).** The manuscript's Reward Design and Table (§IV-E) document `v5_active_agents`, but the reported diagnostic ran `reward_dynamicmaze_memory_v4.yaml` — verified in the raw log rows. v4 lacks the idle- and exit-approach terms the text says addressed the "free-rider" and "passive-evasion" failure modes. *Fix:* re-run everything under one documented config (v5), or explicitly present v4 as the config-of-record and reconcile the narrative; the reward table must match the run of record.

**M2. Claimed exit-non-blocking safety property is inert.** `DynamicWallController.cs:136` gates on `ExitGuard`, but that tag is never assigned; dynamic pillars are tagged `"Wall"`. The formal claim (`journal.tex` §III, "prohibition on blocking exits") does not execute; connectivity is preserved only by the spanning-tree construction. *Fix:* either assign/enforce the `ExitGuard` tag around exits (and test it), or rewrite the claim to attribute exit-reachability solely to the spanning-tree invariant.

**M3. Role budget asymmetry, disclosed but internally inconsistent.** Maze stages use 1.5M/1.5M (0.5M vs 0.75M decision-cycles) while the open-arena stage balances to equal cycles. *Fix:* pick one convention (equal decision-cycles is the principled one), apply it across all stages, or justify the asymmetry explicitly; note it weakens any head-to-head Sentinel-vs-Runner reading.

**M4. Underpowered design (n=3).** Honestly disclosed but below field norm (Gorsane: 10). *Fix:* target ≥5 seeds; frame conclusions around raw effects, CIs, and sign-consistency, never significance.

**M5. Legacy figures/table under a different curriculum + reward.** Figs 1–6 and the phase-results table come from the legacy 3-phase / v4-era runs, not the official 4-stage/v5 protocol, and are not regenerable under the official pipeline. *Fix:* quarantine them explicitly as "legacy motivation," or regenerate under the official protocol before using them as the paper's figures.

**M6. Integrity scripts are untested; a claimed bug-fix is untraceable.** The control-audit scripts underpin the whole leakage/ablation-integrity argument yet have zero unit tests; the "episode-reset / runner-survival" fix (`current_empirical_truth.md:106-107`) is visible only as end-state code + one regression test, with no corresponding commit in the 13-commit history. *Fix:* add unit tests (including adversarial/negative cases) for `validate_*` and `audit_*`; make bug-fixes traceable with commits or a documented changelog.

### MINOR — should be corrected, not decisive

- **m1.** "360-degree raycast" is a planar fan, not spherical — clarify (§III/IV). **[V]**
- **m2.** Single hyperparameter table implies uniform batch/buffer/horizon; open-arena stage differs (batch 1024, horizon 64). Note per-stage. **[V]**
- **m3.** Timeout 120 s (original) vs 180 s (upgrade) is stage-dependent; state which regime each figure/number uses. **[V]**
- **m4.** Runner win rate (31.1%) includes 6 timeout wins that are **not** escapes (25.5%); keep the two strictly distinct in prose. **[V]**
- **m5.** Missing reward-YAML keys silently fall back to different `RewardConfig.Default()` values — add a hard-fail on unknown/missing keys. **[V]**
- **m6.** Repo hygiene: a 23-page root `labyrinth_breach.pdf` coexists with the 6-page `final.pdf` and the journal `.tex`; make the canonical artifact unambiguous. **[V]**

---

## 6. Scores, verdict, and next actions

### Scores (1–10)

| Dimension | Score | Rationale |
|---|---:|---|
| Novelty | **4** | Incremental niche combination; no algorithmic novelty (self-acknowledged). |
| Technical depth | **6** | Strong formalization, correct implementation, exemplary statistics *design*; depth of *completed* science is thin. |
| Evidence | **2** | One confounded, assist-on, single-topology, single-checkpoint, v4-reward diagnostic; 0/5 ablations. |
| Reproducibility | **7** | Real provenance + control audits; headline table regenerates exactly; docked for few tests, untested integrity scripts, thin git history. |
| Writing | **7** | Clear, well-scoped, honest, strong related work; thin Discussion. |
| Current publication readiness | **2** | The study the paper is about has not been run. |

### Realistic venue recommendation
- **Today:** preprint only; not submittable to a journal or main conference track.
- **After the registered matrix + ablations:** a benchmark/datasets track (NeurIPS D&B–style *if* scaled to ≥5 seeds and ≥10 topologies) or an AAMAS/CoRL/robotics **workshop**; a solid **arXiv preprint** is achievable sooner.
- **Not attainable:** any hardware-robotics claim (simulation-only).

### Minimum acceptance checklist (credible workshop / benchmark paper)
1. ≥3 independent policy seeds fully trained under **one fixed reward (v5) + the 4-stage curriculum**; per-seed learning curves exported from audited event files.
2. Fixed-count evaluation (100 episodes) on 1 seen + **5 generated distinct topologies** via the procedural generator, matched non-topology controls, **assist-off canonical**.
3. All five ablations (memory, tactical reward, dynamic walls, curriculum vs direct, action-assist) with paired effects + bootstrap CIs + per-seed values + effect-sign consistency.
4. Every reported table regenerable from raw logs (extend the verified pipeline to the ablation tables).
5. Legacy v4 diagnostic and legacy 3-phase figures removed or explicitly quarantined from the Results narrative.
6. Reward table = run-of-record config; provenance mismatch (M1) resolved.

### Stronger journal-grade checklist
1. **≥5 policy seeds** (10 per Gorsane where feasible); seed×layout variance decomposition.
2. **≥10 held-out topologies**, ideally a held-out generator distribution, ≥30 starts/map (ViPER-scale).
3. **≥1 competitive baseline** (MAPPO or MA-POCA) at matched compute **and** a recurrent/belief-state memory baseline vs last-known-position.
4. **Collision / wall-transition safety metrics** quantified (closes the clipping limitation and the inert-safeguard issue).
5. Balanced role budgets (equal decision-cycles) applied consistently, or a principled justification.
6. Unit tests for all integrity scripts + CI; DOI-archived artifacts; pinned seeds/configs; traceable bug-fix history.
7. Defensible simulation-only framing as a benchmark, or hardware/high-fidelity-sim transfer evidence.

### Direct verdict
**As a journal submission today: reject** (it presents an incomplete study). If the editor is generous and the paper is reframed as a benchmark + registered protocol: **major revision**. **Workshop/preprint-ready** only after the official 3-seed matrix and ablations land. **Journal-submission-ready: no.**

### Five highest-value next actions (priority order)
1. **Run the official matrix** — ≥3 (target ≥5) policy seeds × {1 seen + 5 generated distinct topologies} × 100 episodes, matched controls, **assist-off canonical**. This *is* the paper.
2. **Run the five ablations** paired by seed/layout; report paired effects, bootstrap CIs, and sign-consistency — not p-values.
3. **Resolve reward provenance (M1)** — one documented config end-to-end; make the reward table match the run of record; retire the v4 legacy diagnostic.
4. **Harden integrity (M2, M6)** — fix or re-describe the inert exit safeguard; add unit tests (with negative cases) for the control-audit scripts; make bug-fixes traceable.
5. **Reframe + baseline** — present as a benchmark/registered contribution; add ≥1 stronger MARL baseline or explicitly scope out algorithmic claims; quarantine legacy figures.

---

*Separation of evidence: Sections 3–4 and all [V] items were verified against code/logs (observation math, trainer/self-play config, reward-weight files, action-assist constants, topology generator, dynamic-wall behavior, Wilson/bootstrap/power, exact regeneration of the diagnostic table, reward-file provenance in raw logs, the never-assigned ExitGuard tag). [I] items are inferences from those facts. [U] items — the curriculum benefit, ablation effects, and topology generalization — are unavailable because the experiments are incomplete, and are treated as open, not as results.*
