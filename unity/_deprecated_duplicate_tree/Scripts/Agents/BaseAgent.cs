using System.Collections.Generic;
using Unity.MLAgents;
using Unity.MLAgents.Actuators;
using Unity.MLAgents.Policies;
using Unity.MLAgents.Sensors;
using UnityEngine;

public enum AgentTeam
{
    Sentinel,
    Runner
}

public abstract class BaseAgent : Agent
{
    [Header("Identity")]
    [SerializeField] private AgentTeam team;
    [SerializeField] private string agentId;

    [Header("Movement")]
    [SerializeField] private float moveSpeed = 4f;
    [SerializeField] private bool enableKeyboardMovement;

    [Header("ML-Agents")]
    [SerializeField] private bool configureMlAgentsComponents = true;
    [SerializeField] private int decisionPeriod = 5;

    [Header("Debug")]
    [SerializeField] private bool debugDraw = true;
    [SerializeField] private Color debugColor = Color.white;
    [SerializeField] private float debugRadius = 0.6f;

    private Vector3 spawnPosition;
    private Quaternion spawnRotation;
    private Vector3 velocity;
    private bool isAlive = true;
    private float cumulativeReward;
    private readonly LastKnownPositionMemory targetMemory = new LastKnownPositionMemory();
    private PursuitEvasionEnvController environmentController;

    public AgentTeam Team => team;
    public string AgentId => agentId;
    public float MoveSpeed => moveSpeed;
    public Vector3 Velocity => velocity;
    public bool IsAlive => isAlive;
    public float CumulativeReward => cumulativeReward;
    public LastKnownPositionMemory TargetMemory => targetMemory;

    public virtual void Configure(AgentTeam configuredTeam, float configuredSpeed, string configuredId)
    {
        team = configuredTeam;
        moveSpeed = configuredSpeed;
        agentId = configuredId;
        EnsureMlAgentsComponents();
    }

    public void SetSpawnPose(Vector3 position, Quaternion rotation)
    {
        spawnPosition = position;
        spawnRotation = rotation;
    }

    public virtual void ResetState()
    {
        isAlive = true;
        velocity = Vector3.zero;
        cumulativeReward = 0f;
        ClearEpisodeMemoryState();
        gameObject.SetActive(true);
        transform.SetPositionAndRotation(spawnPosition, spawnRotation);
    }

    public virtual void Deactivate()
    {
        isAlive = false;
        velocity = Vector3.zero;
    }

    public virtual void ApplyReward(float rewardAmount)
    {
        cumulativeReward += rewardAmount;
        AddReward(rewardAmount);
    }

    public virtual void ClearEpisodeMemoryState()
    {
        targetMemory.Reset();
    }

    public SelfStateObservation GetSelfStateObservation()
    {
        return new SelfStateObservation
        {
            Position = transform.position,
            Velocity = velocity,
            Heading = transform.forward,
            Alive = isAlive
        };
    }

    public void AppendSelfStateObservations(List<float> observations, float positionScale)
    {
        SelfStateObservation selfState = GetSelfStateObservation();
        float safePositionScale = Mathf.Max(1f, positionScale);
        observations.Add(selfState.Position.x / safePositionScale);
        observations.Add(selfState.Position.y / safePositionScale);
        observations.Add(selfState.Position.z / safePositionScale);
        observations.Add(selfState.Velocity.x / Mathf.Max(1f, moveSpeed));
        observations.Add(selfState.Velocity.y / Mathf.Max(1f, moveSpeed));
        observations.Add(selfState.Velocity.z / Mathf.Max(1f, moveSpeed));
        observations.Add(selfState.Heading.x);
        observations.Add(selfState.Heading.z);
        observations.Add(selfState.Alive ? 1f : 0f);
        observations.Add(team == AgentTeam.Sentinel ? 1f : -1f);
    }

    public List<float> BuildObservationVector(PursuitEvasionEnvController environmentController)
    {
        return environmentController != null
            ? environmentController.GetObservationVector(this)
            : new List<float>();
    }

    public List<float> BuildEntityObservationRows(PursuitEvasionEnvController environmentController)
    {
        return ObservationAssembler.AssembleEntityRows(this, environmentController);
    }

    public virtual void Move(Vector3 direction)
    {
        if (!isAlive)
        {
            return;
        }

        Vector3 normalizedDirection = direction.sqrMagnitude > 1f ? direction.normalized : direction;
        velocity = normalizedDirection * moveSpeed;
        transform.position += velocity * Time.deltaTime;

        if (normalizedDirection.sqrMagnitude > 0.0001f)
        {
            transform.rotation = Quaternion.LookRotation(normalizedDirection, Vector3.up);
        }
    }

