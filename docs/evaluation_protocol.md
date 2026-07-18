# Evaluation Protocol v2

## Unit of evaluation

Policies are frozen during evaluation. The official matrix uses independent
policy seeds `42`, `101`, and `202`; one seen topology; five held-out topology
seeds `101`, `202`, `303`, `404`, and `505`; and 100 completed episodes per
policy-topology cell. The 30-minute cap marks a failed/incomplete cell and is not
the sampling unit.

Policy seed is the replicate for training-level claims. Episodes and layouts
from one checkpoint do not create additional independent policy replicates.

## Required artifacts and provenance

Every cell must contain non-empty `episode_log.csv`, `agent_step_log.csv`,
`reward_audit.csv`, `replay_events.csv`, `eval_kpi_summary.json`,
`eval_kpi_summary.csv`, run/evaluation metadata, and a successful evaluation
status. Episode rows must identify the effective scene, rule config, reward
config, layout ID, and topology seed. A failed schema, provenance, hash, or
episode-count audit excludes the cell.

## Outcome and timing metrics

- Sentinel and Runner win rates and exit/escape rate.
- First-capture and full-capture time from replay-event timestamps.
- Runner survival ending at that Runner's capture or episode termination,
  averaged over runner-episodes.
- Episode duration, reported under that name rather than as survival time.

## Coordination metrics

For pincer, corridor-block, exit-denial, enclosure, and trap events, report both:

- episode prevalence: fraction of episodes containing at least one event; and
- intensity: mean event count per episode.

Trap success is Sentinel wins conditional on a trap occurring. Sentinel spread
and Runner separation are mean within-team pairwise planar distances, averaged
over snapshots within each episode and then equally over episodes.

## Path and dynamic-response metrics

Path integration is keyed by `(episode_id, agent_id)`, so teleports at episode
reset are never counted as movement. Reports include captures per Sentinel meter,
Runner/Sentinel meters per episode, and straight-line-displacement versus actual
Runner-path ratio (explicitly labeled a proxy).

For each dynamic wall shift at time `tau`, the route-change metric compares the
Runner displacement vector during the one-second window before the shift with
the vector during the one-second window after it. Windows with less than 0.05 m
displacement are directionally undefined and excluded. Report mean absolute
deflection in degrees, fraction of observations at least 45 degrees, number of
Runner-shift observations, and number of wall-shift events.

Sentinel target reacquisition is measured at team level. A gap begins only
after at least one Runner has been visible and all active Sentinels then lose
visibility; it ends when any active Sentinel sees a Runner again. Initial
acquisition is excluded, and gaps still open at episode termination are counted
as right-censored rather than assigned the episode timeout.

## Statistical reporting

- Wilson 95% intervals for binary rates within a policy-layout cell.
- Per-policy and per-layout tables; episode-weighted and layout-balanced means.
- Mean, sample standard deviation, and Student-t learning-curve intervals across
  policy seeds.
- Hierarchical bootstrap over policies, layouts, then episodes for aggregate
  outcome metrics.
- Per-policy seen-minus-layout-balanced-held-out generalization gaps with
  layout/episode bootstrap intervals.
- A balanced seed-by-layout random-effects decomposition of cell means,
  separating policy-seed, layout, and interaction-plus-cell-error variance.
- Ablation deltas paired by policy seed and topology, with raw cell deltas,
  bootstrap intervals, sign consistency, and `d_z` reported descriptively.
- No Nash-equilibrium, broad zero-shot, or hardware-robotics claim from these
  simulation results.
