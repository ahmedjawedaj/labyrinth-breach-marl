using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;
using UnityEngine.SceneManagement;

public enum EpisodeOutcome
{
    InProgress,
    SentinelWinAllRunnersCaptured,
    RunnerWinExitReached,
    RunnerWinTimeout,
    TimeoutNoWinner
}

public class PursuitEvasionEnvController : MonoBehaviour
{
    [Header("Episode")]
    [SerializeField] private SpawnManager spawnManager;
    [SerializeField] private EpisodeStateTracker episodeStateTracker;
    [SerializeField] private float episodeDurationSeconds = 120f;
    [SerializeField] private float minSecondsBeforeTerminalChecks = 3f;
    [SerializeField] private float minimumStartTeamSeparation = 2.5f;
    [SerializeField] private float minRunnerTravelBeforeTerminalChecks = 1.25f;
    [SerializeField] private float minSentinelTravelBeforeTerminalChecks = 1.25f;
    [SerializeField] private bool startEpisodeOnStart = true;
    [SerializeField] private bool timeoutCountsAsRunnerWin = true;

    [Header("Runtime Rule Config")]
    [SerializeField] private bool loadRuleConfigOnBeginEpisode = true;
    [SerializeField] private string ruleConfigPath = "../configs/env_configs/asymmetry_config.yaml";
    [SerializeField] private bool exitWinEnabled;
    [SerializeField] private bool requireActiveRunnerForExit = true;
    [SerializeField] private bool verifyResetIntegrity = true;
    [SerializeField] private MazeGenerator mazeGenerator;
    [SerializeField] private DynamicWallController dynamicWallController;

    [Header("Curriculum")]
    [SerializeField] private bool loadCurriculumConfigOnBeginEpisode;
    [SerializeField] private string curriculumConfigPath = "../configs/curriculum_configs/curriculum_3v2_full_v1.yaml";
    [SerializeField] private string runtimeStageOverridePath = "../configs/runtime_overrides/active_stage.txt";
    [SerializeField] private string runtimeCurriculumOverridePath = "../configs/runtime_overrides/active_curriculum_config.txt";
    [SerializeField] private string runtimeRuleOverridePath = "../configs/runtime_overrides/active_rule_config.txt";
    [SerializeField] private int curriculumStageIndex = -1;

    [Header("Observation Settings")]
    [SerializeField] private float observationPositionScale = 24f;
    [SerializeField] private float observationMaxSpeed = 6f;
    [SerializeField] private float rayMaxDistance = 12f;
    [SerializeField] private int sentinelRayCount = 14;
    [SerializeField] private int runnerRayCount = 16;
    [SerializeField] private LayerMask observationRaycastMask = ~0;
    [SerializeField] private LayerMask visibilityBlockingMask = ~0;
    [SerializeField] private LayerMask movementBlockingMask = ~0;
    [SerializeField] private bool preventWallPassThrough = true;
    [SerializeField] private Collider arenaBoundsCollider;
    [SerializeField] private Renderer arenaBoundsRenderer;
    [SerializeField] private Transform arenaCenterOverride;
    [SerializeField] private Vector2 arenaHalfExtents = new Vector2(12f, 12f);
    [SerializeField] private float arenaBoundaryPadding = 0.35f;
    [SerializeField] [Tooltip("Half the agent footprint on XZ (0.5 for a 1m cube at scale 1) so the mesh does not cross the floor edge; pivot is clamped, not the mesh border.")]
    private float confinementAgentHalfExtentXZ = 0.5f;
    [SerializeField] private string exitTag = "Exit";
    [SerializeField] private float wallShiftIntervalSeconds;
    [SerializeField] [Tooltip("World-space radius for exit success when using position checks (aligns with exit collider size).")]
    private float exitReachRadius = 1.15f;
    [SerializeField] [Tooltip("After movement and physics, clamp all agent positions to confinement (fixes OOB in open arena and edge drift).")]
    private bool enforceConfinementInLateUpdate = true;

    [Header("Rewards")]
    [SerializeField] private RewardEngine rewardEngine;
    [SerializeField] private string rewardConfigPath = "../configs/reward_configs/reward_shared_basic_v1.yaml";
    [SerializeField] private float survivalRewardIntervalSeconds = 1f;
    [SerializeField] private float wallLoopPenaltyCheckIntervalSeconds = 0.5f;
    [SerializeField] private float wallLoopLowDisplacementThreshold = 0.08f;
    [SerializeField] [Range(0f, 1f)] private float wallLoopMinWallProximity = 0.7f;
    [SerializeField] private float pursuitShapingIntervalSeconds = 0.8f;
    [SerializeField] private float orbitStallDistanceThreshold = 1.8f;
    [SerializeField] private float orbitStallDeltaThreshold = 0.05f;
    [SerializeField] private int orbitStallRepeatThreshold = 3;
    [SerializeField] private float sentinelTeammateFocusDeltaThreshold = 0.08f;
    [SerializeField] private float sentinelChaseProgressDeadzone = 0.04f;
    [SerializeField] private int sentinelNonProgressRepeatThreshold = 2;
    [SerializeField] private float sentinelCloseEngagementDistance = 3.25f;
    [SerializeField] private float sentinelPursuitAssistStrength = 0.55f;
    [SerializeField] private float runnerEvadeAssistStrength = 0.5f;

    [Header("Logging")]
    [SerializeField] private StepLogger stepLogger;
    [SerializeField] private EpisodeLogger episodeLogger;
    [SerializeField] private ReplayEventExporter replayEventExporter;
    [SerializeField] private CoordinationKPIExporter coordinationKpiExporter;
    [SerializeField] private bool enableStepLogging = true;
    [SerializeField] private bool enableEpisodeLogging = true;
    [SerializeField] private bool enableReplayExport = true;

    [Header("Debug")]
    [SerializeField] private bool logEpisodeEvents = true;
    [SerializeField] private bool debugDrawEnvironment = true;
    [SerializeField] private bool debugDrawEnvironmentLabels = true;
    [SerializeField] private bool showRewardHud = true;
    [SerializeField] private Vector2 rewardHudPosition = new Vector2(14f, 14f);
    [SerializeField] private Vector2 rewardHudSize = new Vector2(370f, 170f);
    [SerializeField] private Color debugExitColor = Color.green;
    [SerializeField] private Color debugWallTimerColor = Color.yellow;
    [SerializeField] private Color debugArenaBoundsColor = Color.cyan;

    private readonly List<SentinelAgent> sentinels = new List<SentinelAgent>();
    private readonly List<RunnerAgent> runners = new List<RunnerAgent>();
    private readonly List<BaseAgent> loggingAgents = new List<BaseAgent>();

    private float elapsedSeconds;
    private float nextSurvivalRewardTime;
    private float nextWallLoopPenaltyCheckTime;
    private float nextPursuitShapingTime;
    private int episodeId;
    private int episodeStep;
    private bool episodeActive;
    private EpisodeOutcome outcome = EpisodeOutcome.InProgress;
    private EnvRuleConfig activeRuleConfig;
    private CurriculumConfig activeCurriculumConfig = CurriculumConfig.Default();
    private CurriculumStageConfig activeCurriculumStage = CurriculumStageConfig.Default();
    private bool hasActiveCurriculumStage;
    private bool resetIntegrityPassed;
    private ObservationConfig activeObservationConfig = ObservationConfig.Default();
    private RandomizationConfig activeRandomizationConfig = RandomizationConfig.Default();
    private GUIStyle rewardHudStyle;
    private readonly Dictionary<string, Vector3> wallLoopLastPositions = new Dictionary<string, Vector3>();
    private readonly Dictionary<string, float> sentinelLastTrackingDistance = new Dictionary<string, float>();
    private readonly Dictionary<string, float> sentinelLastTeammateDistance = new Dictionary<string, float>();
    private readonly Dictionary<string, int> sentinelNonProgressCounts = new Dictionary<string, int>();
    private readonly Dictionary<string, float> runnerLastThreatDistance = new Dictionary<string, float>();
    private readonly Dictionary<string, Vector3> lastPositionByAgent = new Dictionary<string, Vector3>();
    private readonly Dictionary<string, float> travelDistanceByAgent = new Dictionary<string, float>();
    private readonly Dictionary<string, int> wallLoopRepeatCounts = new Dictionary<string, int>();
    private readonly Dictionary<string, int> orbitStallPairCounts = new Dictionary<string, int>();
    private readonly Dictionary<string, float> orbitStallPairLastDistance = new Dictionary<string, float>();
    private readonly HashSet<int> sentinelVisitedCells = new HashSet<int>();
    private readonly HashSet<int> runnerVisitedCells = new HashSet<int>();

    public EpisodeOutcome Outcome => outcome;
    public float ElapsedSeconds => elapsedSeconds;
    public int EpisodeStep => episodeStep;
    public bool EpisodeActive => episodeActive;
    public bool ResetIntegrityPassed => resetIntegrityPassed;
    public ObservationConfig ActiveObservationConfig => activeObservationConfig;
    public string ActiveCurriculumStageId => hasActiveCurriculumStage ? activeCurriculumStage.StageId : string.Empty;
    public int CurriculumStageIndex => curriculumStageIndex;
    public float ObservationPositionScale => observationPositionScale;
    public float ObservationMaxSpeed => observationMaxSpeed;
    public float ObservationMemoryTimeScale => episodeDurationSeconds;
    public float RayMaxDistance => rayMaxDistance;
    public LayerMask ObservationRaycastMask => observationRaycastMask;
    public LayerMask VisibilityBlockingMask => visibilityBlockingMask;
    public DynamicWallController DynamicWallController => dynamicWallController;
    public Vector2 ArenaHalfExtents => arenaHalfExtents;
    public float ArenaBoundaryPadding => arenaBoundaryPadding;

    /// <summary>Edge inset for where agent *centers* are allowed: small padding + body half-extent (open arena exit placement uses this).</summary>
    public float ArenaConfinementInset => arenaBoundaryPadding + confinementAgentHalfExtentXZ;
    public string RuleConfigPath => ruleConfigPath;
    public string RewardConfigPath => rewardConfigPath;

    /// <summary>Public for <see cref="MazeGenerator"/> and diagnostics; uses <see cref="arenaBoundsCollider"/>, then floor renderer, then half-extents.</summary>
    public Bounds GetArenaBoundsWorld() => GetArenaBoundsWorldInternal();

    /// <summary>Uses walkable AABB for maze levels; open arena uses floor bounds. Keeps agents off extended floor around mazes.</summary>
    public Bounds GetConfinementBounds()
    {
        if (mazeGenerator == null)
        {
            mazeGenerator = FindFirstObjectByType<MazeGenerator>();
        }

        if (mazeGenerator != null
            && mazeGenerator.MazeWallsEnabled
            && mazeGenerator.Generated)
        {
            Bounds walk = mazeGenerator.GetWalkableConfinementBounds();
            if (walk.size.sqrMagnitude > 0.1f)
            {
                return walk;
            }
        }

        return GetArenaBoundsWorldInternal();
    }

    private void Awake()
    {
        EnsureArenaBoundsReferences();
    }

