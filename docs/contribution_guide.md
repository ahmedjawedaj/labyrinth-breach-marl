# Contribution Guide

## Branching Strategy

Use `main` for stable project states and `dev` for integration.

Feature work should use feature branches:

```text
feature/open-arena-controller
feature/reward-engine-v1
feature/dynamic-wall-controller
feature/evaluation-metrics
```

Bug fixes should use:

```text
fix/capture-reset
fix/config-loading
```

## Commit Messages

Use clear, scoped commit messages:

```text
docs: add reproduction guide
config: add open arena environment config
unity: implement base agent reset
python: add pincer metric calculator
```

Commits should be small enough to review. Avoid mixing unrelated Unity, Python, docs, and config changes in one commit.

## Code Style

Python:

- follow PEP8
- use clear module names
- keep scripts deterministic when seeds are provided
- prefer typed function signatures for metric and config utilities
- run `ruff` before committing once Python code exists

Unity C#:

- use PascalCase for classes and public methods
- use camelCase for local variables
- keep episode state centralized in environment-level controllers
- avoid scene-specific hacks and hardcoded object references
- expose tunable values through configs or serialized fields

## Testing and Validation

Before opening a pull request, run applicable checks:

```bash
python scripts/check_large_artifacts.py
python -m pytest python/tests
```

For Unity work, add or run EditMode and PlayMode tests when available:

```text
unity/Tests/EditMode/
unity/Tests/PlayMode/
```

Minimum validation for environment changes:

- agents spawn correctly
- reset clears state
- capture fires once
- terminal conditions work
- logs are written
- configs load without code changes

## Artifact Rules

Do not commit raw training outputs, large videos, TensorBoard logs, or full checkpoint directories to normal Git.

Use the artifact policy in `docs/reproduction_guide.md`:

- Git LFS for selected curated binary artifacts
- external storage for large raw outputs
- manifests for artifact URIs and run metadata

## Pull Request Checklist

Each pull request should include:

- summary of changes
- affected phase or task ID from `docs/project_plan.md`
- test or validation notes
- config changes if applicable
- artifact or result links if applicable

Do not merge changes that make experiments unreproducible.
