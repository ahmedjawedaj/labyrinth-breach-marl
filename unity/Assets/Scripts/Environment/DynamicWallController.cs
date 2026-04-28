using System.Collections.Generic;
using UnityEngine;

public class DynamicWallController : MonoBehaviour
{
    [SerializeField] private bool shiftsEnabled;
    [SerializeField] private float shiftIntervalSeconds = 15f;
    [SerializeField] private int shiftIntensity = 2;
    [SerializeField] private float safeBufferAroundAgents = 1.5f;
    [SerializeField] private bool allowExitBlocking;
    [SerializeField] private float loweredOffset = 3f;

    private readonly List<DynamicWallPillar> walls = new List<DynamicWallPillar>();
    private readonly List<BaseAgent> agents = new List<BaseAgent>();
    private PursuitEvasionEnvController environmentController;
    private float nextShiftTime;
    private int shiftCount;

    public float ShiftIntervalSeconds => shiftIntervalSeconds;
    public float TimeUntilNextShift => shiftsEnabled ? Mathf.Max(0f, nextShiftTime - Time.time) : 0f;
    public int ShiftCount => shiftCount;

    public void Configure(
        bool enabled,
        float intervalSeconds,
        int intensity,
        float safeBuffer,
        bool allowBlockingExits,
        float wallLoweredOffset)
    {
        shiftsEnabled = enabled;
        shiftIntervalSeconds = Mathf.Max(0.1f, intervalSeconds);
        shiftIntensity = Mathf.Max(0, intensity);
        safeBufferAroundAgents = Mathf.Max(0f, safeBuffer);
        allowExitBlocking = allowBlockingExits;
        loweredOffset = Mathf.Max(0.1f, wallLoweredOffset);
        nextShiftTime = Time.time + shiftIntervalSeconds;
    }

    public void RegisterWall(DynamicWallPillar wall)
    {
        if (wall == null || walls.Contains(wall))
        {
            return;
        }

        walls.Add(wall);
    }

    public void ClearWalls()
    {
        walls.Clear();
        shiftCount = 0;
        nextShiftTime = Time.time + shiftIntervalSeconds;
    }

    public void ResetWallStates()
    {
        for (int i = 0; i < walls.Count; i++)
        {
            if (walls[i] != null)
            {
                walls[i].SetRaised(true, true);
            }
        }

        shiftCount = 0;
        nextShiftTime = Time.time + shiftIntervalSeconds;
    }

    private void Update()
    {
        if (!shiftsEnabled || shiftIntensity <= 0 || Time.time < nextShiftTime)
        {
            return;
        }

        ShiftWalls();
        nextShiftTime = Time.time + shiftIntervalSeconds;
    }

    private void ShiftWalls()
    {
        if (environmentController == null)
        {
            environmentController = FindFirstObjectByType<PursuitEvasionEnvController>();
        }

        agents.Clear();
        if (environmentController != null)
        {
            environmentController.GetAllAgentsForObservation(agents);
        }

        int changed = 0;
        int attempts = 0;
        int maxAttempts = Mathf.Max(shiftIntensity * 8, walls.Count);
        while (changed < shiftIntensity && attempts < maxAttempts && walls.Count > 0)
        {
            attempts++;
            DynamicWallPillar wall = walls[Random.Range(0, walls.Count)];
            if (wall == null || !IsSafeToShift(wall))
            {
                continue;
            }

            wall.SetRaised(!wall.IsRaised);
            changed++;
        }

        shiftCount++;
        if (environmentController != null)
        {
            environmentController.RecordWallShift(changed, shiftCount);
            environmentController.SanitizeAllAgentPositions();
        }
    }

    private bool IsSafeToShift(DynamicWallPillar wall)
    {
        Vector3 wallPosition = wall.RaisedPosition;
        for (int i = 0; i < agents.Count; i++)
        {
            BaseAgent agent = agents[i];
            if (agent == null || !agent.IsAlive)
            {
                continue;
            }

            if (Vector3.Distance(agent.transform.position, wallPosition) < safeBufferAroundAgents)
            {
                return false;
            }
        }

        if (!allowExitBlocking && wall.CompareTag("ExitGuard"))
        {
            return false;
        }

        return true;
    }
}
