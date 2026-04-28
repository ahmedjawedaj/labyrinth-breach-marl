using System;
using System.IO;
using UnityEngine;

[Serializable]
public class ActiveRunContext
{
    public string run_id;
    public string mode;
    public string results_dir;
    public string logs_dir;
    public string created_utc;
}

public static class RunLogPathResolver
{
    public static bool TryGetActiveRunContext(out ActiveRunContext context)
    {
        context = null;
        string contextPath = Path.Combine(GetRepoRootPath(), "configs", "runtime_overrides", "active_run_context.json");
        if (!File.Exists(contextPath))
        {
            return false;
        }

        try
        {
            string raw = File.ReadAllText(contextPath);
            if (string.IsNullOrWhiteSpace(raw))
            {
                return false;
            }

            ActiveRunContext parsed = JsonUtility.FromJson<ActiveRunContext>(raw);
            if (parsed == null || string.IsNullOrWhiteSpace(parsed.run_id) || string.IsNullOrWhiteSpace(parsed.results_dir))
            {
                return false;
            }

            context = parsed;
            return true;
        }
        catch (Exception ex)
        {
            Debug.LogWarning($"Failed to parse active run context: {ex.Message}");
            return false;
        }
    }

    public static string GetRepoRoot()
    {
        return GetRepoRootPath();
    }

    public static string ResolveLogDirectory(string defaultLogDirectoryName)
    {
        string overrideDir = ResolveOverrideLogsDirectory();
        if (!string.IsNullOrWhiteSpace(overrideDir))
        {
            Directory.CreateDirectory(overrideDir);
            WriteMarker("last_unity_log_dir.txt", overrideDir);
            return overrideDir;
        }

        string fallback = Path.Combine(Application.persistentDataPath, defaultLogDirectoryName);
        Directory.CreateDirectory(fallback);
        WriteMarker("last_unity_log_dir_fallback.txt", fallback);
        return fallback;
    }

    private static string ResolveOverrideLogsDirectory()
    {
        if (!TryGetActiveRunContext(out ActiveRunContext context))
        {
            return string.Empty;
        }

        return string.IsNullOrWhiteSpace(context.logs_dir) ? string.Empty : context.logs_dir.Trim();
    }

    private static string GetRepoRootPath()
    {
        return Path.GetFullPath(Path.Combine(Application.dataPath, "..", ".."));
    }

    private static void WriteMarker(string fileName, string value)
    {
        try
        {
            string overrideDir = Path.Combine(GetRepoRootPath(), "configs", "runtime_overrides");
            Directory.CreateDirectory(overrideDir);
            File.WriteAllText(Path.Combine(overrideDir, fileName), value + Environment.NewLine);
        }
        catch
        {
            // Marker writes are best-effort and should not break gameplay or training.
        }
    }
}
