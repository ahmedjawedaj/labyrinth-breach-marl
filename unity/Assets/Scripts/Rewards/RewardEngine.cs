using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text.RegularExpressions;
using UnityEngine;

public class RewardEngine : MonoBehaviour
{
    private const string AuditHeader = "episode_id,reward_id,category,event_name,total";
    private const string RewardBreakdownHeader =
        "episode_id,team,total_reward,terminal_reward,shaping_reward,trap_aware_reward,exploration_reward,penalties,reward_breakdown";

    [SerializeField] private string rewardConfigPath = "../configs/reward_configs/reward_shared_basic_v1.yaml";
    [SerializeField] private float trapEvaluationIntervalSeconds = 1f;
    [SerializeField] private float trapDetectionDistance = 4f;
    [SerializeField] private float exitDenialDistance = 2.25f;
    [SerializeField] private float exitPressureDistance = 8f;
    [SerializeField] private float clusterMinSeparation = 1.25f;
    [SerializeField] private float wallProbeDistance = 2f;
    [SerializeField] private float tacticalEventMinimumDurationSeconds = 0.8f;
    [SerializeField] private float chaseShapingDeadzone = 0.08f;
    [SerializeField] private float evadeShapingDeadzone = 0.08f;
    [SerializeField] private float shapingDeltaScale = 1.6f;
    [SerializeField] private LayerMask trapBlockingMask = ~0;
    [SerializeField] private string logDirectoryName = "LabyrinthBreachLogs";

    private readonly Dictionary<string, float> totalsByAgent = new Dictionary<string, float>();
    private readonly Dictionary<string, float> totalsByEvent = new Dictionary<string, float>();
    private readonly Dictionary<string, float> totalsByCategory = new Dictionary<string, float>();
    private readonly Dictionary<string, float> totalsByTeam = new Dictionary<string, float>();
    private readonly Dictionary<string, float> totalsByTeamCategory = new Dictionary<string, float>();
    private readonly Dictionary<string, float> totalsByTeamEvent = new Dictionary<string, float>();

    private EpisodeStateTracker episodeStateTracker;
    private ReplayEventExporter replayEventExporter;
    private RewardConfig activeConfig = RewardConfig.Default();
    private SentinelRewardPolicy sentinelPolicy;
    private RunnerRewardPolicy runnerPolicy;
    private int currentEpisodeId;
    private int trapEventCount;
    private int enclosureEventCount;
    private float nextTrapEvaluationTime;
    private string auditLogPath;
    private string rewardBreakdownLogPath;
    private string seedRewardBreakdownLogPath;
    private TrapEventDetector.TacticalEventTracker tacticalEventTracker;
    private TrapEventDetector.TacticalMetricsSnapshot lastTacticalMetrics = new TrapEventDetector.TacticalMetricsSnapshot();

    public RewardConfig ActiveConfig => activeConfig;
    public int TrapEventCount => trapEventCount;
    public TrapEventDetector.TacticalMetricsSnapshot LastTacticalMetrics => lastTacticalMetrics;

    public void Configure(string configPath)
    {
        if (!string.IsNullOrWhiteSpace(configPath))
        {
            rewardConfigPath = configPath;
        }
    }

    public void SetReplayEventExporter(ReplayEventExporter exporter)
    {
        replayEventExporter = exporter;
    }

    public void BeginEpisode(int episodeId, EpisodeStateTracker tracker, bool logMessages)
    {
        currentEpisodeId = episodeId;
        episodeStateTracker = tracker;
        totalsByAgent.Clear();
        totalsByEvent.Clear();
        totalsByCategory.Clear();
        totalsByTeam.Clear();
        totalsByTeamCategory.Clear();
        totalsByTeamEvent.Clear();
        trapEventCount = 0;
        enclosureEventCount = 0;
        nextTrapEvaluationTime = trapEvaluationIntervalSeconds;
        tacticalEventTracker = new TrapEventDetector.TacticalEventTracker(tacticalEventMinimumDurationSeconds);
        tacticalEventTracker.BeginEpisode();
        lastTacticalMetrics = new TrapEventDetector.TacticalMetricsSnapshot();

        activeConfig = RewardConfig.Default();
        if (RewardConfigLoader.TryLoad(rewardConfigPath, out RewardConfig loadedConfig, out string message))
        {
            activeConfig = loadedConfig;
            if (logMessages)
            {
                Debug.Log(message, this);
            }
        }
        else if (logMessages)
        {
            Debug.LogWarning(message, this);
        }

        sentinelPolicy = new SentinelRewardPolicy(activeConfig);
        runnerPolicy = new RunnerRewardPolicy(activeConfig);
        EnsureAuditFile();
        EnsureRewardBreakdownFiles();
    }