    public Vector3 ConstrainAgentPositionToArena(Vector3 proposedPosition, float extraPadding = 0f)
    {
        float safePadding = Mathf.Max(0f, arenaBoundaryPadding + extraPadding + confinementAgentHalfExtentXZ);
        Bounds arenaBounds = GetConfinementBounds();
        float minX = arenaBounds.min.x + safePadding;
        float maxX = arenaBounds.max.x - safePadding;
        float minZ = arenaBounds.min.z + safePadding;
        float maxZ = arenaBounds.max.z - safePadding;
        if (minX > maxX)
        {
            float centerX = (arenaBounds.min.x + arenaBounds.max.x) * 0.5f;
            minX = centerX;
            maxX = centerX;
        }

        if (minZ > maxZ)
        {
            float centerZ = (arenaBounds.min.z + arenaBounds.max.z) * 0.5f;
            minZ = centerZ;
            maxZ = centerZ;
        }

        proposedPosition.x = Mathf.Clamp(proposedPosition.x, minX, maxX);
        proposedPosition.z = Mathf.Clamp(proposedPosition.z, minZ, maxZ);
        return proposedPosition;
    }

    public Vector3 ResolveConstrainedMovement(
        Vector3 currentPosition,
        Vector3 proposedPosition,
        float extraPadding,
        float collisionRadius)
    {
        Vector3 safeStartPosition = ResolveWallOverlapCandidate(
            currentPosition,
            collisionRadius,
            currentPosition - GetConfinementBounds().center);
        Vector3 adjustedProposedPosition = proposedPosition + (safeStartPosition - currentPosition);
        Vector3 resolvedPosition = adjustedProposedPosition;
        if (preventWallPassThrough)
        {
            Vector3 moveDelta = adjustedProposedPosition - safeStartPosition;
            float distance = moveDelta.magnitude;
            if (distance > 1e-5f)
            {
                Vector3 direction = moveDelta / distance;
                Vector3 castOrigin = safeStartPosition + Vector3.up * 0.25f;
                if (TryGetBlockingHit(
                    castOrigin,
                    Mathf.Max(0.01f, collisionRadius),
                    direction,
                    distance,
                    out RaycastHit hit))
                {
                    // Prefer sliding along obstacles instead of fully canceling movement.
                    float skin = Mathf.Max(0.005f, collisionRadius * 0.1f);
                    float stopDistance = Mathf.Max(0f, hit.distance - skin);
                    Vector3 contactPosition = safeStartPosition + direction * stopDistance;
                    float remainingDistance = Mathf.Max(0f, distance - stopDistance);

                    Vector3 slideDirection = Vector3.ProjectOnPlane(direction, hit.normal);
                    slideDirection.y = 0f;
                    if (slideDirection.sqrMagnitude > 1e-6f && remainingDistance > 1e-4f)
                    {
                        slideDirection.Normalize();
                        Vector3 slideOrigin = contactPosition + Vector3.up * 0.25f;
                        if (TryGetBlockingHit(
                            slideOrigin,
                            Mathf.Max(0.01f, collisionRadius),
                            slideDirection,
                            remainingDistance,
                            out RaycastHit slideHit))
                        {
                            float slideDistance = Mathf.Max(0f, slideHit.distance - skin);
                            resolvedPosition = contactPosition + slideDirection * slideDistance;
                        }
                        else
                        {
                            resolvedPosition = contactPosition + slideDirection * remainingDistance;
                        }
                    }
                    else
                    {
                        resolvedPosition = contactPosition;
                    }
                }
                else
                {
                    resolvedPosition = safeStartPosition + direction * distance;
                }
            }
        }

        resolvedPosition = ResolveWallOverlapCandidate(
            resolvedPosition,
            collisionRadius,
            resolvedPosition - safeStartPosition);
        return ConstrainAgentPositionToArena(resolvedPosition, extraPadding);
    }

    private Vector3 ResolveWallOverlapCandidate(Vector3 position, float collisionRadius, Vector3 fallbackDirection)
    {
        if (!preventWallPassThrough)
        {
            return position;
        }

        Vector3 probe = position + Vector3.up * 0.25f;
        int overlapCount = Physics.OverlapSphereNonAlloc(
            probe,
            Mathf.Max(0.01f, collisionRadius),
            ColOverlapBuffer,
            ~0,
            QueryTriggerInteraction.Ignore);
        if (overlapCount <= 0)
        {
            return position;
        }

        Vector3 push = Vector3.zero;
        for (int i = 0; i < overlapCount; i++)
        {
            Collider collider = ColOverlapBuffer[i];
            if (!IsMovementBlockingCollider(collider))
            {
                continue;
            }

            Vector3 closest = collider.ClosestPoint(probe);
            Vector3 away = probe - closest;
            float distance = away.magnitude;
            if (distance < 1e-4f)
            {
                away = probe - collider.bounds.center;
                away.y = 0f;
                if (away.sqrMagnitude < 1e-5f)
                {
                    away = fallbackDirection;
                }
                if (away.sqrMagnitude < 1e-5f)
                {
                    away = Vector3.right;
                }
                away.Normalize();
                distance = 0f;
            }
            else
            {
                away /= distance;
            }

            float penetration = Mathf.Max(0f, collisionRadius - distance + 0.01f);
            push += away * penetration;
        }

        push.y = 0f;
        if (push.sqrMagnitude > 1e-6f)
        {
            position += push;
        }

        return position;
    }

    private bool TryGetBlockingHit(
        Vector3 origin,
        float radius,
        Vector3 direction,
        float distance,
        out RaycastHit blockingHit)
    {
        blockingHit = default;
        RaycastHit[] hits = Physics.SphereCastAll(
            origin,
            Mathf.Max(0.01f, radius),
            direction,
            distance,
            ~0,
            QueryTriggerInteraction.Ignore);
        if (hits == null || hits.Length == 0)
        {
            return false;
        }

        System.Array.Sort(hits, (a, b) => a.distance.CompareTo(b.distance));
        for (int i = 0; i < hits.Length; i++)
        {
            Collider c = hits[i].collider;
            if (!IsMovementBlockingCollider(c))
            {
                continue;
            }

            blockingHit = hits[i];
            return true;
        }

        return false;
    }

    private static bool IsMovementBlockingCollider(Collider collider)
    {
        if (collider == null || collider.isTrigger)
        {
            return false;
        }

        // Only wall geometry should block steering/collision resolution here.
        // Including floor/props can cause oscillation and "vibration" at low speeds.
        if (!collider.CompareTag("Wall"))
        {
            return false;
        }

        BaseAgent hitAgent = collider.GetComponentInParent<BaseAgent>();
        return hitAgent == null;
    }

    /// <summary>Call after layout changes (e.g. dynamic wall shifts) to unstick agents that overlap solid geometry.</summary>
    public void SanitizeAllAgentPositions(float agentRadius = 0.24f, int maxSteps = 12)
    {
        List<BaseAgent> all = new List<BaseAgent>();
        GetAllAgentsForObservation(all);
        for (int i = 0; i < all.Count; i++)
        {
            if (all[i] == null || !all[i].IsAlive)
            {
                continue;
            }

            Vector3 p = all[i].transform.position;
            p = ConstrainAgentPositionToArena(p, 0.02f);
            for (int step = 0; step < maxSteps; step++)
            {
                if (!IsOverlappingTaggedWall(p, agentRadius))
                {
                    break;
                }

                Vector3 c = GetConfinementBounds().center;
                c.y = p.y;
                p = Vector3.MoveTowards(p, c, 0.2f);
                p = ConstrainAgentPositionToArena(p, 0.02f);
            }

            all[i].transform.position = p;
        }
    }

    private static bool IsOverlappingTaggedWall(Vector3 p, float agentRadius)
    {
        Vector3 probe = p + Vector3.up * 0.3f;
        int hit = Physics.OverlapSphereNonAlloc(
            probe,
            agentRadius,
            ColOverlapBuffer,
            ~0,
            QueryTriggerInteraction.Ignore);
        for (int i = 0; i < hit; i++)
        {
            Collider c = ColOverlapBuffer[i];
            if (c == null)
            {
                continue;
            }

            if (c.isTrigger)
            {
                continue;
            }

            if (c.CompareTag("Wall"))
            {
                return true;
            }
        }

        return false;
    }

    private static readonly Collider[] ColOverlapBuffer = new Collider[16];

    private Bounds GetArenaBoundsWorldInternal()
    {
        EnsureArenaBoundsReferences();
        Collider collider = arenaBoundsCollider;
        Renderer renderer = arenaBoundsRenderer;
        if (collider != null && renderer != null)
        {
            // Use the tighter of play-space vs. mesh. A user-added large Box Collider on the floor would otherwise
            // allow agents past the visible grey play area; renderer bounds follow the art.
            return TightenBoundsInXz(collider.bounds, renderer.bounds);
        }

        if (collider != null)
        {
            return collider.bounds;
        }

        if (renderer != null)
        {
            return renderer.bounds;
        }

        Vector3 center = arenaCenterOverride != null ? arenaCenterOverride.position : transform.position;
        return new Bounds(center, new Vector3(arenaHalfExtents.x * 2f, 0.1f, arenaHalfExtents.y * 2f));
    }

    private static Bounds TightenBoundsInXz(Bounds a, Bounds b)
    {
        float minX = Mathf.Max(a.min.x, b.min.x);
        float maxX = Mathf.Min(a.max.x, b.max.x);
        float minZ = Mathf.Max(a.min.z, b.min.z);
        float maxZ = Mathf.Min(a.max.z, b.max.z);
        if (minX < maxX && minZ < maxZ)
        {
            float h = Mathf.Max(0.1f, (a.size.y + b.size.y) * 0.5f);
            return new Bounds(
                new Vector3((minX + maxX) * 0.5f, (a.center.y + b.center.y) * 0.5f, (minZ + maxZ) * 0.5f),
                new Vector3(maxX - minX, h, maxZ - minZ));
        }

        float areaA = Mathf.Max(0.01f, a.size.x) * Mathf.Max(0.01f, a.size.z);
        float areaB = Mathf.Max(0.01f, b.size.x) * Mathf.Max(0.01f, b.size.z);
        return areaA < areaB ? a : b;
    }

    private void EnsureArenaBoundsReferences()
    {
        if (arenaBoundsCollider != null || arenaBoundsRenderer != null)
        {
            return;
        }

        GameObject floor = GameObject.Find("OpenArena_Floor");
        if (floor == null)
        {
            return;
        }

        if (arenaBoundsCollider == null)
        {
            arenaBoundsCollider = floor.GetComponent<Collider>();
        }

        if (arenaBoundsRenderer == null)
        {
            arenaBoundsRenderer = floor.GetComponent<Renderer>();
        }
    }

    public void SetCurriculumStageIndex(int stageIndex)
    {
        curriculumStageIndex = stageIndex;
    }

    private void Start()
    {
        if (startEpisodeOnStart)
        {
            BeginEpisode();
        }
    }

    private void Update()
    {
        if (!episodeActive)
        {
            return;
        }

        elapsedSeconds += Time.deltaTime;
        episodeStep++;
        UpdateTravelDistanceMetrics();
        UpdateMazeCoverageMetrics();

        ApplySurvivalRewards();
        DetectCaptures();
        EvaluateTrapRewards();
        EvaluateWallLoopPenalties();
        EvaluatePursuitAndEvadeShaping();
        DetectExitSuccess();
        EvaluateTerminalConditions();

        if (episodeActive)
        {
            RecordStepLogs();
        }
    }

    private void LateUpdate()
    {
        if (!enforceConfinementInLateUpdate || !episodeActive)
        {
            return;
        }

        EnforceConfinementForAllAgents();
    }

