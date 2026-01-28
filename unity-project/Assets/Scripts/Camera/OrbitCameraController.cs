using System;
using UnityEngine;

namespace CNCScada.Camera
{
    /// <summary>
    /// Orbit camera controller for Digital Twin visualization.
    /// Supports orbit, pan, zoom, and focus on targets.
    /// Includes smooth transitions and preset viewpoints.
    /// </summary>
    public class OrbitCameraController : MonoBehaviour
    {
        [Header("Target")]
        public Transform target;
        public Vector3 targetOffset = Vector3.zero;

        [Header("Orbit Settings")]
        public float orbitSpeed = 5f;
        public float minVerticalAngle = -80f;
        public float maxVerticalAngle = 80f;
        public bool invertVertical = false;
        public bool invertHorizontal = false;

        [Header("Zoom Settings")]
        public float zoomSpeed = 5f;
        public float minDistance = 0.2f;
        public float maxDistance = 5f;
        public float scrollZoomSpeed = 0.5f;

        [Header("Pan Settings")]
        public float panSpeed = 0.5f;
        public bool enablePan = true;

        [Header("Smooth Movement")]
        public bool smoothMovement = true;
        public float smoothTime = 0.15f;

        [Header("Auto Rotate")]
        public bool autoRotate = false;
        public float autoRotateSpeed = 10f;

        [Header("Input Settings")]
        public KeyCode orbitButton = KeyCode.Mouse0;
        public KeyCode panButton = KeyCode.Mouse2;
        public KeyCode resetButton = KeyCode.R;
        public KeyCode focusButton = KeyCode.F;

        [Header("Current State")]
        [SerializeField] private float currentDistance = 1.5f;
        [SerializeField] private float currentHorizontalAngle = 45f;
        [SerializeField] private float currentVerticalAngle = 30f;

        // Internal state
        private Vector3 currentPanOffset;
        private Vector3 velocity = Vector3.zero;
        private float angleVelocityH, angleVelocityV, distanceVelocity;
        private Vector3 panVelocity;

        private float targetHorizontalAngle;
        private float targetVerticalAngle;
        private float targetDistance;
        private Vector3 targetPanOffset;

        private Vector3 initialPosition;
        private Quaternion initialRotation;

        // Events
        public event Action<Transform> OnTargetChanged;
        public event Action<CameraViewpoint> OnViewpointChanged;

        // Singleton
        public static OrbitCameraController Instance { get; private set; }

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
            }
            else
            {
                Destroy(gameObject);
                return;
            }

            // Initialize target angles from current values
            targetHorizontalAngle = currentHorizontalAngle;
            targetVerticalAngle = currentVerticalAngle;
            targetDistance = currentDistance;
            targetPanOffset = Vector3.zero;

