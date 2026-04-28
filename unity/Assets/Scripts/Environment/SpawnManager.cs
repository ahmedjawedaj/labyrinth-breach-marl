using System.Collections.Generic;
using UnityEngine;
#if UNITY_EDITOR
using UnityEditor;
#endif

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
    [SerializeField] private PursuitEvasionEnvController environmentController;

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
            sentinelSpawnPositions = ConstrainSpawnPositions(configuredSentinelSpawns);
        }

        if (configuredRunnerSpawns != null && configuredRunnerSpawns.Length > 0)
        {
            runnerSpawnPositions = ConstrainSpawnPositions(configuredRunnerSpawns);
        }

        ApplySpawnArraysToActiveAgents();
    }

    private void Start()
    {
        TryAutoRecoverSceneReferences();
        if (spawnedAgents.Count == 0)
        {
            SpawnAgents();
        }
    }

    private void OnValidate()
    {
        TryAutoRecoverSceneReferences();
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
        TryAutoRecoverSceneReferences();
        ClearSpawnedAgents();
        SpawnTeam(sentinelPrefab, sentinelSpawnPositions, AgentTeam.Sentinel, sentinelSpeed, "Sentinel");
        SpawnTeam(runnerPrefab, runnerSpawnPositions, AgentTeam.Runner, runnerSpeed, "Runner");
    }

    private void TryAutoRecoverSceneReferences()
    {
        if (environmentController == null)
        {
            environmentController = FindFirstObjectByType<PursuitEvasionEnvController>();
        }

        if (sentinelPrefab == null)
        {
            sentinelPrefab = TryFindPrefabByName("Sentinel");
        }

        if (runnerPrefab == null)
        {
            runnerPrefab = TryFindPrefabByName("Runner");
        }
    }

    private static GameObject TryFindPrefabByName(string prefabName)
    {
#if UNITY_EDITOR
        if (string.IsNullOrWhiteSpace(prefabName))
        {
            return null;
        }

        string[] guids = AssetDatabase.FindAssets($"t:Prefab {prefabName}");
        for (int i = 0; i < guids.Length; i++)
        {
            string path = AssetDatabase.GUIDToAssetPath(guids[i]);
            if (string.IsNullOrWhiteSpace(path))
            {
                continue;
            }

            GameObject asset = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            if (asset != null && asset.name == prefabName)
            {
                return asset;
            }
        }
#endif
        return null;
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
            Vector3 spawnPosition = spawnPositions[i];
            if (environmentController == null)
            {
                environmentController = FindFirstObjectByType<PursuitEvasionEnvController>();
            }

            if (environmentController != null)
            {
                spawnPosition = environmentController.ConstrainAgentPositionToArena(spawnPosition, 0.15f);
            }

            GameObject agent = Instantiate(prefab, spawnPosition, Quaternion.identity, agentParent);
            agent.name = $"{namePrefix}_{i + 1}";

            BaseAgent baseAgent = agent.GetComponent<BaseAgent>();
            if (baseAgent != null)
            {
                baseAgent.Configure(team, speed, agent.name);
                baseAgent.SetSpawnPose(spawnPosition, Quaternion.identity);
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

    private Vector3[] ConstrainSpawnPositions(Vector3[] positions)
    {
        Vector3[] constrained = new Vector3[positions.Length];
        if (environmentController == null)
        {
            environmentController = FindFirstObjectByType<PursuitEvasionEnvController>();
        }

        for (int i = 0; i < positions.Length; i++)
        {
            constrained[i] = environmentController != null
                ? environmentController.ConstrainAgentPositionToArena(positions[i], 0.15f)
                : positions[i];
        }

        return constrained;
    }

    private void ApplySpawnArraysToActiveAgents()
    {
        if (spawnedAgents.Count == 0)
        {
            return;
        }

        if (environmentController == null)
        {
            environmentController = FindFirstObjectByType<PursuitEvasionEnvController>();
        }

        int n = 0;
        for (int s = 0; s < sentinelSpawnPositions.Length; s++)
        {
            if (n >= spawnedAgents.Count || spawnedAgents[n] == null)
            {
                return;
            }

            BaseAgent agent = spawnedAgents[n].GetComponent<BaseAgent>();
            n++;
            if (agent == null)
            {
                continue;
            }

            Vector3 p = environmentController != null
                ? environmentController.ConstrainAgentPositionToArena(sentinelSpawnPositions[s], 0.15f)
                : sentinelSpawnPositions[s];
            agent.SetSpawnPose(p, Quaternion.identity);
            if (Application.isPlaying)
            {
                agent.transform.SetPositionAndRotation(p, Quaternion.identity);
            }
        }

        for (int r = 0; r < runnerSpawnPositions.Length; r++)
        {
            if (n >= spawnedAgents.Count || spawnedAgents[n] == null)
            {
                return;
            }

            BaseAgent agent = spawnedAgents[n].GetComponent<BaseAgent>();
            n++;
            if (agent == null)
            {
                continue;
            }

            Vector3 p = environmentController != null
                ? environmentController.ConstrainAgentPositionToArena(runnerSpawnPositions[r], 0.15f)
                : runnerSpawnPositions[r];
            agent.SetSpawnPose(p, Quaternion.identity);
            if (Application.isPlaying)
            {
                agent.transform.SetPositionAndRotation(p, Quaternion.identity);
            }
        }
    }
}
