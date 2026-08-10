# Submission Readiness Checklist

Date: 2026-08-10

## Current Submission Position

The manuscript is framed as a reproducible Unity ML-Agents benchmark and audited
simulation study for asymmetric multi-agent pursuit-evasion in dynamic mazes.
It does not claim a new MARL algorithm, hardware validation, or state-of-the-art
controller performance.

## Supervisor Feedback Coverage

| Feedback item | Current handling |
| --- | --- |
| Add recent 2020 to 2026 work | Related work includes recent pursuit-evasion, MARL, XAI, partial-observability, and robotics papers with 13 full primary-paper reviews in the readiness audit |
| Prefer stronger journal references | Bibliography includes journal papers from IEEE RA-L, Transportation Research Part C, IEEE/CAA Journal of Automatica Sinica, Scientific Reports, Applied Intelligence, Artificial Intelligence Review, and Springer journal venues |
| Add state-of-the-art comparison | Table-level comparison positions Labyrinth Breach against recent systems and explicitly avoids unsupported leaderboard claims |
| Include methodology visualization | Manuscript includes a full methodology and evidence-flow diagram |
| Include architecture diagram | Manuscript includes a role-specific PPO policy architecture diagram |
| Add XAI or interpretation | Manuscript adds artifact-level interpretation using reward audit logs, replay events, and paired deployment interventions |
| Use current results | Manuscript uses five trained policy seeds, 30 canonical evaluation cells, 3,002 episodes, audited learning curves, lightweight controls, and two paired deployment interventions |
| Improve reproducibility | Manuscript and docs map each claim to source artifacts and regeneration scripts |
| Match submission author list | Manuscript and PDF include Ahmed Jawed, Imran Ashraf, Muhammad Sikander Raheem, Usman Irshad Bhatti, Arif Mahmood, Irene Delgado Noya, and Eduardo Garcia Villena |
| Add Elsevier submission back matter | Manuscript includes data and code availability, conflict declaration, funding, author contributions, and ethics statement |
| Add submission side files | Repository includes Elsevier highlights, journal-specific cover letters, and an internal reviewer-risk scorecard |
| Remove legacy readiness language | Public manuscript, README, readiness summary, and evidence snapshot no longer contain internal caution wording |

## Ready Artifacts

- `paper/labyrinth_breach_revised_publication_report.pdf`
- `paper/labyrinth_breach_journal.tex`
- `results/official_summary/publication_readiness.md`
- `results/official_summary/current_evidence_snapshot.md`
- `docs/reproducibility_guide.md`
- `docs/no_retraining_upgrade_status_2026-07-24.md`
- `paper/elsevier_highlights.txt`
- `paper/cover_letter_swarm_and_evolutionary_computation.md`
- `paper/cover_letter_robotics_and_autonomous_systems.md`
- `docs/internal_reviewer_scorecard_2026-08-10.md`

## Current Evidence Boundary

The declared-scope submission evidence is complete for the claims made in the
paper. The registered retraining extensions are memory-off, tactical-reward-off,
and direct-dynamic training. These are not used to support the current primary
claims.

## If Reviewers Ask for More Evidence

Priority 1 is the three retraining ablations already registered in the paper.
Run memory-off, tactical-reward-off, and direct-dynamic training with the same
five policy seeds and the same 30-cell evaluation matrix. This directly answers
mechanism-depth concerns.

Priority 2 is a matched-compute learned baseline such as MAPPO or MA-POCA if
runtime permits. This would strengthen comparison claims beyond random and
geometric-heuristic controls.

Priority 3 is SHAP-style grouped feature attribution over semantic observation
channels. This should be added only after the feature grouping and sampling
protocol are fixed.

Priority 4 is hardware or higher-fidelity robot validation. This is the largest
scope expansion and is best treated as follow-up work unless the target venue
demands physical deployment.
