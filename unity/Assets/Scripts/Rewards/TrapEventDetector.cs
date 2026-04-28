using System;
using System.Collections.Generic;
using UnityEngine;

public static class TrapEventDetector
{
    public sealed class TacticalMetricsSnapshot
    {
        public int PincerCount;
        public float PincerAverageDurationSeconds;
        public int CorridorBlockCount;
        public float CorridorBlockAverageDurationSeconds;
        public int ExitDenialCount;
        public float ExitDenialAverageDurationSeconds;
        public int EnclosureCount;
        public int TrapEventCount;
        public int EpisodesWithPincer;
        public int EpisodesWithCorridorBlock;
        public int EpisodesWithExitDenial;
    }

    public sealed class TacticalEventTracker
    {
        private readonly float minimumDurationSeconds;
        private readonly PersistentEventCounter pincerCounter;
        private readonly PersistentEventCounter corridorCounter;
        private readonly PersistentEventCounter exitDenialCounter;
        private float currentTimeSeconds;

        public TacticalEventTracker(float minimumDurationSeconds)
        {
            this.minimumDurationSeconds = Mathf.Max(0.05f, minimumDurationSeconds);
            pincerCounter = new PersistentEventCounter(this.minimumDurationSeconds);
            corridorCounter = new PersistentEventCounter(this.minimumDurationSeconds);
            exitDenialCounter = new PersistentEventCounter(this.minimumDurationSeconds);
        }

        public void BeginEpisode()
        {
            currentTimeSeconds = 0f;
            pincerCounter.Reset();
            corridorCounter.Reset();
            exitDenialCounter.Reset();
        }

        public void BeginTick(float elapsedSeconds)
        {
            currentTimeSeconds = Mathf.Max(0f, elapsedSeconds);
            pincerCounter.BeginTick(currentTimeSeconds);
            corridorCounter.BeginTick(currentTimeSeconds);
            exitDenialCounter.BeginTick(currentTimeSeconds);
        }

        public void ObservePincer(string key)
        {
            if (!string.IsNullOrEmpty(key))
            {
                pincerCounter.Observe(key);
            }
        }

        public void ObserveCorridorBlock(string key)
        {
            if (!string.IsNullOrEmpty(key))
            {
                corridorCounter.Observe(key);
            }
        }

        public void ObserveExitDenial(string key)
        {
            if (!string.IsNullOrEmpty(key))
            {
                exitDenialCounter.Observe(key);
            }
        }

        public void EndTick()
        {
            pincerCounter.EndTick();
            corridorCounter.EndTick();
            exitDenialCounter.EndTick();
        }

        public TacticalMetricsSnapshot EndEpisodeAndSnapshot(int enclosureCount, int trapEventCount)
        {
            pincerCounter.EndEpisode(currentTimeSeconds);
            corridorCounter.EndEpisode(currentTimeSeconds);
            exitDenialCounter.EndEpisode(currentTimeSeconds);
            return new TacticalMetricsSnapshot
            {
                PincerCount = pincerCounter.QualifiedCount,
                PincerAverageDurationSeconds = pincerCounter.AverageDurationSeconds,
                CorridorBlockCount = corridorCounter.QualifiedCount,
                CorridorBlockAverageDurationSeconds = corridorCounter.AverageDurationSeconds,
                ExitDenialCount = exitDenialCounter.QualifiedCount,
                ExitDenialAverageDurationSeconds = exitDenialCounter.AverageDurationSeconds,
                EnclosureCount = Mathf.Max(0, enclosureCount),
                TrapEventCount = Mathf.Max(0, trapEventCount),
                EpisodesWithPincer = pincerCounter.QualifiedCount > 0 ? 1 : 0,
                EpisodesWithCorridorBlock = corridorCounter.QualifiedCount > 0 ? 1 : 0,
                EpisodesWithExitDenial = exitDenialCounter.QualifiedCount > 0 ? 1 : 0,
            };
        }
    }

