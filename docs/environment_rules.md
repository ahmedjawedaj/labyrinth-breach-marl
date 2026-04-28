# Environment Rules

## Teams

Labyrinth Breach uses two asymmetric teams:

- 3 Sentinels as pursuers
- 2 Runners as evaders

Sentinels are slightly slower and focused on trapping, blocking, and coordinated control. Runners are slightly faster and focused on survival, exploration, and exit reaching.

All asymmetry values must be configurable through environment or agent configuration, not hardcoded in scattered scripts.

## Episode Flow

Each episode follows this lifecycle:

1. Environment loads the active config.
2. Maze, exits, and dynamic wall states are initialized.
3. Sentinels and Runners spawn at fixed or randomized spawn points.
4. Episode timer starts.
5. Agents act using observations, memory, and ray sensing.
6. Captures, exits, timeouts, wall shifts, and reward events are monitored.
7. A terminal condition ends the episode.
8. Logs and metrics are finalized.
9. All state resets before the next episode.

## Win Conditions

Sentinels win when:

- both Runners are captured before the timeout

Runners win when:

- at least one active Runner reaches an exit, or
- timeout occurs and the active experiment config treats survival as success

Timeout behavior must be configurable because some experiments may treat timeout as Runner success while others may use stricter exit-only success.

## Capture Mechanism

Capture uses a spherical proximity check.

Capture rules:

- a Sentinel captures a Runner when the Runner is within the configured capture radius
- each Runner can be captured only once per episode
- captured Runners become inactive or frozen cleanly
- captured Runners must not continue receiving duplicate capture rewards
- capture events are logged with timestamp, Sentinel ID, Runner ID, and position

## Exit Zones

Exit zones are trigger regions used for Runner success.

Exit rules:

- only active Runners can trigger exit success
- one successful exit event can trigger team success depending on config
- exit events must be handled centrally by the environment controller
- nearest-exit information should be available to Runner observations when enabled

## Dynamic Walls

Dynamic maze variants use modular wall objects that can raise or lower during an episode.

Wall shift rules:

- shift timing is controlled by config
- wall shifts must not spawn geometry on top of agents
- wall shifts should not make exits impossible unless explicitly configured
- wall shifts should meaningfully change routes and line of sight
- each shift is logged with step, wall IDs, and resulting wall states

## Reset Requirements

Episode reset must clear:

- agent positions and velocities
- alive/captured flags
- reward accumulators
- last-known-position memory
- visibility state
- wall states
- exit states
- logs and per-episode metrics

No state should leak across episodes.
