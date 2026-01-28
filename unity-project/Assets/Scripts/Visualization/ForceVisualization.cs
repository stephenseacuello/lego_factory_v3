using System;
using System.Collections.Generic;
using UnityEngine;

namespace CNCScada.Visualization
{
    /// <summary>
    /// Visualizes cutting forces as 3D vectors on the machine tool.
    /// Displays tangential, radial, and axial force components with color-coded arrows.
    /// Part of Feature 2.1: Force/Vibration Visualization (Phase 2)
    /// </summary>
    public class ForceVisualization : MonoBehaviour
    {
        [Header("Force Display")]
        [SerializeField] private bool enableVisualization = true;
        [SerializeField] private float forceScale = 0.001f; // Scale factor for arrow length (1N = 1mm)
        [SerializeField] private float arrowThickness = 0.002f; // 2mm arrow thickness

        [Header("Colors")]
        [SerializeField] private Color tangentialForceColor = Color.red;
        [SerializeField] private Color radialForceColor = Color.green;
        [SerializeField] private Color axialForceColor = Color.blue;
        [SerializeField] private Color resultantForceColor = Color.yellow;

        [Header("Display Options")]
        [SerializeField] private bool showTangential = true;
        [SerializeField] private bool showRadial = true;
        [SerializeField] private bool showAxial = true;
        [SerializeField] private bool showResultant = true;
        [SerializeField] private bool showForceLabels = true;

        [Header("Tool Reference")]
        [SerializeField] private Transform toolTransform;

        // Force vectors
        private Vector3 tangentialForce = Vector3.zero;
        private Vector3 radialForce = Vector3.zero;
        private Vector3 axialForce = Vector3.zero;
        private Vector3 resultantForce = Vector3.zero;

        // Force arrow objects
        private GameObject tangentialArrow;
        private GameObject radialArrow;
        private GameObject axialArrow;
        private GameObject resultantArrow;

        // Force magnitude tracking
        private float maxForce = 0f;
        private float currentForceMagnitude = 0f;
        private List<float> forceHistory = new List<float>();
        private const int historySize = 100;

        // Events
        public event Action<ForceData> OnForceUpdated;

        void Start()
        {
            InitializeForceArrows();
        }

        void Update()
        {
            if (enableVisualization)
            {
                UpdateForceVisualization();
            }
        }

        /// <summary>
        /// Initialize force arrow visualization objects
        /// </summary>
        private void InitializeForceArrows()
        {
            if (showTangential)
            {
                tangentialArrow = CreateForceArrow("TangentialForce", tangentialForceColor);
            }

            if (showRadial)
            {
                radialArrow = CreateForceArrow("RadialForce", radialForceColor);
            }

            if (showAxial)
            {
                axialArrow = CreateForceArrow("AxialForce", axialForceColor);
            }

            if (showResultant)
            {
                resultantArrow = CreateForceArrow("ResultantForce", resultantForceColor);
            }
        }

        /// <summary>
        /// Create force arrow visualization
        /// </summary>
        private GameObject CreateForceArrow(string name, Color color)
        {
            GameObject arrow = new GameObject(name);
            arrow.transform.SetParent(transform);
            arrow.transform.localPosition = Vector3.zero;

            // Create arrow shaft (cylinder)
            GameObject shaft = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            shaft.transform.SetParent(arrow.transform);
            shaft.transform.localPosition = Vector3.zero;
            shaft.transform.localScale = new Vector3(arrowThickness, 0.5f, arrowThickness);

            // Create arrow head (cone)
            GameObject head = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            head.transform.SetParent(arrow.transform);
            head.transform.localPosition = new Vector3(0, 1, 0);
            head.transform.localScale = new Vector3(arrowThickness * 2, 0.1f, arrowThickness * 2);

            // Set color
            var shaftRenderer = shaft.GetComponent<Renderer>();
            if (shaftRenderer)
            {
                shaftRenderer.material.color = color;
            }

            var headRenderer = head.GetComponent<Renderer>();
            if (headRenderer)
            {
                headRenderer.material.color = color;
            }

            arrow.SetActive(false);
            return arrow;
        }

        /// <summary>
        /// Update force from cutting force data
        /// </summary>
        public void UpdateForce(float tangential, float radial, float axial)
        {
            // Store force components (in tool coordinate system)
            tangentialForce = Vector3.forward * tangential; // Cutting direction
            radialForce = Vector3.right * radial; // Perpendicular to cutting
            axialForce = Vector3.up * axial; // Along tool axis

            // Calculate resultant force
            resultantForce = tangentialForce + radialForce + axialForce;
            currentForceMagnitude = resultantForce.magnitude;

            // Update max force
            maxForce = Mathf.Max(maxForce, currentForceMagnitude);

            // Update history
            forceHistory.Add(currentForceMagnitude);
            if (forceHistory.Count > historySize)
            {
                forceHistory.RemoveAt(0);
            }

            // Trigger event
            var forceData = new ForceData
            {
                Timestamp = DateTime.UtcNow,
                TangentialForce = tangential,
                RadialForce = radial,
                AxialForce = axial,
                ResultantForce = currentForceMagnitude,
                MaxForce = maxForce
            };

            OnForceUpdated?.Invoke(forceData);
        }

