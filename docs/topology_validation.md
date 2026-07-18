# Held-Out Topology Validation

The Unity build fails unless every reserved held-out seed produces a valid,
distinct topology. Validation runs inside `LabyrinthBreachBuild.BuildMacOS`
before `BuildPipeline.BuildPlayer`.

## Invariants

- Grid dimensions: 13 x 13
- Connected traversable graph with every dynamic wall raised
- Exactly 3 Sentinel starts, 2 Runner starts, and 2 exits
- Exactly 5 optional dynamic connections
- Distinct deterministic signature for every reserved seed
- Topology seed fixed within an evaluation cell
- Placement seed varies by episode without changing topology

## Verified Build

Unity `6000.0.40f1` validated these signatures:

| Topology seed | FNV-1a layout signature |
|---:|---|
| 101 | `0C4DD629B826A7A5` |
| 202 | `6B5493F28CEF891D` |
| 303 | `6EACF6A7B165EF4D` |
| 404 | `B62F2F36764FCD25` |
| 505 | `54B0389F7AC786C9` |

The build log is `builds/macos/unity_build.log`. Official episode logs must also
contain the expected `maze_layout_id` and `maze_topology_seed`; the publication
matrix audit enforces both fields.
