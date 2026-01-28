using System;
using System.Collections.Generic;
using UnityEngine;

namespace CNCScada.Safety
{
    /// <summary>
    /// Validates machine position against soft limits and safety zones.
    /// Visualizes boundaries and provides early warning before hitting limits.
    /// Part of Feature 1.2: Collision Detection (HIGH PRIORITY)
    /// </summary>
    public class SafetyZoneValidator : MonoBehaviour
    {
        [Header("Safety Zone Configuration")]
        [SerializeField] private bool enableValidation = true;
        [SerializeField] private Vector3 workspaceMin = new Vector3(-0.5f, 0f, -0.5f);
        [SerializeField] private Vector3 workspaceMax = new Vector3(0.5f, 0.5f, 0.5f);

        [Header("Soft Limits")]
        [SerializeField] private bool enableSoftLimits = true;
        [SerializeField] private float softLimitMargin = 0.05f; // 50mm margin before hard limit

        [Header("Visualization")]
        [SerializeField] private bool visualizeBoundaries = true;
        [SerializeField] private Color safeZoneColor = new Color(0f, 1f, 0f, 0.2f);
        [SerializeField] private Color warningZoneColor = new Color(1f, 1f, 0f, 0.3f);
        [SerializeField] private Color dangerZoneColor = new Color(1f, 0f, 0f, 0.4f);

        [Header("Target")]
        [SerializeField] private Transform targetTransform;

        // State
        private bool isInSafeZone = true;
        private bool isInWarningZone = false;
        private bool isOutOfBounds = false;
        private Vector3 closestBoundary;
        private float distanceToBoundary;

        // Statistics
        private int totalViolations = 0;
        private int totalWarnings = 0;
        private DateTime lastViolationTime;

        // Events
        public event Action<SafetyViolation> OnSafetyViolation;
        public event Action OnSafetyRestored;
        public event Action<SoftLimitWarning> OnSoftLimitWarning;
        public event Action OnSoftLimitCleared;

        void Update()
        {
            if (!enableValidation || targetTransform == null) return;

            ValidatePosition(targetTransform.position);
        }

        void OnDrawGizmos()
        {
            if (!visualizeBoundaries) return;

            // Draw workspace boundaries
            Gizmos.color = safeZoneColor;
            DrawBoundingBox(workspaceMin, workspaceMax);

            // Draw soft limit zone
            if (enableSoftLimits)
            {
                Gizmos.color = warningZoneColor;
                Vector3 softMin = workspaceMin + Vector3.one * softLimitMargin;
                Vector3 softMax = workspaceMax - Vector3.one * softLimitMargin;
                DrawBoundingBox(softMin, softMax);
            }

            // Draw current position indicator
            if (targetTransform != null)
            {
                Gizmos.color = isOutOfBounds ? dangerZoneColor :
                              isInWarningZone ? warningZoneColor : safeZoneColor;
                Gizmos.DrawWireSphere(targetTransform.position, 0.02f);

                // Draw line to closest boundary
                if (distanceToBoundary < softLimitMargin)
                {
                    Gizmos.color = warningZoneColor;
                    Gizmos.DrawLine(targetTransform.position, closestBoundary);
                }
            }
        }

        /// <summary>
        /// Validate position against safety zones
        /// </summary>
        public void ValidatePosition(Vector3 position)
        {
            // Check if position is within workspace
            bool wasInBounds = !isOutOfBounds;
            bool wasInWarning = isInWarningZone;

            isOutOfBounds = !IsWithinWorkspace(position);

            // Calculate distance to nearest boundary
            closestBoundary = GetClosestBoundaryPoint(position);
            distanceToBoundary = Vector3.Distance(position, closestBoundary);

            // Check soft limit zone
            if (enableSoftLimits && !isOutOfBounds)
            {
                isInWarningZone = distanceToBoundary < softLimitMargin;
            }
            else
            {
                isInWarningZone = false;
            }

            isInSafeZone = !isOutOfBounds && !isInWarningZone;

            // Trigger events for state changes
            if (isOutOfBounds && wasInBounds)
            {
                HandleViolation(position);
            }
            else if (!isOutOfBounds && !wasInBounds)
            {
                HandleViolationCleared();
            }

            if (isInWarningZone && !wasInWarning && !isOutOfBounds)
            {
                HandleSoftLimitWarning(position);
            }
            else if (!isInWarningZone && wasInWarning)
            {
                HandleSoftLimitCleared();
            }
        }