    public void ApplyCapture(SentinelAgent sentinel, RunnerAgent runner, int stepId, float elapsedSeconds)
    {
        ApplyReward(
            sentinel,
            runner,
            RewardEvent.CaptureReward,
            sentinelPolicy.CaptureReward,
            stepId,
            elapsedSeconds,
            "runner_captured");
        ApplyReward(
            runner,
            sentinel,
            RewardEvent.CapturePenalty,
            runnerPolicy.TaggedPenalty,
            stepId,
            elapsedSeconds,
            "runner_captured",
            true);
    }

    public void ApplyRunnerSurvival(RunnerAgent runner, int stepId, float elapsedSeconds)
    {
        ApplyReward(
            runner,
            null,
            RewardEvent.SurvivalReward,
            runnerPolicy.SurvivalReward,
            stepId,
            elapsedSeconds,
            "runner_alive_interval");
    }

    public void ApplyWallLoopPenalty(BaseAgent agent, int stepId, float elapsedSeconds, string details, float scale = 1f)
    {
        if (agent == null)
        {
            return;
        }

        float penalty = 0f;
        if (agent is SentinelAgent)
        {
            penalty = sentinelPolicy.WallLoopPenalty;
        }
        else if (agent is RunnerAgent)
        {
            penalty = runnerPolicy.WallLoopPenalty;
        }

        ApplyReward(
            agent,
            null,
            RewardEvent.WallLoopPenalty,
            penalty * Mathf.Max(0f, scale),
            stepId,
            elapsedSeconds,
            details);
    }

    public void ApplyExplorationVisit(BaseAgent agent, int stepId, float elapsedSeconds, string details)
    {
        if (agent == null)
        {
            return;
        }

        float amount = 0f;
        if (agent is SentinelAgent)
        {
            amount = sentinelPolicy.ExplorationVisitBonus;
        }
        else if (agent is RunnerAgent)
        {
            amount = runnerPolicy.ExplorationVisitBonus;
        }

        ApplyReward(
            agent,
            null,
            RewardEvent.ExplorationBonus,
            amount,
            stepId,
            elapsedSeconds,
            details);
    }

    public void ApplyOrbitStallPenalty(BaseAgent agent, int stepId, float elapsedSeconds, string details)
    {
        if (agent == null)
        {
            return;
        }

        float amount = 0f;
        if (agent is SentinelAgent)
        {
            amount = sentinelPolicy.OrbitStallPenalty;
        }
        else if (agent is RunnerAgent)
        {
            amount = runnerPolicy.OrbitStallPenalty;
        }

        ApplyReward(
            agent,
            null,
            RewardEvent.OrbitStallPenalty,
            amount,
            stepId,
            elapsedSeconds,
            details);
    }

    public void ApplySentinelChaseDelta(
        SentinelAgent sentinel,
        float previousDistance,
        float currentDistance,
        int stepId,
        float elapsedSeconds)
    {
        if (sentinel == null || previousDistance <= 1e-4f || currentDistance <= 1e-4f)
        {
            return;
        }

        float delta = previousDistance - currentDistance;
        float deadzone = Mathf.Max(0.01f, chaseShapingDeadzone);
        float scaleDivisor = Mathf.Max(0.25f, shapingDeltaScale);
        if (delta > deadzone)
        {
            float scaled = Mathf.Clamp01(delta / scaleDivisor);
            ApplyReward(
                sentinel,
                null,
                RewardEvent.ChaseProgress,
                sentinelPolicy.ChaseProgressBonus * scaled,
                stepId,
                elapsedSeconds,
                $"chase_delta={delta:0.000}");
        }
        else if (delta < -deadzone)
        {
            float scaled = Mathf.Clamp01((-delta) / scaleDivisor);
            ApplyReward(
                sentinel,
                null,
                RewardEvent.ChaseRegression,
                sentinelPolicy.ChaseRegressionPenalty * scaled,
                stepId,
                elapsedSeconds,
                $"chase_delta={delta:0.000}");
        }
    }

