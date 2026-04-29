using UnityEngine;

[RequireComponent(typeof(Collider))]
public class ExitZoneController : MonoBehaviour
{
    [SerializeField] private PursuitEvasionEnvController environmentController;
    [SerializeField] private bool triggerOnce = true;

    private bool hasTriggered;

    public void Configure(PursuitEvasionEnvController controller)
    {
        environmentController = controller;
        hasTriggered = false;

        Collider exitCollider = GetComponent<Collider>();
        if (exitCollider != null)
        {
            exitCollider.isTrigger = true;
        }

        gameObject.tag = "Exit";
    }

    public void ResetExit()
    {
        hasTriggered = false;
    }

    private void OnTriggerEnter(Collider other)
    {
        if (triggerOnce && hasTriggered)
        {
            return;
        }

        RunnerAgent runner = other.GetComponentInParent<RunnerAgent>();
        if (runner == null || !runner.IsAlive || runner.IsCaptured)
        {
            return;
        }

        if (environmentController == null)
        {
            environmentController = FindFirstObjectByType<PursuitEvasionEnvController>();
        }

        if (environmentController == null)
        {
            return;
        }

        hasTriggered = true;
        environmentController.NotifyRunnerReachedExit(runner);
    }
}