    private sealed class PersistentEventCounter
    {
        private readonly float minimumDurationSeconds;
        private readonly Dictionary<string, float> startTimeByKey = new Dictionary<string, float>();
        private readonly HashSet<string> observedKeysThisTick = new HashSet<string>();
        private readonly HashSet<string> qualifiedKeys = new HashSet<string>();
        private float currentTimeSeconds;
        private float totalDurationSeconds;

        public PersistentEventCounter(float minimumDurationSeconds)
        {
            this.minimumDurationSeconds = Mathf.Max(0.05f, minimumDurationSeconds);
        }

        public int QualifiedCount => qualifiedKeys.Count;

        public float AverageDurationSeconds
        {
            get
            {
                if (QualifiedCount <= 0)
                {
                    return 0f;
                }

                return totalDurationSeconds / QualifiedCount;
            }
        }

        public void Reset()
        {
            startTimeByKey.Clear();
            observedKeysThisTick.Clear();
            qualifiedKeys.Clear();
            currentTimeSeconds = 0f;
            totalDurationSeconds = 0f;
        }

        public void BeginTick(float currentTimeSeconds)
        {
            this.currentTimeSeconds = Mathf.Max(0f, currentTimeSeconds);
            observedKeysThisTick.Clear();
        }

        public void Observe(string key)
        {
            observedKeysThisTick.Add(key);
            if (!startTimeByKey.ContainsKey(key))
            {
                startTimeByKey[key] = currentTimeSeconds;
            }
        }

        public void EndTick()
        {
            List<string> keys = new List<string>(startTimeByKey.Keys);
            for (int i = 0; i < keys.Count; i++)
            {
                string key = keys[i];
                if (observedKeysThisTick.Contains(key))
                {
                    continue;
                }

                FinalizeKey(key, currentTimeSeconds);
            }
        }

        public void EndEpisode(float endTimeSeconds)
        {
            currentTimeSeconds = Mathf.Max(0f, endTimeSeconds);
            List<string> keys = new List<string>(startTimeByKey.Keys);
            for (int i = 0; i < keys.Count; i++)
            {
                FinalizeKey(keys[i], currentTimeSeconds);
            }
        }

        private void FinalizeKey(string key, float endTimeSeconds)
        {
            if (!startTimeByKey.TryGetValue(key, out float startTime))
            {
                return;
            }

            float duration = Mathf.Max(0f, endTimeSeconds - startTime);
            if (duration >= minimumDurationSeconds)
            {
                if (!qualifiedKeys.Contains(key))
                {
                    qualifiedKeys.Add(key);
                }
                totalDurationSeconds += duration;
            }

            startTimeByKey.Remove(key);
        }
    }

    public static string BuildPincerKey(RunnerAgent runner, SentinelAgent first, SentinelAgent second)
    {
        if (runner == null || first == null || second == null)
        {
            return string.Empty;
        }

        string a = first.AgentId;
        string b = second.AgentId;
        if (string.CompareOrdinal(a, b) > 0)
        {
            string swap = a;
            a = b;
            b = swap;
        }

        return $"runner={runner.AgentId}|sentinels={a}+{b}";
    }

    public static string BuildCorridorControlKey(RunnerAgent runner, SentinelAgent first, SentinelAgent second)
    {
        string pincerKey = BuildPincerKey(runner, first, second);
        return string.IsNullOrEmpty(pincerKey) ? string.Empty : "corridor|" + pincerKey;
    }

    public static string BuildExitDenialKey(SentinelAgent sentinel, int exitIndex)
    {
        if (sentinel == null || exitIndex < 0)
        {
            return string.Empty;
        }

        return $"exit={exitIndex}|sentinel={sentinel.AgentId}";
    }