    private void EnforceConfinementForAllAgents()
    {
        for (int i = 0; i < sentinels.Count; i++)
        {
            SentinelAgent agent = sentinels[i];
            if (agent == null || !agent.isActiveAndEnabled)
            {
                continue;
            }

            if (!agent.IsAlive)
            {
                continue;
            }

            Vector3 p = agent.transform.position;
            p = ConstrainAgentPositionToArena(p, 0.02f);
            agent.transform.position = p;
        }

        for (int i = 0; i < runners.Count; i++)
        {
            RunnerAgent agent = runners[i];
            if (agent == null || !agent.isActiveAndEnabled)
            {
                continue;
            }

            if (!agent.IsAlive)
            {
                continue;
            }

            Vector3 p = agent.transform.position;
            p = ConstrainAgentPositionToArena(p, 0.02f);
            agent.transform.position = p;
        }
    }

    [ContextMenu("Begin Episode")]
    public void BeginEpisode()
    {
        episodeId++;
        episodeStep = 0;
        elapsedSeconds = 0f;
        nextSurvivalRewardTime = survivalRewardIntervalSeconds;
        nextWallLoopPenaltyCheckTime = wallLoopPenaltyCheckIntervalSeconds;
        nextPursuitShapingTime = pursuitShapingIntervalSeconds;
        outcome = EpisodeOutcome.InProgress;
        episodeActive = true;
        resetIntegrityPassed = false;

        if (spawnManager == null)
        {
            spawnManager = FindFirstObjectByType<SpawnManager>();
        }

        if (spawnManager == null)
        {
            Debug.LogError("PursuitEvasionEnvController requires a SpawnManager.", this);
            episodeActive = false;
            return;
        }

        if (mazeGenerator == null)
        {
            mazeGenerator = FindFirstObjectByType<MazeGenerator>();
        }

        if (dynamicWallController == null)
        {
            dynamicWallController = FindFirstObjectByType<DynamicWallController>();
        }

        LoadAndApplyRuleConfig();

        if (mazeGenerator != null)
        {
            mazeGenerator.GenerateIfNeeded();
        }

        ResetExitZoneTriggers();

        if (episodeStateTracker == null)
        {
            episodeStateTracker = FindFirstObjectByType<EpisodeStateTracker>();
        }

        if (episodeStateTracker == null)
        {
            episodeStateTracker = gameObject.AddComponent<EpisodeStateTracker>();
        }

        episodeStateTracker.BeginEpisode(episodeId);
        EnsureRewardEngine();
        rewardEngine.Configure(rewardConfigPath);
        EnsureLoggers();
        rewardEngine.SetReplayEventExporter(enableReplayExport ? replayEventExporter : null);
        rewardEngine.BeginEpisode(episodeId, episodeStateTracker, logEpisodeEvents);
        spawnManager.ResetSpawnedAgents();
        CacheAgents();
        if (sentinels.Count == 0 || runners.Count == 0)
        {
            // One retry after potential prefab/reference recovery inside SpawnManager.
            spawnManager.SpawnAgents();
            CacheAgents();
        }

        if (sentinels.Count == 0 || runners.Count == 0)
        {
            Debug.LogError(
                $"Episode start failed: sentinels={sentinels.Count}, runners={runners.Count}. " +
                "Check SpawnManager prefab assignments (Sentinel/Runner).",
                this);
            episodeActive = false;
            return;
        }

        ApplyAgentRuleOverrides();
        ResetAgents();
        EnforceMinimumStartSeparation();
        InitializeTerminalArmingMetrics();
        ResetMazeCoverageMetrics();
        RefreshWallLoopPositionMemory();
        ResetTrackingDistanceMemory();
        resetIntegrityPassed = ValidateResetIntegrity();
        BeginLoggers();

        if (logEpisodeEvents)
        {
            Debug.Log($"Episode {episodeId} started. resetIntegrity={resetIntegrityPassed}", this);
        }
    }

    [ContextMenu("Reset Episode")]
    public void ResetEpisode()
    {
        BeginEpisode();
    }

    public void NotifyRunnerReachedExit(RunnerAgent runner)
    {
        if (!episodeActive || runner == null)
        {
            return;
        }

        if (!AreTerminalChecksArmed())
        {
            return;
        }

        if (!exitWinEnabled)
        {
            return;
        }

        if (requireActiveRunnerForExit && !runner.IsAlive)
        {
            return;
        }

        runner.MarkEscaped();
        if (enableEpisodeLogging && episodeLogger != null)
        {
            episodeLogger.RecordExit();
        }

        if (enableReplayExport && replayEventExporter != null)
        {
            replayEventExporter.RecordExit(episodeStep, elapsedSeconds, runner);
        }

        EnsureRewardEngine();
        rewardEngine.ApplyRunnerExitWin(runners, sentinels, episodeStep, elapsedSeconds);
        EndEpisode(EpisodeOutcome.RunnerWinExitReached);
    }

    private void ResetExitZoneTriggers()
    {
        ExitZoneController[] exits = FindObjectsByType<ExitZoneController>(FindObjectsSortMode.None);
        for (int i = 0; i < exits.Length; i++)
        {
            if (exits[i] != null)
            {
                exits[i].ResetExit();
            }
        }
    }

    private void CacheAgents()
    {
        sentinels.Clear();
        runners.Clear();
        spawnManager.GetSpawnedAgents(sentinels, runners);
    }

    private void ResetAgents()
    {
        for (int i = 0; i < sentinels.Count; i++)
        {
            if (sentinels[i] != null)
            {
                sentinels[i].ResetState();
            }
        }

        for (int i = 0; i < runners.Count; i++)
        {
            if (runners[i] != null)
            {
                runners[i].ResetState();
            }
        }
    }

    private void LoadAndApplyRuleConfig()
    {
        activeRuleConfig = EnvRuleConfig.Default();
        activeRuleConfig.TimeoutSeconds = episodeDurationSeconds;
        activeRuleConfig.TimeoutCountsAsRunnerWin = timeoutCountsAsRunnerWin;
        activeRuleConfig.ExitWinEnabled = exitWinEnabled;
        activeRuleConfig.RequireActiveRunnerForExit = requireActiveRunnerForExit;
        activeRuleConfig.VerifyResetIntegrity = verifyResetIntegrity;

        if (loadRuleConfigOnBeginEpisode)
        {
            if (EnvRuleConfigLoader.TryLoad(ruleConfigPath, out EnvRuleConfig loadedConfig, out string message))
            {
                activeRuleConfig = loadedConfig;
                if (logEpisodeEvents)
                {
                    Debug.Log(message, this);
                }
            }
            else if (logEpisodeEvents)
            {
                Debug.LogWarning(message, this);
            }
        }

        ApplyCurriculumStageIfEnabled();
        ApplyRuntimeRuleOverrideIfPresent();
        ApplyRandomizationControls();

        episodeDurationSeconds = activeRuleConfig.TimeoutSeconds;
        timeoutCountsAsRunnerWin = activeRuleConfig.TimeoutCountsAsRunnerWin;
        exitWinEnabled = activeRuleConfig.ExitWinEnabled;
        requireActiveRunnerForExit = activeRuleConfig.RequireActiveRunnerForExit;
        verifyResetIntegrity = activeRuleConfig.VerifyResetIntegrity;
        activeObservationConfig = activeRuleConfig.ObservationConfig;
        sentinelRayCount = Mathf.Max(0, activeObservationConfig.SentinelRayCount);
        runnerRayCount = Mathf.Max(0, activeObservationConfig.RunnerRayCount);
        wallShiftIntervalSeconds = activeRuleConfig.DynamicWallsEnabled ? activeRuleConfig.WallShiftIntervalSeconds : 0f;
        spawnManager.SetAgentDynamics(activeRuleConfig.SentinelSpeed, activeRuleConfig.RunnerSpeed);
        if (mazeGenerator != null)
        {
            mazeGenerator.SetUseUnseenLayout(activeRuleConfig.UseUnseenMazeLayout);
        }

        if (dynamicWallController != null)
        {
            dynamicWallController.Configure(
                activeRuleConfig.DynamicWallsEnabled,
                activeRuleConfig.WallShiftIntervalSeconds,
                activeRuleConfig.WallShiftIntensity,
                activeRuleConfig.WallSafeBuffer,
                activeRuleConfig.AllowExitBlocking,
                activeRuleConfig.WallLoweredOffset);
        }
    }

    private void ApplyRandomizationControls()
    {
        activeRandomizationConfig = activeRuleConfig.RandomizationConfig;
        System.Random random = new System.Random(activeRandomizationConfig.Seed + episodeId);

        if (activeRandomizationConfig.RandomizeSpeedAsymmetry)
        {
            activeRuleConfig.SentinelSpeed = RandomRange(
                random,
                activeRandomizationConfig.SentinelSpeedMin,
                activeRandomizationConfig.SentinelSpeedMax);
            activeRuleConfig.RunnerSpeed = RandomRange(
                random,
                activeRandomizationConfig.RunnerSpeedMin,
                activeRandomizationConfig.RunnerSpeedMax);
        }

        if (activeRandomizationConfig.RandomizeTimeout)
        {
            activeRuleConfig.TimeoutSeconds = RandomRange(
                random,
                activeRandomizationConfig.TimeoutMinSeconds,
                activeRandomizationConfig.TimeoutMaxSeconds);
        }

        if (activeRuleConfig.DynamicWallsEnabled && activeRandomizationConfig.RandomizeWallShiftFrequency)
        {
            activeRuleConfig.WallShiftIntervalSeconds = RandomRange(
                random,
                activeRandomizationConfig.WallShiftMinSeconds,
                activeRandomizationConfig.WallShiftMaxSeconds);
        }

        if (mazeGenerator != null &&
            (activeRandomizationConfig.RandomizeSpawnPositions || activeRandomizationConfig.RandomizeExitPositions))
        {
            mazeGenerator.ConfigureRandomizationControls(
                activeRandomizationConfig.MazeSeed + episodeId,
                activeRandomizationConfig.RandomizeSpawnPositions,
                activeRandomizationConfig.RandomizeExitPositions);
        }

        if (logEpisodeEvents &&
            (activeRandomizationConfig.RandomizeSpawnPositions ||
            activeRandomizationConfig.RandomizeExitPositions ||
            activeRandomizationConfig.RandomizeWallShiftFrequency ||
            activeRandomizationConfig.RandomizeSpeedAsymmetry ||
            activeRandomizationConfig.RandomizeTimeout))
        {
            Debug.Log(
                $"Applied randomization seed={activeRandomizationConfig.Seed + episodeId}, " +
                $"sentinelSpeed={activeRuleConfig.SentinelSpeed:0.##}, runnerSpeed={activeRuleConfig.RunnerSpeed:0.##}, " +
                $"timeout={activeRuleConfig.TimeoutSeconds:0.##}, " +
                $"wallShiftInterval={activeRuleConfig.WallShiftIntervalSeconds:0.##}, " +
                $"randomSpawns={activeRandomizationConfig.RandomizeSpawnPositions}, " +
                $"randomExits={activeRandomizationConfig.RandomizeExitPositions}.",
                this);
        }
    }

    private static float RandomRange(System.Random random, float min, float max)
    {
        float lower = Mathf.Min(min, max);
        float upper = Mathf.Max(min, max);
        if (Mathf.Approximately(lower, upper))
        {
            return lower;
        }

        return lower + (float)random.NextDouble() * (upper - lower);
    }

