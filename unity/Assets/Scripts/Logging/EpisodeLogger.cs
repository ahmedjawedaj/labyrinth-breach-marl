using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;

public class EpisodeLogger : MonoBehaviour
{
    private const string Header =
        "episode_id,outcome,duration_seconds,total_steps,capture_count,exit_count,wall_shift_count,trap_event_count,rule_config_path,reward_config_path,reward_config_id,curriculum_stage_id,sentinel_reward_total,runner_reward_total,capture_reward_total,trap_reward_total,shaping_reward_total,penalty_reward_total,terminal_reward_total";

    [SerializeField] private string logDirectoryName = "LabyrinthBreachLogs";
    [SerializeField] private bool writeLogs = true;

    private string episodeLogPath;
    private int currentEpisodeId;
    private int captureCount;
    private int exitCount;
    private int wallShiftCount;

    public void BeginEpisode(int episodeId)
    {
        currentEpisodeId = episodeId;
        captureCount = 0;
        exitCount = 0;
        wallShiftCount = 0;
        EnsureLogFile();
    }

    public void RecordCapture()
    {
        captureCount++;
    }

    public void RecordExit()
    {
        exitCount++;
    }

    public void RecordWallShift()
    {
        wallShiftCount++;
    }

    public void EndEpisode(
        EpisodeOutcome outcome,
        float durationSeconds,
        int totalSteps,
        PursuitEvasionEnvController environmentController,
        RewardEngine rewardEngine,
        IReadOnlyList<SentinelAgent> sentinels,
        IReadOnlyList<RunnerAgent> runners)
    {
        if (!writeLogs)
        {
            return;
        }

        EnsureLogFile();
        string rewardConfigId = rewardEngine != null ? rewardEngine.ActiveConfig.RewardId : string.Empty;
        string line = string.Join(
            ",",
            currentEpisodeId.ToString(CultureInfo.InvariantCulture),
            Csv(outcome.ToString()),
            durationSeconds.ToString("0.000", CultureInfo.InvariantCulture),
            totalSteps.ToString(CultureInfo.InvariantCulture),
            captureCount.ToString(CultureInfo.InvariantCulture),
            exitCount.ToString(CultureInfo.InvariantCulture),
            wallShiftCount.ToString(CultureInfo.InvariantCulture),
            (rewardEngine != null ? rewardEngine.TrapEventCount : 0).ToString(CultureInfo.InvariantCulture),
            Csv(environmentController != null ? environmentController.RuleConfigPath : string.Empty),
            Csv(environmentController != null ? environmentController.RewardConfigPath : string.Empty),
            Csv(rewardConfigId),
            Csv(environmentController != null ? environmentController.ActiveCurriculumStageId : string.Empty),
            (rewardEngine != null ? rewardEngine.GetTeamTotal(sentinels) : 0f).ToString("0.000000", CultureInfo.InvariantCulture),
            (rewardEngine != null ? rewardEngine.GetTeamTotal(runners) : 0f).ToString("0.000000", CultureInfo.InvariantCulture),
            GetCategoryTotal(rewardEngine, "capture").ToString("0.000000", CultureInfo.InvariantCulture),
            GetCategoryTotal(rewardEngine, "trap").ToString("0.000000", CultureInfo.InvariantCulture),
            GetCategoryTotal(rewardEngine, "shaping").ToString("0.000000", CultureInfo.InvariantCulture),
            GetCategoryTotal(rewardEngine, "penalty").ToString("0.000000", CultureInfo.InvariantCulture),
            GetCategoryTotal(rewardEngine, "terminal").ToString("0.000000", CultureInfo.InvariantCulture));

        File.AppendAllText(episodeLogPath, line + "\n");
    }

    private static float GetCategoryTotal(RewardEngine rewardEngine, string category)
    {
        return rewardEngine != null ? rewardEngine.GetCategoryTotal(category) : 0f;
    }

    private void EnsureLogFile()
    {
        if (!writeLogs)
        {
            return;
        }

        string directory = RunLogPathResolver.ResolveLogDirectory(logDirectoryName);
        Directory.CreateDirectory(directory);
        episodeLogPath = Path.Combine(directory, "episode_log.csv");
        if (!File.Exists(episodeLogPath))
        {
            File.WriteAllText(episodeLogPath, Header + "\n");
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
