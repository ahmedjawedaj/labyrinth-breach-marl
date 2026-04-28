using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;

public class RewardEngine : MonoBehaviour
{
    private const string AuditHeader = "episode_id,reward_id,category,event_name,total";

    [SerializeField] private string rewardConfigPath = "../configs/reward_configs/reward_shared_basic_v1.yaml";
    [SerializeField] private float trapEvaluationIntervalSeconds = 1f;
    [SerializeField] private float trapDetectionDistance = 4f;
    [SerializeField] private float exitDenialDistance = 2.25f;
    [SerializeField] private float exitPressureDistance = 8f;
    [SerializeField] private float clusterMinSeparation = 1.25f;
    [SerializeField] private float wallProbeDistance = 2f;
    [SerializeField] private LayerMask trapBlockingMask = ~0;
    [SerializeField] private string logDirectoryName = "LabyrinthBreachLogs";

    private readonly Dictionary<string, float> totalsByAgent = new Dictionary<string, float>();
    private readonly Dictionary<string, float> totalsByEvent = new Dictionary<string, float>();
    private readonly Dictionary<string, float> totalsByCategory = new Dictionary<string, float>();

    private EpisodeStateTracker episodeStateTracker;
    private RewardConfig activeConfig = RewardConfig.Default();
    private SentinelRewardPolicy sentinelPolicy;
    private RunnerRewardPolicy runnerPolicy;
    private int currentEpisodeId;
    private float nextTrapEvaluationTime;
    private string auditLogPath;

    public RewardConfig ActiveConfig => activeConfig;

    public void Configure(string configPath)
    {
        if (!string.IsNullOrWhiteSpace(configPath))
        {
            rewardConfigPath = configPath;
        }
    }

    public void BeginEpisode(int episodeId, EpisodeStateTracker tracker, bool logMessages)
    {
        currentEpisodeId = episodeId;
        episodeStateTracker = tracker;
        totalsByAgent.Clear();
        totalsByEvent.Clear();
        totalsByCategory.Clear();
        nextTrapEvaluationTime = trapEvaluationIntervalSeconds;

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
            out SentinelAgent exitGuard))
        {
            ApplyReward(
                exitGuard,
                null,
                RewardEvent.TrapExitDenial,
                sentinelPolicy.ExitDenialReward,
                stepId,
                elapsedSeconds,
                "exit_denial_pressure");
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
        if (!activeConfig.AuditLogRewardEvents)
        {
            return;
        }

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

        if (episodeStateTracker != null)
        {
            episodeStateTracker.RecordRewardEvent(stepId, elapsedSeconds, eventName, agent, target, amount, details);
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

        string directory = Path.Combine(Application.persistentDataPath, logDirectoryName);
        Directory.CreateDirectory(directory);
        auditLogPath = Path.Combine(directory, "reward_audit.csv");
        if (!File.Exists(auditLogPath))
        {
            File.WriteAllText(auditLogPath, AuditHeader + "\n");
        }
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