    private void ApplyCurriculumStageIfEnabled()
    {
        hasActiveCurriculumStage = false;
        activeCurriculumStage = CurriculumStageConfig.Default();

        if (!loadCurriculumConfigOnBeginEpisode)
        {
            return;
        }

        string configuredCurriculumPath = ResolveRuntimeConfigOverridePath(runtimeCurriculumOverridePath);
        if (string.IsNullOrWhiteSpace(configuredCurriculumPath))
        {
            configuredCurriculumPath = curriculumConfigPath;
        }

        if (!CurriculumConfigLoader.TryLoad(
            configuredCurriculumPath,
            out CurriculumConfig loadedCurriculum,
            out string curriculumMessage))
        {
            if (logEpisodeEvents)
            {
                Debug.LogWarning(curriculumMessage, this);
            }

            return;
        }

        activeCurriculumConfig = loadedCurriculum;
        int selectedStageIndex = -1;
        if (TryGetRuntimeStageOverrideIndex(loadedCurriculum, out int overrideStageIndex))
        {
            selectedStageIndex = overrideStageIndex;
        }
        else
        {
            selectedStageIndex = curriculumStageIndex >= 0
                ? curriculumStageIndex
                : FindCurriculumStageIndexForActiveScene(loadedCurriculum);
        }
        selectedStageIndex = Mathf.Clamp(selectedStageIndex, 0, loadedCurriculum.Stages.Count - 1);
        curriculumStageIndex = selectedStageIndex;
        activeCurriculumStage = loadedCurriculum.Stages[selectedStageIndex];
        hasActiveCurriculumStage = true;

        if (!string.IsNullOrWhiteSpace(activeCurriculumStage.RuleConfigPath))
        {
            if (EnvRuleConfigLoader.TryLoad(
                activeCurriculumStage.RuleConfigPath,
                out EnvRuleConfig stageRuleConfig,
                out string ruleMessage))
            {
                activeRuleConfig = stageRuleConfig;
                if (logEpisodeEvents)
                {
                    Debug.Log(ruleMessage, this);
                }
            }
            else if (logEpisodeEvents)
            {
                Debug.LogWarning(ruleMessage, this);
            }
        }

        activeRuleConfig.DynamicWallsEnabled = activeCurriculumStage.DynamicWallsEnabled;
        activeRuleConfig.WallShiftIntervalSeconds = activeCurriculumStage.WallShiftIntervalSeconds;
        activeRuleConfig.WallShiftIntensity = activeCurriculumStage.WallShiftIntensity;
        activeRuleConfig.WallSafeBuffer = activeCurriculumStage.WallSafeBuffer;
        activeRuleConfig.AllowExitBlocking = activeCurriculumStage.AllowExitBlocking;
        activeRuleConfig.WallLoweredOffset = activeCurriculumStage.WallLoweredOffset;

        if (mazeGenerator != null)
        {
            mazeGenerator.ConfigureForCurriculum(
                activeCurriculumStage.MazeEnabled,
                activeCurriculumStage.MazeMode,
                activeCurriculumStage.MazeSeed,
                activeCurriculumStage.RandomizeSpawns,
                activeCurriculumStage.RandomizeExits);
        }

        if (logEpisodeEvents)
        {
            Debug.Log(
                $"{curriculumMessage}. Stage {selectedStageIndex}: {activeCurriculumStage.StageId}, " +
                $"mazeEnabled={activeCurriculumStage.MazeEnabled}, mode={activeCurriculumStage.MazeMode}, " +
                $"dynamicWalls={activeCurriculumStage.DynamicWallsEnabled}, " +
                $"shiftInterval={activeCurriculumStage.WallShiftIntervalSeconds:0.##}s.",
                this);
        }
    }

    private int FindCurriculumStageIndexForActiveScene(CurriculumConfig curriculumConfig)
    {
        string activeSceneName = SceneManager.GetActiveScene().name;
        for (int i = 0; i < curriculumConfig.Stages.Count; i++)
        {
            if (string.Equals(curriculumConfig.Stages[i].SceneName, activeSceneName, System.StringComparison.Ordinal))
            {
                return i;
            }
        }

        return curriculumConfig.DefaultStageIndex;
    }

    private bool TryGetRuntimeStageOverrideIndex(CurriculumConfig curriculumConfig, out int stageIndex)
    {
        stageIndex = -1;
        string stageId = ReadRuntimeStageOverrideId();
        if (string.IsNullOrWhiteSpace(stageId))
        {
            return false;
        }

        for (int i = 0; i < curriculumConfig.Stages.Count; i++)
        {
            if (string.Equals(curriculumConfig.Stages[i].StageId, stageId, System.StringComparison.Ordinal))
            {
                stageIndex = i;
                return true;
            }
        }

        return false;
    }

    private string ReadRuntimeStageOverrideId()
    {
        if (string.IsNullOrWhiteSpace(runtimeStageOverridePath))
        {
            return string.Empty;
        }

        string resolvedPath = string.Empty;
        if (Path.IsPathRooted(runtimeStageOverridePath))
        {
            resolvedPath = runtimeStageOverridePath;
        }
        else
        {
            string projectRootCandidate = Path.GetFullPath(Path.Combine(Application.dataPath, "..", runtimeStageOverridePath));
            if (File.Exists(projectRootCandidate))
            {
                resolvedPath = projectRootCandidate;
            }
            else
            {
                string repoRootCandidate = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", runtimeStageOverridePath));
                resolvedPath = repoRootCandidate;
            }
        }

        if (!File.Exists(resolvedPath))
        {
            return string.Empty;
        }

        string raw = File.ReadAllText(resolvedPath);
        return raw == null ? string.Empty : raw.Trim();
    }

    private void ApplyRuntimeRuleOverrideIfPresent()
    {
        string overrideRulePath = ReadRuntimeRuleOverridePath();
        if (string.IsNullOrWhiteSpace(overrideRulePath))
        {
            return;
        }

        if (EnvRuleConfigLoader.TryLoad(overrideRulePath, out EnvRuleConfig loadedConfig, out string message))
        {
            activeRuleConfig = loadedConfig;
            if (logEpisodeEvents)
            {
                Debug.Log($"Loaded runtime rule override: {overrideRulePath}. {message}", this);
            }
        }
        else if (logEpisodeEvents)
        {
            Debug.LogWarning($"Runtime rule override failed: {overrideRulePath}. {message}", this);
        }
    }

    private string ReadRuntimeRuleOverridePath()
    {
        return ResolveRuntimeConfigOverridePath(runtimeRuleOverridePath);
    }

    private string ResolveRuntimeConfigOverridePath(string overrideFilePath)
    {
        if (string.IsNullOrWhiteSpace(overrideFilePath))
        {
            return string.Empty;
        }

        string resolvedPath = string.Empty;
        if (Path.IsPathRooted(overrideFilePath))
        {
            resolvedPath = overrideFilePath;
        }
        else
        {
            string projectRootCandidate = Path.GetFullPath(Path.Combine(Application.dataPath, "..", overrideFilePath));
            if (File.Exists(projectRootCandidate))
            {
                resolvedPath = projectRootCandidate;
            }
            else
            {
                string repoRootCandidate = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", overrideFilePath));
                resolvedPath = repoRootCandidate;
            }
        }

        if (!File.Exists(resolvedPath))
        {
            return string.Empty;
        }

        string raw = File.ReadAllText(resolvedPath);
        if (string.IsNullOrWhiteSpace(raw))
        {
            return string.Empty;
        }

        string configuredPath = raw.Trim();
        if (Path.IsPathRooted(configuredPath))
        {
            return configuredPath;
        }

        return Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", configuredPath));
    }

    private void ApplyAgentRuleOverrides()
    {
        for (int i = 0; i < sentinels.Count; i++)
        {
            if (sentinels[i] != null)
            {
                sentinels[i].SetCaptureRadius(activeRuleConfig.CaptureRadius);
            }
        }
    }

    private void ApplySurvivalRewards()
    {
        if (survivalRewardIntervalSeconds <= 0f)
        {
            return;
        }

        if (elapsedSeconds < nextSurvivalRewardTime)
        {
            return;
        }

        nextSurvivalRewardTime += survivalRewardIntervalSeconds;

        for (int i = 0; i < runners.Count; i++)
        {
            RunnerAgent runner = runners[i];
            if (runner == null || !runner.IsAlive)
            {
                continue;
            }

            EnsureRewardEngine();
            rewardEngine.ApplyRunnerSurvival(runner, episodeStep, elapsedSeconds);
        }
    }

    private void EvaluateWallLoopPenalties()
    {
        if (wallLoopPenaltyCheckIntervalSeconds <= 0f || elapsedSeconds < nextWallLoopPenaltyCheckTime)
        {
            return;
        }

        nextWallLoopPenaltyCheckTime += wallLoopPenaltyCheckIntervalSeconds;
        EvaluateWallLoopPenaltyForTeam(sentinels);
        EvaluateWallLoopPenaltyForTeam(runners);
    }

    private void EvaluatePursuitAndEvadeShaping()
    {
        if (pursuitShapingIntervalSeconds <= 0f || elapsedSeconds < nextPursuitShapingTime)
        {
            return;
        }

        nextPursuitShapingTime += pursuitShapingIntervalSeconds;
        EnsureRewardEngine();
        if (rewardEngine == null)
        {
            return;
        }

        List<BaseAgent> allAgents = new List<BaseAgent>(8);
        GetAllAgentsForObservation(allAgents);
        EvaluateSentinelTrackingShaping(allAgents);
        EvaluateRunnerThreatShaping(allAgents);
        EvaluateOrbitStallPenalty();
    }

    private void EvaluateSentinelTrackingShaping(List<BaseAgent> allAgents)
    {
        for (int i = 0; i < sentinels.Count; i++)
        {
            SentinelAgent sentinel = sentinels[i];
            if (sentinel == null || !sentinel.IsAlive)
            {
                continue;
            }

            float trackingDistance = GetTrackingDistanceForSentinel(sentinel, allAgents);
            if (trackingDistance <= 1e-4f)
            {
                sentinelNonProgressCounts[sentinel.AgentId] = 0;
                continue;
            }

            float teammateDistance = GetNearestSentinelTeammateDistance(sentinel);
            if (sentinelLastTrackingDistance.TryGetValue(sentinel.AgentId, out float previousDistance))
            {
                rewardEngine.ApplySentinelChaseDelta(
                    sentinel,
                    previousDistance,
                    trackingDistance,
                    episodeStep,
                    elapsedSeconds);

                float chaseDelta = previousDistance - trackingDistance;
                int nonProgressCount = sentinelNonProgressCounts.TryGetValue(sentinel.AgentId, out int count) ? count : 0;
                nonProgressCount = chaseDelta <= sentinelChaseProgressDeadzone ? nonProgressCount + 1 : 0;
                sentinelNonProgressCounts[sentinel.AgentId] = nonProgressCount;

                if (nonProgressCount >= Mathf.Max(1, sentinelNonProgressRepeatThreshold))
                {
                    rewardEngine.ApplyWallLoopPenalty(
                        sentinel,
                        episodeStep,
                        elapsedSeconds,
                        $"sentinel_nonprogress_chase;delta={chaseDelta:0.000};repeat={nonProgressCount}",
                        1.35f);
                    sentinelNonProgressCounts[sentinel.AgentId] = 0;
                }

                if (trackingDistance <= Mathf.Max(1.25f, sentinelCloseEngagementDistance)
                    && chaseDelta <= sentinelChaseProgressDeadzone)
                {
                    rewardEngine.ApplyWallLoopPenalty(
                        sentinel,
                        episodeStep,
                        elapsedSeconds,
                        $"sentinel_close_no_engage;distance={trackingDistance:0.000};delta={chaseDelta:0.000}",
                        1.65f);
                }

                if (sentinelLastTeammateDistance.TryGetValue(sentinel.AgentId, out float previousTeammateDistance))
                {
                    float teammateDelta = previousTeammateDistance - teammateDistance;
                    if (teammateDelta > sentinelTeammateFocusDeltaThreshold
                        && chaseDelta <= sentinelChaseProgressDeadzone)
                    {
                        rewardEngine.ApplyWallLoopPenalty(
                            sentinel,
                            episodeStep,
                            elapsedSeconds,
                            $"sentinel_teammate_focus;mate_delta={teammateDelta:0.000};chase_delta={chaseDelta:0.000}",
                            1.5f);
                    }
                }
            }

            sentinelLastTrackingDistance[sentinel.AgentId] = trackingDistance;
            sentinelLastTeammateDistance[sentinel.AgentId] = teammateDistance;
        }
    }

