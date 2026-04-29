using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;

public struct CurriculumStageConfig
{
    public string StageId;
    public string SceneName;
    public string RuleConfigPath;
    public bool MazeEnabled;
    public MazeMode MazeMode;
    public int MazeSeed;
    public bool RandomizeSpawns;
    public bool RandomizeExits;
    public bool DynamicWallsEnabled;
    public float WallShiftIntervalSeconds;
    public int WallShiftIntensity;
    public float WallSafeBuffer;
    public bool AllowExitBlocking;
    public float WallLoweredOffset;
    public int MinEpisodes;
    public float SentinelWinRateThreshold;

    public static CurriculumStageConfig Default()
    {
        return new CurriculumStageConfig
        {
            StageId = "open_arena_no_shifts",
            SceneName = "01_Baseline_OpenArena_3v2",
            RuleConfigPath = "configs/env_configs/asymmetry_config.yaml",
            MazeEnabled = false,
            MazeMode = MazeMode.Static,
            MazeSeed = 42,
            RandomizeSpawns = false,
            RandomizeExits = false,
            DynamicWallsEnabled = false,
            WallShiftIntervalSeconds = 15f,
            WallShiftIntensity = 0,
            WallSafeBuffer = 1.5f,
            AllowExitBlocking = false,
            WallLoweredOffset = 3f,
            MinEpisodes = 0,
            SentinelWinRateThreshold = 0f
        };
    }
}

public struct CurriculumConfig
{
    public string CurriculumId;
    public int DefaultStageIndex;
    public List<CurriculumStageConfig> Stages;

    public static CurriculumConfig Default()
    {
        return new CurriculumConfig
        {
            CurriculumId = "curriculum_3v2_full_v1",
            DefaultStageIndex = 0,
            Stages = new List<CurriculumStageConfig> { CurriculumStageConfig.Default() }
        };
    }
}

public static class CurriculumConfigLoader
{
    public static bool TryLoad(string configPath, out CurriculumConfig config, out string message)
    {
        config = CurriculumConfig.Default();
        message = string.Empty;

        string resolvedPath = ResolvePath(configPath);
        if (string.IsNullOrEmpty(resolvedPath) || !File.Exists(resolvedPath))
        {
            message = $"Curriculum config not found: {configPath}";
            return false;
        }

        string[] lines = File.ReadAllLines(resolvedPath);
        List<CurriculumStageConfig> stages = new List<CurriculumStageConfig>();
        CurriculumStageConfig currentStage = CurriculumStageConfig.Default();
        bool hasCurrentStage = false;
        string section = string.Empty;

        for (int i = 0; i < lines.Length; i++)
        {
            string rawLine = StripComment(lines[i]);
            if (string.IsNullOrWhiteSpace(rawLine))
            {
                continue;
            }

            int indent = CountLeadingSpaces(rawLine);
            string line = rawLine.Trim();
            if (line.StartsWith("- ", StringComparison.Ordinal))
            {
                if (hasCurrentStage)
                {
                    stages.Add(currentStage);
                }

                currentStage = CurriculumStageConfig.Default();
                hasCurrentStage = true;
                section = string.Empty;
                ParseAssignment(line.Substring(2), out string listKey, out string listValue);
                ApplyStageValue(ref currentStage, listKey, listValue);
                continue;
            }

            ParseAssignment(line, out string key, out string value);
            if (string.IsNullOrEmpty(key))
            {
                continue;
            }

            if (!hasCurrentStage)
            {
                if (key == "curriculum_id")
                {
                    config.CurriculumId = value;
                }
                else if (key == "default_stage_index")
                {
                    config.DefaultStageIndex = GetInt(value, config.DefaultStageIndex);
                }

                continue;
            }

            if (string.IsNullOrEmpty(value))
            {
                section = key;
                continue;
            }

            string scopedKey = indent >= 6 && !string.IsNullOrEmpty(section) ? section + "." + key : key;
            ApplyStageValue(ref currentStage, scopedKey, value);
        }

        if (hasCurrentStage)
        {
            stages.Add(currentStage);
        }

        if (stages.Count > 0)
        {
            config.Stages = stages;
            config.DefaultStageIndex = Mathf.Clamp(config.DefaultStageIndex, 0, stages.Count - 1);
        }

        message = $"Loaded curriculum config: {resolvedPath}";
        return true;
    }

    private static void ApplyStageValue(ref CurriculumStageConfig stage, string key, string value)
    {
        switch (key)
        {
            case "stage_id":
                stage.StageId = value;
                break;
            case "scene":
            case "scene_name":
                stage.SceneName = value;
                break;
            case "rule_config":
                stage.RuleConfigPath = value;
                break;
            case "env_config":
                ApplyEnvConfig(ref stage, value);
                break;
            case "maze.enabled":
                stage.MazeEnabled = GetBool(value, stage.MazeEnabled);
                break;
            case "maze.mode":
                stage.MazeMode = ParseMazeMode(value, stage.MazeMode);
                break;
            case "maze.seed":
                stage.MazeSeed = GetInt(value, stage.MazeSeed);
                break;
            case "maze.randomize_spawns":
                stage.RandomizeSpawns = GetBool(value, stage.RandomizeSpawns);
                break;
            case "maze.randomize_exits":
                stage.RandomizeExits = GetBool(value, stage.RandomizeExits);
                break;
            case "dynamic_walls.enabled":
                stage.DynamicWallsEnabled = GetBool(value, stage.DynamicWallsEnabled);
                break;
            case "dynamic_walls.shift_interval_seconds":
                stage.WallShiftIntervalSeconds = GetFloat(value, stage.WallShiftIntervalSeconds);
                break;
            case "dynamic_walls.shift_intensity":
                stage.WallShiftIntensity = GetInt(value, stage.WallShiftIntensity);
                break;
            case "dynamic_walls.safe_buffer":
                stage.WallSafeBuffer = GetFloat(value, stage.WallSafeBuffer);
                break;
            case "dynamic_walls.allow_exit_blocking":
                stage.AllowExitBlocking = GetBool(value, stage.AllowExitBlocking);
                break;
            case "dynamic_walls.wall_lowered_offset":
                stage.WallLoweredOffset = GetFloat(value, stage.WallLoweredOffset);
                break;
            case "completion_criteria.min_episodes":
                stage.MinEpisodes = GetInt(value, stage.MinEpisodes);
                break;
            case "completion_criteria.sentinel_win_rate_threshold":
                stage.SentinelWinRateThreshold = GetFloat(value, stage.SentinelWinRateThreshold);
                break;
        }
    }