    public void ApplyRunnerThreatDelta(
        RunnerAgent runner,
        float previousDistance,
        float currentDistance,
        int stepId,
        float elapsedSeconds)
    {
        if (runner == null || previousDistance <= 1e-4f || currentDistance <= 1e-4f)
        {
            return;
        }

        bool underThreatNow = currentDistance <= runnerPolicy.ThreatRadius;
        bool underThreatBefore = previousDistance <= runnerPolicy.ThreatRadius;
        if (!underThreatNow && !underThreatBefore)
        {
            return;
        }

        float delta = currentDistance - previousDistance;
        float deadzone = Mathf.Max(0.01f, evadeShapingDeadzone);
        float scaleDivisor = Mathf.Max(0.25f, shapingDeltaScale);
        if (delta > deadzone)
        {
            float scaled = Mathf.Clamp01(delta / scaleDivisor);
            ApplyReward(
                runner,
                null,
                RewardEvent.EvadeProgress,
                runnerPolicy.EvadeProgressBonus * scaled,
                stepId,
                elapsedSeconds,
                $"evade_delta={delta:0.000}");
        }
        else if (delta < -deadzone)
        {
            float scaled = Mathf.Clamp01((-delta) / scaleDivisor);
            ApplyReward(
                runner,
                null,
                RewardEvent.ThreatApproachPenalty,
                runnerPolicy.ThreatApproachPenalty * scaled,
                stepId,
                elapsedSeconds,
                $"evade_delta={delta:0.000}");
        }
    }

    public void ApplyRunnerExitWin(
        IReadOnlyList<RunnerAgent> runners,
        IReadOnlyList<SentinelAgent> sentinels,
        int stepId,
        float elapsedSeconds)
    {
        ApplyRunnerTeam(runners, RewardEvent.EpisodeWin, runnerPolicy.TeamExitSuccessReward, stepId, elapsedSeconds, "runner_exit_success");
        ApplySentinelTeam(
            sentinels,
            RewardEvent.EpisodeLoss,
            sentinelPolicy.TimeoutOrEscapePenalty,
            stepId,
            elapsedSeconds,
            "runner_exit_success",
            true);
    }

    public void ApplyRunnerTimeoutWin(
        IReadOnlyList<RunnerAgent> runners,
        IReadOnlyList<SentinelAgent> sentinels,
        int stepId,
        float elapsedSeconds)
    {
        ApplyRunnerTeam(runners, RewardEvent.EpisodeWin, runnerPolicy.TeamExitSuccessReward, stepId, elapsedSeconds, "timeout_survival");
        ApplySentinelTeam(
            sentinels,
            RewardEvent.TimeoutPenalty,
            sentinelPolicy.TimeoutOrEscapePenalty,
            stepId,
            elapsedSeconds,
            "timeout_survival",
            true);
    }

    public void ApplyTimeoutNoWinner(IReadOnlyList<SentinelAgent> sentinels, int stepId, float elapsedSeconds)
    {
        ApplySentinelTeam(
            sentinels,
            RewardEvent.TimeoutPenalty,
            sentinelPolicy.TimeoutOrEscapePenalty,
            stepId,
            elapsedSeconds,
            "timeout_no_survival_success",
            true);
    }

