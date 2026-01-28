using System;
using System.Collections.Generic;
using UnityEngine;

namespace CNCScada.Safety
{
    /// <summary>
    /// Physics-based collision detection between tool, workpiece, fixtures, and machine.
    /// Provides real-time collision warnings and prevention.
    /// Part of Feature 1.2: Collision Detection (HIGH PRIORITY)
    /// </summary>
    public class CollisionDetector : MonoBehaviour
    {
        [Header("Collision Settings")]
        [SerializeField] private bool enableCollisionDetection = true;
        [SerializeField] private float checkInterval = 0.1f; // seconds
        [SerializeField] private float proximityWarningDistance = 0.05f; // meters (50mm)

        [Header("Collision Layers")]
        [SerializeField] private LayerMask toolLayer;
        [SerializeField] private LayerMask fixtureLayer;
        [SerializeField] private LayerMask workpieceLayer;
        [SerializeField] private LayerMask machineLayer;

        [Header("Tool Configuration")]
        [SerializeField] private Transform toolTip;
        [SerializeField] private float toolRadius = 0.003f; // 3mm default
        [SerializeField] private float toolLength = 0.05f; // 50mm default

        [Header("Visualization")]
        [SerializeField] private bool visualizeCollisions = true;
        [SerializeField] private bool visualizeProximity = true;
        [SerializeField] private Color collisionColor = Color.red;
        [SerializeField] private Color proximityColor = Color.yellow;
        [SerializeField] private Color safeColor = Color.green;

        // State
        private float checkTimer = 0f;
        private bool isColliding = false;
        private bool isInProximity = false;
        private List<Collision> activeCollisions = new List<Collision>();
        private List<GameObject> proximityObjects = new List<GameObject>();

        // Statistics
        private int totalCollisionsDetected = 0;
        private int totalProximityWarnings = 0;
        private DateTime lastCollisionTime;

        // Events
        public event Action<CollisionEvent> OnCollisionDetected;
        public event Action OnCollisionCleared;
        public event Action<ProximityWarning> OnProximityWarning;
        public event Action OnProximityClear;

        void Update()
        {
            if (!enableCollisionDetection) return;

            checkTimer += Time.deltaTime;
            if (checkTimer >= checkInterval)
            {
                PerformCollisionCheck();
                checkTimer = 0f;
            }
        }

        void OnDrawGizmos()
        {
            if (!visualizeCollisions || toolTip == null) return;

            // Draw tool cylinder
            Gizmos.color = isColliding ? collisionColor :
                          isInProximity ? proximityColor : safeColor;

            DrawToolGizmo();

            // Draw proximity warnings
            if (visualizeProximity && proximityObjects.Count > 0)
            {
                Gizmos.color = proximityColor;
                foreach (var obj in proximityObjects)
                {
                    if (obj != null)
                    {
                        Gizmos.DrawLine(toolTip.position, obj.transform.position);
                    }
                }
            }
        }

        /// <summary>
        /// Perform collision check for tool against all collision layers
        /// </summary>
        public void PerformCollisionCheck()
        {
            if (toolTip == null) return;

            activeCollisions.Clear();
            proximityObjects.Clear();

            // Check tool cylinder against all layers
            Vector3 start = toolTip.position;
            Vector3 end = toolTip.position + toolTip.up * toolLength;

            // Cast capsule for tool shape
            RaycastHit[] hits = Physics.CapsuleCastAll(
                start,
                end,
                toolRadius,
                toolTip.forward,
                0.001f,  // Very small distance (essentially checking current position)
                fixtureLayer | workpieceLayer | machineLayer
            );

            bool collisionThisFrame = false;
            bool proximityThisFrame = false;

            foreach (var hit in hits)
            {
                float distance = hit.distance;

                if (distance < 0.001f)
                {
                    // Collision detected
                    collisionThisFrame = true;
                    activeCollisions.Add(hit.collider.GetComponent<Collision>());

                    if (!isColliding)
                    {
                        HandleCollisionStart(hit);
                    }
                }
                else if (distance < proximityWarningDistance)
                {
                    // Proximity warning
                    proximityThisFrame = true;
                    proximityObjects.Add(hit.collider.gameObject);

                    if (!isInProximity)
                    {
                        HandleProximityStart(hit);
                    }
                }
            }

            // Update state
            if (isColliding && !collisionThisFrame)
            {
                HandleCollisionEnd();
            }

            if (isInProximity && !proximityThisFrame)
            {
                HandleProximityEnd();
            }

            isColliding = collisionThisFrame;
            isInProximity = proximityThisFrame;
        }

        /// <summary>
        /// Check if a specific path segment will cause collision
        /// </summary>
        public CollisionCheckResult CheckPathSegment(Vector3 start, Vector3 end)
        {
            Vector3 direction = (end - start).normalized;
            float distance = Vector3.Distance(start, end);

            // Perform sphere sweep along path
            RaycastHit[] hits = Physics.SphereCastAll(
                start,
                toolRadius,
                direction,
                distance,
                fixtureLayer | workpieceLayer | machineLayer
            );

            if (hits.Length > 0)
            {
                // Find closest collision
                float minDistance = float.MaxValue;
                RaycastHit closestHit = hits[0];

                foreach (var hit in hits)
                {
                    if (hit.distance < minDistance)
                    {
                        minDistance = hit.distance;
                        closestHit = hit;
                    }
                }

                return new CollisionCheckResult
                {
                    WillCollide = true,
                    CollisionPoint = closestHit.point,
                    CollisionNormal = closestHit.normal,
                    CollisionObject = closestHit.collider.gameObject,
                    DistanceToCollision = closestHit.distance
                };
            }

            return new CollisionCheckResult { WillCollide = false };
        }

