using UnityEngine;

[RequireComponent(typeof(Collider))]
public class DynamicWallPillar : MonoBehaviour
{
    [SerializeField] private bool raised = true;
    [SerializeField] private Vector3 raisedPosition;
    [SerializeField] private Vector3 loweredPosition;
    [SerializeField] private float transitionSpeed = 8f;
    [SerializeField] private bool disableColliderWhenLowered = true;

    private Collider wallCollider;

    public bool IsRaised => raised;
    public Vector3 RaisedPosition => raisedPosition;

    public void Configure(Vector3 configuredRaisedPosition, float loweredOffset)
    {
        raisedPosition = configuredRaisedPosition;
        loweredPosition = configuredRaisedPosition + Vector3.down * Mathf.Abs(loweredOffset);
        wallCollider = GetComponent<Collider>();
        SetRaised(raised, true);
    }

    public void SetRaised(bool shouldRaise, bool immediate = false)
    {
        raised = shouldRaise;
        if (wallCollider == null)
        {
            wallCollider = GetComponent<Collider>();
        }

        if (wallCollider != null)
        {
            wallCollider.enabled = raised || !disableColliderWhenLowered;
        }

        if (immediate)
        {
            transform.position = raised ? raisedPosition : loweredPosition;
        }
    }

    private void Update()
    {
        Vector3 targetPosition = raised ? raisedPosition : loweredPosition;
        transform.position = Vector3.MoveTowards(
            transform.position,
            targetPosition,
            transitionSpeed * Time.deltaTime);
    }
}
