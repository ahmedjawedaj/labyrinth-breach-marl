using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;

public struct RewardConfig
{
    public string RewardId;
    public float SentinelTeamFullCapture;
    public float SentinelTimeoutOrEscapePenalty;
    public float SentinelIndividualCaptureBonus;
    public float SentinelEncirclementBonus;
    public float SentinelClusterPenalty;
    public float SentinelExitGuardShaping;
    public float SentinelStepPenalty;
    public float SentinelWallLoopPenalty;
    public float SentinelChaseProgressBonus;
    public float SentinelChaseRegressionPenalty;
    public float SentinelExplorationVisitBonus;
    public float SentinelOrbitStallPenalty;
    public float RunnerTeamExitSuccess;
    public float RunnerBothCapturedPenalty;
    public float RunnerTaggedPenalty;
    public float RunnerSurvivalStepBonus;
    public float RunnerExplorationBonus;
    public float RunnerTeamSeparationShaping;
    public float RunnerWallLoopPenalty;
    public float RunnerEvadeProgressBonus;
    public float RunnerThreatApproachPenalty;
    public float RunnerThreatRadius;
    public float RunnerExplorationVisitBonus;
    public float RunnerOrbitStallPenalty;
    public bool TrapAwareEnabled;
    public float TrapPincerFormationBonus;
    public float TrapOppositeSideEnclosureBonus;
    public float TrapDeadEndForcingBonus;
    public float TrapExitDenialPressureBonus;
    public float TrapCorridorControlBonus;
    public bool AuditLogRewardEvents;

    public static RewardConfig Default()
    {
        return new RewardConfig
        {
            RewardId = "reward_shared_basic_v1",
            SentinelTeamFullCapture = 1f,
            SentinelTimeoutOrEscapePenalty = -1f,
            SentinelIndividualCaptureBonus = 0.1f,
            SentinelEncirclementBonus = 0f,
            SentinelClusterPenalty = 0f,
            SentinelExitGuardShaping = 0f,
            SentinelStepPenalty = 0f,
            SentinelWallLoopPenalty = -0.002f,
            SentinelChaseProgressBonus = 0.003f,
            SentinelChaseRegressionPenalty = -0.0025f,
            SentinelExplorationVisitBonus = 0.0008f,
            SentinelOrbitStallPenalty = -0.0025f,
            RunnerTeamExitSuccess = 1f,
            RunnerBothCapturedPenalty = -1f,
            RunnerTaggedPenalty = -0.2f,
            RunnerSurvivalStepBonus = 0.0005f,
            RunnerExplorationBonus = 0f,
            RunnerTeamSeparationShaping = 0f,
            RunnerWallLoopPenalty = -0.0015f,
            RunnerEvadeProgressBonus = 0.0025f,
            RunnerThreatApproachPenalty = -0.0035f,
            RunnerThreatRadius = 5f,
            RunnerExplorationVisitBonus = 0.0012f,
            RunnerOrbitStallPenalty = -0.003f,
            TrapAwareEnabled = false,
            TrapPincerFormationBonus = 0f,
            TrapOppositeSideEnclosureBonus = 0f,
            TrapDeadEndForcingBonus = 0f,
            TrapExitDenialPressureBonus = 0f,
            TrapCorridorControlBonus = 0f,
            AuditLogRewardEvents = true
        };
    }
}

