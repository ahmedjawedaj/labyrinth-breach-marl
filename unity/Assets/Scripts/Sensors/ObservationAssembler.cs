using System.Collections.Generic;
using UnityEngine;

public struct SelfStateObservation
{
    public Vector3 Position;
    public Vector3 Velocity;
    public Vector3 Heading;
    public bool Alive;
}

public struct EnvironmentContextObservation
{
    public float NormalizedTimeRemaining;
    public float NormalizedNearestExitDistance;
    public Vector3 NormalizedNearestExitDirection;
    public float NormalizedWallProximity;
    public float NormalizedWallShiftTimer;
}

public static class ObservationAssembler
{
    public const int SelfStateSize = 10;
    public const int EnvironmentContextSize = 7;
    public const int MemorySize = 6;
    public const int OpponentSummarySize = 10;

    public static List<float> AssembleVector(
        BaseAgent agent,
        PursuitEvasionEnvController environmentController)
    {
        List<float> observations = new List<float>(176);
        if (agent == null || environmentController == null)
        {
            return observations;
        }

        ObservationConfig observationConfig = environmentController.ActiveObservationConfig;
        agent.AppendSelfStateObservations(observations, environmentController.ObservationPositionScale);
        AppendEnvironmentContext(environmentController.GetEnvironmentContext(agent), observations, observationConfig.IncludeExitVector);

        RaySensorBuilder.Append360RayObservations(
            agent,
            environmentController.GetRayCount(agent),
            environmentController.RayMaxDistance,
            environmentController.ObservationRaycastMask,
            observations,
            observationConfig.UseRays);

        if (observationConfig.UseMemory)
        {
            agent.TargetMemory.AppendObservation(
                agent,
                environmentController.ObservationPositionScale,
                environmentController.ObservationMemoryTimeScale,
                observations);
        }
        else
        {
            AppendZeros(MemorySize, observations);
        }

        if (observationConfig.IncludeOpponentSummary)
        {
            AppendOpponentSummary(agent, environmentController, observations);
        }
        else
        {
            AppendZeros(OpponentSummarySize, observations);
        }

        return observations;
    }

    public static List<float> AssembleEntityRows(
        BaseAgent agent,
        PursuitEvasionEnvController environmentController)
    {
        List<float> rows = new List<float>();
        if (agent == null || environmentController == null)
        {
            return rows;
        }

        ObservationConfig observationConfig = environmentController.ActiveObservationConfig;
        List<BaseAgent> allAgents = new List<BaseAgent>();
        environmentController.GetAllAgentsForObservation(allAgents);

        EntityBufferSensorWriter.AppendEntityRows(
            agent,
            allAgents,
            environmentController.ObservationPositionScale,
            environmentController.ObservationMaxSpeed,
            environmentController.VisibilityBlockingMask,
            observationConfig.IncludeTeammates,
            observationConfig.IncludeOpponents,
            observationConfig.UseBufferSensors,
            rows);

        return rows;
    }

    private static void AppendEnvironmentContext(
        EnvironmentContextObservation context,
        List<float> observations,
        bool includeExitVector)
    {
        observations.Add(context.NormalizedTimeRemaining);
        observations.Add(context.NormalizedNearestExitDistance);
        if (includeExitVector)
        {
            observations.Add(context.NormalizedNearestExitDirection.x);
            observations.Add(context.NormalizedNearestExitDirection.y);
            observations.Add(context.NormalizedNearestExitDirection.z);
        }
        else
        {
            observations.Add(0f);
            observations.Add(0f);
            observations.Add(0f);
        }

        observations.Add(context.NormalizedWallProximity);
        observations.Add(context.NormalizedWallShiftTimer);
    }

    private static void AppendZeros(int count, List<float> observations)
    {
        for (int i = 0; i < count; i++)
        {
            observations.Add(0f);
        }
    }

    /// <summary>
    /// Nearest and second-nearest opponents in the observer's local XZ frame (e.g. negative Z = behind).
    /// This gives agents enough context to avoid tunnel-vision on a single opponent.
    /// </summary>
    private static void AppendOpponentSummary(
        BaseAgent agent,
        PursuitEvasionEnvController environmentController,
        List<float> observations)
    {
        List<BaseAgent> others = new List<BaseAgent>(8);
        environmentController.GetAllAgentsForObservation(others);
        BaseAgent nearest = null;
        BaseAgent secondNearest = null;
        float nearestSq = float.MaxValue;
        float secondNearestSq = float.MaxValue;
        for (int i = 0; i < others.Count; i++)
        {
            BaseAgent b = others[i];
            if (b == null || b == agent || b.Team == agent.Team || !b.IsAlive)
            {
                continue;
            }

            Vector3 delta = b.transform.position - agent.transform.position;
            delta.y = 0f;
            float s = delta.sqrMagnitude;
            if (s < nearestSq)
            {
                secondNearestSq = nearestSq;
                secondNearest = nearest;
                nearestSq = s;
                nearest = b;
            }
            else if (s < secondNearestSq)
            {
                secondNearestSq = s;
                secondNearest = b;
            }
        }

        AppendSingleOpponentSummary(agent, environmentController, nearest, nearestSq, observations);
        AppendSingleOpponentSummary(agent, environmentController, secondNearest, secondNearestSq, observations);
    }

    private static void AppendSingleOpponentSummary(
        BaseAgent observer,
        PursuitEvasionEnvController environmentController,
        BaseAgent opponent,
        float opponentDistanceSq,
        List<float> observations)
    {
        if (opponent == null)
        {
            observations.Add(1f);
            observations.Add(0f);
            observations.Add(0f);
            observations.Add(0f);
            observations.Add(0f);
            return;
        }

        float dist = Mathf.Sqrt(Mathf.Max(0f, opponentDistanceSq));
        float scale = Mathf.Max(1f, environmentController.RayMaxDistance);
        float distNorm = Mathf.Clamp01(dist / scale);
        Vector3 worldFlat = opponent.transform.position - observer.transform.position;
        worldFlat.y = 0f;
        float m = worldFlat.magnitude;
        float localX;
        float localZ;
        if (m < 1e-4f)
        {
            localX = 0f;
            localZ = 0f;
        }
        else
        {
            worldFlat /= m;
            Vector3 local = observer.transform.InverseTransformDirection(worldFlat);
            local.y = 0f;
            float lmag = new Vector2(local.x, local.z).magnitude;
            if (lmag > 1e-4f)
            {
                local.x /= lmag;
                local.z /= lmag;
            }

            localX = Mathf.Clamp(local.x, -1f, 1f);
            localZ = Mathf.Clamp(local.z, -1f, 1f);
        }

        observations.Add(distNorm);
        observations.Add(localX);
        observations.Add(localZ);

        bool los = VisibilityTracker.HasLineOfSight(
            observer,
            opponent,
            environmentController.RayMaxDistance,
            environmentController.VisibilityBlockingMask);
        observations.Add(los ? 1f : 0f);
        float pressureRange = Mathf.Max(4f, environmentController.RayMaxDistance * 0.4f);
        float pressure = Mathf.Clamp01(1f - dist / pressureRange);
        observations.Add(pressure);
    }
}