    private float GetNearestSentinelTeammateDistance(SentinelAgent source)
    {
        if (source == null)
        {
            return float.MaxValue;
        }

        float nearest = float.MaxValue;
        for (int i = 0; i < sentinels.Count; i++)
        {
            SentinelAgent other = sentinels[i];
            if (other == null || !other.IsAlive || other == source)
            {
                continue;
            }

            float d = Vector3.Distance(source.transform.position, other.transform.position);
            if (d < nearest)
            {
                nearest = d;
            }
        }

        return nearest;
    }

    public bool TryGetSentinelPursuitAssist(SentinelAgent sentinel, out Vector3 assistDirection, out float assistWeight)
    {
        assistDirection = Vector3.zero;
        assistWeight = 0f;
        if (sentinel == null || !sentinel.IsAlive)
        {
            return false;
        }

        List<BaseAgent> allAgents = new List<BaseAgent>(8);
        GetAllAgentsForObservation(allAgents);
        BaseAgent visibleOpponent = VisibilityTracker.FindNearestVisibleOpponent(
            sentinel,
            allAgents,
            rayMaxDistance,
            visibilityBlockingMask);

        Vector3 targetPosition;
        if (visibleOpponent != null)
        {
            targetPosition = visibleOpponent.transform.position;
        }
        else if (activeObservationConfig.UseMemory && sentinel.TargetMemory.LastKnownValid)
        {
            targetPosition = sentinel.TargetMemory.LastKnownTargetPosition;
        }
        else
        {
            return false;
        }

        Vector3 toTarget = targetPosition - sentinel.transform.position;
        toTarget.y = 0f;
        float distance = toTarget.magnitude;
        if (distance <= 1e-4f)
        {
            return false;
        }

        Vector3 desired = toTarget / distance;
        float castDistance = Mathf.Min(distance, 2.5f);
        Vector3 castOrigin = sentinel.transform.position + Vector3.up * 0.25f;
        if (TryGetBlockingHit(castOrigin, 0.45f, desired, castDistance, out RaycastHit hit))
        {
            Vector3 slide = Vector3.ProjectOnPlane(desired, hit.normal);
            slide.y = 0f;
            if (slide.sqrMagnitude > 1e-5f)
            {
                desired = (desired * 0.4f + slide.normalized * 0.6f).normalized;
            }
        }

        assistDirection = desired;
        float urgency = Mathf.Clamp01(1f - (distance / Mathf.Max(1f, rayMaxDistance)));
        assistWeight = Mathf.Clamp01(sentinelPursuitAssistStrength * (0.35f + 0.65f * urgency));
        return true;
    }

    public bool TryGetRunnerEvadeAssist(RunnerAgent runner, out Vector3 evadeDirection, out float evadeWeight)
    {
        evadeDirection = Vector3.zero;
        evadeWeight = 0f;
        if (runner == null || !runner.IsAlive || runner.IsCaptured)
        {
            return false;
        }

        List<BaseAgent> allAgents = new List<BaseAgent>(8);
        GetAllAgentsForObservation(allAgents);
        BaseAgent visibleThreat = VisibilityTracker.FindNearestVisibleOpponent(
            runner,
            allAgents,
            rayMaxDistance,
            visibilityBlockingMask);
        if (visibleThreat == null)
        {
            return false;
        }

        Vector3 awayFromThreat = runner.transform.position - visibleThreat.transform.position;
        awayFromThreat.y = 0f;
        float distance = awayFromThreat.magnitude;
        if (distance <= 1e-4f)
        {
            return false;
        }

        Vector3 desired = awayFromThreat / distance;
        float castDistance = Mathf.Min(2.2f, Mathf.Max(1f, distance * 0.7f));
        Vector3 castOrigin = runner.transform.position + Vector3.up * 0.25f;
        if (TryGetBlockingHit(castOrigin, 0.45f, desired, castDistance, out RaycastHit hit))
        {
            Vector3 slide = Vector3.ProjectOnPlane(desired, hit.normal);
            slide.y = 0f;
            if (slide.sqrMagnitude > 1e-5f)
            {
                desired = (desired * 0.35f + slide.normalized * 0.65f).normalized;
            }
        }

        evadeDirection = desired;
        float urgency = Mathf.Clamp01(1f - (distance / Mathf.Max(1f, rayMaxDistance)));
        evadeWeight = Mathf.Clamp01(runnerEvadeAssistStrength * (0.3f + 0.7f * urgency));
        return true;
    }

    private void EvaluateRunnerThreatShaping(List<BaseAgent> allAgents)
    {
        for (int i = 0; i < runners.Count; i++)
        {
            RunnerAgent runner = runners[i];
            if (runner == null || !runner.IsAlive || runner.IsCaptured)
            {
                continue;
            }

            float threatDistance = GetThreatDistanceForRunner(runner, allAgents);
            if (threatDistance <= 1e-4f)
            {
                continue;
            }

            if (runnerLastThreatDistance.TryGetValue(runner.AgentId, out float previousDistance))
            {
                rewardEngine.ApplyRunnerThreatDelta(
                    runner,
                    previousDistance,
                    threatDistance,
                    episodeStep,
                    elapsedSeconds);
            }

            runnerLastThreatDistance[runner.AgentId] = threatDistance;
        }
    }

    private void EvaluateOrbitStallPenalty()
    {
        int repeatThreshold = Mathf.Max(2, orbitStallRepeatThreshold);
        float distanceThreshold = Mathf.Max(0.8f, orbitStallDistanceThreshold);
        float deltaThreshold = Mathf.Max(0.005f, orbitStallDeltaThreshold);
        for (int r = 0; r < runners.Count; r++)
        {
            RunnerAgent runner = runners[r];
            if (runner == null || !runner.IsAlive || runner.IsCaptured)
            {
                continue;
            }

            SentinelAgent nearestSentinel = null;
            float nearestDistance = float.MaxValue;
            for (int s = 0; s < sentinels.Count; s++)
            {
                SentinelAgent sentinel = sentinels[s];
                if (sentinel == null || !sentinel.IsAlive)
                {
                    continue;
                }

                float d = Vector3.Distance(runner.transform.position, sentinel.transform.position);
                if (d < nearestDistance)
                {
                    nearestDistance = d;
                    nearestSentinel = sentinel;
                }
            }

            if (nearestSentinel == null || nearestDistance > distanceThreshold)
            {
                continue;
            }

            string pairKey = nearestSentinel.AgentId + "|" + runner.AgentId;
            if (orbitStallPairLastDistance.TryGetValue(pairKey, out float prevDistance))
            {
                float delta = Mathf.Abs(nearestDistance - prevDistance);
                int count = orbitStallPairCounts.TryGetValue(pairKey, out int currentCount) ? currentCount : 0;
                count = delta <= deltaThreshold ? count + 1 : 0;
                orbitStallPairCounts[pairKey] = count;
                if (count >= repeatThreshold)
                {
                    rewardEngine.ApplyOrbitStallPenalty(
                        nearestSentinel,
                        episodeStep,
                        elapsedSeconds,
                        $"pair={pairKey};dist={nearestDistance:0.000}");
                    rewardEngine.ApplyOrbitStallPenalty(
                        runner,
                        episodeStep,
                        elapsedSeconds,
                        $"pair={pairKey};dist={nearestDistance:0.000}");
                    orbitStallPairCounts[pairKey] = 0;
                }
            }

            orbitStallPairLastDistance[pairKey] = nearestDistance;
        }
    }

    private float GetTrackingDistanceForSentinel(SentinelAgent sentinel, List<BaseAgent> allAgents)
    {
        BaseAgent visibleOpponent = VisibilityTracker.FindNearestVisibleOpponent(
            sentinel,
            allAgents,
            rayMaxDistance,
            visibilityBlockingMask);
        if (visibleOpponent != null)
        {
            return Vector3.Distance(sentinel.transform.position, visibleOpponent.transform.position);
        }

        if (activeObservationConfig.UseMemory && sentinel.TargetMemory.LastKnownValid)
        {
            Vector3 memoryTarget = sentinel.TargetMemory.LastKnownTargetPosition;
            return Vector3.Distance(sentinel.transform.position, memoryTarget);
        }

        return 0f;
    }

    private float GetThreatDistanceForRunner(RunnerAgent runner, List<BaseAgent> allAgents)
    {
        BaseAgent visibleOpponent = VisibilityTracker.FindNearestVisibleOpponent(
            runner,
            allAgents,
            rayMaxDistance,
            visibilityBlockingMask);
        if (visibleOpponent != null)
        {
            return Vector3.Distance(runner.transform.position, visibleOpponent.transform.position);
        }

        return 0f;
    }

    private void EvaluateWallLoopPenaltyForTeam<TAgent>(IReadOnlyList<TAgent> agents) where TAgent : BaseAgent
    {
        if (agents == null || agents.Count == 0)
        {
            return;
        }

        EnsureRewardEngine();
        for (int i = 0; i < agents.Count; i++)
        {
            TAgent agent = agents[i];
            if (agent == null || !agent.IsAlive)
            {
                continue;
            }

            string key = agent.AgentId;
            if (string.IsNullOrEmpty(key))
            {
                key = agent.GetInstanceID().ToString(CultureInfo.InvariantCulture);
            }

            Vector3 current = agent.transform.position;
            if (!wallLoopLastPositions.TryGetValue(key, out Vector3 previous))
            {
                wallLoopLastPositions[key] = current;
                continue;
            }

            float displacement = Vector3.Distance(current, previous);
            float wallProximity = GetNormalizedWallProximity(agent);
            if (wallProximity >= wallLoopMinWallProximity && displacement <= wallLoopLowDisplacementThreshold)
            {
                int repeatCount = wallLoopRepeatCounts.TryGetValue(key, out int currentRepeat) ? currentRepeat + 1 : 1;
                wallLoopRepeatCounts[key] = repeatCount;
                float scale = repeatCount >= 3 ? 1.5f : 1f;
                rewardEngine.ApplyWallLoopPenalty(
                    agent,
                    episodeStep,
                    elapsedSeconds,
                    $"wall_proximity={wallProximity:0.000};displacement={displacement:0.000};repeat={repeatCount}",
                    scale);
            }
            else
            {
                wallLoopRepeatCounts[key] = 0;
            }

            wallLoopLastPositions[key] = current;
        }
    }

