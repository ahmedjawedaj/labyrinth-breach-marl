using System.Collections.Generic;
using UnityEngine;

public static class EntityBufferSensorWriter
{
    public const int ValuesPerEntity = 10;

    public static void AppendEntityRows(
        BaseAgent observer,
        IReadOnlyList<BaseAgent> entities,
        float maxDistance,
        float maxSpeed,
        LayerMask visibilityBlockingLayers,
        bool includeTeammates,
        bool includeOpponents,
        bool enabled,
        List<float> rows)
    {
        if (!enabled || observer == null)
        {
            return;
        }

        for (int i = 0; i < entities.Count; i++)
        {
            BaseAgent entity = entities[i];
            if (entity == null || entity == observer)
            {
                continue;
            }

            bool isTeammate = entity.Team == observer.Team;
            if ((isTeammate && !includeTeammates) || (!isTeammate && !includeOpponents))
            {
                continue;
            }

            AppendEntityRow(observer, entity, maxDistance, maxSpeed, visibilityBlockingLayers, rows);
        }
    }

    public static void AppendEntityRow(
        BaseAgent observer,
        BaseAgent entity,
        float maxDistance,
        float maxSpeed,
        LayerMask visibilityBlockingLayers,
        List<float> rows)
    {
        Vector3 relativePosition = (entity.transform.position - observer.transform.position) / Mathf.Max(1f, maxDistance);
        Vector3 relativeVelocity = (entity.Velocity - observer.Velocity) / Mathf.Max(1f, maxSpeed);
        bool visible = VisibilityTracker.HasLineOfSight(observer, entity, maxDistance, visibilityBlockingLayers);

        rows.Add(relativePosition.x);
        rows.Add(relativePosition.y);
        rows.Add(relativePosition.z);
        rows.Add(relativeVelocity.x);
        rows.Add(relativeVelocity.y);
        rows.Add(relativeVelocity.z);
        rows.Add(entity.Team == AgentTeam.Sentinel ? 1f : 0f);
        rows.Add(entity.Team == AgentTeam.Runner ? 1f : 0f);
        rows.Add(entity.IsAlive ? 1f : 0f);
        rows.Add(visible ? 1f : 0f);
    }
}
