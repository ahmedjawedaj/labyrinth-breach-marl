using System.Collections.Generic;
using UnityEngine;

public enum MazeMode
{
    Static,
    Dynamic
}

public class MazeGenerator : MonoBehaviour
{
    private const int InvalidCellId = -1;
    [Header("Maze")]
    [SerializeField] private MazeMode mazeMode = MazeMode.Static;
    [SerializeField] private int seed = 42;
    [SerializeField] private int placementSeed = 42;
    [SerializeField] private float cellSize = 2f;
    [SerializeField] private float wallHeight = 2f;
    [SerializeField] private float wallThickness = 0.9f;
    [SerializeField] private Material wallMaterial;
    [SerializeField] private Material exitMaterial;
    [SerializeField] private bool generateOnStart = true;
    [SerializeField] private bool mazeEnabled = true;
    [SerializeField] private bool useUnseenLayout;
    [SerializeField] private bool randomizeSpawns;
    [SerializeField] private bool randomizeExits;
    [SerializeField] private float randomizedSentinelSeparation = 2.5f;
    [SerializeField] private float randomizedRunnerSeparationFromSentinels = 5.5f;

    [Header("References")]
    [SerializeField] private SpawnManager spawnManager;
    [SerializeField] private PursuitEvasionEnvController environmentController;
    [SerializeField] private DynamicWallController dynamicWallController;

    private readonly List<GameObject> generatedObjects = new List<GameObject>();
    private readonly List<Vector3> sentinelSpawns = new List<Vector3>();
    private readonly List<Vector3> runnerSpawns = new List<Vector3>();
    private readonly List<Vector3> exitPositions = new List<Vector3>();
    private bool generated;
    private readonly Dictionary<int, int> walkableCellByPackedCoord = new Dictionary<int, int>();
    private int walkableCellCount;
    private string[] cachedProceduralLayout;
    private int cachedProceduralSeed = int.MinValue;

    public IReadOnlyList<Vector3> SentinelSpawns => sentinelSpawns;
    public IReadOnlyList<Vector3> RunnerSpawns => runnerSpawns;
    public IReadOnlyList<Vector3> ExitPositions => exitPositions;
    public bool Generated => generated;
    public int WalkableCellCount => walkableCellCount;

    /// <summary>When false, the "open arena" path runs (no maze walls) but spawns and exits are still placed.</summary>
    public bool MazeWallsEnabled => mazeEnabled;
    public string ActiveLayoutId => useUnseenLayout ? $"procedural_seed_{seed}" : "training_layout_v1";
    public int TopologySeed => seed;

    private static readonly string[] TrainingLayout =
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
        placementSeed = configuredSeed;
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
        bool changed = placementSeed != configuredSeed ||
            randomizeSpawns != shouldRandomizeSpawns ||
            randomizeExits != shouldRandomizeExits;

        placementSeed = configuredSeed;
        randomizeSpawns = shouldRandomizeSpawns;
        randomizeExits = shouldRandomizeExits;

