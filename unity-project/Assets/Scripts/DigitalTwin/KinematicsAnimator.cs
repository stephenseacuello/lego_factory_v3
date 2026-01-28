using UnityEngine;
using System;
using System.Collections.Generic;

namespace CNCScada.DigitalTwin
{
    /// <summary>
    /// Kinematics Animator for 6-Axis CNC Machine
    /// Animates machine axes (X, Y, Z, A, B, C) based on ISO 23247 state
    /// Part of Phase 2: Real-Time Visualization (60Hz)
    /// </summary>
    public class KinematicsAnimator : MonoBehaviour
    {
        [Header("State Handler Reference")]
        [SerializeField] private ISO23247StateHandler stateHandler;

        [Header("Axis Transform References")]
        [SerializeField] private Transform xAxisTransform;
        [SerializeField] private Transform yAxisTransform;
        [SerializeField] private Transform zAxisTransform;
        [SerializeField] private Transform aAxisTransform; // Rotational around X
        [SerializeField] private Transform bAxisTransform; // Rotational around Y
        [SerializeField] private Transform cAxisTransform; // Rotational around Z

        [Header("Axis Configuration")]
        [SerializeField] private Vector3 xAxisDirection = Vector3.right;
        [SerializeField] private Vector3 yAxisDirection = Vector3.forward;
        [SerializeField] private Vector3 zAxisDirection = Vector3.up;
        [SerializeField] private float positionScale = 0.001f; // mm to Unity units

        [Header("Axis Limits (mm)")]
        [SerializeField] private Vector2 xLimits = new Vector2(-300f, 300f);
        [SerializeField] private Vector2 yLimits = new Vector2(-300f, 300f);
        [SerializeField] private Vector2 zLimits = new Vector2(-200f, 200f);
        [SerializeField] private Vector2 aLimits = new Vector2(-180f, 180f); // degrees
        [SerializeField] private Vector2 bLimits = new Vector2(-180f, 180f);
        [SerializeField] private Vector2 cLimits = new Vector2(-360f, 360f);

        [Header("Animation Settings")]
        [SerializeField] private bool useInterpolation = true;
        [SerializeField] private bool usePrediction = true;
        [SerializeField] private float smoothingFactor = 0.15f;
        [SerializeField] private bool enableMotionBlur = false;
        [SerializeField] private float motionBlurThreshold = 100f; // mm/min

        [Header("Visualization")]
        [SerializeField] private bool showAxisGizmos = true;
        [SerializeField] private bool showLimits = true;
        [SerializeField] private bool showVelocityVectors = true;
        [SerializeField] private Color xAxisColor = Color.red;
        [SerializeField] private Color yAxisColor = Color.green;
        [SerializeField] private Color zAxisColor = Color.blue;

        // Current positions
        private Vector3 currentPosition = Vector3.zero;
        private Vector3 targetPosition = Vector3.zero;
        private Vector3 smoothedPosition = Vector3.zero;
        private Vector3 currentRotation = Vector3.zero; // A, B, C in degrees

        // Velocity tracking
        private Vector3 currentVelocity = Vector3.zero;
        private Vector3 previousPosition = Vector3.zero;
        private float velocityMagnitude = 0f;

        // Base positions for relative movement
        private Vector3 xAxisBasePosition;
        private Vector3 yAxisBasePosition;
        private Vector3 zAxisBasePosition;

        // Statistics
        private int totalUpdates = 0;
        private float averageUpdateRate = 0f;
        private List<float> updateRateSamples = new List<float>();
        private float lastUpdateTime = 0f;

        // Events
        public event Action<Vector3> OnPositionChanged;
        public event Action<Vector3> OnRotationChanged;
        public event Action<string> OnLimitExceeded;

        void Start()
        {
            if (stateHandler == null)
            {
                stateHandler = FindObjectOfType<ISO23247StateHandler>();
                if (stateHandler == null)
                {
                    Debug.LogError("[KinematicsAnimator] ISO23247StateHandler not found!");
                    return;
                }
            }

            // Subscribe to state updates
            stateHandler.OnStateUpdated += OnStateUpdated;

            // Store base positions
            StoreBasePositions();

            lastUpdateTime = Time.time;
            Debug.Log("[KinematicsAnimator] Initialized - 6-axis animation ready");
        }

