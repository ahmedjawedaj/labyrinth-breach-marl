using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;

public static class LabyrinthBreachBuild
{
    private static readonly string[] Scenes =
    {
        "Assets/Scenes/01_Baseline_OpenArena_3v2.unity",
        "Assets/Scenes/02_StaticMaze_3v2.unity",
        "Assets/Scenes/03_DynamicMaze_3v2.unity",
        "Assets/Scenes/04_Eval_UnseenMaze_3v2.unity"
    };

    public static void BuildMacOS()
    {
        ValidateHeldOutTopologies();

        string outputPath = GetArg("-buildOutput");
        if (string.IsNullOrWhiteSpace(outputPath))
        {
            outputPath = "../builds/macos/LabyrinthBreach.app";
        }

        bool serverBuild = HasArg("-serverBuild");
        BuildPlayerOptions options = new BuildPlayerOptions
        {
            scenes = Scenes,
            locationPathName = outputPath,
            target = BuildTarget.StandaloneOSX,
            options = BuildOptions.StrictMode,
            subtarget = (int)StandaloneBuildSubtarget.Player
        };

#if UNITY_2021_2_OR_NEWER
        if (serverBuild)
        {
            options.subtarget = (int)StandaloneBuildSubtarget.Server;
        }
#endif

        BuildReport report = BuildPipeline.BuildPlayer(options);
        BuildSummary summary = report.summary;
        Console.WriteLine(
            $"Labyrinth Breach build result={summary.result} output={summary.outputPath} " +
            $"size={summary.totalSize} warnings={summary.totalWarnings} errors={summary.totalErrors}");

        if (summary.result != BuildResult.Succeeded)
        {
            throw new Exception($"Unity build failed with result {summary.result}");
        }
    }

    private static void ValidateHeldOutTopologies()
    {
        int[] seeds = { 101, 202, 303, 404, 505 };
        HashSet<string> signatures = new HashSet<string>();
        for (int i = 0; i < seeds.Length; i++)
        {
            if (!MazeGenerator.TryValidateProceduralLayout(seeds[i], out string signature, out string error))
            {
                throw new Exception($"Held-out topology validation failed: {error}");
            }
            if (!signatures.Add(signature))
            {
                throw new Exception($"Held-out topology seed {seeds[i]} duplicates an earlier layout signature {signature}.");
            }
            Console.WriteLine($"Validated held-out topology seed={seeds[i]} signature={signature}");
        }
    }

    private static string GetArg(string name)
    {
        string[] args = Environment.GetCommandLineArgs();
        for (int i = 0; i < args.Length - 1; i++)
        {
            if (args[i] == name)
            {
                return args[i + 1];
            }
        }

        return string.Empty;
    }

    private static bool HasArg(string name)
    {
        return Environment.GetCommandLineArgs().Any(arg => arg == name);
    }
}