    public void ApplySentinelFullCaptureWin(
        IReadOnlyList<SentinelAgent> sentinels,
        IReadOnlyList<RunnerAgent> runners,
        int stepId,
        float elapsedSeconds)
    {
        ApplySentinelTeam(
            sentinels,
            RewardEvent.EpisodeWin,
            sentinelPolicy.TeamFullCaptureReward,
            stepId,
            elapsedSeconds,
            "all_runners_captured",
            true);
        ApplyRunnerTeam(
            runners,
            RewardEvent.EpisodeLoss,
            runnerPolicy.BothCapturedPenalty,
            stepId,
            elapsedSeconds,
            "all_runners_captured",
            true);
    }

    public void EvaluateTrapRewards(
        IReadOnlyList<SentinelAgent> sentinels,
        IReadOnlyList<RunnerAgent> runners,
        IReadOnlyList<Vector3> exitPositions,
        int stepId,
        float elapsedSeconds)
    {
        if (!activeConfig.TrapAwareEnabled || trapEvaluationIntervalSeconds <= 0f || elapsedSeconds < nextTrapEvaluationTime)
        {
            return;
        }

        nextTrapEvaluationTime += trapEvaluationIntervalSeconds;
        RunnerAgent nearestActiveRunner = FindNearestActiveRunnerToAnySentinel(sentinels, runners);
        tacticalEventTracker.BeginTick(elapsedSeconds);
        if (runners != null)
        {
            for (int i = 0; i < runners.Count; i++)
            {
                RunnerAgent runner = runners[i];
                if (runner == null || !runner.IsAlive || runner.IsCaptured)
                {
                    continue;
                }

                if (TrapEventDetector.TryFindPincer(
                    sentinels,
                    runner,
                    trapDetectionDistance,
                    out SentinelAgent trackedFirstPincer,
                    out SentinelAgent trackedSecondPincer))
                {
                    tacticalEventTracker.ObservePincer(TrapEventDetector.BuildPincerKey(runner, trackedFirstPincer, trackedSecondPincer));
                }

                if (TrapEventDetector.TryFindCorridorControl(
                    sentinels,
                    runner,
                    trapDetectionDistance,
                    wallProbeDistance,
                    trapBlockingMask,
                    out SentinelAgent trackedFirstCorridor,
                    out SentinelAgent trackedSecondCorridor))
                {
                    tacticalEventTracker.ObserveCorridorBlock(
                        TrapEventDetector.BuildCorridorControlKey(runner, trackedFirstCorridor, trackedSecondCorridor));
                }
            }
        }

        if (TrapEventDetector.TryFindExitDenial(
            sentinels,
            exitPositions,
            runners,
            exitDenialDistance,
            exitPressureDistance,
            out SentinelAgent trackedExitGuard,
            out int trackedExitIndex))
        {
            tacticalEventTracker.ObserveExitDenial(TrapEventDetector.BuildExitDenialKey(trackedExitGuard, trackedExitIndex));
        }
        tacticalEventTracker.EndTick();

        if (nearestActiveRunner != null
            && TrapEventDetector.TryFindPincer(
                sentinels,
                nearestActiveRunner,
                trapDetectionDistance,
                out SentinelAgent firstPincerSentinel,
                out SentinelAgent secondPincerSentinel))
        {
            ApplyReward(
                firstPincerSentinel,
                nearestActiveRunner,
                RewardEvent.TrapPincer,
                sentinelPolicy.PincerReward,
                stepId,
                elapsedSeconds,
                "pincer_formation");
            ApplyReward(
                secondPincerSentinel,
                nearestActiveRunner,
                RewardEvent.TrapPincer,
                sentinelPolicy.PincerReward,
                stepId,
                elapsedSeconds,
                "pincer_formation");
        }

        if (nearestActiveRunner != null
            && TrapEventDetector.TryFindEnclosure(
                sentinels,
                nearestActiveRunner,
                trapDetectionDistance,
                out SentinelAgent firstEnclosureSentinel,
                out SentinelAgent secondEnclosureSentinel,
                out SentinelAgent thirdEnclosureSentinel))
        {
            ApplyReward(
                firstEnclosureSentinel,
                nearestActiveRunner,
                RewardEvent.TrapEnclosure,
                sentinelPolicy.EnclosureReward,
                stepId,
                elapsedSeconds,
                "opposite_side_enclosure");
            ApplyReward(
                secondEnclosureSentinel,
                nearestActiveRunner,
                RewardEvent.TrapEnclosure,
                sentinelPolicy.EnclosureReward,
                stepId,
                elapsedSeconds,
                "opposite_side_enclosure");
            ApplyReward(
                thirdEnclosureSentinel,
                nearestActiveRunner,
                RewardEvent.TrapEnclosure,
                sentinelPolicy.EnclosureReward,
                stepId,
                elapsedSeconds,
                "opposite_side_enclosure");
            enclosureEventCount++;
        }

        if (nearestActiveRunner != null
            && TrapEventDetector.TryFindDeadEndForcing(
                sentinels,
                nearestActiveRunner,
                trapDetectionDistance,
                wallProbeDistance,
                trapBlockingMask,
                out SentinelAgent deadEndPressureSentinel))
        {
            ApplyReward(
                deadEndPressureSentinel,
                nearestActiveRunner,
                RewardEvent.TrapDeadEndForcing,
                sentinelPolicy.DeadEndForcingReward,
                stepId,
                elapsedSeconds,
                "dead_end_forcing");
        }

        if (nearestActiveRunner != null
            && TrapEventDetector.TryFindCorridorControl(
                sentinels,
                nearestActiveRunner,
                trapDetectionDistance,
                wallProbeDistance,
                trapBlockingMask,
                out SentinelAgent firstCorridorSentinel,
                out SentinelAgent secondCorridorSentinel))
        {
            ApplyReward(
                firstCorridorSentinel,
                nearestActiveRunner,
                RewardEvent.TrapCorridorControl,
                sentinelPolicy.CorridorControlReward,
                stepId,
                elapsedSeconds,
                "corridor_control");
            ApplyReward(
                secondCorridorSentinel,
                nearestActiveRunner,
                RewardEvent.TrapCorridorControl,
                sentinelPolicy.CorridorControlReward,
                stepId,
                elapsedSeconds,
                "corridor_control");
        }

        if (TrapEventDetector.TryFindExitDenial(
            sentinels,
            exitPositions,
            runners,
            exitDenialDistance,
            exitPressureDistance,
            out SentinelAgent exitGuard,
            out int deniedExitIndex))
        {
            ApplyReward(
                exitGuard,
                null,
                RewardEvent.TrapExitDenial,
                sentinelPolicy.ExitDenialReward,
                stepId,
                elapsedSeconds,
                $"exit_denial_pressure exit_index={deniedExitIndex}");
        }

        if (TrapEventDetector.TryFindClusterPenalty(
            sentinels,
            clusterMinSeparation,
            out SentinelAgent firstClusteredSentinel,
            out SentinelAgent secondClusteredSentinel))
        {
            ApplyReward(
                firstClusteredSentinel,
                secondClusteredSentinel,
                RewardEvent.ClusterPenalty,
                sentinelPolicy.ClusterPenalty,
                stepId,
                elapsedSeconds,
                "sentinel_cluster");
            ApplyReward(
                secondClusteredSentinel,
                firstClusteredSentinel,
                RewardEvent.ClusterPenalty,
                sentinelPolicy.ClusterPenalty,
                stepId,
                elapsedSeconds,
                "sentinel_cluster");
        }
    }