    public static bool TryFindPincer(
        IReadOnlyList<SentinelAgent> sentinels,
        RunnerAgent runner,
        float maxDistance,
        out SentinelAgent first,
        out SentinelAgent second)
    {
        first = null;
        second = null;
        if (sentinels == null || runner == null || !runner.IsAlive)
        {
            return false;
        }

        Vector3 runnerPosition = Flatten(runner.transform.position);
        float safeMaxDistance = Mathf.Max(0.1f, maxDistance);
        for (int i = 0; i < sentinels.Count; i++)
        {
            SentinelAgent a = sentinels[i];
            if (a == null || !a.IsAlive)
            {
                continue;
            }

            Vector3 fromRunnerToA = Flatten(a.transform.position) - runnerPosition;
            if (fromRunnerToA.magnitude > safeMaxDistance)
            {
                continue;
            }

            for (int j = i + 1; j < sentinels.Count; j++)
            {
                SentinelAgent b = sentinels[j];
                if (b == null || !b.IsAlive)
                {
                    continue;
                }

                Vector3 fromRunnerToB = Flatten(b.transform.position) - runnerPosition;
                if (fromRunnerToB.magnitude > safeMaxDistance)
                {
                    continue;
                }

                float opposingDirection = Vector3.Dot(fromRunnerToA.normalized, fromRunnerToB.normalized);
                if (opposingDirection <= -0.45f)
                {
                    first = a;
                    second = b;
                    return true;
                }
            }
        }

        return false;
    }

    public static bool TryFindExitDenial(
        IReadOnlyList<SentinelAgent> sentinels,
        IReadOnlyList<Vector3> exitPositions,
        IReadOnlyList<RunnerAgent> runners,
        float maxDistance,
        float runnerPressureDistance,
        out SentinelAgent sentinel,
        out int deniedExitIndex)
    {
        sentinel = null;
        deniedExitIndex = -1;
        if (sentinels == null || exitPositions == null || exitPositions.Count == 0)
        {
            return false;
        }

        float safeMaxDistance = Mathf.Max(0.1f, maxDistance);
        float safeRunnerPressureDistance = Mathf.Max(safeMaxDistance, runnerPressureDistance);
        for (int i = 0; i < sentinels.Count; i++)
        {
            SentinelAgent candidate = sentinels[i];
            if (candidate == null || !candidate.IsAlive)
            {
                continue;
            }

            Vector3 sentinelPosition = Flatten(candidate.transform.position);
            for (int j = 0; j < exitPositions.Count; j++)
            {
                Vector3 exitPosition = Flatten(exitPositions[j]);
                if (Vector3.Distance(sentinelPosition, exitPosition) <= safeMaxDistance
                    && HasActiveRunnerNearPosition(runners, exitPosition, safeRunnerPressureDistance))
                {
                    sentinel = candidate;
                    deniedExitIndex = j;
                    return true;
                }
            }
        }

        return false;
    }

    public static bool TryFindEnclosure(
        IReadOnlyList<SentinelAgent> sentinels,
        RunnerAgent runner,
        float maxDistance,
        out SentinelAgent first,
        out SentinelAgent second,
        out SentinelAgent third)
    {
        first = null;
        second = null;
        third = null;
        if (sentinels == null || runner == null || !runner.IsAlive)
        {
            return false;
        }

        Vector3 runnerPosition = Flatten(runner.transform.position);
        List<SentinelAgent> nearby = new List<SentinelAgent>();
        for (int i = 0; i < sentinels.Count; i++)
        {
            SentinelAgent sentinel = sentinels[i];
            if (sentinel == null || !sentinel.IsAlive)
            {
                continue;
            }

            if (Vector3.Distance(Flatten(sentinel.transform.position), runnerPosition) <= maxDistance)
            {
                nearby.Add(sentinel);
            }
        }

        if (nearby.Count < 3)
        {
            return false;
        }

        first = nearby[0];
        second = nearby[1];
        third = nearby[2];
        return HasDiverseAngles(runnerPosition, first, second, third);
    }

    public static bool TryFindDeadEndForcing(
        IReadOnlyList<SentinelAgent> sentinels,
        RunnerAgent runner,
        float sentinelMaxDistance,
        float wallProbeDistance,
        LayerMask blockingMask,
        out SentinelAgent pressureSentinel)
    {
        pressureSentinel = null;
        if (sentinels == null || runner == null || !runner.IsAlive)
        {
            return false;
        }

        int blockedDirections = CountBlockedCardinalDirections(runner.transform.position, wallProbeDistance, blockingMask);
        if (blockedDirections < 2)
        {
            return false;
        }

        Vector3 runnerPosition = Flatten(runner.transform.position);
        for (int i = 0; i < sentinels.Count; i++)
        {
            SentinelAgent sentinel = sentinels[i];
            if (sentinel == null || !sentinel.IsAlive)
            {
                continue;
            }

            if (Vector3.Distance(Flatten(sentinel.transform.position), runnerPosition) <= sentinelMaxDistance)
            {
                pressureSentinel = sentinel;
                return true;
            }
        }

        return false;
    }

