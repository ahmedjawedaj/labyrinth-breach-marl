# Internal Reviewer Scorecard

Date: 2026-08-10

## Verdict

The manuscript is suitable for another submission as a benchmark and audited
simulation study. The strongest fit is a multidisciplinary or systems-oriented
venue that accepts simulation evidence and values reproducibility. The paper is
less suitable for venues that require a new algorithm, physical robot trials, or
clear state-of-the-art controller performance.

## Score Estimate

| Category | Earlier course report | Current manuscript |
| --- | ---: | ---: |
| Research framing | 4/10 | 8/10 |
| Related work currency | 3/10 | 8/10 |
| Methodology clarity | 4/10 | 8/10 |
| Reproducibility | 3/10 | 9/10 |
| Evaluation breadth | 3/10 | 7/10 |
| Ablation depth | 1/10 | 5/10 |
| Baseline strength | 1/10 | 5/10 |
| Submission polish | 4/10 | 8/10 |

Overall internal score: 7.5/10 for benchmark-style submission.

## Highest Confidence Claims

- The environment is reproducible and configurable.
- The official evaluation uses five policy seeds and five held-out topology
  seeds.
- The benchmark is balanced because Runner wins and escapes remain common.
- Dynamic walls change tactical-event prevalence more clearly than terminal win
  rate in the completed sample.
- The current PPO policy is competent but not dominant against the geometric
  heuristic.

## Claims to Avoid

- Do not claim state-of-the-art controller performance.
- Do not claim hardware transfer.
- Do not claim Nash equilibrium or game-theoretic convergence.
- Do not claim that memory, tactical rewards, or curriculum caused the observed
  behavior until retraining ablations are completed.
- Do not call the random and heuristic controllers matched-compute learned
  baselines.

## Reviewer Attack Points

| Risk | Current defense | Stronger future defense |
| --- | --- | --- |
| Simulation-only evidence | Scope is declared and limitations are explicit | Add physical or higher-fidelity robot validation |
| Only two completed paired interventions | Paper does not use missing retraining ablations as primary claims | Complete memory-off, tactical-reward-off, and direct-dynamic retraining |
| No learned SOTA baseline | Random and heuristic controls are labeled diagnostic | Add MAPPO or MA-POCA under matched compute |
| Small effect sensitivity | Power audit and confidence intervals are reported | Increase to 10 policy seeds if runtime permits |
| XAI is coarse | Interpretation uses logs, replay events, and interventions | Add grouped SHAP over semantic observation channels |

## Next Work Order

1. Complete the three registered retraining ablations if a reviewer requests
   mechanism-level evidence.
2. Add one learned matched-compute baseline for a stronger resubmission package.
3. Add grouped SHAP only after the observation-channel protocol is fixed.
4. Keep the current manuscript as the declared-scope submission version.
