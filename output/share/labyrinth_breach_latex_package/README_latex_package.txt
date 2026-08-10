Labyrinth Breach LaTeX Package

Main file:
- labyrinth_breach_journal.tex

Reference PDF:
- labyrinth_breach_journal.pdf
- labyrinth_breach_revised_publication_report.pdf

Required figure PDFs:
- fig_official_training_reward.pdf
- fig_official_training_elo.pdf
- fig_reward_curves.pdf
- fig_reward_breakdown.pdf
- fig_win_rate.pdf
- fig_penalty_reduction.pdf
- fig_shaping_signals.pdf
- fig_phase_summary.pdf

Optional figure PNGs are included for review convenience.

Evidence summaries:
- current_evidence_snapshot.json
- current_evidence_snapshot.csv
- current_evidence_snapshot.md
- memory_off_checkpoint_summary.json
- memory_off_checkpoint_summary.csv
- memory_off_checkpoint_summary.md

Compilation:
- Run latexmk -pdf labyrinth_breach_journal.tex
- The bibliography is embedded inside the TeX file.
- IEEEtran is expected to be available in the LaTeX installation or Overleaf.