            // Store initial transform
            initialPosition = transform.position;
            initialRotation = transform.rotation;
        }

        private void Start()
        {
            if (target == null)
            {
                // Try to find factory cell as default target
                var factoryCell = GameObject.Find("FactoryCell");
                if (factoryCell != null)
                {
                    target = factoryCell.transform;
                }
            }

            // Apply initial position
            UpdateCameraPosition(true);
        }

        private void LateUpdate()
        {
            HandleInput();
            UpdateCameraPosition(false);
        }

        private void HandleInput()
        {
#if ENABLE_LEGACY_INPUT_MANAGER
            // Orbit with left mouse button
            if (Input.GetKey(orbitButton))
            {
                float h = Input.GetAxis("Mouse X") * orbitSpeed;
                float v = Input.GetAxis("Mouse Y") * orbitSpeed;

                if (invertHorizontal) h = -h;
                if (invertVertical) v = -v;

                targetHorizontalAngle += h;
                targetVerticalAngle -= v;
                targetVerticalAngle = Mathf.Clamp(targetVerticalAngle, minVerticalAngle, maxVerticalAngle);

                autoRotate = false; // Disable auto-rotate when user interacts
            }

            // Pan with middle mouse button
            if (enablePan && Input.GetKey(panButton))
            {
                float h = Input.GetAxis("Mouse X") * panSpeed;
                float v = Input.GetAxis("Mouse Y") * panSpeed;

                Vector3 right = transform.right;
                Vector3 up = transform.up;

                targetPanOffset -= right * h + up * v;
            }

            // Zoom with scroll wheel
            float scroll = Input.GetAxis("Mouse ScrollWheel");
            if (Mathf.Abs(scroll) > 0.01f)
            {
                targetDistance -= scroll * scrollZoomSpeed * targetDistance;
                targetDistance = Mathf.Clamp(targetDistance, minDistance, maxDistance);
            }

            // Keyboard zoom
            if (Input.GetKey(KeyCode.Equals) || Input.GetKey(KeyCode.Plus))
            {
                targetDistance -= zoomSpeed * Time.deltaTime;
                targetDistance = Mathf.Max(targetDistance, minDistance);
            }
            if (Input.GetKey(KeyCode.Minus))
            {
                targetDistance += zoomSpeed * Time.deltaTime;
                targetDistance = Mathf.Min(targetDistance, maxDistance);
            }

            // Reset view
            if (Input.GetKeyDown(resetButton))
            {
                ResetView();
            }

            // Focus on selected object
            if (Input.GetKeyDown(focusButton))
            {
                FocusOnSelection();
            }

            // Auto rotate
            if (autoRotate)
            {
                targetHorizontalAngle += autoRotateSpeed * Time.deltaTime;
            }

            // Preset views with number keys
            if (Input.GetKeyDown(KeyCode.Alpha1)) SetViewpoint(CameraViewpoint.Front);
            if (Input.GetKeyDown(KeyCode.Alpha2)) SetViewpoint(CameraViewpoint.Right);
            if (Input.GetKeyDown(KeyCode.Alpha3)) SetViewpoint(CameraViewpoint.Top);
            if (Input.GetKeyDown(KeyCode.Alpha4)) SetViewpoint(CameraViewpoint.Isometric);
            if (Input.GetKeyDown(KeyCode.Alpha5)) SetViewpoint(CameraViewpoint.CNCFocus);
            if (Input.GetKeyDown(KeyCode.Alpha6)) SetViewpoint(CameraViewpoint.RobotFocus);
#endif
        }

        private void UpdateCameraPosition(bool immediate)
        {
            if (target == null) return;

            // Smooth or immediate movement
            if (smoothMovement && !immediate)
            {
                currentHorizontalAngle = Mathf.SmoothDamp(currentHorizontalAngle, targetHorizontalAngle, ref angleVelocityH, smoothTime);
                currentVerticalAngle = Mathf.SmoothDamp(currentVerticalAngle, targetVerticalAngle, ref angleVelocityV, smoothTime);
                currentDistance = Mathf.SmoothDamp(currentDistance, targetDistance, ref distanceVelocity, smoothTime);
                currentPanOffset = Vector3.SmoothDamp(currentPanOffset, targetPanOffset, ref panVelocity, smoothTime);
            }
            else
            {
                currentHorizontalAngle = targetHorizontalAngle;
                currentVerticalAngle = targetVerticalAngle;
                currentDistance = targetDistance;
                currentPanOffset = targetPanOffset;
            }

            // Calculate position from angles
            float h = currentHorizontalAngle * Mathf.Deg2Rad;
            float v = currentVerticalAngle * Mathf.Deg2Rad;

            Vector3 direction = new Vector3(
                Mathf.Sin(h) * Mathf.Cos(v),
                Mathf.Sin(v),
                Mathf.Cos(h) * Mathf.Cos(v)
            );

            Vector3 targetPosition = target.position + targetOffset + currentPanOffset;
            Vector3 cameraPosition = targetPosition + direction * currentDistance;

            transform.position = cameraPosition;
            transform.LookAt(targetPosition);
        }

        // =========================================================================
        // Public API
        // =========================================================================

        /// <summary>
        /// Set a new orbit target
        /// </summary>
        public void SetTarget(Transform newTarget, bool focusOnTarget = true)
        {
            target = newTarget;
            targetOffset = Vector3.zero;

            if (focusOnTarget)
            {
                FocusOnTarget(newTarget);
            }

            OnTargetChanged?.Invoke(newTarget);
            Debug.Log($"[OrbitCamera] Target set to {newTarget.name}");
        }

        /// <summary>
        /// Focus camera on a specific target
        /// </summary>
        public void FocusOnTarget(Transform focusTarget, float distance = -1)
        {
            if (focusTarget == null) return;

            target = focusTarget;
            targetPanOffset = Vector3.zero;

            // Calculate appropriate distance if not specified
            if (distance < 0)
            {
                Bounds bounds = GetBounds(focusTarget);
                distance = bounds.size.magnitude * 1.5f;
                distance = Mathf.Clamp(distance, minDistance, maxDistance);
            }

            targetDistance = distance;
            UpdateCameraPosition(false);

            Debug.Log($"[OrbitCamera] Focused on {focusTarget.name}");
        }

        /// <summary>
        /// Focus on currently selected object in editor
        /// </summary>
        public void FocusOnSelection()
        {
            // In runtime, find the first highlighted machine
            var cnc = FindObjectOfType<CNCScada.Machines.BantamCNCController>();
            if (cnc != null)
            {
                FocusOnTarget(cnc.transform, 0.8f);
            }
        }

        /// <summary>
        /// Reset view to initial state
        /// </summary>
        public void ResetView()
        {
            targetHorizontalAngle = 45f;
            targetVerticalAngle = 30f;
            targetDistance = 1.5f;
            targetPanOffset = Vector3.zero;
            autoRotate = false;

            Debug.Log("[OrbitCamera] View reset");
        }

        /// <summary>
        /// Set camera to a preset viewpoint
        /// </summary>
        public void SetViewpoint(CameraViewpoint viewpoint)
        {
            switch (viewpoint)
            {
                case CameraViewpoint.Front:
                    targetHorizontalAngle = 0f;
                    targetVerticalAngle = 0f;
                    break;
                case CameraViewpoint.Back:
                    targetHorizontalAngle = 180f;
                    targetVerticalAngle = 0f;
                    break;
                case CameraViewpoint.Left:
                    targetHorizontalAngle = -90f;
                    targetVerticalAngle = 0f;
                    break;
                case CameraViewpoint.Right:
                    targetHorizontalAngle = 90f;
                    targetVerticalAngle = 0f;
                    break;
                case CameraViewpoint.Top:
                    targetHorizontalAngle = 0f;
                    targetVerticalAngle = 89f;
                    break;
                case CameraViewpoint.Bottom:
                    targetHorizontalAngle = 0f;
                    targetVerticalAngle = -89f;
                    break;
                case CameraViewpoint.Isometric:
                    targetHorizontalAngle = 45f;
                    targetVerticalAngle = 35.264f; // arctan(1/sqrt(2))
                    break;
                case CameraViewpoint.CNCFocus:
                    var cnc = FindObjectOfType<CNCScada.Machines.BantamCNCController>();
                    if (cnc != null)
                    {
                        SetTarget(cnc.transform);
                        targetDistance = 0.6f;
                        targetHorizontalAngle = 30f;
                        targetVerticalAngle = 20f;
                    }
                    break;
                case CameraViewpoint.RobotFocus:
                    var xarm = FindObjectOfType<CNCScada.Machines.XArmLite6Controller>();
                    if (xarm != null)
                    {
                        SetTarget(xarm.transform);
                        targetDistance = 0.8f;
                        targetHorizontalAngle = -45f;
                        targetVerticalAngle = 25f;
                    }
                    break;
                case CameraViewpoint.Overview:
                    targetHorizontalAngle = 45f;
                    targetVerticalAngle = 45f;
                    targetDistance = 2.5f;
                    targetPanOffset = Vector3.zero;
                    break;
            }

            OnViewpointChanged?.Invoke(viewpoint);
            Debug.Log($"[OrbitCamera] Viewpoint set to {viewpoint}");
        }

        /// <summary>
        /// Smoothly transition to a specific orbit configuration
        /// </summary>
        public void TransitionTo(float horizontalAngle, float verticalAngle, float distance, float duration = 1f)
        {
            targetHorizontalAngle = horizontalAngle;
            targetVerticalAngle = verticalAngle;
            targetDistance = distance;

            // Adjust smooth time for transition
            StartCoroutine(TransitionCoroutine(duration));
        }

        private System.Collections.IEnumerator TransitionCoroutine(float duration)
        {
            float originalSmoothTime = smoothTime;
            smoothTime = duration * 0.5f;

            yield return new WaitForSeconds(duration);

            smoothTime = originalSmoothTime;
        }

        /// <summary>
        /// Enable/disable auto rotation
        /// </summary>
        public void SetAutoRotate(bool enabled, float speed = 10f)
        {
            autoRotate = enabled;
            autoRotateSpeed = speed;
        }

        /// <summary>
        /// Get bounds of a transform including all children
        /// </summary>
        private Bounds GetBounds(Transform target)
        {
            var renderers = target.GetComponentsInChildren<Renderer>();
            if (renderers.Length == 0)
            {
                return new Bounds(target.position, Vector3.one * 0.5f);
            }

            Bounds bounds = renderers[0].bounds;
            for (int i = 1; i < renderers.Length; i++)
            {
                bounds.Encapsulate(renderers[i].bounds);
            }
            return bounds;
        }

        // Properties
        public float Distance => currentDistance;
        public float HorizontalAngle => currentHorizontalAngle;
        public float VerticalAngle => currentVerticalAngle;
    }

    /// <summary>
    /// Preset camera viewpoints
    /// </summary>
    public enum CameraViewpoint
    {
        Front,
        Back,
        Left,
        Right,
        Top,
        Bottom,
        Isometric,
        CNCFocus,
        RobotFocus,
        Overview
    }
}