    private void RefreshWallLoopPositionMemory()
    {
        wallLoopLastPositions.Clear();
        CacheWallLoopPositionsForTeam(sentinels);
        CacheWallLoopPositionsForTeam(runners);
    }

    private void ResetTrackingDistanceMemory()
    {
        sentinelLastTrackingDistance.Clear();
        sentinelLastTeammateDistance.Clear();
        sentinelNonProgressCounts.Clear();
        runnerLastThreatDistance.Clear();
        orbitStallPairCounts.Clear();
        orbitStallPairLastDistance.Clear();
        wallLoopRepeatCounts.Clear();
    }

    private void CacheWallLoopPositionsForTeam<TAgent>(IReadOnlyList<TAgent> agents) where TAgent : BaseAgent
    {
        if (agents == null)
        {
            return;
        }

        for (int i = 0; i < agents.Count; i++)
        {
            TAgent agent = agents[i];
            if (agent == null)
            {
                continue;
            }

            string key = agent.AgentId;
            if (string.IsNullOrEmpty(key))
            {
                key = agent.GetInstanceID().ToString(CultureInfo.InvariantCulture);
            }

            wallLoopLastPositions[key] = agent.transform.position;
        }
    }

    public int GetRayCount(BaseAgent agent)
    {
        if (agent == null)
        {
            return 0;
        }

        return agent.Team == AgentTeam.Sentinel ? sentinelRayCount : runnerRayCount;
    }

    public EnvironmentContextObservation GetEnvironmentContext(BaseAgent agent)
    {
        return new EnvironmentContextObservation
        {
            NormalizedTimeRemaining = GetNormalizedTimeRemaining(),
            NormalizedNearestExitDistance = GetNormalizedNearestExitDistance(agent, out Vector3 exitDirection),
            NormalizedNearestExitDirection = exitDirection,
            NormalizedWallProximity = GetNormalizedWallProximity(agent),
            NormalizedWallShiftTimer = GetNormalizedWallShiftTimer()
        };
    }

    public void GetAllAgentsForObservation(List<BaseAgent> agents)
    {
        agents.Clear();
        for (int i = 0; i < sentinels.Count; i++)
        {
            if (sentinels[i] != null)
            {
                agents.Add(sentinels[i]);
            }
        }

        for (int i = 0; i < runners.Count; i++)
        {
            if (runners[i] != null)
            {
                agents.Add(runners[i]);
            }
        }
    }

    public List<float> GetObservationVector(BaseAgent agent)
    {
        UpdateAgentMemory(agent);
        return ObservationAssembler.AssembleVector(agent, this);
    }

    public List<float> GetEntityObservationRows(BaseAgent agent)
    {
        return ObservationAssembler.AssembleEntityRows(agent, this);
    }

    private void UpdateAgentMemory(BaseAgent agent)
    {
        if (agent == null || !activeObservationConfig.UseMemory)
        {
            return;
        }

        List<BaseAgent> allAgents = new List<BaseAgent>();
        GetAllAgentsForObservation(allAgents);
        BaseAgent visibleOpponent = VisibilityTracker.FindNearestVisibleOpponent(
            agent,
            allAgents,
            rayMaxDistance,
            visibilityBlockingMask);

        if (visibleOpponent != null)
        {
            agent.TargetMemory.UpdateVisibleTarget(visibleOpponent);
        }
        else
        {
            agent.TargetMemory.MarkNoVisibleTarget(Time.deltaTime, Mathf.Max(1f, episodeDurationSeconds));
        }
    }

    private float GetNormalizedTimeRemaining()
    {
        if (episodeDurationSeconds <= 0f)
        {
            return 0f;
        }

        return Mathf.Clamp01((episodeDurationSeconds - elapsedSeconds) / episodeDurationSeconds);
    }

    private float GetNormalizedNearestExitDistance(BaseAgent agent, out Vector3 normalizedDirection)
    {
        normalizedDirection = Vector3.zero;
        if (agent == null || !exitWinEnabled)
        {
            return 1f;
        }

        float nearestDistance;
        Vector3 nearestOffset;
        if (!TryGetNearestExitInfo(agent, out nearestDistance, out nearestOffset))
        {
            return 1f;
        }

        normalizedDirection = nearestOffset / Mathf.Max(1f, observationPositionScale);
        return Mathf.Clamp01(nearestDistance / Mathf.Max(1f, observationPositionScale));
    }

    private bool TryGetNearestExitInfo(
        BaseAgent agent,
        out float nearestDistance,
        out Vector3 offsetToExit)
    {
        offsetToExit = Vector3.zero;
        nearestDistance = float.MaxValue;

        if (mazeGenerator == null)
        {
            mazeGenerator = FindFirstObjectByType<MazeGenerator>();
        }

        if (mazeGenerator != null
            && mazeGenerator.ExitPositions != null
            && mazeGenerator.ExitPositions.Count > 0)
        {
            IReadOnlyList<Vector3> exits = mazeGenerator.ExitPositions;
            for (int i = 0; i < exits.Count; i++)
            {
                Vector3 offset = (Vector3)exits[i] - agent.transform.position;
                float distance = offset.magnitude;
                if (distance < nearestDistance)
                {
                    nearestDistance = distance;
                    offsetToExit = offset;
                }
            }

            if (nearestDistance < float.MaxValue)
            {
                return true;
            }
        }

        GameObject[] taggedExits;
        try
        {
            taggedExits = GameObject.FindGameObjectsWithTag(exitTag);
        }
        catch (UnityException)
        {
            return false;
        }

        if (taggedExits == null || taggedExits.Length == 0)
        {
            return false;
        }

        for (int i = 0; i < taggedExits.Length; i++)
        {
            if (taggedExits[i] == null)
            {
                continue;
            }

            Vector3 o = taggedExits[i].transform.position - agent.transform.position;
            float d = o.magnitude;
            if (d < nearestDistance)
            {
                nearestDistance = d;
                offsetToExit = o;
            }
        }

        return nearestDistance < float.MaxValue;
    }

    private float GetNormalizedWallProximity(BaseAgent agent)
    {
        if (agent == null)
        {
            return 0f;
        }

        Bounds b = GetConfinementBounds();
        Vector3 position = agent.transform.position;
        float distanceToXEdge = b.extents.x - Mathf.Abs(position.x - b.center.x);
        float distanceToZEdge = b.extents.z - Mathf.Abs(position.z - b.center.z);
        float nearestBoundaryDistance = Mathf.Max(0f, Mathf.Min(distanceToXEdge, distanceToZEdge));
        float normalizedDistance = Mathf.Clamp01(nearestBoundaryDistance / Mathf.Max(1f, rayMaxDistance));
        return 1f - normalizedDistance;
    }

    private float GetNormalizedWallShiftTimer()
    {
        if (wallShiftIntervalSeconds <= 0f)
        {
            return dynamicWallController != null && dynamicWallController.ShiftIntervalSeconds > 0f
                ? Mathf.Clamp01(dynamicWallController.TimeUntilNextShift / dynamicWallController.ShiftIntervalSeconds)
                : 1f;
        }

        float timeSinceLastShift = elapsedSeconds % wallShiftIntervalSeconds;
        return Mathf.Clamp01((wallShiftIntervalSeconds - timeSinceLastShift) / wallShiftIntervalSeconds);
    }

    private void DetectCaptures()
    {
        if (!AreTerminalChecksArmed())
        {
            return;
        }

        for (int i = 0; i < sentinels.Count; i++)
        {
            SentinelAgent sentinel = sentinels[i];
            if (sentinel == null || !sentinel.IsAlive)
            {
                continue;
            }

            for (int j = 0; j < runners.Count; j++)
            {
                RunnerAgent runner = runners[j];
                if (runner == null || !runner.IsAlive || runner.IsCaptured)
                {
                    continue;
                }

                float distance;
                if (!sentinel.TryCaptureRunner(runner, out distance))
                {
                    continue;
                }

                sentinel.OnRunnerCaptured(runner);
                EnsureRewardEngine();
                rewardEngine.ApplyCapture(sentinel, runner, episodeStep, elapsedSeconds);

                if (episodeStateTracker != null)
                {
                    episodeStateTracker.RecordCapture(episodeStep, elapsedSeconds, sentinel, runner, 0f);
                }

                if (enableEpisodeLogging && episodeLogger != null)
                {
                    episodeLogger.RecordCapture();
                }

                if (enableReplayExport && replayEventExporter != null)
                {
                    replayEventExporter.RecordCapture(episodeStep, elapsedSeconds, sentinel, runner, distance);
                }

                if (logEpisodeEvents)
                {
                    Debug.Log(
                        $"{sentinel.AgentId} captured {runner.AgentId} at {elapsedSeconds:0.00}s distance={distance:0.00}.",
                        this);
                }
            }
        }
    }

    private void EvaluateTrapRewards()
    {
        if (rewardEngine == null)
        {
            return;
        }

        rewardEngine.EvaluateTrapRewards(sentinels, runners, GetExitPositionsForRewards(), episodeStep, elapsedSeconds);
    }

    private void DetectExitSuccess()
    {
        if (!AreTerminalChecksArmed())
        {
            return;
        }

        if (!exitWinEnabled || mazeGenerator == null)
        {
            return;
        }

        IReadOnlyList<Vector3> exitPositions = mazeGenerator.ExitPositions;
        if (exitPositions == null || exitPositions.Count == 0)
        {
            return;
        }

        for (int i = 0; i < runners.Count; i++)
        {
            RunnerAgent runner = runners[i];
            if (runner == null || !runner.IsAlive || runner.IsCaptured || runner.HasEscaped)
            {
                continue;
            }

            for (int j = 0; j < exitPositions.Count; j++)
            {
                Vector3 runnerPosition = runner.transform.position;
                Vector3 exitPosition = exitPositions[j];
                runnerPosition.y = 0f;
                exitPosition.y = 0f;
                if (Vector3.Distance(runnerPosition, exitPosition) <= exitReachRadius)
                {
                    NotifyRunnerReachedExit(runner);
                    return;
                }
            }
        }
    }

    private void EnforceMinimumStartSeparation()
    {
        float captureSafeSeparation = activeRuleConfig.CaptureRadius > 0f
            ? activeRuleConfig.CaptureRadius * 1.8f
            : 0f;
        float requiredSeparation = Mathf.Max(1.75f, Mathf.Max(minimumStartTeamSeparation, captureSafeSeparation));
        if (mazeGenerator == null)
        {
            mazeGenerator = FindFirstObjectByType<MazeGenerator>();
        }

        IReadOnlyList<Vector3> runnerCandidates = mazeGenerator != null ? mazeGenerator.RunnerSpawns : null;
        for (int i = 0; i < runners.Count; i++)
        {
            RunnerAgent runner = runners[i];
            if (runner == null || !runner.IsAlive)
            {
                continue;
            }

            if (DistanceToNearestSentinel(runner.transform.position) >= requiredSeparation)
            {
                continue;
            }

            Vector3 fallback = runner.transform.position;
            bool found = TryFindBestRunnerCandidate(runnerCandidates, requiredSeparation, out Vector3 bestCandidate);
            Vector3 target = found ? bestCandidate : FindFarthestPointInArenaFromSentinels(fallback);
            target = ConstrainAgentPositionToArena(target, 0.05f);
            target.y = runner.transform.position.y;
            runner.transform.position = target;
            runner.SetSpawnPose(target, runner.transform.rotation);
        }

        ResolveInitialAgentOverlaps(requiredSeparation * 0.45f);
    }

