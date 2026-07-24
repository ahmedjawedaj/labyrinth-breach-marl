# Current Evidence Snapshot

Generated UTC: `2026-07-24T09:09:13.691682+00:00`

Readiness: **BLOCKED**
Gates: **15/16**
Blocking gates: `ablation_results`

## Canonical Evaluation

| Split | Episodes | Sentinel win | Escape |
| --- | ---: | ---: | ---: |
| seen | 501 | 41.5% | 52.9% |
| unseen | 2501 | 42.2% | 53.5% |

## Lightweight Baselines

| Controller | Split | Cells | Episodes | Sentinel win | Escape | Full capture | Pincer |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| heuristic | seen | 1 | 26 | 73.1% | 26.9% | 10.18 s | 26.9% |
| heuristic | unseen | 5 | 126 | 68.3% | 30.1% | 8.74 s | 26.3% |
| random | seen | 1 | 25 | 32.0% | 48.0% | 106.04 s | 16.0% |
| random | unseen | 5 | 125 | 27.2% | 44.8% | 103.03 s | 8.8% |

## Completed Ablations

| Ablation | Split | Metric | Matched cells | Delta | dz | Bootstrap interval |
| --- | --- | --- | ---: | ---: | ---: | --- |
| action_assist_on | unseen | sentinel_win | 25 | -0.0126 | -0.17 | [-0.0688, 0.0444] |
| action_assist_on | unseen | escape | 25 | 0.0182 | 0.25 | [-0.0364, 0.0738] |
| action_assist_on | unseen | sentinel_spread_meters | 25 | -0.1528 | -0.48 | [-0.2897, -0.0108] |
| dynamic_wall_off | unseen | sentinel_win | 25 | 0.0206 | 0.29 | [-0.0274, 0.0722] |
| dynamic_wall_off | unseen | pincer_episode_rate | 25 | 0.0275 | 0.63 | [0.0108, 0.0452] |
| dynamic_wall_off | unseen | exit_denial_episode_rate | 25 | 0.0234 | 0.45 | [0.0020, 0.0458] |
| dynamic_wall_off | unseen | trap_episode_rate | 25 | 0.0316 | 0.76 | [0.0108, 0.0540] |
| dynamic_wall_off | unseen | stall_step_fraction | 25 | -0.0646 | -1.21 | [-0.0877, -0.0377] |

## Remaining

No-retraining work can improve framing, traceability, and diagnostic controls.
The remaining publication blocker is empirical: three paired ablations require retraining.