    public static bool TryFindCorridorControl(
        IReadOnlyList<SentinelAgent> sentinels,
        RunnerAgent runner,
        float sentinelMaxDistance,
        float wallProbeDistance,
        LayerMask blockingMask,
        out SentinelAgent first,
        out SentinelAgent second)
    {
        first = null;
        second = null;
        if (sentinels == null || runner == null || !runner.IsAlive)
        {
            return false;
        }

        int blockedDirections = CountBlockedCardinalDirections(runner.transform.position, wallProbeDistance, blockingMask);
        if (blockedDirections < 3)
        {
            return false;
        }

        return TryFindPincer(sentinels, runner, sentinelMaxDistance, out first, out second);
    }

    public static bool TryFindClusterPenalty(
        IReadOnlyList<SentinelAgent> sentinels,
        float minSeparation,
        out SentinelAgent first,
        out SentinelAgent second)
    {
        first = null;
        second = null;
        if (sentinels == null)
        {
            return false;
        }

        float safeMinSeparation = Mathf.Max(0.1f, minSeparation);
        for (int i = 0; i < sentinels.Count; i++)
        {
            SentinelAgent a = sentinels[i];
            if (a == null || !a.IsAlive)
            {
                continue;
            }

            for (int j = i + 1; j < sentinels.Count; j++)
            {
                SentinelAgent b = sentinels[j];
                if (b == null || !b.IsAlive)
                {
                    continue;
                }

                if (Vector3.Distance(Flatten(a.transform.position), Flatten(b.transform.position)) < safeMinSeparation)
                {
                    first = a;
                    second = b;
                    return true;
                }
            }
        }

        return false;
    }

    private static Vector3 Flatten(Vector3 value)
    {
        value.y = 0f;
        return value;
    }

    private static bool HasActiveRunnerNearPosition(
        IReadOnlyList<RunnerAgent> runners,
        Vector3 position,
        float maxDistance)
    {
        if (runners == null)
        {
            return false;
        }

        for (int i = 0; i < runners.Count; i++)
        {
            RunnerAgent runner = runners[i];
            if (runner == null || !runner.IsAlive || runner.IsCaptured)
            {
                continue;
            }

            if (Vector3.Distance(Flatten(runner.transform.position), position) <= maxDistance)
            {
                return true;
            }
        }

        return false;
    }

    private static bool HasDiverseAngles(
        Vector3 runnerPosition,
        SentinelAgent first,
        SentinelAgent second,
        SentinelAgent third)
    {
        Vector3 a = (Flatten(first.transform.position) - runnerPosition).normalized;
        Vector3 b = (Flatten(second.transform.position) - runnerPosition).normalized;
        Vector3 c = (Flatten(third.transform.position) - runnerPosition).normalized;
        return Vector3.Dot(a, b) < 0.7f && Vector3.Dot(a, c) < 0.7f && Vector3.Dot(b, c) < 0.7f;
    }

    private static int CountBlockedCardinalDirections(Vector3 position, float distance, LayerMask blockingMask)
    {
        Vector3 origin = position + Vector3.up * 0.25f;
        int blocked = 0;
        if (Physics.Raycast(origin, Vector3.forward, distance, blockingMask))
        {
            blocked++;
        }

        if (Physics.Raycast(origin, Vector3.back, distance, blockingMask))
        {
            blocked++;
        }

        if (Physics.Raycast(origin, Vector3.left, distance, blockingMask))
        {
            blocked++;
        }

        if (Physics.Raycast(origin, Vector3.right, distance, blockingMask))
        {
            blocked++;
        }

        return blocked;
    }
}
