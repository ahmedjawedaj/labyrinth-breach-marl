using System.Collections.Generic;
using UnityEngine;

public enum MazeMode
{
    Static,
    Dynamic
}

public class MazeGenerator : MonoBehaviour
{
    [Header("Maze")]
    [SerializeField] private MazeMode mazeMode = MazeMode.Static;
    [SerializeField] private int seed = 42;
    [SerializeField] private float cellSize = 2f;
    [SerializeField] private float wallHeight = 2f;
    [SerializeField] private float wallThickness = 1.8f;
    [SerializeField] private Material wallMaterial;
    [SerializeField] private Material exitMaterial;
    [SerializeField] private bool generateOnStart = true;
    [SerializeField] private bool mazeEnabled = true;
    [SerializeField] private bool randomizeSpawns;
    [SerializeField] private bool randomizeExits;

    [Header("References")]
    [SerializeField] private SpawnManager spawnManager;
    [SerializeField] private PursuitEvasionEnvController environmentController;
    [SerializeField] private DynamicWallController dynamicWallController;

    private readonly List<GameObject> generatedObjects = new List<GameObject>();
    private readonly List<Vector3> sentinelSpawns = new List<Vector3>();
    private readonly List<Vector3> runnerSpawns = new List<Vector3>();
    private readonly List<Vector3> exitPositions = new List<Vector3>();
    private bool generated;

    public IReadOnlyList<Vector3> SentinelSpawns => sentinelSpawns;
    public IReadOnlyList<Vector3> RunnerSpawns => runnerSpawns;
    public IReadOnlyList<Vector3> ExitPositions => exitPositions;
    public bool Generated => generated;

    private static readonly string[] Layout =
    {
        "#############",
        "#S...#....E.#",
        "#.#.#.#.###.#",
        "#.#...#...#.#",
        "#.###D###.#.#",
        "#...#...#...#",
        "###.#.#.#.###",
        "#...#D#...R.#",
        "#.###.###.#.#",
        "#S....#...#E#",
        "#.#.###.#.#.#",
        "#..R...#...S#",
        "#############"
    };

    private void Start()
    {
        if (generateOnStart)
        {
            GenerateIfNeeded();
        }
    }

    public void GenerateIfNeeded()
    {
        if (!generated)
        {
            Generate();
        }
    }

    public void ConfigureForCurriculum(
        bool enabled,
        MazeMode configuredMazeMode,
        int configuredSeed,
        bool shouldRandomizeSpawns,
        bool shouldRandomizeExits)
    {
        bool changed = mazeEnabled != enabled ||
            mazeMode != configuredMazeMode ||
            seed != configuredSeed ||
            randomizeSpawns != shouldRandomizeSpawns ||
            randomizeExits != shouldRandomizeExits;

        mazeEnabled = enabled;
        mazeMode = configuredMazeMode;
        seed = configuredSeed;
        randomizeSpawns = shouldRandomizeSpawns;
        randomizeExits = shouldRandomizeExits;

        if (changed)
        {
            generated = false;
        }
    }

    public void ConfigureRandomizationControls(
        int configuredSeed,
        bool shouldRandomizeSpawns,
        bool shouldRandomizeExits)
    {
        bool changed = seed != configuredSeed ||
            randomizeSpawns != shouldRandomizeSpawns ||
            randomizeExits != shouldRandomizeExits;

        seed = configuredSeed;
        randomizeSpawns = shouldRandomizeSpawns;
        randomizeExits = shouldRandomizeExits;

        if (changed)
        {
            generated = false;
        }
    }

