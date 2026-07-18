# Seen and Held-Out Evaluation Protocol (Official)

The publication protocol is registered in:

- `configs/experiment_manifests/official_publication_eval_matrix.yaml`

The older `official_seen_unseen_eval_matrix.yaml` is retained only for historical
compatibility. It is not sufficient for publication because it contains one
unseen configuration and uses a wall-clock duration as the sampling unit.

## Experimental cells

Each independently trained policy seed (`42`, `101`, `202`, `606`, `707`) is
evaluated on:

- one seen training-family topology (`seen_seed42`); and
- five generated held-out topologies (`unseen_seed101`, `202`, `303`, `404`,
  and `505`).

Every policy-topology cell must produce 100 completed episodes. The 30-minute
limit is a failure timeout, not an evaluation budget. Inference is deterministic,
while placement/event seeds vary by episode and the topology seed remains fixed
within a cell.

## Execution

```bash
python scripts/run_publication_eval_matrix.py \
  --results-dir results/publication_eval_official \
  --target-episodes 100 \
  --no-graphics \
  --resume-completed
```

Evaluation starts only after the source Stage 4 training run reports success.
The launcher validates seen/held-out controls before execution and the final
audit enforces episode schema, source checkpoint, scene, rule config, reward
config, topology seed, layout ID, required artifacts, and completed-episode
count.

## Result layout

- Per policy seed and topology:
  `results/publication_eval_official/policy_seed_<seed>/<eval_run_id>/`
- Aggregate tables and audit:
  `results/publication_eval_official/aggregate/`
- Strict training-plus-evaluation tracker:
  `results/LB_3v2_curriculum_official_v1/completion/`

Run `python scripts/seed_completion_tracker.py` for the 20 training stages and
30 evaluation cells. It exits nonzero until every required artifact is complete
and hash-valid.
