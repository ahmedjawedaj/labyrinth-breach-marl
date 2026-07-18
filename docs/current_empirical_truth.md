# Current Empirical Truth

## Status

The standalone evaluation pipeline is operational and provenance-audited. The
current evidence is a validated diagnostic of one legacy checkpoint pair, not a
publication-grade multi-policy-seed result.

The registered five-seed study reached 20/20 audited official training runs on
2026-07-17, but that gate has been reopened for an integrity-preserving repair.
A subsequently launched inference process overwrote the required seed-42 Stage
4 `Player-0.log` because ML-Agents wrote evaluation files into the source
training directory. The otherwise-complete run and its five-seed curve export
were preserved as invalidated artifacts rather than relabeled. A clean seed-42
Stage 4 replacement is training from its audited Stage 3 checkpoint on an
isolated port; the strict current state is therefore 19/20 baseline and 23/65
total registered training runs. The evaluator now uses ephemeral checkpoint
snapshots, and the tested fix was propagated to all five workers. Training-stage
KPIs are operational monitoring only and are not paper results.

The corrected official training pipeline is also operational. Two 5,000-step
gates verified Stage 1 fixed-layout routing and Stage 1-to-Stage 2 checkpoint
transfer. Both gates produced all raw logs and KPI outputs under the earlier
19-check audit; the canonical audit now contains 33 checks, including exact CSV
schema, contiguous episode IDs, invalidation markers, and maze provenance. A
third gate verified the canonical V5 reward and the
new topology provenance columns. An earlier 590-episode partial Stage 1 run was
invalidated because the old manifests changed reward definitions between
stages. A first V5 retry was also invalidated after detecting that ML-Agents
`--force` did not clear Unity's append-only CSVs. The launcher now deletes the
whole target run directory before a forced launch. A later clean retry was
stopped at approximately 740k/490k Sentinel/Runner steps after live monitoring
showed that equal role limits would freeze the three-agent Sentinel policy while
the two-agent Runner policy continued training. It is explicitly invalidated.
A corrected-budget retry with simultaneous latest-policy PPO was stopped at
approximately 790k/520k Sentinel/Runner steps after Sentinel wins moved from
92% in the first 100 episodes to 8% in the last 100. This is adversarial policy
cycling, not stable improvement, and the run is explicitly invalidated. The
corrected protocol uses alternating opponent-snapshot self-play with a
ten-checkpoint window, a 0.5 latest-policy ratio, 20k-step saves, 2k-step
opponent swaps, and 100k-step team changes. Its 1.5M/1.0M behavior-step budgets
were then found to conflict with the ghost controller's equal-step alternation:
Runner would finish after ten turns while Sentinel still required five turns.
That partial run was stopped at approximately 200k/110k and invalidated. The
final corrected protocol uses 1.5M trainer samples for each role per stage, so
both roles receive the same optimizer sample budget and finish self-play
together. Because of 3v2 parameter sharing, this corresponds to 0.5M Sentinel
team decision cycles and 0.75M Runner team decision cycles per stage; the paper
discloses this distinction rather than claiming both units are equal.

## Validated diagnostic

- Source checkpoint: `v5_dynamicmaze`
- Evaluation seeds: 42, 101, 202
- Topologies: one seen topology and one hard-coded unseen topology
- Unseen configurations: seeds 101, 202, 303, 404, 505 changed placement and
  stochastic-event sequences, not topology connectivity
- Legacy split confound: the seen and unseen files also changed agent speeds,
  capture radius, and wall timing, so their difference is not a topology effect
- Runtime: 30 wall-clock seconds per matrix cell
- Matrix: 18/18 cells completed
- Artifact audit: 108/108 required raw/KPI artifacts present
- Provenance audit: every completed episode used the expected Unity scene,
  seed-specific rule config, and `reward_dynamicmaze_memory_v4.yaml`

Episode-weighted outcomes:

| Split | Episodes | Sentinel wins | Runner wins | Escape rate | Sentinel 95% Wilson CI | Mean full capture |
|---|---:|---:|---:|---:|---:|---:|
| Seen | 12 | 75.0% | 25.0% | 0.0% | 46.8%-91.1% | 13.33 s |
| Unseen | 106 | 68.9% | 31.1% | 25.5% | 59.5%-76.9% | 21.04 s |

Held-out Sentinel win rates vary materially by seed configuration: seed 101 = 80.6%, seed
202 = 88.2%, seed 303 = 75.0%, seed 404 = 64.3%, and seed 505 = 33.3%.

## What this means

The legacy checkpoint transfers to the held-out scene, but it remains
Sentinel-favored overall and is sensitive to placement/event seeds. Because all
five configurations reused one hard-coded unseen topology, these data do not
measure topology generalization and cannot support balanced-play,
layout-invariance, or robust zero-shot claims. The legacy rule differences make
the seen/unseen contrast a compound environment shift rather than a controlled
intervention.

The three seeds above are evaluation seeds. They do not replace the five
independent policy pairs required by the official protocol. The 30-second cells
are also too short for final
per-seed estimates, particularly in timeout-heavy seen episodes.

## Invalidated matrix

The earlier `results/publication_eval/` 15-second matrix is retained only for
audit history. It evaluated the default standalone configuration because scene,
bare rule-config, and reward-config routing were incomplete. It must not be used
in the paper. See `results/publication_eval/aggregate/INVALIDATED.md`.

## Remaining publication blockers

1. Complete 100 episodes on one seen and five genuinely distinct held-out
   topologies for each trained policy seed.
2. Complete action-assist, memory, trap-reward, dynamic-wall, and curriculum
   ablations.
3. Report per-policy-seed estimates, confidence intervals, and ablation effect
   sizes from canonical logs.
4. Add hardware or higher-fidelity simulator evidence if targeting a venue that
   expects physical robotics validation.

The replacement official rule files have now passed a 10/10 control audit: all
non-topology dynamics are identical across the seen topology and five held-out
topologies. The memory intervention passes 8/8 training/evaluation alignment
checks. The two evaluation-only ablations pass 6/6 matched-control checks each,
allowing only action-assist coefficients or the dynamic-wall enable flag to
change. Assist-off is canonical; assist-on is the paired intervention.

Canonical KPI summaries now use `evaluation_protocol.md@v2` / schema v3. A code
audit found and fixed episode-reset jumps in path integration and a runner
survival aggregation error before official evaluations began. Route response is
now measured as pre/post wall-shift heading deflection; spread/separation are
episode-balanced. Eleven regression and protocol-integrity tests cover these
calculations, statistical interval behavior, and negative control-audit cases.
The noncentral-t power audit makes explicit that five policy seeds still have
80% power only for large paired effects (|dz| approximately 1.68), so final
interpretation must emphasize raw effects, uncertainty, and seed consistency.
