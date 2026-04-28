using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text.RegularExpressions;
using UnityEngine;

public class CoordinationKPIExporter : MonoBehaviour
{
    private const string Header =
        "run_id,seed,episode_id,outcome,capture_success,pincer_rate,corridor_block_rate,exit_denial_rate,trap_success_rate,enclosure_rate,pincer_avg_duration_seconds,corridor_block_avg_duration_seconds,exit_denial_avg_duration_seconds,pincer_event_count,corridor_block_event_count,exit_denial_event_count,enclosure_event_count,trap_event_count,captured_runners,total_runners,duration_seconds,total_steps";

    private readonly List<string> episodeRows = new List<string>();
    private string outputPath;
    private string runId = "unknown_run";
    private int seed = -1;
    private int episodeCounter;
    private int sentinelWinEpisodes;
    private int episodesWithAnyTrap;
    private int totalPincerCount;
    private int totalCorridorCount;
    private int totalExitDenialCount;
    private int totalEnclosureCount;

    public void BeginEpisode()
    {
        EnsureOutputFileInitialized();
    }

    public void RecordEpisode(
        int episodeId,
        EpisodeOutcome outcome,
        float durationSeconds,
        int totalSteps,
        int capturedRunners,
        int totalRunners,
        TrapEventDetector.TacticalMetricsSnapshot metrics)
    {
        EnsureOutputFileInitialized();
        metrics ??= new TrapEventDetector.TacticalMetricsSnapshot();

        bool captureSuccess = outcome == EpisodeOutcome.SentinelWinAllRunnersCaptured;
        episodeCounter++;
        if (captureSuccess)
        {
            sentinelWinEpisodes++;
        }

        int trapCount = Mathf.Max(0, metrics.TrapEventCount);
        if (trapCount > 0)
        {
            episodesWithAnyTrap++;
        }

        totalPincerCount += Mathf.Max(0, metrics.PincerCount);
        totalCorridorCount += Mathf.Max(0, metrics.CorridorBlockCount);
        totalExitDenialCount += Mathf.Max(0, metrics.ExitDenialCount);
        totalEnclosureCount += Mathf.Max(0, metrics.EnclosureCount);

        float pincerRate = metrics.PincerCount > 0 ? 1f : 0f;
        float corridorRate = metrics.CorridorBlockCount > 0 ? 1f : 0f;
        float exitDenialRate = metrics.ExitDenialCount > 0 ? 1f : 0f;
        float trapSuccessRate = trapCount > 0 && captureSuccess ? 1f : 0f;
        float enclosureRate = metrics.EnclosureCount > 0 ? 1f : 0f;

        string row = string.Join(
            ",",
            Csv(runId),
            seed.ToString(CultureInfo.InvariantCulture),
            episodeId.ToString(CultureInfo.InvariantCulture),
            Csv(outcome.ToString()),
            captureSuccess ? "true" : "false",
            pincerRate.ToString("0.000000", CultureInfo.InvariantCulture),
            corridorRate.ToString("0.000000", CultureInfo.InvariantCulture),
            exitDenialRate.ToString("0.000000", CultureInfo.InvariantCulture),
            trapSuccessRate.ToString("0.000000", CultureInfo.InvariantCulture),
            enclosureRate.ToString("0.000000", CultureInfo.InvariantCulture),
            metrics.PincerAverageDurationSeconds.ToString("0.000000", CultureInfo.InvariantCulture),
            metrics.CorridorBlockAverageDurationSeconds.ToString("0.000000", CultureInfo.InvariantCulture),
            metrics.ExitDenialAverageDurationSeconds.ToString("0.000000", CultureInfo.InvariantCulture),
            metrics.PincerCount.ToString(CultureInfo.InvariantCulture),
            metrics.CorridorBlockCount.ToString(CultureInfo.InvariantCulture),
            metrics.ExitDenialCount.ToString(CultureInfo.InvariantCulture),
            metrics.EnclosureCount.ToString(CultureInfo.InvariantCulture),
            trapCount.ToString(CultureInfo.InvariantCulture),
            capturedRunners.ToString(CultureInfo.InvariantCulture),
            totalRunners.ToString(CultureInfo.InvariantCulture),
            durationSeconds.ToString("0.000", CultureInfo.InvariantCulture),
            totalSteps.ToString(CultureInfo.InvariantCulture));
        episodeRows.Add(row);
        RewriteFileWithSummary();
    }