    public void EndEpisode()
    {
        if (activeConfig.AuditLogRewardEvents)
        {
            EnsureAuditFile();
            foreach (KeyValuePair<string, float> entry in totalsByCategory)
            {
                AppendAuditLine(entry.Key, "__category_total__", entry.Value);
            }

            foreach (KeyValuePair<string, float> entry in totalsByEvent)
            {
                AppendAuditLine(RewardEvent.CategoryFor(entry.Key), entry.Key, entry.Value);
            }
        }

        lastTacticalMetrics = tacticalEventTracker != null
            ? tacticalEventTracker.EndEpisodeAndSnapshot(enclosureEventCount, trapEventCount)
            : new TrapEventDetector.TacticalMetricsSnapshot();
        if (activeConfig.AuditLogRewardEvents)
        {
            AppendTacticalAuditSummary(lastTacticalMetrics);
        }
        AppendRewardBreakdownRows();
    }

    private void ApplySentinelTeam(
        IReadOnlyList<SentinelAgent> sentinels,
        string eventName,
        float amount,
        int stepId,
        float elapsedSeconds,
        string details,
        bool allowInactive = false)
    {
        if (sentinels == null)
        {
            return;
        }

        for (int i = 0; i < sentinels.Count; i++)
        {
            ApplyReward(sentinels[i], null, eventName, amount, stepId, elapsedSeconds, details, allowInactive);
        }
    }

