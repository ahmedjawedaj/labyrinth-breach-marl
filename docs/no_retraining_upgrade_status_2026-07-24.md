# Publication Upgrade Status

Date: 2026-07-24

## Current Position

The publication pass improves the paper, references, traceability, and
diagnostic evidence without starting new training. The current readiness audit
passes 15 of 16 evidence checks. Memory off, tactical reward off, and direct
dynamic training require paired retraining and are registered as extensions
rather than used as primary evidence claims.

## Completed Publication Evidence

- Rebuilt the IEEE-style manuscript as a 16-page PDF.
- Added environment, behavior, methodology, and PPO architecture diagrams.
- Regenerated the lightweight random and geometric-heuristic baseline aggregate.
- Fixed readiness-audit routing so the current paper PDF and valid 30-cell
  evaluation audit are recognized.
- Generated a current evidence snapshot in JSON, CSV, and Markdown under
  `results/official_summary/current_evidence_snapshot.*`.
- Strengthened the repository-level explanation of reported evidence and
  registered extensions.

## Evidence Now Available

| Evidence item | Status | Location |
| --- | --- | --- |
| Journal-style manuscript PDF | Complete | `paper/labyrinth_breach_revised_publication_report.pdf` |
| Official five-seed training curves | Complete | `results/official_summary/training_curves/` |
| Canonical assist-off evaluation | Complete | `results/publication_eval_official/aggregate/` |
| Lightweight baselines | Complete as diagnostics | `results/lightweight_baselines/aggregate/` |
| Action-assist paired ablation | Complete | `results/official_summary/ablations/action_assist_on/` |
| Dynamic-wall paired ablation | Complete | `results/official_summary/ablations/dynamic_wall_off/` |
| Formal evidence pack | Development snapshot available | Full pack can include registered extensions after retraining |

## Publication Risk

The paper is much stronger than the earlier course report and is framed as a
benchmark and audited simulation study. The main review risk is mechanism depth:
reviewers may ask for retraining ablations that isolate memory, tactical
rewards, and curriculum transfer.

## Recommended Next Decision

Use the current PDF for supervisor review or journal submission with benchmark
framing. Continue retraining if reviewers request mechanism-level ablations for
memory, tactical rewards, or curriculum benefit.
