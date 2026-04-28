using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;

public struct EnvRuleConfig
{
    public float SentinelSpeed;
    public float RunnerSpeed;
    public float CaptureRadius;
    public float TimeoutSeconds;
    public bool TimeoutCountsAsRunnerWin;
    public bool ExitWinEnabled;
    public bool RequireActiveRunnerForExit;
    public bool VerifyResetIntegrity;
    public ObservationConfig ObservationConfig;
    public bool DynamicWallsEnabled;
    public float WallShiftIntervalSeconds;
    public int WallShiftIntensity;
    public float WallSafeBuffer;
    public bool AllowExitBlocking;
    public float WallLoweredOffset;
    public RandomizationConfig RandomizationConfig;

    public static EnvRuleConfig Default()
    {
        return new EnvRuleConfig
        {
            SentinelSpeed = 4f,
            RunnerSpeed = 4.5f,
            CaptureRadius = 1.25f,
            TimeoutSeconds = 120f,
            TimeoutCountsAsRunnerWin = true,
            ExitWinEnabled = false,
            RequireActiveRunnerForExit = true,
            VerifyResetIntegrity = true,
            ObservationConfig = ObservationConfig.Default(),
            DynamicWallsEnabled = false,
            WallShiftIntervalSeconds = 15f,
            WallShiftIntensity = 2,
            WallSafeBuffer = 1.5f,
            AllowExitBlocking = false,
            WallLoweredOffset = 3f,
            RandomizationConfig = RandomizationConfig.Default()
        };
    }
}

public struct ObservationConfig
{
    public bool UseRays;
    public bool UseMemory;
    public bool UseBufferSensors;
    public bool IncludeTeammates;
    public bool IncludeOpponents;
    public bool IncludeExitVector;
    public int SentinelRayCount;
    public int RunnerRayCount;

    public static ObservationConfig Default()
    {
        return new ObservationConfig
        {
            UseRays = false,
            UseMemory = true,
            UseBufferSensors = true,
            IncludeTeammates = true,
            IncludeOpponents = true,
            IncludeExitVector = false,
            SentinelRayCount = 14,
            RunnerRayCount = 16
        };
    }
}

public struct RandomizationConfig
{
    public int Seed;
    public bool RandomizeSpawnPositions;
    public int MazeSeed;
    public bool RandomizeExitPositions;
    public bool RandomizeWallShiftFrequency;
    public float WallShiftMinSeconds;
    public float WallShiftMaxSeconds;
    public bool RandomizeSpeedAsymmetry;
    public float SentinelSpeedMin;
    public float SentinelSpeedMax;
    public float RunnerSpeedMin;
    public float RunnerSpeedMax;
    public bool RandomizeTimeout;
    public float TimeoutMinSeconds;
    public float TimeoutMaxSeconds;

    public static RandomizationConfig Default()
    {
        return new RandomizationConfig
        {
            Seed = 42,
            RandomizeSpawnPositions = false,
            MazeSeed = 42,
            RandomizeExitPositions = false,
            RandomizeWallShiftFrequency = false,
            WallShiftMinSeconds = 8f,
            WallShiftMaxSeconds = 18f,
            RandomizeSpeedAsymmetry = false,
            SentinelSpeedMin = 3.8f,
            SentinelSpeedMax = 4.2f,
            RunnerSpeedMin = 4.3f,
            RunnerSpeedMax = 4.8f,
            RandomizeTimeout = false,
            TimeoutMinSeconds = 120f,
            TimeoutMaxSeconds = 180f
        };
    }
}