    private void ApplyRunnerTeam(
        IReadOnlyList<RunnerAgent> runners,
        string eventName,
        float amount,
        int stepId,
        float elapsedSeconds,
        string details,
        bool allowInactive = false)
    {
        if (runners == null)
        {
            return;
        }

        for (int i = 0; i < runners.Count; i++)
        {
            ApplyReward(runners[i], null, eventName, amount, stepId, elapsedSeconds, details, allowInactive);
        }
    }

    private void ApplyReward(
        BaseAgent agent,
        BaseAgent target,
        string eventName,
        float amount,
        int stepId,
        float elapsedSeconds,
        string details,
        bool allowInactive = false)
    {
        if (agent == null || Mathf.Approximately(amount, 0f))
        {
            return;
        }

        if (!agent.IsAlive && !allowInactive && !RewardEvent.CanApplyToInactiveAgent(eventName))
        {
            return;
        }

        agent.ApplyReward(amount);
        AddTotal(totalsByAgent, agent.AgentId, amount);
        AddTotal(totalsByEvent, eventName, amount);
        AddTotal(totalsByCategory, RewardEvent.CategoryFor(eventName), amount);
        string team = agent.Team.ToString();
        AddTotal(totalsByTeam, team, amount);
        AddTotal(totalsByTeamCategory, $"{team}|{RewardEvent.CategoryFor(eventName)}", amount);
        AddTotal(totalsByTeamEvent, $"{team}|{eventName}", amount);

        if (episodeStateTracker != null)
        {
            episodeStateTracker.RecordRewardEvent(stepId, elapsedSeconds, eventName, agent, target, amount, details);
        }

        if (replayEventExporter != null)
        {
            replayEventExporter.RecordReward(stepId, elapsedSeconds, eventName, agent, target, amount, details);
        }

        if (RewardEvent.CategoryFor(eventName) == "trap")
        {
            trapEventCount++;
        }
    }

    private RunnerAgent FindNearestActiveRunnerToAnySentinel(
        IReadOnlyList<SentinelAgent> sentinels,
        IReadOnlyList<RunnerAgent> runners)
    {
        if (sentinels == null || runners == null)
        {
            return null;
        }

        RunnerAgent nearest = null;
        float nearestDistance = float.MaxValue;
        for (int i = 0; i < runners.Count; i++)
        {
            RunnerAgent runner = runners[i];
            if (runner == null || !runner.IsAlive || runner.IsCaptured)
            {
                continue;
            }

            for (int j = 0; j < sentinels.Count; j++)
            {
                SentinelAgent sentinel = sentinels[j];
                if (sentinel == null || !sentinel.IsAlive)
                {
                    continue;
                }

                float distance = Vector3.Distance(runner.transform.position, sentinel.transform.position);
                if (distance < nearestDistance)
                {
                    nearestDistance = distance;
                    nearest = runner;
                }
            }
        }

        return nearest;
    }

    private void EnsureAuditFile()
    {
        if (!activeConfig.AuditLogRewardEvents)
        {
            return;
        }

        string directory = RunLogPathResolver.ResolveLogDirectory(logDirectoryName);
        Directory.CreateDirectory(directory);
        auditLogPath = Path.Combine(directory, "reward_audit.csv");
        if (!File.Exists(auditLogPath))
        {
            File.WriteAllText(auditLogPath, AuditHeader + "\n");
        }
    }

