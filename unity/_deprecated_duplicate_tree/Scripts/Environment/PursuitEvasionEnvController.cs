using System.Collections.Generic;
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
    [SerializeField] private int curriculumStageIndex = -1;

    [Header("Observation Settings")]
    [SerializeField] private float observationPositionScale = 24f;
    [SerializeField] private float observationMaxSpeed = 6f;
    [SerializeField] private float rayMaxDistance = 12f;
    [SerializeField] private int sentinelRayCount = 14;
    [SerializeField] private int runnerRayCount = 16;
    [SerializeField] private LayerMask observationRaycastMask = ~0;
    [SerializeField] private LayerMask visibilityBlockingMask = ~0;
    [SerializeField] private Vector2 arenaHalfExtents = new Vector2(12f, 12f);
    [SerializeField] private string exitTag = "Exit";
    [SerializeField] private float wallShiftIntervalSeconds;

    [Header("Rewards")]
    [SerializeField] private RewardEngine rewardEngine;
    [SerializeField] private string rewardConfigPath = "../configs/reward_configs/reward_shared_basic_v1.yaml";
    [SerializeField] private float survivalRewardIntervalSeconds = 1f;

    [Header("Debug")]
    [SerializeField] private bool logEpisodeEvents = true;

    private readonly List<SentinelAgent> sentinels = new List<SentinelAgent>();
    private readonly List<RunnerAgent> runners = new List<RunnerAgent>();

    private float elapsedSeconds;
    private float nextSurvivalRewardTime;
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

        ApplySurvivalRewards();
        DetectCaptures();
        EvaluateTrapRewards();
        DetectExitSuccess();
        EvaluateTerminalConditions();
    }

    [ContextMenu("Begin Episode")]
    public void BeginEpisode()
    {
        episodeId++;
        episodeStep = 0;
        elapsedSeconds = 0f;
        nextSurvivalRewardTime = survivalRewardIntervalSeconds;
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
        rewardEngine.BeginEpisode(episodeId, episodeStateTracker, logEpisodeEvents);
        spawnManager.ResetSpawnedAgents();
        CacheAgents();
        ApplyAgentRuleOverrides();
        ResetAgents();
        resetIntegrityPassed = ValidateResetIntegrity();

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

        if (!exitWinEnabled)
        {
            return;
        }

        if (requireActiveRunnerForExit && !runner.IsAlive)
        {
            return;
        }

        runner.MarkEscaped();
        EnsureRewardEngine();
        rewardEngine.ApplyRunnerExitWin(runners, sentinels, episodeStep, elapsedSeconds);
        EndEpisode(EpisodeOutcome.RunnerWinExitReached);
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

        if (!CurriculumConfigLoader.TryLoad(
            curriculumConfigPath,
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
        int selectedStageIndex = curriculumStageIndex >= 0
            ? curriculumStageIndex
            : FindCurriculumStageIndexForActiveScene(loadedCurriculum);
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

        GameObject[] exits;
        try
        {
            exits = GameObject.FindGameObjectsWithTag(exitTag);
        }
        catch (UnityException)
        {
            return 1f;
        }
        if (exits == null || exits.Length == 0)
        {
            return 1f;
        }

        float nearestDistance = float.MaxValue;
        Vector3 nearestOffset = Vector3.zero;
        for (int i = 0; i < exits.Length; i++)
        {
            if (exits[i] == null)
            {
                continue;
            }

            Vector3 offset = exits[i].transform.position - agent.transform.position;
            float distance = offset.magnitude;
            if (distance < nearestDistance)
            {
                nearestDistance = distance;
                nearestOffset = offset;
            }
        }

        if (nearestDistance == float.MaxValue)
        {
            return 1f;
        }

        normalizedDirection = nearestOffset / Mathf.Max(1f, observationPositionScale);
        return Mathf.Clamp01(nearestDistance / Mathf.Max(1f, observationPositionScale));
    }

    private float GetNormalizedWallProximity(BaseAgent agent)
    {
        if (agent == null)
        {
            return 0f;
        }

        Vector3 position = agent.transform.position;
        float distanceToXEdge = arenaHalfExtents.x - Mathf.Abs(position.x);
        float distanceToZEdge = arenaHalfExtents.y - Mathf.Abs(position.z);
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
                if (Vector3.Distance(runnerPosition, exitPosition) <= 1f)
                {
                    NotifyRunnerReachedExit(runner);
                    return;
                }
            }
        }
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

    private void EndEpisode(EpisodeOutcome finalOutcome)
    {
        if (!episodeActive)
        {
            return;
        }

        outcome = finalOutcome;
        episodeActive = false;
        if (rewardEngine != null)
        {
            rewardEngine.EndEpisode();
        }

        if (episodeStateTracker != null)
        {
            episodeStateTracker.EndEpisode(episodeId, outcome, elapsedSeconds, episodeStep);
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