    [ContextMenu("Generate Maze")]
    public void Generate()
    {
        ClearGeneratedObjects();
        sentinelSpawns.Clear();
        runnerSpawns.Clear();
        exitPositions.Clear();

        Random.InitState(seed);

        if (spawnManager == null)
        {
            spawnManager = FindFirstObjectByType<SpawnManager>();
        }

        if (environmentController == null)
        {
            environmentController = FindFirstObjectByType<PursuitEvasionEnvController>();
        }

        if (dynamicWallController == null)
        {
            dynamicWallController = FindFirstObjectByType<DynamicWallController>();
        }

        if (dynamicWallController != null)
        {
            dynamicWallController.ClearWalls();
        }

        if (!mazeEnabled)
        {
            AddOpenArenaSpawns();
            ApplySpawnPositions();
            generated = true;
            return;
        }

        List<Vector3> walkableCells = new List<Vector3>();
        for (int row = 0; row < Layout.Length; row++)
        {
            for (int column = 0; column < Layout[row].Length; column++)
            {
                char cell = Layout[row][column];
                Vector3 worldPosition = CellToWorld(row, column);
                switch (cell)
                {
                    case '#':
                        CreateWall(worldPosition, false);
                        break;
                    case 'D':
                        CreateWall(worldPosition, mazeMode == MazeMode.Dynamic);
                        break;
                    case 'S':
                        sentinelSpawns.Add(worldPosition + Vector3.up * 0.5f);
                        walkableCells.Add(worldPosition);
                        break;
                    case 'R':
                        runnerSpawns.Add(worldPosition + Vector3.up * 0.5f);
                        walkableCells.Add(worldPosition);
                        break;
                    case 'E':
                        exitPositions.Add(worldPosition);
                        walkableCells.Add(worldPosition);
                        break;
                    default:
                        walkableCells.Add(worldPosition);
                        break;
                }
            }
        }

        if (randomizeSpawns)
        {
            RandomizeSpawnPositions(walkableCells);
        }

        if (randomizeExits)
        {
            RandomizeExitPositions(walkableCells);
        }

        for (int i = 0; i < exitPositions.Count; i++)
        {
            CreateExitZone(exitPositions[i]);
        }

        EnsureSpawnCounts();
        ApplySpawnPositions();

        if (dynamicWallController != null)
        {
            dynamicWallController.ResetWallStates();
        }

        generated = true;
    }

    public bool IsSpawnSafe(Vector3 position)
    {
        for (int i = 0; i < generatedObjects.Count; i++)
        {
            GameObject generatedObject = generatedObjects[i];
            if (generatedObject == null || generatedObject.tag != "Wall")
            {
                continue;
            }

            if (Vector3.Distance(generatedObject.transform.position, position) < cellSize * 0.75f)
            {
                return false;
            }
        }

        return true;
    }

    private void AddOpenArenaSpawns()
    {
        sentinelSpawns.Add(new Vector3(-6f, 0.5f, -4f));
        sentinelSpawns.Add(new Vector3(-6f, 0.5f, 0f));
        sentinelSpawns.Add(new Vector3(-6f, 0.5f, 4f));
        runnerSpawns.Add(new Vector3(6f, 0.5f, -2f));
        runnerSpawns.Add(new Vector3(6f, 0.5f, 2f));
    }

    private void RandomizeSpawnPositions(List<Vector3> walkableCells)
    {
        List<Vector3> availableCells = new List<Vector3>(walkableCells);
        sentinelSpawns.Clear();
        runnerSpawns.Clear();

        for (int i = 0; i < 3; i++)
        {
            sentinelSpawns.Add(TakeRandomCell(availableCells, 0f) + Vector3.up * 0.5f);
        }

        for (int i = 0; i < 2; i++)
        {
            runnerSpawns.Add(TakeRandomCell(availableCells, cellSize * 2f) + Vector3.up * 0.5f);
        }
    }

    private void RandomizeExitPositions(List<Vector3> walkableCells)
    {
        List<Vector3> availableCells = new List<Vector3>(walkableCells);
        RemoveCellsNearSpawns(availableCells);
        exitPositions.Clear();

        for (int i = 0; i < 2 && availableCells.Count > 0; i++)
        {
            exitPositions.Add(TakeRandomCell(availableCells, cellSize * 2f));
        }
    }

    private Vector3 TakeRandomCell(List<Vector3> availableCells, float minDistanceFromExisting)
    {
        if (availableCells.Count == 0)
        {
            return Vector3.zero;
        }

        for (int attempt = 0; attempt < 32; attempt++)
        {
            int index = Random.Range(0, availableCells.Count);
            Vector3 candidate = availableCells[index];
            if (IsFarEnoughFromExisting(candidate, minDistanceFromExisting))
            {
                availableCells.RemoveAt(index);
                return candidate;
            }
        }

        int fallbackIndex = Random.Range(0, availableCells.Count);
        Vector3 fallback = availableCells[fallbackIndex];
        availableCells.RemoveAt(fallbackIndex);
        return fallback;
    }

