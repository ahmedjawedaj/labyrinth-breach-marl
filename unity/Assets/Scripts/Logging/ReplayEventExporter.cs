using System.Globalization;
using System.IO;
using UnityEngine;

public class ReplayEventExporter : MonoBehaviour
{
    private const string Header =
        "episode_id,step_id,time_seconds,event_type,event_name,actor_id,actor_team,target_id,target_team,x,y,z,value,details";

    [SerializeField] private string logDirectoryName = "LabyrinthBreachLogs";
    [SerializeField] private bool writeLogs = true;

    private string replayLogPath;
    private int currentEpisodeId;

    public void BeginEpisode(int episodeId)
    {
        currentEpisodeId = episodeId;
        EnsureLogFile();
        RecordRaw(0, 0f, "episode", "episode_start", null, null, Vector3.zero, 0f, string.Empty);
    }

    public void RecordReward(
        int stepId,
        float timeSeconds,
        string eventName,
        BaseAgent agent,
        BaseAgent target,
        float rewardAmount,
        string details)
    {
        RecordRaw(stepId, timeSeconds, "reward", eventName, agent, target, PositionOrZero(agent), rewardAmount, details);
    }

    public void RecordCapture(
        int stepId,
        float timeSeconds,
        SentinelAgent sentinel,
        RunnerAgent runner,
        float distance)
    {
        RecordRaw(stepId, timeSeconds, "capture", RewardEvent.CaptureEvent, sentinel, runner, PositionOrZero(runner), distance, "runner_captured");
    }

    public void RecordExit(int stepId, float timeSeconds, RunnerAgent runner)
    {
        RecordRaw(stepId, timeSeconds, "exit", "runner_exit_reached", runner, null, PositionOrZero(runner), 0f, "runner_exit_success");
    }

    public void RecordWallShift(int stepId, float timeSeconds, int shiftCount, int changedWallCount)
    {
        RecordRaw(
            stepId,
            timeSeconds,
            "wall_shift",
            "dynamic_wall_shift",
            null,
            null,
            Vector3.zero,
            changedWallCount,
            $"shift_count={shiftCount}");
    }

    public void EndEpisode(int stepId, float timeSeconds, EpisodeOutcome outcome)
    {
        RecordRaw(stepId, timeSeconds, "episode", "episode_end", null, null, Vector3.zero, 0f, outcome.ToString());
    }

    private void RecordRaw(
        int stepId,
        float timeSeconds,
        string eventType,
        string eventName,
        BaseAgent actor,
        BaseAgent target,
        Vector3 position,
        float value,
        string details)
    {
        if (!writeLogs)
        {
            return;
        }

        EnsureLogFile();
        string line = string.Join(
            ",",
            currentEpisodeId.ToString(CultureInfo.InvariantCulture),
            stepId.ToString(CultureInfo.InvariantCulture),
            timeSeconds.ToString("0.000", CultureInfo.InvariantCulture),
            Csv(eventType),
            Csv(eventName),
            Csv(actor != null ? actor.AgentId : string.Empty),
            Csv(actor != null ? actor.Team.ToString() : string.Empty),
            Csv(target != null ? target.AgentId : string.Empty),
            Csv(target != null ? target.Team.ToString() : string.Empty),
            position.x.ToString("0.000", CultureInfo.InvariantCulture),
            position.y.ToString("0.000", CultureInfo.InvariantCulture),
            position.z.ToString("0.000", CultureInfo.InvariantCulture),
            value.ToString("0.000000", CultureInfo.InvariantCulture),
            Csv(details));

        File.AppendAllText(replayLogPath, line + "\n");
    }

    private static Vector3 PositionOrZero(BaseAgent agent)
    {
        return agent != null ? agent.transform.position : Vector3.zero;
    }

    private void EnsureLogFile()
    {
        if (!writeLogs)
        {
            return;
        }

        string directory = RunLogPathResolver.ResolveLogDirectory(logDirectoryName);
        Directory.CreateDirectory(directory);
        replayLogPath = Path.Combine(directory, "replay_events.csv");
        if (!File.Exists(replayLogPath))
        {
            File.WriteAllText(replayLogPath, Header + "\n");
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
