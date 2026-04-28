using UnityEngine;

public class LastKnownPositionMemory
{
    private const float MinimumConfidence = 0f;
    private const float MaximumConfidence = 1f;

    private string currentVisibleTargetId = string.Empty;
    private string lastKnownTargetId = string.Empty;
    private Vector3 lastKnownTargetPosition;
    private float timeSinceLastSeen;
    private bool lastKnownValid;
    private float confidence;

    public string CurrentVisibleTargetId => currentVisibleTargetId;
    public string LastKnownTargetId => lastKnownTargetId;
    public Vector3 LastKnownTargetPosition => lastKnownTargetPosition;
    public float TimeSinceLastSeen => timeSinceLastSeen;
    public bool LastKnownValid => lastKnownValid;
    public float Confidence => confidence;

    public void Reset()
    {
        currentVisibleTargetId = string.Empty;
        lastKnownTargetId = string.Empty;
        lastKnownTargetPosition = Vector3.zero;
        timeSinceLastSeen = 0f;
        lastKnownValid = false;
        confidence = MinimumConfidence;
    }

    public void UpdateVisibleTarget(BaseAgent target)
    {
        if (target == null)
        {
            MarkNoVisibleTarget(Time.deltaTime, 1f);
            return;
        }

        currentVisibleTargetId = target.AgentId;
        lastKnownTargetId = target.AgentId;
        lastKnownTargetPosition = target.transform.position;
        timeSinceLastSeen = 0f;
        lastKnownValid = true;
        confidence = MaximumConfidence;
    }

    public void MarkNoVisibleTarget(float deltaTime, float confidenceDecaySeconds)
    {
        currentVisibleTargetId = string.Empty;
        if (!lastKnownValid)
        {
            return;
        }

        timeSinceLastSeen += Mathf.Max(0f, deltaTime);
        if (confidenceDecaySeconds <= 0f)
        {
            confidence = MinimumConfidence;
        }
        else
        {
            confidence = Mathf.Clamp01(1f - (timeSinceLastSeen / confidenceDecaySeconds));
        }

        if (confidence <= MinimumConfidence)
        {
            lastKnownValid = false;
        }
    }

    public void ClearIfTargetInvalid(BaseAgent target)
    {
        if (target == null)
        {
            return;
        }

        if (!target.IsAlive && lastKnownTargetId == target.AgentId)
        {
            Reset();
        }
    }

    public void AppendObservation(
        BaseAgent observer,
        float positionScale,
        float timeScale,
        System.Collections.Generic.List<float> observations)
    {
        Vector3 relativePosition = lastKnownValid && observer != null
            ? (lastKnownTargetPosition - observer.transform.position) / Mathf.Max(1f, positionScale)
            : Vector3.zero;

        observations.Add(relativePosition.x);
        observations.Add(relativePosition.y);
        observations.Add(relativePosition.z);
        observations.Add(lastKnownValid ? 1f : 0f);
        observations.Add(Mathf.Clamp01(timeSinceLastSeen / Mathf.Max(1f, timeScale)));
        observations.Add(confidence);
    }

    public void DrawDebug(BaseAgent observer, Color color, bool drawLabel)
    {
        if (observer == null || !lastKnownValid)
        {
            return;
        }

        Color memoryColor = new Color(color.r, color.g, color.b, Mathf.Clamp(confidence, 0.25f, 1f));
        Vector3 markerPosition = lastKnownTargetPosition + Vector3.up * 0.25f;
        DebugDrawUtils.DrawSphere(markerPosition, 0.25f, memoryColor);
        DebugDrawUtils.DrawLine(observer.transform.position + Vector3.up * 0.35f, markerPosition, memoryColor);

        if (drawLabel)
        {
            DebugDrawUtils.DrawLabel(
                markerPosition + Vector3.up * 0.45f,
                $"last seen: {lastKnownTargetId}\n{timeSinceLastSeen:0.0}s ago\nconf: {confidence:0.00}",
                memoryColor);
        }
    }
}
