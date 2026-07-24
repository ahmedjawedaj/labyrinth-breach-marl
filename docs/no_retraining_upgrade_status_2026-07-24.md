# No-Retraining Publication Upgrade Status

Date: 2026-07-24

## Current Position

The no-retraining pass improves the paper, references, traceability, and
diagnostic evidence without starting new training. The current readiness audit
passes 15 of 16 gates. The only remaining blocker is empirical ablation
completion: memory off, tactical reward off, and direct dynamic training require
paired retraining and cannot be inferred from the existing checkpoints.

## Completed Without Retraining

- Rebuilt the IEEE-style manuscript as a 17-page PDF.
- Added environment, behavior, methodology, and PPO architecture diagrams.
- Regenerated the lightweight random and geometric-heuristic baseline aggregate.
- Fixed readiness-audit routing so the current paper PDF and valid 30-cell
  evaluation audit are recognized.
- Generated a current evidence snapshot in JSON, CSV, and Markdown under
  `results/official_summary/current_evidence_snapshot.*`.
- Strengthened the repository-level explanation of what is complete and what is
  blocked.

## Evidence Now Available

| Evidence item | Status | Location |
| --- | --- | --- |
| Journal-style manuscript PDF | Complete | `paper/labyrinth_breach_revised_publication_report.pdf` |
| Official five-seed training curves | Complete | `results/official_summary/training_curves/` |
| Canonical assist-off evaluation | Complete | `results/publication_eval_official/aggregate/` |
| Lightweight baselines | Complete as diagnostics | `results/lightweight_baselines/aggregate/` |
| Action-assist paired ablation | Complete | `results/official_summary/ablations/action_assist_on/` |
| Dynamic-wall paired ablation | Complete | `results/official_summary/ablations/dynamic_wall_off/` |
| Formal evidence pack | Blocked | Requires all five paired ablations |

## Remaining Publication Risk

The paper is much stronger than the earlier course report, but it is still not a
finished journal evidence package. A multidisciplinary venue or preprint review
path is realistic with the current draft. A stronger journal submission needs
the remaining three retraining ablations because they test the main mechanism
claims.

## Recommended Next Decision

Use the current PDF for supervisor review now. Continue retraining only if the
target is a full journal submission with mechanism claims about memory,
tactical rewards, and curriculum benefit.