        void StoreBasePositions()
        {
            if (xAxisTransform != null) xAxisBasePosition = xAxisTransform.localPosition;
            if (yAxisTransform != null) yAxisBasePosition = yAxisTransform.localPosition;
            if (zAxisTransform != null) zAxisBasePosition = zAxisTransform.localPosition;
        }

        void OnStateUpdated(ISO23247StateHandler.MachineState state)
        {
            if (state == null) return;

            // Get the appropriate state (interpolated or predicted)
            ISO23247StateHandler.MachineState activeState;
            if (usePrediction && useInterpolation)
            {
                activeState = stateHandler.GetInterpolatedState();
            }
            else if (useInterpolation)
            {
                activeState = stateHandler.GetInterpolatedState();
            }
            else
            {
                activeState = state;
            }

            if (activeState == null) return;

            // Update target position
            previousPosition = targetPosition;
            targetPosition = activeState.position;
            currentVelocity = activeState.velocity;

            // Calculate velocity magnitude
            velocityMagnitude = currentVelocity.magnitude;

            // Track update rate
            float updateDelta = Time.time - lastUpdateTime;
            if (updateDelta > 0f)
            {
                RecordUpdateRate(1f / updateDelta);
            }
            lastUpdateTime = Time.time;

            totalUpdates++;
        }

        void Update()
        {
            // Smooth position movement
            if (useInterpolation)
            {
                smoothedPosition = Vector3.Lerp(smoothedPosition, targetPosition, smoothingFactor);
                currentPosition = smoothedPosition;
            }
            else
            {
                currentPosition = targetPosition;
            }

            // Apply axis animations
            AnimateLinearAxes();
            AnimateRotationalAxes();

            // Check limits
            CheckAxisLimits();
        }

        void AnimateLinearAxes()
        {
            // Convert mm to Unity units
            Vector3 scaledPosition = currentPosition * positionScale;

            // X Axis - moves along X direction
            if (xAxisTransform != null)
            {
                Vector3 xOffset = xAxisDirection.normalized * scaledPosition.x;
                xAxisTransform.localPosition = xAxisBasePosition + xOffset;
            }

            // Y Axis - moves along Y direction
            if (yAxisTransform != null)
            {
                Vector3 yOffset = yAxisDirection.normalized * scaledPosition.y;
                yAxisTransform.localPosition = yAxisBasePosition + yOffset;
            }

            // Z Axis - moves along Z direction
            if (zAxisTransform != null)
            {
                Vector3 zOffset = zAxisDirection.normalized * scaledPosition.z;
                zAxisTransform.localPosition = zAxisBasePosition + zOffset;
            }

            OnPositionChanged?.Invoke(currentPosition);
        }

        void AnimateRotationalAxes()
        {
            // A Axis - rotation around X
            if (aAxisTransform != null)
            {
                aAxisTransform.localRotation = Quaternion.Euler(currentRotation.x, 0f, 0f);
            }

            // B Axis - rotation around Y
            if (bAxisTransform != null)
            {
                bAxisTransform.localRotation = Quaternion.Euler(0f, currentRotation.y, 0f);
            }

            // C Axis - rotation around Z
            if (cAxisTransform != null)
            {
                cAxisTransform.localRotation = Quaternion.Euler(0f, 0f, currentRotation.z);
            }

            OnRotationChanged?.Invoke(currentRotation);
        }

        void CheckAxisLimits()
        {
            bool limitExceeded = false;
            string limitMessage = "";

            if (currentPosition.x < xLimits.x || currentPosition.x > xLimits.y)
            {
                limitExceeded = true;
                limitMessage += $"X-axis limit ({currentPosition.x:F2}mm) ";
            }

            if (currentPosition.y < yLimits.x || currentPosition.y > yLimits.y)
            {
                limitExceeded = true;
                limitMessage += $"Y-axis limit ({currentPosition.y:F2}mm) ";
            }

            if (currentPosition.z < zLimits.x || currentPosition.z > zLimits.y)
            {
                limitExceeded = true;
                limitMessage += $"Z-axis limit ({currentPosition.z:F2}mm) ";
            }

            if (limitExceeded)
            {
                OnLimitExceeded?.Invoke(limitMessage.Trim());
            }
        }

