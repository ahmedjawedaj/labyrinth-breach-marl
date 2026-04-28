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

    public static List<float> AssembleVector(
        BaseAgent agent,
        PursuitEvasionEnvController environmentController)
    {
        List<float> observations = new List<float>(160);
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
}