    private void EnsureOutputFileInitialized()
    {
        if (!string.IsNullOrEmpty(outputPath))
        {
            return;
        }

        string resultsRoot = Path.Combine(RunLogPathResolver.GetRepoRoot(), "results");
        if (RunLogPathResolver.TryGetActiveRunContext(out ActiveRunContext context) && !string.IsNullOrWhiteSpace(context.results_dir))
        {
            resultsRoot = context.results_dir;
            runId = string.IsNullOrWhiteSpace(context.run_id) ? runId : context.run_id.Trim();
        }

        seed = ParseSeedFromRunId(runId);
        string seedFolder = seed >= 0 ? $"seed_{seed}" : "seed_unknown";
        string directory = Path.Combine(resultsRoot, seedFolder, "kpis");
        Directory.CreateDirectory(directory);
        outputPath = Path.Combine(directory, "coordination_metrics.csv");
        if (!File.Exists(outputPath))
        {
            File.WriteAllText(outputPath, Header + "\n");
        }
    }

    private void RewriteFileWithSummary()
    {
        List<string> lines = new List<string>
        {
            Header
        };
        lines.AddRange(episodeRows);
        lines.Add(BuildSummaryRow());
        File.WriteAllText(outputPath, string.Join("\n", lines) + "\n");
    }

    private string BuildSummaryRow()
    {
        float safeEpisodes = Mathf.Max(1, episodeCounter);
        float pincerRate = totalPincerCount / safeEpisodes;
        float corridorRate = totalCorridorCount / safeEpisodes;
        float exitRate = totalExitDenialCount / safeEpisodes;
        float trapSuccessRate = episodesWithAnyTrap > 0 ? (float)sentinelWinEpisodes / safeEpisodes : 0f;
        float enclosureRate = totalEnclosureCount / safeEpisodes;
        return string.Join(
            ",",
            Csv(runId),
            seed.ToString(CultureInfo.InvariantCulture),
            "summary",
            Csv("summary"),
            "false",
            pincerRate.ToString("0.000000", CultureInfo.InvariantCulture),
            corridorRate.ToString("0.000000", CultureInfo.InvariantCulture),
            exitRate.ToString("0.000000", CultureInfo.InvariantCulture),
            trapSuccessRate.ToString("0.000000", CultureInfo.InvariantCulture),
            enclosureRate.ToString("0.000000", CultureInfo.InvariantCulture),
            "0.000000",
            "0.000000",
            "0.000000",
            totalPincerCount.ToString(CultureInfo.InvariantCulture),
            totalCorridorCount.ToString(CultureInfo.InvariantCulture),
            totalExitDenialCount.ToString(CultureInfo.InvariantCulture),
            totalEnclosureCount.ToString(CultureInfo.InvariantCulture),
            episodesWithAnyTrap.ToString(CultureInfo.InvariantCulture),
            "0",
            "0",
            "0.000",
            "0");
    }

    private static int ParseSeedFromRunId(string runId)
    {
        if (string.IsNullOrEmpty(runId))
        {
            return -1;
        }

        Match match = Regex.Match(runId, @"seed(?<seed>\d+)");
        if (!match.Success)
        {
            return -1;
        }

        return int.TryParse(match.Groups["seed"].Value, NumberStyles.Integer, CultureInfo.InvariantCulture, out int value)
            ? value
            : -1;
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
