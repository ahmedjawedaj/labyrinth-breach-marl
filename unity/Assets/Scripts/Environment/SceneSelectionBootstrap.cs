using System;
using UnityEngine;
using UnityEngine.SceneManagement;

public static class SceneSelectionBootstrap
{
    private const string SceneEnvironmentVariable = "LABYRINTH_SCENE";

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void LoadConfiguredScene()
    {
        string configuredScene = Environment.GetEnvironmentVariable(SceneEnvironmentVariable);
        if (string.IsNullOrWhiteSpace(configuredScene))
        {
            return;
        }

        configuredScene = configuredScene.Trim();
        if (SceneManager.GetActiveScene().name == configuredScene)
        {
            return;
        }

        if (!Application.CanStreamedLevelBeLoaded(configuredScene))
        {
            Debug.LogError($"Configured evaluation scene is not in the player build: {configuredScene}");
            return;
        }

        SceneManager.LoadScene(configuredScene, LoadSceneMode.Single);
    }
}
