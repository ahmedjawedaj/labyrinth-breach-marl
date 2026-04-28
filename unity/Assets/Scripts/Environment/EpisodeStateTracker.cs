using System.Globalization;
using System.IO;
using UnityEngine;

public class EpisodeStateTracker : MonoBehaviour
{
    private const string EventHeader =
        "episode_id,step_id,time_seconds,event_name,agent_id,team,target_agent_id,target_team,reward_amount,details";

    private const string SummaryHeader =
        "episode_id,outcome,duration_seconds,total_steps,capture_count,timeout_flag,sentinel_reward_total,runner_reward_total";

    [SerializeField] private string logDirectoryName = "LabyrinthBreachLogs";
    [SerializeField] private bool writeLogs = true;

    private string eventLogPath;
    private string summaryLogPath;
    private int currentEpisodeId;
    private int captureCount;
    private float sentinelRewardTotal;
    private float runnerRewardTotal;

    public int CurrentEpisodeId => currentEpisodeId;

    public void BeginEpisode(int episodeId)
    {
        currentEpisodeId = episodeId;
        captureCount = 0;
        sentinelRewardTotal = 0f;
        runnerRewardTotal = 0f;

        EnsureLogFiles();
    }

    public void RecordCapture(
        int stepId,
        float timeSeconds,
        SentinelAgent sentinel,
        RunnerAgent runner,
        float rewardAmount)
    {
        captureCount++;
        RecordRewardEvent(
            stepId,
            timeSeconds,
            RewardEvent.CaptureEvent,
            sentinel,
            runner,
            0f,
            "runner_captured");
    }

    public void RecordRewardEvent(
        int stepId,
        float timeSeconds,
        string eventName,
        BaseAgent agent,
        BaseAgent target,
        float rewardAmount,
        string details)
    {
        if (agent != null)
        {
            if (agent.Team == AgentTeam.Sentinel)
            {
                sentinelRewardTotal += rewardAmount;
            }
            else if (agent.Team == AgentTeam.Runner)
            {
                runnerRewardTotal += rewardAmount;
            }
        }

        if (!writeLogs)
        {
            return;
        }

        EnsureLogFiles();
        string line = string.Join(
            ",",
            currentEpisodeId.ToString(CultureInfo.InvariantCulture),
            stepId.ToString(CultureInfo.InvariantCulture),
            timeSeconds.ToString("0.000", CultureInfo.InvariantCulture),
            Csv(eventName),
            Csv(agent != null ? agent.AgentId : string.Empty),
            Csv(agent != null ? agent.Team.ToString() : string.Empty),
            Csv(target != null ? target.AgentId : string.Empty),
            Csv(target != null ? target.Team.ToString() : string.Empty),
            rewardAmount.ToString("0.000000", CultureInfo.InvariantCulture),
            Csv(details));

        File.AppendAllText(eventLogPath, line + "\n");
    }

    public void EndEpisode(
        int episodeId,
        EpisodeOutcome outcome,
        float durationSeconds,
        int totalSteps)
    {
        if (!writeLogs)
        {
            return;
        }

        EnsureLogFiles();
        bool timeout = outcome == EpisodeOutcome.RunnerWinTimeout;
        string line = string.Join(
            ",",
            episodeId.ToString(CultureInfo.InvariantCulture),
            Csv(outcome.ToString()),
            durationSeconds.ToString("0.000", CultureInfo.InvariantCulture),
            totalSteps.ToString(CultureInfo.InvariantCulture),
            captureCount.ToString(CultureInfo.InvariantCulture),
            timeout ? "true" : "false",
            sentinelRewardTotal.ToString("0.000000", CultureInfo.InvariantCulture),
            runnerRewardTotal.ToString("0.000000", CultureInfo.InvariantCulture));

        File.AppendAllText(summaryLogPath, line + "\n");
    }

    private void EnsureLogFiles()
    {
        if (!writeLogs)
        {
            return;
        }

        string directory = RunLogPathResolver.ResolveLogDirectory(logDirectoryName);
        Directory.CreateDirectory(directory);

        eventLogPath = Path.Combine(directory, "open_arena_events.csv");
        summaryLogPath = Path.Combine(directory, "open_arena_episode_summary.csv");

        if (!File.Exists(eventLogPath))
        {
            File.WriteAllText(eventLogPath, EventHeader + "\n");
        }

        if (!File.Exists(summaryLogPath))
        {
            File.WriteAllText(summaryLogPath, SummaryHeader + "\n");
        }
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