        /// <summary>
        /// Update force visualization
        /// </summary>
        private void UpdateForceVisualization()
        {
            if (toolTransform == null) return;

            Vector3 toolPosition = toolTransform.position;
            Quaternion toolRotation = toolTransform.rotation;

            // Update tangential force arrow
            if (showTangential && tangentialArrow != null)
            {
                UpdateArrow(tangentialArrow, toolPosition, toolRotation * tangentialForce, tangentialForce.magnitude);
            }

            // Update radial force arrow
            if (showRadial && radialArrow != null)
            {
                UpdateArrow(radialArrow, toolPosition, toolRotation * radialForce, radialForce.magnitude);
            }

            // Update axial force arrow
            if (showAxial && axialArrow != null)
            {
                UpdateArrow(axialArrow, toolPosition, toolRotation * axialForce, axialForce.magnitude);
            }

            // Update resultant force arrow
            if (showResultant && resultantArrow != null)
            {
                UpdateArrow(resultantArrow, toolPosition, toolRotation * resultantForce, resultantForce.magnitude);
            }
        }

        /// <summary>
        /// Update individual arrow visualization
        /// </summary>
        private void UpdateArrow(GameObject arrow, Vector3 position, Vector3 forceVector, float magnitude)
        {
            if (magnitude < 0.1f) // Hide if force is negligible
            {
                arrow.SetActive(false);
                return;
            }

            arrow.SetActive(true);

            // Scale arrow length based on force magnitude
            float arrowLength = magnitude * forceScale;
            Vector3 forceDirection = forceVector.normalized;

            // Position arrow at tool tip
            arrow.transform.position = position;

            // Orient arrow in force direction
            if (forceDirection != Vector3.zero)
            {
                arrow.transform.rotation = Quaternion.LookRotation(forceDirection);
            }

            // Scale arrow shaft
            Transform shaft = arrow.transform.GetChild(0);
            if (shaft != null)
            {
                shaft.localScale = new Vector3(arrowThickness, arrowLength / 2, arrowThickness);
                shaft.localPosition = new Vector3(0, arrowLength / 2, 0);
            }

            // Position arrow head
            Transform head = arrow.transform.GetChild(1);
            if (head != null)
            {
                head.localPosition = new Vector3(0, arrowLength, 0);
            }
        }

        /// <summary>
        /// Get force statistics
        /// </summary>
        public ForceStatistics GetStatistics()
        {
            float avgForce = 0f;
            if (forceHistory.Count > 0)
            {
                foreach (float f in forceHistory)
                {
                    avgForce += f;
                }
                avgForce /= forceHistory.Count;
            }

            return new ForceStatistics
            {
                CurrentForce = currentForceMagnitude,
                MaxForce = maxForce,
                AverageForce = avgForce,
                TangentialComponent = tangentialForce.magnitude,
                RadialComponent = radialForce.magnitude,
                AxialComponent = axialForce.magnitude,
                HistorySize = forceHistory.Count
            };
        }

        /// <summary>
        /// Reset force visualization
        /// </summary>
        public void ResetForces()
        {
            tangentialForce = Vector3.zero;
            radialForce = Vector3.zero;
            axialForce = Vector3.zero;
            resultantForce = Vector3.zero;
            currentForceMagnitude = 0f;
            maxForce = 0f;
            forceHistory.Clear();
        }

        /// <summary>
        /// Set visualization visibility
        /// </summary>
        public void SetVisualizationEnabled(bool enabled)
        {
            enableVisualization = enabled;

            if (!enabled)
            {
                // Hide all arrows
                if (tangentialArrow != null) tangentialArrow.SetActive(false);
                if (radialArrow != null) radialArrow.SetActive(false);
                if (axialArrow != null) axialArrow.SetActive(false);
                if (resultantArrow != null) resultantArrow.SetActive(false);
            }
        }

        void OnDrawGizmos()
        {
            if (!enableVisualization || toolTransform == null) return;

            // Draw force vectors as Gizmos for debugging
            Vector3 toolPos = toolTransform.position;

            if (showTangential && tangentialForce.magnitude > 0.1f)
            {
                Gizmos.color = tangentialForceColor;
                Gizmos.DrawRay(toolPos, toolTransform.rotation * tangentialForce * forceScale);
            }

            if (showRadial && radialForce.magnitude > 0.1f)
            {
                Gizmos.color = radialForceColor;
                Gizmos.DrawRay(toolPos, toolTransform.rotation * radialForce * forceScale);
            }

            if (showAxial && axialForce.magnitude > 0.1f)
            {
                Gizmos.color = axialForceColor;
                Gizmos.DrawRay(toolPos, toolTransform.rotation * axialForce * forceScale);
            }
        }

        #region Public Properties

        public float CurrentForceMagnitude => currentForceMagnitude;
        public float MaxForce => maxForce;
        public bool IsVisualizationEnabled => enableVisualization;

        #endregion
    }

    #region Data Structures

    /// <summary>
    /// Force data event structure
    /// </summary>
    [Serializable]
    public struct ForceData
    {
        public DateTime Timestamp;
        public float TangentialForce; // N
        public float RadialForce; // N
        public float AxialForce; // N
        public float ResultantForce; // N
        public float MaxForce; // N
    }

    /// <summary>
    /// Force statistics
    /// </summary>
    [Serializable]
    public struct ForceStatistics
    {
        public float CurrentForce;
        public float MaxForce;
        public float AverageForce;
        public float TangentialComponent;
        public float RadialComponent;
        public float AxialComponent;
        public int HistorySize;
    }

    #endregion
}