    private void ResolveInitialAgentOverlaps(float minSeparation)
    {
        float required = Mathf.Max(0.8f, minSeparation);
        for (int iter = 0; iter < 4; iter++)
        {
            bool moved = false;
            for (int s = 0; s < sentinels.Count; s++)
            {
                SentinelAgent sentinel = sentinels[s];
                if (sentinel == null || !sentinel.IsAlive)
                {
                    continue;
                }

                for (int r = 0; r < runners.Count; r++)
                {
                    RunnerAgent runner = runners[r];
                    if (runner == null || !runner.IsAlive)
                    {
                        continue;
                    }

                    Vector3 delta = runner.transform.position - sentinel.transform.position;
                    delta.y = 0f;
                    float d = delta.magnitude;
                    if (d >= required)
                    {
                        continue;
                    }

                    Vector3 dir = d > 1e-4f ? delta / d : Vector3.right;
                    float push = (required - d) + 0.05f;
                    Vector3 runnerTarget = ConstrainAgentPositionToArena(runner.transform.position + dir * push, 0.05f);
                    runnerTarget.y = runner.transform.position.y;
                    runner.transform.position = runnerTarget;
                    runner.SetSpawnPose(runnerTarget, runner.transform.rotation);
                    moved = true;
                }
            }

            if (!moved)
            {
                break;
            }
        }
    }

    private bool TryFindBestRunnerCandidate(IReadOnlyList<Vector3> candidates, float requiredSeparation, out Vector3 best)
    {
        best = Vector3.zero;
        if (candidates == null || candidates.Count == 0)
        {
            return false;
        }

        float bestDistance = float.MinValue;
        for (int i = 0; i < candidates.Count; i++)
        {
            Vector3 candidate = candidates[i] + Vector3.up * 0.5f;
            candidate = ConstrainAgentPositionToArena(candidate, 0.05f);
            float nearest = DistanceToNearestSentinel(candidate);
            if (nearest > bestDistance)
            {
                bestDistance = nearest;
                best = candidate;
            }
        }

        return bestDistance >= requiredSeparation;
    }

    private Vector3 FindFarthestPointInArenaFromSentinels(Vector3 fallback)
    {
        Bounds bounds = GetConfinementBounds();
        Vector3[] candidates =
        {
            new Vector3(bounds.min.x, fallback.y, bounds.min.z),
            new Vector3(bounds.min.x, fallback.y, bounds.max.z),
            new Vector3(bounds.max.x, fallback.y, bounds.min.z),
            new Vector3(bounds.max.x, fallback.y, bounds.max.z),
            new Vector3(bounds.center.x, fallback.y, bounds.center.z)
        };

        Vector3 best = fallback;
        float bestDistance = DistanceToNearestSentinel(fallback);
        for (int i = 0; i < candidates.Length; i++)
        {
            float nearest = DistanceToNearestSentinel(candidates[i]);
            if (nearest > bestDistance)
            {
                bestDistance = nearest;
                best = candidates[i];
            }
        }

        return best;
    }

    private float DistanceToNearestSentinel(Vector3 point)
    {
        float nearest = float.MaxValue;
        for (int i = 0; i < sentinels.Count; i++)
        {
            SentinelAgent sentinel = sentinels[i];
            if (sentinel == null || !sentinel.IsAlive)
            {
                continue;
            }

            float d = Vector3.Distance(point, sentinel.transform.position);
            if (d < nearest)
            {
                nearest = d;
            }
        }

        return nearest < float.MaxValue ? nearest : 0f;
    }

    private void InitializeTerminalArmingMetrics()
    {
        lastPositionByAgent.Clear();
        travelDistanceByAgent.Clear();
        InitializeTravelMetricsForTeam(sentinels);
        InitializeTravelMetricsForTeam(runners);
    }

    private void InitializeTravelMetricsForTeam<TAgent>(IReadOnlyList<TAgent> agents) where TAgent : BaseAgent
    {
        if (agents == null)
        {
            return;
        }

        for (int i = 0; i < agents.Count; i++)
        {
            TAgent agent = agents[i];
            if (agent == null)
            {
                continue;
            }

            string key = GetAgentMetricKey(agent);
            lastPositionByAgent[key] = agent.transform.position;
            travelDistanceByAgent[key] = 0f;
        }
    }

    private void UpdateTravelDistanceMetrics()
    {
        UpdateTravelMetricsForTeam(sentinels);
        UpdateTravelMetricsForTeam(runners);
    }

    private void UpdateTravelMetricsForTeam<TAgent>(IReadOnlyList<TAgent> agents) where TAgent : BaseAgent
    {
        if (agents == null)
        {
            return;
        }

        for (int i = 0; i < agents.Count; i++)
        {
            TAgent agent = agents[i];
            if (agent == null || !agent.IsAlive)
            {
                continue;
            }

            string key = GetAgentMetricKey(agent);
            Vector3 current = agent.transform.position;
            if (lastPositionByAgent.TryGetValue(key, out Vector3 previous))
            {
                float delta = Vector3.Distance(current, previous);
                if (delta > 1e-4f)
                {
                    travelDistanceByAgent.TryGetValue(key, out float total);
                    travelDistanceByAgent[key] = total + delta;
                }
            }
            else
            {
                travelDistanceByAgent[key] = 0f;
            }

            lastPositionByAgent[key] = current;
        }
    }

    private bool AreTerminalChecksArmed()
    {
        float terminalGraceSeconds = Mathf.Max(2f, minSecondsBeforeTerminalChecks);
        if (elapsedSeconds < terminalGraceSeconds)
        {
            return false;
        }

        float sentinelTravel = TeamTravelDistance(sentinels);
        float runnerTravel = TeamTravelDistance(runners);
        float sentinelRequired = Mathf.Clamp(minSentinelTravelBeforeTerminalChecks, 0f, 1.5f);
        float runnerRequired = Mathf.Clamp(minRunnerTravelBeforeTerminalChecks, 0f, 1.5f);
        return sentinelTravel >= sentinelRequired
            && runnerTravel >= runnerRequired;
    }

    private float TeamTravelDistance<TAgent>(IReadOnlyList<TAgent> agents) where TAgent : BaseAgent
    {
        if (agents == null)
        {
            return 0f;
        }

        float total = 0f;
        for (int i = 0; i < agents.Count; i++)
        {
            TAgent agent = agents[i];
            if (agent == null)
            {
                continue;
            }

            string key = GetAgentMetricKey(agent);
            if (travelDistanceByAgent.TryGetValue(key, out float value))
            {
                total += value;
            }
        }

        return total;
    }

    private static string GetAgentMetricKey(BaseAgent agent)
    {
        if (agent == null)
        {
            return "null";
        }

        if (!string.IsNullOrEmpty(agent.AgentId))
        {
            return agent.AgentId;
        }

        return agent.GetInstanceID().ToString(CultureInfo.InvariantCulture);
    }

    private void ResetMazeCoverageMetrics()
    {
        sentinelVisitedCells.Clear();
        runnerVisitedCells.Clear();
        UpdateMazeCoverageMetrics();
    }

    private void UpdateMazeCoverageMetrics()
    {
        if (mazeGenerator == null || !mazeGenerator.Generated || !mazeGenerator.MazeWallsEnabled)
        {
            return;
        }

        UpdateTeamCoverage(sentinels, sentinelVisitedCells);
        UpdateTeamCoverage(runners, runnerVisitedCells);
    }

    private void UpdateTeamCoverage<TAgent>(IReadOnlyList<TAgent> agents, HashSet<int> visited)
        where TAgent : BaseAgent
    {
        if (agents == null || visited == null)
        {
            return;
        }

        for (int i = 0; i < agents.Count; i++)
        {
            TAgent agent = agents[i];
            if (agent == null || !agent.IsAlive)
            {
                continue;
            }

            int cellId = mazeGenerator.GetWalkableCellId(agent.transform.position);
            if (cellId >= 0)
            {
                bool isNewCell = visited.Add(cellId);
                if (isNewCell && rewardEngine != null)
                {
                    rewardEngine.ApplyExplorationVisit(
                        agent,
                        episodeStep,
                        elapsedSeconds,
                        $"cell={cellId};team={agent.Team}");
                }
            }
        }
    }

    private float GetTeamCoveragePercent(HashSet<int> visited)
    {
        if (mazeGenerator == null || mazeGenerator.WalkableCellCount <= 0 || visited == null)
        {
            return 0f;
        }

        return 100f * visited.Count / Mathf.Max(1, mazeGenerator.WalkableCellCount);
    }

    private void EvaluateTerminalConditions()
    {
        if (elapsedSeconds >= episodeDurationSeconds)
        {
            if (timeoutCountsAsRunnerWin)
            {
                EnsureRewardEngine();
                rewardEngine.ApplyRunnerTimeoutWin(runners, sentinels, episodeStep, elapsedSeconds);
                EndEpisode(EpisodeOutcome.RunnerWinTimeout);
            }
            else
            {
                EnsureRewardEngine();
                rewardEngine.ApplyTimeoutNoWinner(sentinels, episodeStep, elapsedSeconds);
                EndEpisode(EpisodeOutcome.TimeoutNoWinner);
            }

            return;
        }

        if (AllRunnersCaptured())
        {
            EnsureRewardEngine();
            rewardEngine.ApplySentinelFullCaptureWin(sentinels, runners, episodeStep, elapsedSeconds);
            EndEpisode(EpisodeOutcome.SentinelWinAllRunnersCaptured);
            return;
        }
    }

    private bool AllRunnersCaptured()
    {
        if (runners.Count == 0)
        {
            return false;
        }

        for (int i = 0; i < runners.Count; i++)
        {
            if (runners[i] != null && runners[i].IsAlive)
            {
                return false;
            }
        }

        return true;
    }

    private void OnDrawGizmos()
    {
        if (!debugDrawEnvironment)
        {
            return;
        }

        DrawArenaBoundsDebug();
        DrawExitDebug();
        DrawWallShiftDebug();
    }

