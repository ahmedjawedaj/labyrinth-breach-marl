using System.Collections.Generic;
using UnityEngine;

public class SpawnManager : MonoBehaviour
{
    [Header("Prefabs")]
    [SerializeField] private GameObject sentinelPrefab;
    [SerializeField] private GameObject runnerPrefab;

    [Header("Spawn Positions")]
    [SerializeField]
    private Vector3[] sentinelSpawnPositions =
    {
        new Vector3(-6f, 0.5f, -4f),
        new Vector3(-6f, 0.5f, 0f),
        new Vector3(-6f, 0.5f, 4f)
    };

    [SerializeField]
    private Vector3[] runnerSpawnPositions =
    {
        new Vector3(6f, 0.5f, -2f),
        new Vector3(6f, 0.5f, 2f)
    };

    [Header("Agent Settings")]
    [SerializeField] private float sentinelSpeed = 4f;
    [SerializeField] private float runnerSpeed = 4.5f;
    [SerializeField] private Transform agentParent;

    private readonly List<GameObject> spawnedAgents = new List<GameObject>();

    public int ExpectedSentinelCount => sentinelSpawnPositions.Length;
    public int ExpectedRunnerCount => runnerSpawnPositions.Length;

    public void SetAgentDynamics(float configuredSentinelSpeed, float configuredRunnerSpeed)
    {
        sentinelSpeed = Mathf.Max(0f, configuredSentinelSpeed);
        runnerSpeed = Mathf.Max(0f, configuredRunnerSpeed);
        ApplyConfiguredSpeedsToExistingAgents();
    }

    public void SetSpawnPositions(Vector3[] configuredSentinelSpawns, Vector3[] configuredRunnerSpawns)
    {
        if (configuredSentinelSpawns != null && configuredSentinelSpawns.Length > 0)
        {
            sentinelSpawnPositions = configuredSentinelSpawns;
        }

        if (configuredRunnerSpawns != null && configuredRunnerSpawns.Length > 0)
        {
            runnerSpawnPositions = configuredRunnerSpawns;
        }
    }

    private void Start()
    {
        if (spawnedAgents.Count == 0)
        {
            SpawnAgents();
        }
    }

    [ContextMenu("Respawn Agents")]
    public void ResetSpawnedAgents()
    {
        if (spawnedAgents.Count == sentinelSpawnPositions.Length + runnerSpawnPositions.Length)
        {
            ResetExistingAgents();
            return;
        }

        SpawnAgents();
    }

    public void Reset()
    {
        ResetSpawnedAgents();
    }

    public void SpawnAgents()
    {
        ClearSpawnedAgents();
        SpawnTeam(sentinelPrefab, sentinelSpawnPositions, AgentTeam.Sentinel, sentinelSpeed, "Sentinel");
        SpawnTeam(runnerPrefab, runnerSpawnPositions, AgentTeam.Runner, runnerSpeed, "Runner");
    }

    public void GetSpawnedAgents(List<SentinelAgent> sentinels, List<RunnerAgent> runners)
    {
        sentinels.Clear();
        runners.Clear();

        for (int i = 0; i < spawnedAgents.Count; i++)
        {
            GameObject agent = spawnedAgents[i];
            if (agent == null)
            {
                continue;
            }

            SentinelAgent sentinel = agent.GetComponent<SentinelAgent>();
            if (sentinel != null)
            {
                sentinels.Add(sentinel);
                continue;
            }

            RunnerAgent runner = agent.GetComponent<RunnerAgent>();
            if (runner != null)
            {
                runners.Add(runner);
            }
        }
    }

    private void SpawnTeam(
        GameObject prefab,
        Vector3[] spawnPositions,
        AgentTeam team,
        float speed,
        string namePrefix)
    {
        if (prefab == null)
        {
            Debug.LogWarning($"{namePrefix} prefab is not assigned.", this);
            return;
        }

        for (int i = 0; i < spawnPositions.Length; i++)
        {
            GameObject agent = Instantiate(prefab, spawnPositions[i], Quaternion.identity, agentParent);
            agent.name = $"{namePrefix}_{i + 1}";

            BaseAgent baseAgent = agent.GetComponent<BaseAgent>();
            if (baseAgent != null)
            {
                baseAgent.Configure(team, speed, agent.name);
                baseAgent.SetSpawnPose(spawnPositions[i], Quaternion.identity);
            }

            spawnedAgents.Add(agent);
        }
    }

    private void ResetExistingAgents()
    {
        for (int i = 0; i < spawnedAgents.Count; i++)
        {
            if (spawnedAgents[i] == null)
            {
                SpawnAgents();
                return;
            }

            BaseAgent baseAgent = spawnedAgents[i].GetComponent<BaseAgent>();
            if (baseAgent != null)
            {
                ConfigureExistingAgent(baseAgent);
                baseAgent.ResetState();
            }
        }
    }

    private void ApplyConfiguredSpeedsToExistingAgents()
    {
        for (int i = 0; i < spawnedAgents.Count; i++)
        {
            if (spawnedAgents[i] == null)
            {
                continue;
            }

            BaseAgent baseAgent = spawnedAgents[i].GetComponent<BaseAgent>();
            if (baseAgent != null)
            {
                ConfigureExistingAgent(baseAgent);
            }
        }
    }

    private void ConfigureExistingAgent(BaseAgent baseAgent)
    {
        if (baseAgent.Team == AgentTeam.Sentinel)
        {
            baseAgent.Configure(AgentTeam.Sentinel, sentinelSpeed, baseAgent.AgentId);
        }
        else if (baseAgent.Team == AgentTeam.Runner)
        {
            baseAgent.Configure(AgentTeam.Runner, runnerSpeed, baseAgent.AgentId);
        }
    }

    private void ClearSpawnedAgents()
    {
        for (int i = spawnedAgents.Count - 1; i >= 0; i--)
        {
            GameObject agent = spawnedAgents[i];
            if (agent == null)
            {
                continue;
            }

            if (Application.isPlaying)
            {
                Destroy(agent);
            }
            else
            {
                DestroyImmediate(agent);
            }
        }

        spawnedAgents.Clear();
    }
}