        /// <summary>
        /// Check if tool will collide at a specific position
        /// </summary>
        public bool CheckPosition(Vector3 position, Quaternion rotation)
        {
            // Temporarily move tool to check position
            Vector3 originalPos = toolTip.position;
            Quaternion originalRot = toolTip.rotation;

            toolTip.position = position;
            toolTip.rotation = rotation;

            bool hasCollision = Physics.CheckCapsule(
                position,
                position + rotation * Vector3.up * toolLength,
                toolRadius,
                fixtureLayer | workpieceLayer | machineLayer
            );

            // Restore original position
            toolTip.position = originalPos;
            toolTip.rotation = originalRot;

            return hasCollision;
        }

        /// <summary>
        /// Set tool dimensions
        /// </summary>
        public void SetToolDimensions(float radius, float length)
        {
            toolRadius = radius;
            toolLength = length;
            Debug.Log($"[CollisionDetector] Tool dimensions set: R={radius}m, L={length}m");
        }

        /// <summary>
        /// Enable or disable collision detection
        /// </summary>
        public void SetCollisionDetection(bool enabled)
        {
            enableCollisionDetection = enabled;
            if (!enabled)
            {
                if (isColliding)
                {
                    HandleCollisionEnd();
                }
                if (isInProximity)
                {
                    HandleProximityEnd();
                }
            }
        }

        /// <summary>
        /// Get collision statistics
        /// </summary>
        public CollisionStatistics GetStatistics()
        {
            return new CollisionStatistics
            {
                TotalCollisionsDetected = totalCollisionsDetected,
                TotalProximityWarnings = totalProximityWarnings,
                IsCurrentlyColliding = isColliding,
                IsCurrentlyInProximity = isInProximity,
                ActiveCollisionCount = activeCollisions.Count,
                LastCollisionTime = lastCollisionTime
            };
        }

        private void HandleCollisionStart(RaycastHit hit)
        {
            totalCollisionsDetected++;
            lastCollisionTime = DateTime.UtcNow;

            var collisionEvent = new CollisionEvent
            {
                Timestamp = DateTime.UtcNow,
                CollisionPoint = hit.point,
                CollisionNormal = hit.normal,
                CollidingObject = hit.collider.gameObject,
                ToolPosition = toolTip.position,
                Severity = CollisionSeverity.Critical
            };

            Debug.LogError($"[CollisionDetector] COLLISION DETECTED with {hit.collider.gameObject.name} at {hit.point}");
            OnCollisionDetected?.Invoke(collisionEvent);
        }

        private void HandleCollisionEnd()
        {
            Debug.Log("[CollisionDetector] Collision cleared");
            OnCollisionCleared?.Invoke();
        }

        private void HandleProximityStart(RaycastHit hit)
        {
            totalProximityWarnings++;

            var warning = new ProximityWarning
            {
                Timestamp = DateTime.UtcNow,
                NearbyObject = hit.collider.gameObject,
                Distance = hit.distance,
                ToolPosition = toolTip.position
            };

            Debug.LogWarning($"[CollisionDetector] Proximity warning: {hit.distance:F3}m from {hit.collider.gameObject.name}");
            OnProximityWarning?.Invoke(warning);
        }

        private void HandleProximityEnd()
        {
            Debug.Log("[CollisionDetector] Proximity cleared");
            OnProximityClear?.Invoke();
        }

        private void DrawToolGizmo()
        {
            if (toolTip == null) return;

            Vector3 start = toolTip.position;
            Vector3 end = start + toolTip.up * toolLength;

            // Draw tool cylinder
            Gizmos.DrawLine(start, end);
            Gizmos.DrawWireSphere(start, toolRadius);
            Gizmos.DrawWireSphere(end, toolRadius);

            // Draw collision points
            if (visualizeCollisions)
            {
                Gizmos.color = Color.red;
                foreach (var collision in activeCollisions)
                {
                    if (collision != null)
                    {
                        Gizmos.DrawWireSphere(collision.transform.position, 0.01f);
                    }
                }
            }
        }

        #region Public Properties

        public bool IsColliding => isColliding;
        public bool IsInProximity => isInProximity;
        public int ActiveCollisionCount => activeCollisions.Count;
        public bool IsEnabled => enableCollisionDetection;

        #endregion
    }

    #region Data Structures

    /// <summary>
    /// Collision event data
    /// </summary>
    [Serializable]
    public struct CollisionEvent
    {
        public DateTime Timestamp;
        public Vector3 CollisionPoint;
        public Vector3 CollisionNormal;
        public GameObject CollidingObject;
        public Vector3 ToolPosition;
        public CollisionSeverity Severity;
    }

    /// <summary>
    /// Proximity warning data
    /// </summary>
    [Serializable]
    public struct ProximityWarning
    {
        public DateTime Timestamp;
        public GameObject NearbyObject;
        public float Distance;
        public Vector3 ToolPosition;
    }

    /// <summary>
    /// Collision check result
    /// </summary>
    [Serializable]
    public struct CollisionCheckResult
    {
        public bool WillCollide;
        public Vector3 CollisionPoint;
        public Vector3 CollisionNormal;
        public GameObject CollisionObject;
        public float DistanceToCollision;
    }

    /// <summary>
    /// Collision statistics
    /// </summary>
    [Serializable]
    public struct CollisionStatistics
    {
        public int TotalCollisionsDetected;
        public int TotalProximityWarnings;
        public bool IsCurrentlyColliding;
        public bool IsCurrentlyInProximity;
        public int ActiveCollisionCount;
        public DateTime LastCollisionTime;
    }

    /// <summary>
    /// Collision severity levels
    /// </summary>
    public enum CollisionSeverity
    {
        Warning,    // Close proximity
        Moderate,   // Light contact
        Critical    // Hard collision
    }

    #endregion
}