    private static void ApplyEnvConfig(ref CurriculumStageConfig stage, string envConfigPath)
    {
        string resolvedPath = ResolvePath(envConfigPath);
        if (string.IsNullOrEmpty(resolvedPath) || !File.Exists(resolvedPath))
        {
            return;
        }

        Dictionary<string, string> values = ParseYamlLikeFile(resolvedPath);
        if (values.TryGetValue("scene", out string sceneName))
        {
            stage.SceneName = sceneName;
        }

        if (values.TryGetValue("rule_config", out string ruleConfigPath))
        {
            stage.RuleConfigPath = ResolveRelativeToEnvConfig(resolvedPath, ruleConfigPath);
        }

        if (values.TryGetValue("maze.type", out string mazeType))
        {
            stage.MazeMode = ParseMazeMode(mazeType, stage.MazeMode);
            stage.MazeEnabled = !string.Equals(mazeType, "open", StringComparison.OrdinalIgnoreCase);
        }

        stage.MazeSeed = GetValueInt(values, "maze.seed", stage.MazeSeed);
        stage.RandomizeSpawns = GetValueBool(values, "spawning.randomize_spawns", stage.RandomizeSpawns);
        stage.DynamicWallsEnabled = GetValueBool(values, "dynamic_walls.enabled", stage.DynamicWallsEnabled);
        stage.WallShiftIntervalSeconds = GetValueFloat(
            values,
            "dynamic_walls.shift_interval_seconds",
            stage.WallShiftIntervalSeconds);
        stage.WallShiftIntensity = GetValueInt(values, "dynamic_walls.shift_intensity", stage.WallShiftIntensity);
        stage.WallSafeBuffer = GetValueFloat(values, "dynamic_walls.safe_buffer", stage.WallSafeBuffer);
        stage.AllowExitBlocking = GetValueBool(
            values,
            "dynamic_walls.allow_exit_blocking",
            stage.AllowExitBlocking);
        stage.WallLoweredOffset = GetValueFloat(
            values,
            "dynamic_walls.wall_lowered_offset",
            stage.WallLoweredOffset);
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
            ParseAssignment(line, out string key, out string value);
            if (string.IsNullOrEmpty(key))
            {
                continue;
            }

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

    private static string ResolveRelativeToEnvConfig(string envConfigPath, string referencedPath)
    {
        if (Path.IsPathRooted(referencedPath) || referencedPath.Contains("/") || referencedPath.Contains("\\"))
        {
            return referencedPath;
        }

        string envConfigDirectory = Path.GetDirectoryName(envConfigPath);
        return string.IsNullOrEmpty(envConfigDirectory)
            ? referencedPath
            : Path.Combine(envConfigDirectory, referencedPath);
    }

    private static MazeMode ParseMazeMode(string value, MazeMode fallback)
    {
        if (string.Equals(value, "dynamic", StringComparison.OrdinalIgnoreCase))
        {
            return MazeMode.Dynamic;
        }

        if (string.Equals(value, "static", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(value, "open", StringComparison.OrdinalIgnoreCase))
        {
            return MazeMode.Static;
        }

        return fallback;
    }

    private static void ParseAssignment(string line, out string key, out string value)
    {
        key = string.Empty;
        value = string.Empty;

        int separator = line.IndexOf(':');
        if (separator < 0)
        {
            return;
        }

        key = line.Substring(0, separator).Trim();
        value = line.Substring(separator + 1).Trim().Trim('"', '\'');
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

    private static float GetFloat(string rawValue, float fallback)
    {
        return float.TryParse(rawValue, NumberStyles.Float, CultureInfo.InvariantCulture, out float parsed)
            ? parsed
            : fallback;
    }

    private static bool GetBool(string rawValue, bool fallback)
    {
        return bool.TryParse(rawValue, out bool parsed) ? parsed : fallback;
    }

    private static int GetInt(string rawValue, int fallback)
    {
        return int.TryParse(rawValue, NumberStyles.Integer, CultureInfo.InvariantCulture, out int parsed)
            ? parsed
            : fallback;
    }

    private static float GetValueFloat(Dictionary<string, string> values, string key, float fallback)
    {
        return values.TryGetValue(key, out string rawValue) ? GetFloat(rawValue, fallback) : fallback;
    }

    private static bool GetValueBool(Dictionary<string, string> values, string key, bool fallback)
    {
        return values.TryGetValue(key, out string rawValue) ? GetBool(rawValue, fallback) : fallback;
    }

    private static int GetValueInt(Dictionary<string, string> values, string key, int fallback)
    {
        return values.TryGetValue(key, out string rawValue) ? GetInt(rawValue, fallback) : fallback;
    }
}