public static class EnvRuleConfigLoader
{
    public static bool TryLoad(string configPath, out EnvRuleConfig config, out string message)
    {
        config = EnvRuleConfig.Default();
        message = string.Empty;

        string resolvedPath = ResolvePath(configPath);
        if (string.IsNullOrEmpty(resolvedPath) || !File.Exists(resolvedPath))
        {
            message = $"Rule config not found: {configPath}";
            return false;
        }

        Dictionary<string, string> values = ParseYamlLikeFile(resolvedPath);
        config.SentinelSpeed = GetFloat(values, "sentinel.speed", config.SentinelSpeed);
        config.RunnerSpeed = GetFloat(values, "runner.speed", config.RunnerSpeed);
        config.CaptureRadius = GetFloat(values, "sentinel.capture_radius", config.CaptureRadius);
        config.TimeoutSeconds = GetFloat(values, "episode.timeout_seconds", config.TimeoutSeconds);
        config.TimeoutCountsAsRunnerWin = GetBool(
            values,
            "episode.timeout_counts_as_runner_win",
            config.TimeoutCountsAsRunnerWin);
        config.ExitWinEnabled = GetBool(values, "exit.enabled", config.ExitWinEnabled);
        config.RequireActiveRunnerForExit = GetBool(
            values,
            "exit.require_active_runner",
            config.RequireActiveRunnerForExit);
        config.VerifyResetIntegrity = GetBool(values, "reset.verify_integrity", config.VerifyResetIntegrity);
        config.DynamicWallsEnabled = GetBool(values, "dynamic_walls.enabled", config.DynamicWallsEnabled);
        config.WallShiftIntervalSeconds = GetFloat(
            values,
            "dynamic_walls.shift_interval_seconds",
            config.WallShiftIntervalSeconds);
        config.WallShiftIntensity = GetInt(values, "dynamic_walls.shift_intensity", config.WallShiftIntensity);
        config.WallSafeBuffer = GetFloat(values, "dynamic_walls.safe_buffer", config.WallSafeBuffer);
        config.AllowExitBlocking = GetBool(
            values,
            "dynamic_walls.allow_exit_blocking",
            config.AllowExitBlocking);
        config.WallLoweredOffset = GetFloat(
            values,
            "dynamic_walls.wall_lowered_offset",
            config.WallLoweredOffset);
        ObservationConfig observationConfig = config.ObservationConfig;
        observationConfig.UseRays = GetBool(values, "observations.use_rays", observationConfig.UseRays);
        observationConfig.UseMemory = GetBool(values, "observations.use_memory", observationConfig.UseMemory);
        observationConfig.UseBufferSensors = GetBool(
            values,
            "observations.use_buffer_sensors",
            observationConfig.UseBufferSensors);
        observationConfig.IncludeTeammates = GetBool(
            values,
            "observations.include_teammates",
            observationConfig.IncludeTeammates);
        observationConfig.IncludeOpponents = GetBool(
            values,
            "observations.include_opponents",
            observationConfig.IncludeOpponents);
        observationConfig.IncludeExitVector = GetBool(
            values,
            "observations.include_exit_vector",
            observationConfig.IncludeExitVector);
        observationConfig.SentinelRayCount = GetInt(
            values,
            "observations.sentinel_ray_count",
            observationConfig.SentinelRayCount);
        observationConfig.RunnerRayCount = GetInt(
            values,
            "observations.runner_ray_count",
            observationConfig.RunnerRayCount);
        config.ObservationConfig = observationConfig;

        RandomizationConfig randomizationConfig = config.RandomizationConfig;
        randomizationConfig.Seed = GetInt(values, "randomization.seed", randomizationConfig.Seed);
        randomizationConfig.RandomizeSpawnPositions = GetBool(
            values,
            "randomization.spawn_positions",
            randomizationConfig.RandomizeSpawnPositions);
        randomizationConfig.MazeSeed = GetInt(values, "randomization.maze_seed", randomizationConfig.MazeSeed);
        randomizationConfig.RandomizeExitPositions = GetBool(
            values,
            "randomization.exit_positions",
            randomizationConfig.RandomizeExitPositions);
        randomizationConfig.RandomizeWallShiftFrequency = GetBool(
            values,
            "randomization.wall_shift_frequency.enabled",
            randomizationConfig.RandomizeWallShiftFrequency);
        randomizationConfig.WallShiftMinSeconds = GetFloat(
            values,
            "randomization.wall_shift_frequency.min_seconds",
            randomizationConfig.WallShiftMinSeconds);
        randomizationConfig.WallShiftMaxSeconds = GetFloat(
            values,
            "randomization.wall_shift_frequency.max_seconds",
            randomizationConfig.WallShiftMaxSeconds);
        randomizationConfig.RandomizeSpeedAsymmetry = GetBool(
            values,
            "randomization.speed_asymmetry.enabled",
            randomizationConfig.RandomizeSpeedAsymmetry);
        randomizationConfig.SentinelSpeedMin = GetFloat(
            values,
            "randomization.speed_asymmetry.sentinel_min",
            randomizationConfig.SentinelSpeedMin);
        randomizationConfig.SentinelSpeedMax = GetFloat(
            values,
            "randomization.speed_asymmetry.sentinel_max",
            randomizationConfig.SentinelSpeedMax);
        randomizationConfig.RunnerSpeedMin = GetFloat(
            values,
            "randomization.speed_asymmetry.runner_min",
            randomizationConfig.RunnerSpeedMin);
        randomizationConfig.RunnerSpeedMax = GetFloat(
            values,
            "randomization.speed_asymmetry.runner_max",
            randomizationConfig.RunnerSpeedMax);
        randomizationConfig.RandomizeTimeout = GetBool(
            values,
            "randomization.timeout.enabled",
            randomizationConfig.RandomizeTimeout);
        randomizationConfig.TimeoutMinSeconds = GetFloat(
            values,
            "randomization.timeout.min_seconds",
            randomizationConfig.TimeoutMinSeconds);
        randomizationConfig.TimeoutMaxSeconds = GetFloat(
            values,
            "randomization.timeout.max_seconds",
            randomizationConfig.TimeoutMaxSeconds);
        config.RandomizationConfig = randomizationConfig;

        message = $"Loaded rule config: {resolvedPath}";
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

            int indent = CountLeadingSpaces(rawLine);
            int level = indent / 2;
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

    private static int GetInt(Dictionary<string, string> values, string key, int fallback)
    {
        if (!values.TryGetValue(key, out string rawValue))
        {
            return fallback;
        }

        return int.TryParse(rawValue, NumberStyles.Integer, CultureInfo.InvariantCulture, out int parsed)
            ? parsed
            : fallback;
    }
}
