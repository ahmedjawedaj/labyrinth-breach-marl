using System;
using System.IO;
using UnityEngine;

public static class LabyrinthPathResolver
{
    private const string RepoRootEnvironmentVariable = "LABYRINTH_REPO_ROOT";

    public static string GetRepoRoot()
    {
        string configuredRoot = Environment.GetEnvironmentVariable(RepoRootEnvironmentVariable);
        if (!string.IsNullOrWhiteSpace(configuredRoot) && Directory.Exists(configuredRoot))
        {
            return Path.GetFullPath(configuredRoot.Trim());
        }

        string workingDirectory = Directory.GetCurrentDirectory();
        if (Directory.Exists(Path.Combine(workingDirectory, "configs")))
        {
            return Path.GetFullPath(workingDirectory);
        }

        return Path.GetFullPath(Path.Combine(Application.dataPath, "..", ".."));
    }

    public static string ResolvePath(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return string.Empty;
        }

        if (Path.IsPathRooted(path))
        {
            return Path.GetFullPath(path);
        }

        string repoRelativePath = path.Replace('\\', '/');
        while (repoRelativePath.StartsWith("../", StringComparison.Ordinal))
        {
            repoRelativePath = repoRelativePath.Substring(3);
        }

        if (repoRelativePath.StartsWith("./", StringComparison.Ordinal))
        {
            repoRelativePath = repoRelativePath.Substring(2);
        }

        string repoCandidate = Path.GetFullPath(Path.Combine(GetRepoRoot(), repoRelativePath));
        if (File.Exists(repoCandidate) || Directory.Exists(repoCandidate))
        {
            return repoCandidate;
        }

        string projectCandidate = Path.GetFullPath(Path.Combine(Application.dataPath, "..", path));
        if (File.Exists(projectCandidate) || Directory.Exists(projectCandidate))
        {
            return projectCandidate;
        }

        return repoCandidate;
    }
}