public static class RewardConfigLoader
{
    public static bool TryLoad(string configPath, out RewardConfig config, out string message)
    {
        config = RewardConfig.Default();
        message = string.Empty;

        string resolvedPath = ResolvePath(configPath);
        if (string.IsNullOrEmpty(resolvedPath) || !File.Exists(resolvedPath))
        {
            message = $"Reward config not found: {configPath}";
            return false;
        }

        Dictionary<string, string> values = ParseYamlLikeFile(resolvedPath);
        config.RewardId = GetString(values, "reward_id", config.RewardId);
        config.SentinelTeamFullCapture = GetFloat(values, "sentinel.team_full_capture", config.SentinelTeamFullCapture);
        config.SentinelTimeoutOrEscapePenalty = GetFloat(
            values,
            "sentinel.timeout_or_escape_penalty",
            config.SentinelTimeoutOrEscapePenalty);
        config.SentinelIndividualCaptureBonus = GetFloat(
            values,
            "sentinel.individual_capture_bonus",
            config.SentinelIndividualCaptureBonus);
        config.SentinelEncirclementBonus = GetFloat(
            values,
            "sentinel.encirclement_bonus",
            config.SentinelEncirclementBonus);
        config.SentinelClusterPenalty = GetFloat(values, "sentinel.cluster_penalty", config.SentinelClusterPenalty);
        config.SentinelExitGuardShaping = GetFloat(
            values,
            "sentinel.exit_guard_shaping",
            config.SentinelExitGuardShaping);
        config.SentinelStepPenalty = GetFloat(values, "sentinel.step_penalty", config.SentinelStepPenalty);
        config.SentinelWallLoopPenalty = GetFloat(
            values,
            "sentinel.wall_loop_penalty",
            config.SentinelWallLoopPenalty);
        config.SentinelChaseProgressBonus = GetFloat(
            values,
            "sentinel.chase_progress_bonus",
            config.SentinelChaseProgressBonus);
        config.SentinelChaseRegressionPenalty = GetFloat(
            values,
            "sentinel.chase_regression_penalty",
            config.SentinelChaseRegressionPenalty);
        config.SentinelExplorationVisitBonus = GetFloat(
            values,
            "sentinel.exploration_visit_bonus",
            config.SentinelExplorationVisitBonus);
        config.SentinelOrbitStallPenalty = GetFloat(
            values,
            "sentinel.orbit_stall_penalty",
            config.SentinelOrbitStallPenalty);
        config.RunnerTeamExitSuccess = GetFloat(values, "runner.team_exit_success", config.RunnerTeamExitSuccess);
        config.RunnerBothCapturedPenalty = GetFloat(
            values,
            "runner.both_captured_penalty",
            config.RunnerBothCapturedPenalty);
        config.RunnerTaggedPenalty = GetFloat(values, "runner.tagged_penalty", config.RunnerTaggedPenalty);
        config.RunnerSurvivalStepBonus = GetFloat(
            values,
            "runner.survival_step_bonus",
            config.RunnerSurvivalStepBonus);
        config.RunnerExplorationBonus = GetFloat(values, "runner.exploration_bonus", config.RunnerExplorationBonus);
        config.RunnerTeamSeparationShaping = GetFloat(
            values,
            "runner.team_separation_shaping",
            config.RunnerTeamSeparationShaping);
        config.RunnerWallLoopPenalty = GetFloat(
            values,
            "runner.wall_loop_penalty",
            config.RunnerWallLoopPenalty);
        config.RunnerEvadeProgressBonus = GetFloat(
            values,
            "runner.evade_progress_bonus",
            config.RunnerEvadeProgressBonus);
        config.RunnerThreatApproachPenalty = GetFloat(
            values,
            "runner.threat_approach_penalty",
            config.RunnerThreatApproachPenalty);
        config.RunnerThreatRadius = GetFloat(
            values,
            "runner.threat_radius",
            config.RunnerThreatRadius);
        config.RunnerExplorationVisitBonus = GetFloat(
            values,
            "runner.exploration_visit_bonus",
            config.RunnerExplorationVisitBonus);
        config.RunnerOrbitStallPenalty = GetFloat(
            values,
            "runner.orbit_stall_penalty",
            config.RunnerOrbitStallPenalty);
        config.TrapAwareEnabled = GetBool(values, "trap_aware.enabled", config.TrapAwareEnabled);
        config.TrapPincerFormationBonus = GetFloat(
            values,
            "trap_aware.pincer_formation_bonus",
            config.TrapPincerFormationBonus);
        config.TrapOppositeSideEnclosureBonus = GetFloat(
            values,
            "trap_aware.opposite_side_enclosure_bonus",
            config.TrapOppositeSideEnclosureBonus);
        config.TrapDeadEndForcingBonus = GetFloat(
            values,
            "trap_aware.dead_end_forcing_bonus",
            config.TrapDeadEndForcingBonus);
        config.TrapExitDenialPressureBonus = GetFloat(
            values,
            "trap_aware.exit_denial_pressure_bonus",
            config.TrapExitDenialPressureBonus);
        config.TrapCorridorControlBonus = GetFloat(
            values,
            "trap_aware.corridor_control_bonus",
            config.TrapCorridorControlBonus);
        config.AuditLogRewardEvents = GetBool(values, "audit.log_reward_events", config.AuditLogRewardEvents);

        message = $"Loaded reward config: {resolvedPath}";
        return true;
    }

