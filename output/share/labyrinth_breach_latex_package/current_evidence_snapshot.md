# Current Evidence Snapshot

Generated UTC: `2026-08-10T17:08:23.545828+00:00`

Readiness: **READY_FOR_SUBMISSION_REVIEW**
Required checks: **16/16**
All tracked checks: **16/17**
Required evidence gates: `none`
Registered extension gates: `ablation_results`

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

## Memory-Off Checkpoint Audit

| Run | Seed | Stage | Episodes | Sentinel win | Escape | Full capture | Reacquisition | Control audit |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| LB_3v2_memory_off_seed202_stage4 | 202 | stage4 | 3145 | 58.7% | 31.2% | 27.88 s | 2.59 s | True |

This is a completed single-seed checkpoint audit, not a full five-seed paired memory ablation result.

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

## Registered Extensions

The current submission evidence is limited to the reported canonical evaluation, control policies, and paired deployment interventions.
Memory-off, tactical-reward-off, and direct-dynamic conditions are registered retraining extensions.