        if (changed)
        {
            generated = false;
        }
    }

    public void SetTopologySeed(int configuredSeed)
    {
        if (seed == configuredSeed)
        {
            return;
        }

        seed = configuredSeed;
        cachedProceduralLayout = null;
        cachedProceduralSeed = int.MinValue;
        generated = false;
    }

    public void SetUseUnseenLayout(bool shouldUseUnseenLayout)
    {
        if (useUnseenLayout == shouldUseUnseenLayout)
        {
            return;
        }

        useUnseenLayout = shouldUseUnseenLayout;
        generated = false;
    }

    [ContextMenu("Generate Maze")]
    public void Generate()
    {
        ClearGeneratedObjects();
        sentinelSpawns.Clear();
        runnerSpawns.Clear();
        exitPositions.Clear();
        walkableCellByPackedCoord.Clear();
        walkableCellCount = 0;

        // Keep corridors physically traversable for agent collision radii.
        // Some scenes serialized a high wallThickness, which can pinch passages and trap policies.
        wallThickness = Mathf.Clamp(wallThickness, 0.5f, cellSize * 0.55f);

        string[] activeLayout = GetActiveLayout();
        Random.InitState(placementSeed);

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
            CreateOpenArenaExitZones();
            ApplySpawnPositions();
            generated = true;
            return;
        }

        List<Vector3> walkableCells = new List<Vector3>();
        for (int row = 0; row < activeLayout.Length; row++)
        {
            for (int column = 0; column < activeLayout[row].Length; column++)
            {
                char cell = activeLayout[row][column];
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

                if (cell != '#' && cell != 'D')
                {
                    int packed = PackCellCoord(row, column);
                    if (!walkableCellByPackedCoord.ContainsKey(packed))
                    {
                        walkableCellByPackedCoord[packed] = walkableCellCount++;
                    }
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

    /// <summary>
    /// Tight AABB of all non-wall walkable cell centers in the current layout, expanded by ~half a cell
    /// so agent clamping matches navigable area inside the outer <c>#</c> ring (excludes <c>D</c> wall pillars).
    /// </summary>
    public Bounds GetWalkableConfinementBounds()
    {
        if (!mazeEnabled)
        {
            return new Bounds();
        }

        string[] activeLayout = GetActiveLayout();
        bool has = false;
        float minX = 0f;
        float maxX = 0f;
        float minZ = 0f;
        float maxZ = 0f;

        for (int row = 0; row < activeLayout.Length; row++)
        {
            for (int column = 0; column < activeLayout[row].Length; column++)
            {
                char c = activeLayout[row][column];
                if (c == '#' || c == 'D')
                {
                    continue;
                }

                Vector3 p = CellToWorld(row, column);
                p.y = 0f;
                if (!has)
                {
                    has = true;
                    minX = maxX = p.x;
                    minZ = maxZ = p.z;
                }
                else
                {
                    if (p.x < minX)
                    {
                        minX = p.x;
                    }

                    if (p.x > maxX)
                    {
                        maxX = p.x;
                    }

                    if (p.z < minZ)
                    {
                        minZ = p.z;
                    }

                    if (p.z > maxZ)
                    {
                        maxZ = p.z;
                    }
                }
            }
        }

        if (!has)
        {
            return new Bounds();
        }

        const float yExtent = 2f;
        // Cell centers are walk path midpoints; modest expansion (not full half-cell) avoids pushing agents into the outer # ring.
        float expand = cellSize * 0.3f;
        return new Bounds(
            new Vector3(
                (minX + maxX) * 0.5f,
                yExtent * 0.5f,
                (minZ + maxZ) * 0.5f),
            new Vector3(maxX - minX + expand * 2f, yExtent, maxZ - minZ + expand * 2f));
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

    /// <summary>Places exit triggers on the arena floor (east/west) so agents receive exit signals and can score exit wins in open-arena mode.</summary>
    private void CreateOpenArenaExitZones()
    {
        if (environmentController == null)
        {
            environmentController = FindFirstObjectByType<PursuitEvasionEnvController>();
        }

        if (environmentController == null)
        {
            return;
        }

        Bounds b = environmentController.GetArenaBoundsWorld();
        if (b.size.sqrMagnitude < 0.25f)
        {
            return;
        }

        float margin = Mathf.Max(environmentController.ArenaConfinementInset, cellSize * 0.4f);
        float minX = b.min.x + margin;
        float maxX = b.max.x - margin;
        float minZ = b.min.z + margin;
        float maxZ = b.max.z - margin;
        if (minX > maxX || minZ > maxZ)
        {
            return;
        }

        float cx = b.center.x;
        float cz = b.center.z;
        Vector3 west = new Vector3(minX, 0f, cz);
        Vector3 east = new Vector3(maxX, 0f, cz);
        exitPositions.Add(west);
        exitPositions.Add(east);
        CreateExitZone(west);
        CreateExitZone(east);
    }

    private void RandomizeSpawnPositions(List<Vector3> walkableCells)
    {
        float sentinelSpacing = Mathf.Clamp(
            Mathf.Max(cellSize * 0.8f, randomizedSentinelSeparation),
            cellSize * 0.8f,
            cellSize * 1.6f);
        float runnerSafeDistance = Mathf.Clamp(
            Mathf.Max(cellSize * 1.5f, randomizedRunnerSeparationFromSentinels),
            cellSize * 1.5f,
            cellSize * 2.4f);
        bool generatedValidSet = false;

        for (int attempt = 0; attempt < 10; attempt++)
        {
            List<Vector3> availableCells = new List<Vector3>(walkableCells);
            sentinelSpawns.Clear();
            runnerSpawns.Clear();

            for (int i = 0; i < 3; i++)
            {
                sentinelSpawns.Add(TakeRandomCell(availableCells, sentinelSpacing) + Vector3.up * 0.5f);
            }

            for (int i = 0; i < 2; i++)
            {
                runnerSpawns.Add(TakeRandomCell(availableCells, runnerSafeDistance) + Vector3.up * 0.5f);
            }

            if (AreTeamsWellSeparated(runnerSafeDistance))
            {
                generatedValidSet = true;
                break;
            }
        }

        if (!generatedValidSet)
        {
            // Fallback to previous permissive behavior rather than failing generation.
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
    }

    private bool AreTeamsWellSeparated(float minDistance)
    {
        for (int i = 0; i < sentinelSpawns.Count; i++)
        {
            Vector3 sentinel = sentinelSpawns[i];
            sentinel.y = 0f;
            for (int j = 0; j < runnerSpawns.Count; j++)
            {
                Vector3 runner = runnerSpawns[j];
                runner.y = 0f;
                if (Vector3.Distance(sentinel, runner) < minDistance)
                {
                    return false;
                }
            }
        }

        return true;
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
        string[] activeLayout = GetActiveLayout();
        float x = (column - (activeLayout[row].Length - 1) * 0.5f) * cellSize;
        float z = ((activeLayout.Length - 1) * 0.5f - row) * cellSize;
        return new Vector3(x, 0f, z);
    }

    public int GetWalkableCellId(Vector3 worldPosition)
    {
        string[] activeLayout = GetActiveLayout();
        int rows = activeLayout.Length;
        if (rows == 0)
        {
            return InvalidCellId;
        }

        int cols = activeLayout[0].Length;
        if (cols == 0)
        {
            return InvalidCellId;
        }

        float colFloat = (worldPosition.x / cellSize) + (cols - 1) * 0.5f;
        float rowFloat = ((rows - 1) * 0.5f) - (worldPosition.z / cellSize);
        int row = Mathf.Clamp(Mathf.RoundToInt(rowFloat), 0, rows - 1);
        int column = Mathf.Clamp(Mathf.RoundToInt(colFloat), 0, cols - 1);
        int packed = PackCellCoord(row, column);
        return walkableCellByPackedCoord.TryGetValue(packed, out int id) ? id : InvalidCellId;
    }

    private static int PackCellCoord(int row, int column)
    {
        return (row << 16) ^ (column & 0xFFFF);
    }

    private string[] GetActiveLayout()
    {
        if (!useUnseenLayout)
        {
            return TrainingLayout;
        }

        if (cachedProceduralLayout == null || cachedProceduralSeed != seed)
        {
            cachedProceduralLayout = BuildProceduralLayout(seed);
            cachedProceduralSeed = seed;
        }

        return cachedProceduralLayout;
    }

    private static string[] BuildProceduralLayout(int layoutSeed)
    {
        const int size = 13;
        char[][] grid = new char[size][];
        for (int row = 0; row < size; row++)
        {
            grid[row] = new char[size];
            for (int column = 0; column < size; column++)
            {
                grid[row][column] = '#';
            }
        }

        System.Random random = new System.Random(layoutSeed);
        bool[,] visited = new bool[size, size];
        Stack<Vector2Int> stack = new Stack<Vector2Int>();
        Vector2Int start = new Vector2Int(1, 1);
        visited[start.x, start.y] = true;
        grid[start.x][start.y] = '.';
        stack.Push(start);
        Vector2Int[] directions =
        {
            new Vector2Int(-2, 0),
            new Vector2Int(2, 0),
            new Vector2Int(0, -2),
            new Vector2Int(0, 2)
        };

        while (stack.Count > 0)
        {
            Vector2Int current = stack.Peek();
            List<Vector2Int> candidates = new List<Vector2Int>();
            for (int i = 0; i < directions.Length; i++)
            {
                Vector2Int next = current + directions[i];
                if (next.x > 0 && next.x < size - 1 &&
                    next.y > 0 && next.y < size - 1 &&
                    !visited[next.x, next.y])
                {
                    candidates.Add(next);
                }
            }

            if (candidates.Count == 0)
            {
                stack.Pop();
                continue;
            }

            Vector2Int selected = candidates[random.Next(candidates.Count)];
            int wallRow = (current.x + selected.x) / 2;
            int wallColumn = (current.y + selected.y) / 2;
            grid[wallRow][wallColumn] = '.';
            grid[selected.x][selected.y] = '.';
            visited[selected.x, selected.y] = true;
            stack.Push(selected);
        }

        List<Vector2Int> optionalConnections = new List<Vector2Int>();
        for (int row = 1; row < size - 1; row++)
        {
            for (int column = 1; column < size - 1; column++)
            {
                if (grid[row][column] != '#')
                {
                    continue;
                }

                bool joinsVertical = row % 2 == 0 && column % 2 == 1 &&
                    grid[row - 1][column] != '#' && grid[row + 1][column] != '#';
                bool joinsHorizontal = row % 2 == 1 && column % 2 == 0 &&
                    grid[row][column - 1] != '#' && grid[row][column + 1] != '#';
                if (joinsVertical || joinsHorizontal)
                {
                    optionalConnections.Add(new Vector2Int(row, column));
                }
            }
        }

        Shuffle(optionalConnections, random);
        int permanentLoops = Mathf.Min(4, optionalConnections.Count);
        for (int i = 0; i < permanentLoops; i++)
        {
            Vector2Int cell = optionalConnections[i];
            grid[cell.x][cell.y] = '.';
        }
        int dynamicConnections = Mathf.Min(5, optionalConnections.Count - permanentLoops);
        for (int i = 0; i < dynamicConnections; i++)
        {
            Vector2Int cell = optionalConnections[permanentLoops + i];
            grid[cell.x][cell.y] = 'D';
        }

        List<Vector2Int> placementCells = new List<Vector2Int>();
        for (int row = 1; row < size - 1; row += 2)
        {
            for (int column = 1; column < size - 1; column += 2)
            {
                placementCells.Add(new Vector2Int(row, column));
            }
        }
        Shuffle(placementCells, random);
        for (int i = 0; i < 3; i++)
        {
            Vector2Int cell = placementCells[i];
            grid[cell.x][cell.y] = 'S';
        }
        for (int i = 3; i < 5; i++)
        {
            Vector2Int cell = placementCells[i];
            grid[cell.x][cell.y] = 'R';
        }
        for (int i = 5; i < 7; i++)
        {
            Vector2Int cell = placementCells[i];
            grid[cell.x][cell.y] = 'E';
        }

        string[] layout = new string[size];
        for (int row = 0; row < size; row++)
        {
            layout[row] = new string(grid[row]);
        }
        return layout;
    }

    public static bool TryValidateProceduralLayout(int layoutSeed, out string signature, out string error)
    {
        string[] layout = BuildProceduralLayout(layoutSeed);
        int sentinels = 0;
        int runners = 0;
        int exits = 0;
        int dynamicWalls = 0;
        int traversable = 0;
        Vector2Int start = new Vector2Int(-1, -1);
        ulong hash = 1469598103934665603UL;

        for (int row = 0; row < layout.Length; row++)
        {
            for (int column = 0; column < layout[row].Length; column++)
            {
                char cell = layout[row][column];
                hash ^= cell;
                hash *= 1099511628211UL;
                sentinels += cell == 'S' ? 1 : 0;
                runners += cell == 'R' ? 1 : 0;
                exits += cell == 'E' ? 1 : 0;
                dynamicWalls += cell == 'D' ? 1 : 0;
                if (cell != '#' && cell != 'D')
                {
                    traversable++;
                    if (start.x < 0)
                    {
                        start = new Vector2Int(row, column);
                    }
                }
            }
        }

        signature = hash.ToString("X16");
        if (layout.Length != 13 || sentinels != 3 || runners != 2 || exits != 2 || dynamicWalls != 5)
        {
            error = $"seed={layoutSeed} shape/marker failure: rows={layout.Length}, S={sentinels}, R={runners}, E={exits}, D={dynamicWalls}";
            return false;
        }

        bool[,] visited = new bool[layout.Length, layout[0].Length];
        Queue<Vector2Int> queue = new Queue<Vector2Int>();
        queue.Enqueue(start);
        visited[start.x, start.y] = true;
        int reached = 0;
        Vector2Int[] neighbors =
        {
            new Vector2Int(-1, 0),
            new Vector2Int(1, 0),
            new Vector2Int(0, -1),
            new Vector2Int(0, 1)
        };
        while (queue.Count > 0)
        {
            Vector2Int current = queue.Dequeue();
            reached++;
            for (int i = 0; i < neighbors.Length; i++)
            {
                Vector2Int next = current + neighbors[i];
                if (next.x < 0 || next.x >= layout.Length ||
                    next.y < 0 || next.y >= layout[next.x].Length ||
                    visited[next.x, next.y])
                {
                    continue;
                }

                char cell = layout[next.x][next.y];
                if (cell == '#' || cell == 'D')
                {
                    continue;
                }
                visited[next.x, next.y] = true;
                queue.Enqueue(next);
            }
        }

        if (reached != traversable)
        {
            error = $"seed={layoutSeed} disconnected with dynamic walls raised: reached={reached}, traversable={traversable}";
            return false;
        }

        error = string.Empty;
        return true;
    }

    private static void Shuffle<T>(List<T> items, System.Random random)
    {
        for (int i = items.Count - 1; i > 0; i--)
        {
            int selected = random.Next(i + 1);
            T value = items[i];
            items[i] = items[selected];
            items[selected] = value;
        }
    }

    private void CreateWall(Vector3 center, bool dynamic)
    {
        GameObject wall = GameObject.CreatePrimitive(PrimitiveType.Cube);
        wall.name = dynamic ? "DynamicWallPillar" : "MazeWall";
        wall.tag = "Wall";
        wall.transform.SetParent(transform);
        wall.transform.position = center + Vector3.up * (wallHeight * 0.5f);
        wall.transform.localScale = new Vector3(wallThickness, wallHeight, wallThickness);
        Collider wallCollider = wall.GetComponent<Collider>();
        if (wallCollider != null)
        {
            wallCollider.isTrigger = false;
        }

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