    private void EnsureRewardBreakdownFiles()
    {
        string directory = RunLogPathResolver.ResolveLogDirectory(logDirectoryName);
        Directory.CreateDirectory(directory);
        rewardBreakdownLogPath = Path.Combine(directory, "reward_breakdown.csv");
        if (!File.Exists(rewardBreakdownLogPath))
        {
            File.WriteAllText(rewardBreakdownLogPath, RewardBreakdownHeader + "\n");
        }

        seedRewardBreakdownLogPath = ResolveSeedRewardBreakdownPath();
        if (!string.IsNullOrEmpty(seedRewardBreakdownLogPath))
        {
            string parent = Path.GetDirectoryName(seedRewardBreakdownLogPath);
            if (!string.IsNullOrEmpty(parent))
            {
                Directory.CreateDirectory(parent);
            }

            if (!File.Exists(seedRewardBreakdownLogPath))
            {
                File.WriteAllText(seedRewardBreakdownLogPath, RewardBreakdownHeader + "\n");
            }
        }
    }

    public float GetAgentTotal(string agentId)
    {
        if (string.IsNullOrEmpty(agentId))
        {
            return 0f;
        }

        return totalsByAgent.TryGetValue(agentId, out float total) ? total : 0f;
    }

    public float GetCategoryTotal(string category)
    {
        if (string.IsNullOrEmpty(category))
        {
            return 0f;
        }

        return totalsByCategory.TryGetValue(category, out float total) ? total : 0f;
    }

    public float GetEventTotal(string eventName)
    {
        if (string.IsNullOrEmpty(eventName))
        {
            return 0f;
        }

        return totalsByEvent.TryGetValue(eventName, out float total) ? total : 0f;
    }

    public float GetTeamTotal<TAgent>(IReadOnlyList<TAgent> agents)
        where TAgent : BaseAgent
    {
        if (agents == null)
        {
            return 0f;
        }

        float total = 0f;
        for (int i = 0; i < agents.Count; i++)
        {
            BaseAgent agent = agents[i];
            if (agent != null)
            {
                total += GetAgentTotal(agent.AgentId);
            }
        }

        return total;
    }

    private void AppendAuditLine(string category, string eventName, float total)
    {
        string line = string.Join(
            ",",
            currentEpisodeId.ToString(CultureInfo.InvariantCulture),
            Csv(activeConfig.RewardId),
            Csv(category),
            Csv(eventName),
            total.ToString("0.000000", CultureInfo.InvariantCulture));
        File.AppendAllText(auditLogPath, line + "\n");
    }

    private void AppendTacticalAuditSummary(TrapEventDetector.TacticalMetricsSnapshot metrics)
    {
        if (metrics == null)
        {
            return;
        }

        AppendAuditLine("coordination", "pincer_event_count", metrics.PincerCount);
        AppendAuditLine("coordination", "pincer_event_avg_duration_seconds", metrics.PincerAverageDurationSeconds);
        AppendAuditLine("coordination", "corridor_block_event_count", metrics.CorridorBlockCount);
        AppendAuditLine("coordination", "corridor_block_avg_duration_seconds", metrics.CorridorBlockAverageDurationSeconds);
        AppendAuditLine("coordination", "exit_denial_event_count", metrics.ExitDenialCount);
        AppendAuditLine("coordination", "exit_denial_avg_duration_seconds", metrics.ExitDenialAverageDurationSeconds);
        AppendAuditLine("coordination", "enclosure_event_count", metrics.EnclosureCount);
        AppendAuditLine("coordination", "trap_event_count", metrics.TrapEventCount);
    }

    private void AppendRewardBreakdownRows()
    {
        EnsureRewardBreakdownFiles();
        AppendRewardBreakdownForTeam("Sentinel");
        AppendRewardBreakdownForTeam("Runner");
    }