    private bool IsFarEnoughFromExisting(Vector3 candidate, float minDistance)
    {
        if (minDistance <= 0f)
        {
            return true;
        }

        for (int i = 0; i < sentinelSpawns.Count; i++)
        {
            Vector3 spawn = sentinelSpawns[i];
            spawn.y = 0f;
            if (Vector3.Distance(candidate, spawn) < minDistance)
            {
                return false;
            }
        }

        for (int i = 0; i < runnerSpawns.Count; i++)
        {
            Vector3 spawn = runnerSpawns[i];
            spawn.y = 0f;
            if (Vector3.Distance(candidate, spawn) < minDistance)
            {
                return false;
            }
        }

        for (int i = 0; i < exitPositions.Count; i++)
        {
            Vector3 exit = exitPositions[i];
            exit.y = 0f;
            if (Vector3.Distance(candidate, exit) < minDistance)
            {
                return false;
            }
        }

        return true;
    }

    private void RemoveCellsNearSpawns(List<Vector3> availableCells)
    {
        for (int i = availableCells.Count - 1; i >= 0; i--)
        {
            if (!IsFarEnoughFromExisting(availableCells[i], cellSize * 2f))
            {
                availableCells.RemoveAt(i);
            }
        }
    }

    private void ApplySpawnPositions()
    {
        if (spawnManager != null)
        {
            spawnManager.SetSpawnPositions(sentinelSpawns.ToArray(), runnerSpawns.ToArray());
        }
    }

    private Vector3 CellToWorld(int row, int column)
    {
        float x = (column - (Layout[row].Length - 1) * 0.5f) * cellSize;
        float z = ((Layout.Length - 1) * 0.5f - row) * cellSize;
        return new Vector3(x, 0f, z);
    }

    private void CreateWall(Vector3 center, bool dynamic)
    {
        GameObject wall = GameObject.CreatePrimitive(PrimitiveType.Cube);
        wall.name = dynamic ? "DynamicWallPillar" : "MazeWall";
        wall.tag = "Wall";
        wall.transform.SetParent(transform);
        wall.transform.position = center + Vector3.up * (wallHeight * 0.5f);
        wall.transform.localScale = new Vector3(wallThickness, wallHeight, wallThickness);

        Renderer renderer = wall.GetComponent<Renderer>();
        if (renderer != null && wallMaterial != null)
        {
            renderer.sharedMaterial = wallMaterial;
        }

        generatedObjects.Add(wall);

        if (dynamic && dynamicWallController != null)
        {
            DynamicWallPillar pillar = wall.AddComponent<DynamicWallPillar>();
            pillar.Configure(wall.transform.position, wallHeight + 0.5f);
            dynamicWallController.RegisterWall(pillar);
        }
    }

    private void CreateExitZone(Vector3 center)
    {
        GameObject exit = GameObject.CreatePrimitive(PrimitiveType.Cube);
        exit.name = "ExitZone";
        exit.tag = "Exit";
        exit.transform.SetParent(transform);
        exit.transform.position = center + Vector3.up * 0.05f;
        exit.transform.localScale = new Vector3(cellSize * 0.8f, 0.1f, cellSize * 0.8f);

        Collider exitCollider = exit.GetComponent<Collider>();
        if (exitCollider != null)
        {
            exitCollider.isTrigger = true;
        }

        Renderer renderer = exit.GetComponent<Renderer>();
        if (renderer != null && exitMaterial != null)
        {
            renderer.sharedMaterial = exitMaterial;
        }

        ExitZoneController exitZoneController = exit.AddComponent<ExitZoneController>();
        exitZoneController.Configure(environmentController);
        generatedObjects.Add(exit);
    }

    private void EnsureSpawnCounts()
    {
        while (sentinelSpawns.Count < 3)
        {
            sentinelSpawns.Add(new Vector3(-8f, 0.5f, -4f + sentinelSpawns.Count * 4f));
        }

        while (runnerSpawns.Count < 2)
        {
            runnerSpawns.Add(new Vector3(8f, 0.5f, -2f + runnerSpawns.Count * 4f));
        }
    }

    private void ClearGeneratedObjects()
    {
        for (int i = generatedObjects.Count - 1; i >= 0; i--)
        {
            GameObject generatedObject = generatedObjects[i];
            if (generatedObject == null)
            {
                continue;
            }

            if (Application.isPlaying)
            {
                Destroy(generatedObject);
            }
            else
            {
                DestroyImmediate(generatedObject);
            }
        }

        generatedObjects.Clear();
        generated = false;
    }
}
