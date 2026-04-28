using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;

public class StepLogger : MonoBehaviour
{
    private const string Header =
        "episode_id,step_id,time_seconds,agent_id,team,pos_x,pos_y,pos_z,vel_x,vel_y,vel_z,heading_x,heading_y,heading_z,alive,visible_target_id,visible_target_team,visible_target_distance,reward_delta,cumulative_reward";

    [SerializeField] private string logDirectoryName = "LabyrinthBreachLogs";
    [SerializeField] private bool writeLogs = true;
    [SerializeField] private int sampleEverySteps = 1;

    private readonly Dictionary<string, float> previousRewardByAgent = new Dictionary<string, float>();
    private readonly List<BaseAgent> allAgents = new List<BaseAgent>();
    private string stepLogPath;
    private int currentEpisodeId;

    public void BeginEpisode(int episodeId, IReadOnlyList<BaseAgent> agents)
    {
        currentEpisodeId = episodeId;
        previousRewardByAgent.Clear();
        EnsureLogFile();

        if (agents == null)
        {
            return;
        }

        for (int i = 0; i < agents.Count; i++)
        {
            BaseAgent agent = agents[i];
            if (agent != null)
            {
                previousRewardByAgent[agent.AgentId] = agent.CumulativeReward;
            }
        }
    }

    public void RecordStep(
        PursuitEvasionEnvController environmentController,
        int stepId,
        float timeSeconds,
        IReadOnlyList<BaseAgent> agents,
        bool forceWrite = false)
    {
        if (!writeLogs || environmentController == null || agents == null)
        {
            return;
        }

        int safeSampleRate = Mathf.Max(1, sampleEverySteps);
        if (!forceWrite && stepId % safeSampleRate != 0)
        {
            return;
        }

        EnsureLogFile();
        allAgents.Clear();
        environmentController.GetAllAgentsForObservation(allAgents);

        StringBuilder builder = new StringBuilder();
        for (int i = 0; i < agents.Count; i++)
        {
            BaseAgent agent = agents[i];
            if (agent == null)
            {
                continue;
            }

            BaseAgent visibleTarget = VisibilityTracker.FindNearestVisibleOpponent(
                agent,
                allAgents,
                environmentController.RayMaxDistance,
                environmentController.VisibilityBlockingMask);

            float previousReward = 0f;
            previousRewardByAgent.TryGetValue(agent.AgentId, out previousReward);
            float rewardDelta = agent.CumulativeReward - previousReward;
            previousRewardByAgent[agent.AgentId] = agent.CumulativeReward;

            Vector3 position = agent.transform.position;
            Vector3 velocity = agent.Velocity;
            Vector3 heading = agent.transform.forward;
            float visibleDistance = visibleTarget != null
                ? Vector3.Distance(position, visibleTarget.transform.position)
                : -1f;

            builder.AppendLine(string.Join(
                ",",
                currentEpisodeId.ToString(CultureInfo.InvariantCulture),
                stepId.ToString(CultureInfo.InvariantCulture),
                timeSeconds.ToString("0.000", CultureInfo.InvariantCulture),
                Csv(agent.AgentId),
                Csv(agent.Team.ToString()),
                position.x.ToString("0.000", CultureInfo.InvariantCulture),
                position.y.ToString("0.000", CultureInfo.InvariantCulture),
                position.z.ToString("0.000", CultureInfo.InvariantCulture),
                velocity.x.ToString("0.000", CultureInfo.InvariantCulture),
                velocity.y.ToString("0.000", CultureInfo.InvariantCulture),
                velocity.z.ToString("0.000", CultureInfo.InvariantCulture),
                heading.x.ToString("0.000", CultureInfo.InvariantCulture),
                heading.y.ToString("0.000", CultureInfo.InvariantCulture),
                heading.z.ToString("0.000", CultureInfo.InvariantCulture),
                agent.IsAlive ? "true" : "false",
                Csv(visibleTarget != null ? visibleTarget.AgentId : string.Empty),
                Csv(visibleTarget != null ? visibleTarget.Team.ToString() : string.Empty),
                visibleDistance.ToString("0.000", CultureInfo.InvariantCulture),
                rewardDelta.ToString("0.000000", CultureInfo.InvariantCulture),
                agent.CumulativeReward.ToString("0.000000", CultureInfo.InvariantCulture)));
        }

        if (builder.Length > 0)
        {
            File.AppendAllText(stepLogPath, builder.ToString());
        }
    }

    private void EnsureLogFile()
    {
        if (!writeLogs)
        {
            return;
        }

        string directory = RunLogPathResolver.ResolveLogDirectory(logDirectoryName);
        Directory.CreateDirectory(directory);
        stepLogPath = Path.Combine(directory, "agent_step_log.csv");
        if (!File.Exists(stepLogPath))
        {
            File.WriteAllText(stepLogPath, Header + "\n");
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