    public string GetDebugState()
    {
        return $"{agentId} team={team} alive={isAlive} position={transform.position}";
    }

    public override void CollectObservations(VectorSensor sensor)
    {
        if (environmentController == null)
        {
            environmentController = FindFirstObjectByType<PursuitEvasionEnvController>();
        }

        List<float> observations = BuildObservationVector(environmentController);
        int expectedSize = GetExpectedVectorObservationSize();
        for (int i = 0; i < expectedSize; i++)
        {
            sensor.AddObservation(i < observations.Count ? observations[i] : 0f);
        }
    }

    public override void OnActionReceived(ActionBuffers actions)
    {
        ActionSegment<float> continuousActions = actions.ContinuousActions;
        float horizontal = continuousActions.Length > 0 ? Mathf.Clamp(continuousActions[0], -1f, 1f) : 0f;
        float vertical = continuousActions.Length > 1 ? Mathf.Clamp(continuousActions[1], -1f, 1f) : 0f;
        Move(new Vector3(horizontal, 0f, vertical));
    }

    public override void Heuristic(in ActionBuffers actionsOut)
    {
        ActionSegment<float> continuousActions = actionsOut.ContinuousActions;
        if (continuousActions.Length > 0)
        {
            continuousActions[0] = Input.GetAxisRaw("Horizontal");
        }

        if (continuousActions.Length > 1)
        {
            continuousActions[1] = Input.GetAxisRaw("Vertical");
        }
    }

    public override void OnEpisodeBegin()
    {
        if (environmentController == null)
        {
            environmentController = FindFirstObjectByType<PursuitEvasionEnvController>();
        }

        if (environmentController != null && !environmentController.EpisodeActive)
        {
            environmentController.BeginEpisode();
        }
    }

    protected virtual void Awake()
    {
        SetSpawnPose(transform.position, transform.rotation);
        environmentController = FindFirstObjectByType<PursuitEvasionEnvController>();
        EnsureMlAgentsComponents();
    }

    protected virtual void Update()
    {
        if (!enableKeyboardMovement)
        {
            return;
        }

        float horizontal = Input.GetAxisRaw("Horizontal");
        float vertical = Input.GetAxisRaw("Vertical");
        Move(new Vector3(horizontal, 0f, vertical));
    }

    private int GetExpectedVectorObservationSize()
    {
        int rayCount = team == AgentTeam.Sentinel ? 14 : 16;
        return ObservationAssembler.SelfStateSize
            + ObservationAssembler.EnvironmentContextSize
            + ObservationAssembler.MemorySize
            + rayCount * RaySensorBuilder.ValuesPerRay;
    }

    private void EnsureMlAgentsComponents()
    {
        if (!configureMlAgentsComponents)
        {
            // BehaviorParameters and DecisionRequester are pre-baked in the prefab.
            // Just enforce BehaviorType = Default so training mode works correctly.
            BehaviorParameters existing = GetComponent<BehaviorParameters>();
            if (existing != null)
            {
                existing.BehaviorType = BehaviorType.Default;
                existing.TeamId = team == AgentTeam.Sentinel ? 0 : 1;
            }

            return;
        }

        BehaviorParameters behaviorParameters = GetComponent<BehaviorParameters>();
        if (behaviorParameters == null)
        {
            behaviorParameters = gameObject.AddComponent<BehaviorParameters>();
        }

        behaviorParameters.BehaviorName = team == AgentTeam.Sentinel ? "Sentinel" : "Runner";
        behaviorParameters.BehaviorType = BehaviorType.Default;
        behaviorParameters.TeamId = team == AgentTeam.Sentinel ? 0 : 1;
        behaviorParameters.BrainParameters.VectorObservationSize = GetExpectedVectorObservationSize();
        behaviorParameters.BrainParameters.NumStackedVectorObservations = 1;
        behaviorParameters.BrainParameters.ActionSpec = ActionSpec.MakeContinuous(2);

        DecisionRequester decisionRequester = GetComponent<DecisionRequester>();
        if (decisionRequester == null)
        {
            decisionRequester = gameObject.AddComponent<DecisionRequester>();
        }

        decisionRequester.DecisionPeriod = Mathf.Max(1, decisionPeriod);
        decisionRequester.TakeActionsBetweenDecisions = true;
    }

    protected virtual void OnDrawGizmos()
    {
        if (!debugDraw)
        {
            return;
        }

        Gizmos.color = debugColor;
        Gizmos.DrawWireSphere(transform.position, debugRadius);
        Gizmos.DrawLine(transform.position, transform.position + transform.forward);
    }
}