    private void AppendRewardBreakdownForTeam(string team)
    {
        float totalReward = GetFromMap(totalsByTeam, team);
        float terminalReward = GetFromMap(totalsByTeamCategory, $"{team}|terminal");
        float shapingReward = GetFromMap(totalsByTeamCategory, $"{team}|shaping");
        float trapAwareReward = GetFromMap(totalsByTeamCategory, $"{team}|trap");
        float penalties = GetFromMap(totalsByTeamCategory, $"{team}|penalty") + GetFromMap(totalsByTeamCategory, $"{team}|capture");
        float explorationReward = GetFromMap(totalsByTeamEvent, $"{team}|{RewardEvent.ExplorationBonus}");
        string breakdown = BuildTeamBreakdownJson(team);
        string line = string.Join(
            ",",
            currentEpisodeId.ToString(CultureInfo.InvariantCulture),
            Csv(team),
            totalReward.ToString("0.000000", CultureInfo.InvariantCulture),
            terminalReward.ToString("0.000000", CultureInfo.InvariantCulture),
            shapingReward.ToString("0.000000", CultureInfo.InvariantCulture),
            trapAwareReward.ToString("0.000000", CultureInfo.InvariantCulture),
            explorationReward.ToString("0.000000", CultureInfo.InvariantCulture),
            penalties.ToString("0.000000", CultureInfo.InvariantCulture),
            Csv(breakdown));
        File.AppendAllText(rewardBreakdownLogPath, line + "\n");
        if (!string.IsNullOrEmpty(seedRewardBreakdownLogPath))
        {
            File.AppendAllText(seedRewardBreakdownLogPath, line + "\n");
        }
    }

    private string BuildTeamBreakdownJson(string team)
    {
        string[] eventKeys = new string[]
        {
            RewardEvent.CaptureReward,
            RewardEvent.CapturePenalty,
            RewardEvent.SurvivalReward,
            RewardEvent.ExplorationBonus,
            RewardEvent.TimeoutPenalty,
            RewardEvent.EpisodeWin,
            RewardEvent.EpisodeLoss,
            RewardEvent.TrapPincer,
            RewardEvent.TrapEnclosure,
            RewardEvent.TrapDeadEndForcing,
            RewardEvent.TrapExitDenial,
            RewardEvent.TrapCorridorControl,
            RewardEvent.ChaseProgress,
            RewardEvent.ChaseRegression,
            RewardEvent.EvadeProgress,
            RewardEvent.ThreatApproachPenalty,
            RewardEvent.OrbitStallPenalty,
            RewardEvent.WallLoopPenalty,
            RewardEvent.ClusterPenalty,
        };

        List<string> parts = new List<string>(eventKeys.Length);
        for (int i = 0; i < eventKeys.Length; i++)
        {
            string eventName = eventKeys[i];
            float value = GetFromMap(totalsByTeamEvent, $"{team}|{eventName}");
            parts.Add($"\\\"{eventName}\\\":{value.ToString("0.000000", CultureInfo.InvariantCulture)}");
        }

        return "{" + string.Join(",", parts) + "}";
    }

    private string ResolveSeedRewardBreakdownPath()
    {
        if (!RunLogPathResolver.TryGetActiveRunContext(out ActiveRunContext context))
        {
            return string.Empty;
        }

        int seed = ParseSeedFromRunId(context.run_id);
        if (seed < 0 || string.IsNullOrWhiteSpace(context.results_dir))
        {
            return string.Empty;
        }

        return Path.Combine(context.results_dir, $"seed_{seed}", "logs", "reward_breakdown.csv");
    }

    private static int ParseSeedFromRunId(string runId)
    {
        if (string.IsNullOrEmpty(runId))
        {
            return -1;
        }

        Match match = Regex.Match(runId, @"seed(?<seed>\d+)");
        if (!match.Success)
        {
            return -1;
        }

        return int.TryParse(match.Groups["seed"].Value, NumberStyles.Integer, CultureInfo.InvariantCulture, out int seed)
            ? seed
            : -1;
    }

    private static float GetFromMap(Dictionary<string, float> totals, string key)
    {
        return totals.TryGetValue(key, out float value) ? value : 0f;
    }

    private static void AddTotal(Dictionary<string, float> totals, string key, float amount)
    {
        if (string.IsNullOrEmpty(key))
        {
            key = "unknown";
        }

        totals.TryGetValue(key, out float current);
        totals[key] = current + amount;
    }

    private static string Csv(string value)
    {
        if (value == null)
        {
            value = string.Empty;
        }

        return "\"" + value.Replace("\"", "\"\"") + "\"";
    }
}