        void RecordUpdateRate(float rate)
        {
            updateRateSamples.Add(rate);
            if (updateRateSamples.Count > 60)
            {
                updateRateSamples.RemoveAt(0);
            }

            float sum = 0f;
            foreach (float sample in updateRateSamples)
            {
                sum += sample;
            }
            averageUpdateRate = sum / updateRateSamples.Count;
        }

        /// <summary>
        /// Set rotational axis position (degrees)
        /// </summary>
        public void SetRotationalAxis(string axis, float degrees)
        {
            switch (axis.ToUpper())
            {
                case "A":
                    currentRotation.x = Mathf.Clamp(degrees, aLimits.x, aLimits.y);
                    break;
                case "B":
                    currentRotation.y = Mathf.Clamp(degrees, bLimits.x, bLimits.y);
                    break;
                case "C":
                    currentRotation.z = Mathf.Clamp(degrees, cLimits.x, cLimits.y);
                    break;
            }
        }

        /// <summary>
        /// Reset all axes to home position
        /// </summary>
        public void ResetToHome()
        {
            targetPosition = Vector3.zero;
            smoothedPosition = Vector3.zero;
            currentPosition = Vector3.zero;
            currentRotation = Vector3.zero;

            AnimateLinearAxes();
            AnimateRotationalAxes();

            Debug.Log("[KinematicsAnimator] Reset to home position");
        }

        public Vector3 GetCurrentPosition()
        {
            return currentPosition;
        }

        public Vector3 GetCurrentRotation()
        {
            return currentRotation;
        }

        public Vector3 GetCurrentVelocity()
        {
            return currentVelocity;
        }

        public Dictionary<string, object> GetStatistics()
        {
            return new Dictionary<string, object>
            {
                {"total_updates", totalUpdates},
                {"average_update_rate_hz", averageUpdateRate},
                {"current_position_mm", currentPosition},
                {"current_rotation_deg", currentRotation},
                {"velocity_magnitude_mm_min", velocityMagnitude},
                {"interpolation_enabled", useInterpolation},
                {"prediction_enabled", usePrediction}
            };
        }

        void OnDrawGizmos()
        {
            if (!Application.isPlaying || !showAxisGizmos) return;

            Vector3 worldPos = transform.position + currentPosition * positionScale;

            // Draw current position
            Gizmos.color = Color.white;
            Gizmos.DrawWireSphere(worldPos, 0.05f);

            // Draw axis limits
            if (showLimits)
            {
                // X axis limits
                Gizmos.color = xAxisColor;
                Vector3 xMin = transform.position + xAxisDirection.normalized * xLimits.x * positionScale;
                Vector3 xMax = transform.position + xAxisDirection.normalized * xLimits.y * positionScale;
                Gizmos.DrawLine(xMin, xMax);
                Gizmos.DrawWireCube(xMin, Vector3.one * 0.02f);
                Gizmos.DrawWireCube(xMax, Vector3.one * 0.02f);

                // Y axis limits
                Gizmos.color = yAxisColor;
                Vector3 yMin = transform.position + yAxisDirection.normalized * yLimits.x * positionScale;
                Vector3 yMax = transform.position + yAxisDirection.normalized * yLimits.y * positionScale;
                Gizmos.DrawLine(yMin, yMax);
                Gizmos.DrawWireCube(yMin, Vector3.one * 0.02f);
                Gizmos.DrawWireCube(yMax, Vector3.one * 0.02f);

                // Z axis limits
                Gizmos.color = zAxisColor;
                Vector3 zMin = transform.position + zAxisDirection.normalized * zLimits.x * positionScale;
                Vector3 zMax = transform.position + zAxisDirection.normalized * zLimits.y * positionScale;
                Gizmos.DrawLine(zMin, zMax);
                Gizmos.DrawWireCube(zMin, Vector3.one * 0.02f);
                Gizmos.DrawWireCube(zMax, Vector3.one * 0.02f);
            }

            // Draw velocity vector
            if (showVelocityVectors && velocityMagnitude > 0.01f)
            {
                Gizmos.color = Color.cyan;
                Vector3 velocityVector = currentVelocity.normalized * 0.1f;
                Gizmos.DrawRay(worldPos, velocityVector);
            }
        }

        void OnDestroy()
        {
            if (stateHandler != null)
            {
                stateHandler.OnStateUpdated -= OnStateUpdated;
            }
        }
    }
}