    private void OnGUI()
    {
        if (!showRewardHud || !Application.isPlaying)
        {
            return;
        }

        EnsureRewardEngine();
        if (rewardEngine == null)
        {
            return;
        }

        if (rewardHudStyle == null)
        {
            rewardHudStyle = new GUIStyle(GUI.skin.box)
            {
                alignment = TextAnchor.UpperLeft,
                fontSize = 12,
                richText = true,
                wordWrap = true,
                padding = new RectOffset(10, 10, 8, 8)
            };
        }

        float sentinelTotal = rewardEngine.GetTeamTotal(sentinels);
        float runnerTotal = rewardEngine.GetTeamTotal(runners);
        float penaltyTotal = rewardEngine.GetCategoryTotal("penalty");
        float trapTotal = rewardEngine.GetCategoryTotal("trap");
        float captureTotal = rewardEngine.GetCategoryTotal("capture");
        float shapingTotal = rewardEngine.GetCategoryTotal("shaping");
        float terminalTotal = rewardEngine.GetCategoryTotal("terminal");
        float timeoutPenalty = rewardEngine.GetEventTotal(RewardEvent.TimeoutPenalty);
        float clusterPenalty = rewardEngine.GetEventTotal(RewardEvent.ClusterPenalty);
        float capturePenalty = rewardEngine.GetEventTotal(RewardEvent.CapturePenalty);
        float episodeLoss = rewardEngine.GetEventTotal(RewardEvent.EpisodeLoss);
        float sentinelCoverage = GetTeamCoveragePercent(sentinelVisitedCells);
        float runnerCoverage = GetTeamCoveragePercent(runnerVisitedCells);

        string hudText =
            "<b>Reward / Penalty HUD</b>\n" +
            $"Episode: {episodeId}  Step: {episodeStep}  Time: {elapsedSeconds:0.0}s\n" +
            $"Sentinel total: <color=#66B2FF>{sentinelTotal:0.000}</color>    " +
            $"Runner total: <color=#FF66CC>{runnerTotal:0.000}</color>\n" +
            $"Penalty: {penaltyTotal:0.000}  Capture: {captureTotal:0.000}  Trap: {trapTotal:0.000}\n" +
            $"Shaping: {shapingTotal:0.000}  Terminal: {terminalTotal:0.000}\n" +
            $"TimeoutPen: {timeoutPenalty:0.000}  ClusterPen: {clusterPenalty:0.000}  " +
            $"TagPen: {capturePenalty:0.000}  EpisodeLoss: {episodeLoss:0.000}\n" +
            $"Coverage S/R: {sentinelCoverage:0.0}% / {runnerCoverage:0.0}%";

        GUI.Box(new Rect(rewardHudPosition.x, rewardHudPosition.y, rewardHudSize.x, rewardHudSize.y), hudText, rewardHudStyle);
    }

    private void DrawArenaBoundsDebug()
    {
        Bounds arenaBounds = GetConfinementBounds();
        Vector3 center = arenaBounds.center;
        Vector3 fullSize = new Vector3(arenaBounds.size.x, 0.05f, arenaBounds.size.z);
        DebugDrawUtils.DrawWireCube(center, fullSize, debugArenaBoundsColor);

        float inset = Mathf.Max(0f, ArenaConfinementInset);
        float innerX = Mathf.Max(0f, (arenaBounds.size.x * 0.5f) - inset);
        float innerZ = Mathf.Max(0f, (arenaBounds.size.z * 0.5f) - inset);
        Vector3 innerSize = new Vector3(innerX * 2f, 0.05f, innerZ * 2f);
        DebugDrawUtils.DrawWireCube(center + Vector3.up * 0.02f, innerSize, debugArenaBoundsColor);

        if (debugDrawEnvironmentLabels)
        {
            DebugDrawUtils.DrawLabel(
                center + Vector3.up * 0.8f,
                $"arena bounds {(arenaBounds.size.x * 0.5f):0.##} x {(arenaBounds.size.z * 0.5f):0.##}\nconfinement inset {inset:0.##}",
                debugArenaBoundsColor);
        }
    }

    private void DrawExitDebug()
    {
        IReadOnlyList<Vector3> exitPositions = mazeGenerator != null ? mazeGenerator.ExitPositions : null;
        if (exitPositions != null && exitPositions.Count > 0)
        {
            for (int i = 0; i < exitPositions.Count; i++)
            {
                DrawExitMarker(exitPositions[i], i);
            }

            return;
        }

        GameObject[] exits;
        try
        {
            exits = GameObject.FindGameObjectsWithTag(exitTag);
        }
        catch (UnityException)
        {
            return;
        }

        for (int i = 0; i < exits.Length; i++)
        {
            if (exits[i] != null)
            {
                DrawExitMarker(exits[i].transform.position, i);
            }
        }
    }

    private void DrawExitMarker(Vector3 position, int index)
    {
        Vector3 center = position + Vector3.up * 0.08f;
        DebugDrawUtils.DrawWireCube(center, new Vector3(1.6f, 0.15f, 1.6f), debugExitColor);
        DebugDrawUtils.DrawWireSphere(position, 1f, debugExitColor);

        if (debugDrawEnvironmentLabels)
        {
            DebugDrawUtils.DrawLabel(position + Vector3.up * 0.8f, $"Exit {index + 1}", debugExitColor);
        }
    }

    private void DrawWallShiftDebug()
    {
        if (dynamicWallController == null)
        {
            return;
        }

        Vector3 labelPosition = transform.position + Vector3.up * 2.5f;
        string label = $"wall shift: {dynamicWallController.TimeUntilNextShift:0.0}s\nshifts: {dynamicWallController.ShiftCount}";
        DebugDrawUtils.DrawLabel(labelPosition, label, debugWallTimerColor);
    }

    private IReadOnlyList<Vector3> GetExitPositionsForRewards()
    {
        if (mazeGenerator == null || mazeGenerator.ExitPositions == null)
        {
            return new List<Vector3>();
        }

        return mazeGenerator.ExitPositions;
    }

    private bool ValidateResetIntegrity()
    {
        if (!verifyResetIntegrity)
        {
            return true;
        }

        bool valid = true;
        valid &= sentinels.Count == spawnManager.ExpectedSentinelCount;
        valid &= runners.Count == spawnManager.ExpectedRunnerCount;
        valid &= outcome == EpisodeOutcome.InProgress;
        valid &= episodeActive;
        valid &= episodeStep == 0;
        valid &= Mathf.Approximately(elapsedSeconds, 0f);

        for (int i = 0; i < sentinels.Count; i++)
        {
            SentinelAgent sentinel = sentinels[i];
            valid &= sentinel != null;
            if (sentinel != null)
            {
                valid &= sentinel.IsAlive;
                valid &= Mathf.Approximately(sentinel.CumulativeReward, 0f);
            }
        }

        for (int i = 0; i < runners.Count; i++)
        {
            RunnerAgent runner = runners[i];
            valid &= runner != null;
            if (runner != null)
            {
                valid &= runner.IsAlive;
                valid &= !runner.IsCaptured;
                valid &= !runner.HasEscaped;
                valid &= Mathf.Approximately(runner.CumulativeReward, 0f);
            }
        }

        if (!valid)
        {
            Debug.LogError("Episode reset integrity check failed.", this);
        }

        return valid;
    }

    private void EnsureRewardEngine()
    {
        if (rewardEngine == null)
        {
            rewardEngine = FindFirstObjectByType<RewardEngine>();
        }

        if (rewardEngine == null)
        {
            rewardEngine = gameObject.AddComponent<RewardEngine>();
        }
    }

    public void RecordWallShift(int changedWallCount, int shiftCount)
    {
        if (!episodeActive)
        {
            return;
        }

        if (enableEpisodeLogging && episodeLogger != null)
        {
            episodeLogger.RecordWallShift();
        }

        if (enableReplayExport && replayEventExporter != null)
        {
            replayEventExporter.RecordWallShift(episodeStep, elapsedSeconds, shiftCount, changedWallCount);
        }
    }

    private void EnsureLoggers()
    {
        if (enableStepLogging && stepLogger == null)
        {
            stepLogger = FindFirstObjectByType<StepLogger>();
        }

        if (enableStepLogging && stepLogger == null)
        {
            stepLogger = gameObject.AddComponent<StepLogger>();
        }

        if (enableEpisodeLogging && episodeLogger == null)
        {
            episodeLogger = FindFirstObjectByType<EpisodeLogger>();
        }

        if (enableEpisodeLogging && episodeLogger == null)
        {
            episodeLogger = gameObject.AddComponent<EpisodeLogger>();
        }

        if (enableReplayExport && replayEventExporter == null)
        {
            replayEventExporter = FindFirstObjectByType<ReplayEventExporter>();
        }

        if (enableReplayExport && replayEventExporter == null)
        {
            replayEventExporter = gameObject.AddComponent<ReplayEventExporter>();
        }

        if (coordinationKpiExporter == null)
        {
            coordinationKpiExporter = FindFirstObjectByType<CoordinationKPIExporter>();
        }

        if (coordinationKpiExporter == null)
        {
            coordinationKpiExporter = gameObject.AddComponent<CoordinationKPIExporter>();
        }
    }

    private void BeginLoggers()
    {
        BuildLoggingAgentList();

        if (enableStepLogging && stepLogger != null)
        {
            stepLogger.BeginEpisode(episodeId, loggingAgents);
        }

        if (enableEpisodeLogging && episodeLogger != null)
        {
            episodeLogger.BeginEpisode(episodeId);
        }

        if (enableReplayExport && replayEventExporter != null)
        {
            replayEventExporter.BeginEpisode(episodeId);
        }

        if (coordinationKpiExporter != null)
        {
            coordinationKpiExporter.BeginEpisode();
        }
    }

    private void RecordStepLogs(bool forceWrite = false)
    {
        if (!enableStepLogging || stepLogger == null)
        {
            return;
        }

        BuildLoggingAgentList();
        stepLogger.RecordStep(this, episodeStep, elapsedSeconds, loggingAgents, forceWrite);
    }

    private void BuildLoggingAgentList()
    {
        loggingAgents.Clear();
        for (int i = 0; i < sentinels.Count; i++)
        {
            if (sentinels[i] != null)
            {
                loggingAgents.Add(sentinels[i]);
            }
        }

        for (int i = 0; i < runners.Count; i++)
        {
            if (runners[i] != null)
            {
                loggingAgents.Add(runners[i]);
            }
        }
    }

    private void EndEpisode(EpisodeOutcome finalOutcome)
    {
        if (!episodeActive)
        {
            return;
        }

        outcome = finalOutcome;
        RecordStepLogs(true);
        episodeActive = false;
        if (rewardEngine != null)
        {
            rewardEngine.EndEpisode();
        }

        if (episodeStateTracker != null)
        {
            episodeStateTracker.EndEpisode(episodeId, outcome, elapsedSeconds, episodeStep);
        }

        if (enableEpisodeLogging && episodeLogger != null)
        {
            episodeLogger.EndEpisode(outcome, elapsedSeconds, episodeStep, this, rewardEngine, sentinels, runners);
        }

        if (enableReplayExport && replayEventExporter != null)
        {
            replayEventExporter.EndEpisode(episodeStep, elapsedSeconds, outcome);
        }

        if (coordinationKpiExporter != null)
        {
            int capturedRunners = 0;
            for (int i = 0; i < runners.Count; i++)
            {
                if (runners[i] != null && runners[i].IsCaptured)
                {
                    capturedRunners++;
                }
            }

            coordinationKpiExporter.RecordEpisode(
                episodeId,
                outcome,
                elapsedSeconds,
                episodeStep,
                capturedRunners,
                runners.Count,
                rewardEngine != null ? rewardEngine.LastTacticalMetrics : null);
        }

        if (logEpisodeEvents)
        {
            Debug.Log($"Episode {episodeId} ended: {outcome}.", this);
        }

        EndMlAgentsEpisodes();
    }

    private void EndMlAgentsEpisodes()
    {
        for (int i = 0; i < sentinels.Count; i++)
        {
            if (sentinels[i] != null)
            {
                sentinels[i].EndEpisode();
            }
        }

        for (int i = 0; i < runners.Count; i++)
        {
            if (runners[i] != null)
            {
                runners[i].EndEpisode();
            }
        }
    }
}