        /// <summary>
        /// Check if position is within workspace
        /// </summary>
        public bool IsWithinWorkspace(Vector3 position)
        {
            return position.x >= workspaceMin.x && position.x <= workspaceMax.x &&
                   position.y >= workspaceMin.y && position.y <= workspaceMax.y &&
                   position.z >= workspaceMin.z && position.z <= workspaceMax.z;
        }

        /// <summary>
        /// Get closest point on workspace boundary
        /// </summary>
        public Vector3 GetClosestBoundaryPoint(Vector3 position)
        {
            Vector3 clamped = new Vector3(
                Mathf.Clamp(position.x, workspaceMin.x, workspaceMax.x),
                Mathf.Clamp(position.y, workspaceMin.y, workspaceMax.y),
                Mathf.Clamp(position.z, workspaceMin.z, workspaceMax.z)
            );
            return clamped;
        }

        /// <summary>
        /// Clamp position to workspace
        /// </summary>
        public Vector3 ClampToWorkspace(Vector3 position)
        {
            return GetClosestBoundaryPoint(position);
        }

        /// <summary>
        /// Set workspace bounds
        /// </summary>
        public void SetWorkspaceBounds(Vector3 min, Vector3 max)
        {
            workspaceMin = min;
            workspaceMax = max;
            Debug.Log($"[SafetyZoneValidator] Workspace bounds set: Min={min}, Max={max}");
        }

        /// <summary>
        /// Set soft limit margin
        /// </summary>
        public void SetSoftLimitMargin(float margin)
        {
            softLimitMargin = margin;
            Debug.Log($"[SafetyZoneValidator] Soft limit margin set: {margin}m");
        }

        /// <summary>
        /// Enable or disable validation
        /// </summary>
        public void SetValidationEnabled(bool enabled)
        {
            enableValidation = enabled;
            if (!enabled)
            {
                isInSafeZone = true;
                isInWarningZone = false;
                isOutOfBounds = false;
            }
        }

        /// <summary>
        /// Get safety statistics
        /// </summary>
        public SafetyStatistics GetStatistics()
        {
            return new SafetyStatistics
            {
                TotalViolations = totalViolations,
                TotalWarnings = totalWarnings,
                IsInSafeZone = isInSafeZone,
                IsInWarningZone = isInWarningZone,
                IsOutOfBounds = isOutOfBounds,
                DistanceToBoundary = distanceToBoundary,
                LastViolationTime = lastViolationTime
            };
        }

        private void HandleViolation(Vector3 position)
        {
            totalViolations++;
            lastViolationTime = DateTime.UtcNow;

            var violation = new SafetyViolation
            {
                Timestamp = DateTime.UtcNow,
                Position = position,
                ClosestBoundary = closestBoundary,
                DistanceOutOfBounds = distanceToBoundary,
                ViolationType = DetermineViolationType(position)
            };

            Debug.LogError($"[SafetyZoneValidator] SAFETY VIOLATION at {position}");
            OnSafetyViolation?.Invoke(violation);
        }

        private void HandleViolationCleared()
        {
            Debug.Log("[SafetyZoneValidator] Safety violation cleared");
            OnSafetyRestored?.Invoke();
        }

        private void HandleSoftLimitWarning(Vector3 position)
        {
            totalWarnings++;

            var warning = new SoftLimitWarning
            {
                Timestamp = DateTime.UtcNow,
                Position = position,
                ClosestBoundary = closestBoundary,
                DistanceToBoundary = distanceToBoundary,
                Axis = DetermineClosestAxis(position)
            };

            Debug.LogWarning($"[SafetyZoneValidator] Soft limit warning: {distanceToBoundary:F3}m from boundary");
            OnSoftLimitWarning?.Invoke(warning);
        }

        private void HandleSoftLimitCleared()
        {
            Debug.Log("[SafetyZoneValidator] Soft limit warning cleared");
            OnSoftLimitCleared?.Invoke();
        }