    private static string ResolvePath(string configPath)
    {
        if (string.IsNullOrWhiteSpace(configPath))
        {
            return string.Empty;
        }

        if (Path.IsPathRooted(configPath))
        {
            return configPath;
        }

        string projectRootPath = Path.GetFullPath(Path.Combine(Application.dataPath, "..", configPath));
        if (File.Exists(projectRootPath))
        {
            return projectRootPath;
        }

        string repoRootPath = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", configPath));
        if (File.Exists(repoRootPath))
        {
            return repoRootPath;
        }

        return projectRootPath;
    }

    private static Dictionary<string, string> ParseYamlLikeFile(string path)
    {
        Dictionary<string, string> values = new Dictionary<string, string>();
        Stack<string> sections = new Stack<string>();
        string[] lines = File.ReadAllLines(path);

        for (int i = 0; i < lines.Length; i++)
        {
            string rawLine = StripComment(lines[i]);
            if (string.IsNullOrWhiteSpace(rawLine))
            {
                continue;
            }

            int level = CountLeadingSpaces(rawLine) / 2;
            while (sections.Count > level)
            {
                sections.Pop();
            }

            string line = rawLine.Trim();
            int separator = line.IndexOf(':');
            if (separator < 0)
            {
                continue;
            }

            string key = line.Substring(0, separator).Trim();
            string value = line.Substring(separator + 1).Trim().Trim('"', '\'');
            if (string.IsNullOrEmpty(value))
            {
                sections.Push(key);
                continue;
            }

            string[] prefix = sections.ToArray();
            Array.Reverse(prefix);
            string fullKey = prefix.Length > 0 ? string.Join(".", prefix) + "." + key : key;
            values[fullKey] = value;
        }

        return values;
    }

    private static string StripComment(string line)
    {
        int commentIndex = line.IndexOf('#');
        return commentIndex >= 0 ? line.Substring(0, commentIndex) : line;
    }

    private static int CountLeadingSpaces(string line)
    {
        int count = 0;
        while (count < line.Length && line[count] == ' ')
        {
            count++;
        }

        return count;
    }

    private static string GetString(Dictionary<string, string> values, string key, string fallback)
    {
        return values.TryGetValue(key, out string rawValue) ? rawValue : fallback;
    }

    private static float GetFloat(Dictionary<string, string> values, string key, float fallback)
    {
        if (!values.TryGetValue(key, out string rawValue))
        {
            return fallback;
        }

        return float.TryParse(rawValue, NumberStyles.Float, CultureInfo.InvariantCulture, out float parsed)
            ? parsed
            : fallback;
    }

    private static bool GetBool(Dictionary<string, string> values, string key, bool fallback)
    {
        if (!values.TryGetValue(key, out string rawValue))
        {
            return fallback;
        }

        return bool.TryParse(rawValue, out bool parsed) ? parsed : fallback;
    }
}
