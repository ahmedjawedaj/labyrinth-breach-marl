using UnityEngine;

public class SentinelAgent : BaseAgent
{
    [Header("Sentinel Settings")]
    [SerializeField] private float captureRadius = 1.25f;

    public float CaptureRadius => captureRadius;

    public void SetCaptureRadius(float configuredCaptureRadius)
    {
        captureRadius = Mathf.Max(0f, configuredCaptureRadius);
    }

    public bool IsRunnerInCaptureRange(RunnerAgent runner)
    {
        if (runner == null || !IsAlive || !runner.IsAlive || runner.IsCaptured)
        {
            return false;
        }

        return Vector3.Distance(transform.position, runner.transform.position) <= captureRadius;
    }

    public bool TryCaptureRunner(RunnerAgent runner, out float distance)
    {
        distance = float.MaxValue;
        if (runner == null || !IsAlive || !runner.IsAlive || runner.IsCaptured)
        {
            return false;
        }

        distance = Vector3.Distance(transform.position, runner.transform.position);
        if (distance > captureRadius)
        {
            return false;
        }

        return runner.TryMarkCaptured();
    }

    public void OnRunnerCaptured(RunnerAgent runner)
    {
        // Hook for future Sentinel-specific logging, animation, or reward event forwarding.
    }

    protected override void Awake()
    {
        base.Awake();
        Configure(AgentTeam.Sentinel, MoveSpeed, string.IsNullOrEmpty(AgentId) ? "Sentinel" : AgentId);
    }
}
