using System.Collections.Generic;
using UnityEngine;

public static class VisibilityTracker
{
    public static bool HasLineOfSight(
        BaseAgent observer,
        BaseAgent target,
        float maxDistance,
        LayerMask blockingLayers,
        float eyeHeight = 0.5f)
    {
        if (observer == null || target == null || !observer.IsAlive || !target.IsAlive)
        {
            return false;
        }

        Vector3 origin = observer.transform.position + Vector3.up * eyeHeight;
        Vector3 destination = target.transform.position + Vector3.up * eyeHeight;
        Vector3 direction = destination - origin;
        float distance = direction.magnitude;
        if (distance <= 0.0001f || distance > maxDistance)
        {
            return false;
        }

        RaycastHit[] hits = Physics.RaycastAll(origin, direction.normalized, distance, blockingLayers);
        System.Array.Sort(hits, (left, right) => left.distance.CompareTo(right.distance));
        for (int i = 0; i < hits.Length; i++)
        {
            BaseAgent hitAgent = hits[i].collider.GetComponentInParent<BaseAgent>();
            if (hitAgent == observer)
            {
                continue;
            }

            return hitAgent == target;
        }

        return true;
    }

    public static BaseAgent FindNearestVisibleOpponent(
        BaseAgent observer,
        IReadOnlyList<BaseAgent> candidates,
        float maxDistance,
        LayerMask blockingLayers)
    {
        BaseAgent nearest = null;
        float nearestDistanceSquared = float.MaxValue;

        for (int i = 0; i < candidates.Count; i++)
        {
            BaseAgent candidate = candidates[i];
            if (candidate == null || candidate.Team == observer.Team)
            {
                continue;
            }

            if (!HasLineOfSight(observer, candidate, maxDistance, blockingLayers))
            {
                continue;
            }

            float distanceSquared = (candidate.transform.position - observer.transform.position).sqrMagnitude;
            if (distanceSquared < nearestDistanceSquared)
            {
                nearest = candidate;
                nearestDistanceSquared = distanceSquared;
            }
        }

        return nearest;
    }
}