        private ViolationType DetermineViolationType(Vector3 position)
        {
            if (position.x < workspaceMin.x || position.x > workspaceMax.x)
                return ViolationType.XAxisLimit;
            if (position.y < workspaceMin.y || position.y > workspaceMax.y)
                return ViolationType.YAxisLimit;
            if (position.z < workspaceMin.z || position.z > workspaceMax.z)
                return ViolationType.ZAxisLimit;
            return ViolationType.Unknown;
        }

        private string DetermineClosestAxis(Vector3 position)
        {
            float distX = Mathf.Min(Mathf.Abs(position.x - workspaceMin.x), Mathf.Abs(position.x - workspaceMax.x));
            float distY = Mathf.Min(Mathf.Abs(position.y - workspaceMin.y), Mathf.Abs(position.y - workspaceMax.y));
            float distZ = Mathf.Min(Mathf.Abs(position.z - workspaceMin.z), Mathf.Abs(position.z - workspaceMax.z));

            if (distX < distY && distX < distZ) return "X";
            if (distY < distZ) return "Y";
            return "Z";
        }

        private void DrawBoundingBox(Vector3 min, Vector3 max)
        {
            // Bottom face
            Gizmos.DrawLine(new Vector3(min.x, min.y, min.z), new Vector3(max.x, min.y, min.z));
            Gizmos.DrawLine(new Vector3(max.x, min.y, min.z), new Vector3(max.x, min.y, max.z));
            Gizmos.DrawLine(new Vector3(max.x, min.y, max.z), new Vector3(min.x, min.y, max.z));
            Gizmos.DrawLine(new Vector3(min.x, min.y, max.z), new Vector3(min.x, min.y, min.z));

            // Top face
            Gizmos.DrawLine(new Vector3(min.x, max.y, min.z), new Vector3(max.x, max.y, min.z));
            Gizmos.DrawLine(new Vector3(max.x, max.y, min.z), new Vector3(max.x, max.y, max.z));
            Gizmos.DrawLine(new Vector3(max.x, max.y, max.z), new Vector3(min.x, max.y, max.z));
            Gizmos.DrawLine(new Vector3(min.x, max.y, max.z), new Vector3(min.x, max.y, min.z));

            // Vertical edges
            Gizmos.DrawLine(new Vector3(min.x, min.y, min.z), new Vector3(min.x, max.y, min.z));
            Gizmos.DrawLine(new Vector3(max.x, min.y, min.z), new Vector3(max.x, max.y, min.z));
            Gizmos.DrawLine(new Vector3(max.x, min.y, max.z), new Vector3(max.x, max.y, max.z));
            Gizmos.DrawLine(new Vector3(min.x, min.y, max.z), new Vector3(min.x, max.y, max.z));
        }

        #region Public Properties

        public bool IsInSafeZone => isInSafeZone;
        public bool IsInWarningZone => isInWarningZone;
        public bool IsOutOfBounds => isOutOfBounds;
        public float DistanceToBoundary => distanceToBoundary;
        public Vector3 ClosestBoundary => closestBoundary;

        #endregion
    }

    #region Data Structures

    /// <summary>
    /// Safety violation data
    /// </summary>
    [Serializable]
    public struct SafetyViolation
    {
        public DateTime Timestamp;
        public Vector3 Position;
        public Vector3 ClosestBoundary;
        public float DistanceOutOfBounds;
        public ViolationType ViolationType;
    }

    /// <summary>
    /// Soft limit warning data
    /// </summary>
    [Serializable]
    public struct SoftLimitWarning
    {
        public DateTime Timestamp;
        public Vector3 Position;
        public Vector3 ClosestBoundary;
        public float DistanceToBoundary;
        public string Axis;
    }

    /// <summary>
    /// Safety statistics
    /// </summary>
    [Serializable]
    public struct SafetyStatistics
    {
        public int TotalViolations;
        public int TotalWarnings;
        public bool IsInSafeZone;
        public bool IsInWarningZone;
        public bool IsOutOfBounds;
        public float DistanceToBoundary;
        public DateTime LastViolationTime;
    }

    /// <summary>
    /// Violation type enumeration
    /// </summary>
    public enum ViolationType
    {
        Unknown,
        XAxisLimit,
        YAxisLimit,
        ZAxisLimit,
        SafetyZone,
        NoGoZone
    }

    #endregion
}

