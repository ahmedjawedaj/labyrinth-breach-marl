using UnityEngine;

#if UNITY_EDITOR
using UnityEditor;
#endif

public static class DebugDrawUtils
{
    public static void DrawWireSphere(Vector3 center, float radius, Color color)
    {
        Gizmos.color = color;
        Gizmos.DrawWireSphere(center, Mathf.Max(0f, radius));
    }

    public static void DrawSphere(Vector3 center, float radius, Color color)
    {
        Gizmos.color = color;
        Gizmos.DrawSphere(center, Mathf.Max(0f, radius));
    }

    public static void DrawLine(Vector3 start, Vector3 end, Color color)
    {
        Gizmos.color = color;
        Gizmos.DrawLine(start, end);
    }

    public static void DrawRay(Vector3 origin, Vector3 direction, float length, Color color)
    {
        DrawLine(origin, origin + direction.normalized * Mathf.Max(0f, length), color);
    }

    public static void DrawWireCube(Vector3 center, Vector3 size, Color color)
    {
        Gizmos.color = color;
        Gizmos.DrawWireCube(center, size);
    }

    public static void DrawLabel(Vector3 position, string text, Color color)
    {
#if UNITY_EDITOR
        GUIStyle style = new GUIStyle(EditorStyles.boldLabel);
        style.normal.textColor = color;
        Handles.Label(position, text, style);
#endif
    }
}
