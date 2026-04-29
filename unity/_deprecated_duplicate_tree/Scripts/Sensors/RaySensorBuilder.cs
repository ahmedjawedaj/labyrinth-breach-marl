using System.Collections.Generic;
using UnityEngine;

public enum RaySensorHitType
{
    None,
    Wall,
    Exit,
    Teammate,
    Opponent,
    Other
}

public struct RaySensorReading
{
    public float NormalizedDistance;
    public RaySensorHitType HitType;
    public Vector3 Direction;
}

public static class RaySensorBuilder
{
    public const int ValuesPerRay = 6;

    public static void Append360RayObservations(
        BaseAgent observer,
        int rayCount,
        float maxDistance,
        LayerMask raycastMask,
        List<float> observations,
        bool enabled)
    {
        int safeRayCount = Mathf.Max(0, rayCount);
        if (!enabled || observer == null)
        {
            AppendEmptyRayObservations(safeRayCount, observations);
            return;
        }

        for (int i = 0; i < safeRayCount; i++)
        {
            float angle = safeRayCount <= 1 ? 0f : (360f / safeRayCount) * i;
            Vector3 direction = Quaternion.Euler(0f, angle, 0f) * observer.transform.forward;
            RaySensorReading reading = CastRay(observer, direction.normalized, maxDistance, raycastMask);
            AppendReading(reading, observations);
        }
    }

    public static RaySensorReading CastRay(
        BaseAgent observer,
        Vector3 direction,
        float maxDistance,
        LayerMask raycastMask,
        float originHeight = 0.5f)
    {
        RaySensorReading reading = new RaySensorReading
        {
            NormalizedDistance = 1f,
            HitType = RaySensorHitType.None,
            Direction = direction
        };

        Vector3 origin = observer.transform.position + Vector3.up * originHeight;
        RaycastHit[] hits = Physics.RaycastAll(origin, direction, maxDistance, raycastMask);
        System.Array.Sort(hits, (left, right) => left.distance.CompareTo(right.distance));
        for (int i = 0; i < hits.Length; i++)
        {
            BaseAgent hitAgent = hits[i].collider.GetComponentInParent<BaseAgent>();
            if (hitAgent == observer)
            {
                continue;
            }

            reading.NormalizedDistance = Mathf.Clamp01(hits[i].distance / Mathf.Max(0.001f, maxDistance));
            reading.HitType = ClassifyHit(observer, hits[i].collider);
            return reading;
        }

        return reading;
    }

    private static RaySensorHitType ClassifyHit(BaseAgent observer, Collider collider)
    {
        if (collider == null)
        {
            return RaySensorHitType.None;
        }

        if (collider.tag == "Wall")
        {
            return RaySensorHitType.Wall;
        }

        if (collider.tag == "Exit")
        {
            return RaySensorHitType.Exit;
        }

        BaseAgent hitAgent = collider.GetComponentInParent<BaseAgent>();
        if (hitAgent != null)
        {
            return hitAgent.Team == observer.Team ? RaySensorHitType.Teammate : RaySensorHitType.Opponent;
        }

        return RaySensorHitType.Other;
    }

    private static void AppendEmptyRayObservations(int rayCount, List<float> observations)
    {
        for (int i = 0; i < rayCount * ValuesPerRay; i++)
        {
            observations.Add(0f);
        }
    }

    private static void AppendReading(RaySensorReading reading, List<float> observations)
    {
        observations.Add(reading.NormalizedDistance);
        observations.Add(reading.HitType == RaySensorHitType.Wall ? 1f : 0f);
        observations.Add(reading.HitType == RaySensorHitType.Exit ? 1f : 0f);
        observations.Add(reading.HitType == RaySensorHitType.Teammate ? 1f : 0f);
        observations.Add(reading.HitType == RaySensorHitType.Opponent ? 1f : 0f);
        observations.Add(reading.HitType == RaySensorHitType.Other ? 1f : 0f);
    }
}
