using UnityEngine;

public class RunnerAgent : BaseAgent
{
    private bool isCaptured;
    private bool hasEscaped;

    public bool IsCaptured => isCaptured;
    public bool HasEscaped => hasEscaped;

    public override void ResetState()
    {
        base.ResetState();
        isCaptured = false;
        hasEscaped = false;
    }

    public void MarkEscaped()
    {
        if (isCaptured)
        {
            return;
        }

        hasEscaped = true;
        Deactivate();
    }

    public bool TryMarkCaptured()
    {
        if (isCaptured || !IsAlive)
        {
            return false;
        }

        isCaptured = true;
        Deactivate();
        return true;
    }

    public void MarkCaptured()
    {
        TryMarkCaptured();
    }

    protected override void Awake()
    {
        base.Awake();
        Configure(AgentTeam.Runner, MoveSpeed, string.IsNullOrEmpty(AgentId) ? "Runner" : AgentId);
    }

    protected override string GetDebugLifecycleState()
    {
        if (isCaptured)
        {
            return "Captured";
        }

        if (hasEscaped)
        {
            return "Escaped";
        }

        return IsAlive ? "Alive" : "Inactive";
    }
}
