using UnityEngine;
using System;

namespace CNCScada.DigitalTwin
{
    /// <summary>
    /// Animates 6-axis CNC machine kinematics (X, Y, Z, A, B, C)
    /// Handles axis limits, collision detection, and smooth motion
    /// </summary>
    public class KinematicsAnimator : MonoBehaviour
    {
        #region Serialized Fields

        [Header("Axis Transforms")]
        [SerializeField] private Transform xAxisTransform;
        [SerializeField] private Transform yAxisTransform;
        [SerializeField] private Transform zAxisTransform;
        [SerializeField] private Transform aAxisTransform; // Rotary A
        [SerializeField] private Transform bAxisTransform; // Rotary B
        [SerializeField] private Transform cAxisTransform; // Rotary C

        [Header("Axis Limits (mm or degrees)")]
        [SerializeField] public Vector2 xLimits = new Vector2(0, 200);
        [SerializeField] public Vector2 yLimits = new Vector2(0, 150);
        [SerializeField] public Vector2 zLimits = new Vector2(-100, 0);
        [SerializeField] public Vector2 aLimits = new Vector2(-360, 360);
        [SerializeField] public Vector2 bLimits = new Vector2(-90, 90);
        [SerializeField] public Vector2 cLimits = new Vector2(-360, 360);

        [Header("Animation Settings")]
        [SerializeField] private float linearSpeed = 100f; // mm/s
        [SerializeField] private float rotarySpeed = 90f; // deg/s
        [SerializeField] private bool smoothMotion = true;
        [SerializeField] private float dampingTime = 0.1f;

        [Header("Safety")]
        [SerializeField] private bool enforceHardLimits = true;
        [SerializeField] private bool enableCollisionDetection = true;
        [SerializeField] private float softLimitMargin = 5f; // mm

        #endregion

        #region Private Fields

        private Vector3 _targetPosition;
        private Vector3 _targetRotation;
        private Vector3 _currentVelocity;
        private Vector3 _rotationVelocity;
        private bool _limitViolation;
        private ISO23247StateHandler _stateHandler;

        #endregion

        #region Events

        public event Action<string> OnLimitViolation;
        public event Action OnTargetReached;
        public event Action<Vector3, Vector3> OnMotionUpdate;

        #endregion

        #region Unity Lifecycle

        void Start()
        {
            _stateHandler = GetComponent<ISO23247StateHandler>();
            if (_stateHandler != null)
            {
                _stateHandler.OnStateUpdated += HandleStateUpdate;
            }
        }

        void Update()
        {
            if (smoothMotion)
            {
                AnimateSmooth();
            }
        }

        void OnDestroy()
        {
            if (_stateHandler != null)
            {
                _stateHandler.OnStateUpdated -= HandleStateUpdate;
            }
        }

        #endregion

        #region Public Methods

        /// <summary>
        /// Set target position for all axes
        /// </summary>
        public void SetTargetPosition(Vector3 linearPosition, Vector3 rotaryPosition)
        {
            _targetPosition = linearPosition;
            _targetRotation = rotaryPosition;

            if (enforceHardLimits)
            {
                ClampToLimits();
            }

            if (!smoothMotion)
            {
                ApplyTargetImmediate();
            }
        }

        /// <summary>
        /// Get current target position
        /// </summary>
        public Vector3 GetTargetPosition()
        {
            return _targetPosition;
        }

        /// <summary>
        /// Check if position is within limits
        /// </summary>
        public bool IsWithinLimits()
        {
            return IsInRange(_targetPosition.x, xLimits) &&
                   IsInRange(_targetPosition.y, yLimits) &&
                   IsInRange(_targetPosition.z, zLimits) &&
                   IsInRange(_targetRotation.x, aLimits) &&
                   IsInRange(_targetRotation.y, bLimits) &&
                   IsInRange(_targetRotation.z, cLimits);
        }

        /// <summary>
        /// Get distance to soft limits
        /// </summary>
        public float GetSoftLimitDistance()
        {
            float minDist = float.MaxValue;

            minDist = Mathf.Min(minDist, _targetPosition.x - (xLimits.x + softLimitMargin));
            minDist = Mathf.Min(minDist, (xLimits.y - softLimitMargin) - _targetPosition.x);
            minDist = Mathf.Min(minDist, _targetPosition.y - (yLimits.x + softLimitMargin));
            minDist = Mathf.Min(minDist, (yLimits.y - softLimitMargin) - _targetPosition.y);
            minDist = Mathf.Min(minDist, _targetPosition.z - (zLimits.x + softLimitMargin));
            minDist = Mathf.Min(minDist, (zLimits.y - softLimitMargin) - _targetPosition.z);

            return minDist;
        }

        /// <summary>
        /// Emergency stop - halt all motion
        /// </summary>
        public void EmergencyStop()
        {
            _targetPosition = GetCurrentPosition();
            _targetRotation = GetCurrentRotation();
            _currentVelocity = Vector3.zero;
            _rotationVelocity = Vector3.zero;
        }

        /// <summary>
        /// Get current linear position
        /// </summary>
        public Vector3 GetCurrentPosition()
        {
            if (xAxisTransform == null) return Vector3.zero;
            return xAxisTransform.localPosition;
        }

        /// <summary>
        /// Get current rotary position
        /// </summary>
        public Vector3 GetCurrentRotation()
        {
            if (aAxisTransform == null) return Vector3.zero;
            return aAxisTransform.localEulerAngles;
        }

        #endregion

        #region Private Methods

        private void HandleStateUpdate(MachineState state)
        {
            var linearPos = new Vector3(state.x, state.z, state.y); // Unity coordinate conversion
            var rotaryPos = new Vector3(state.a, state.b, state.c);
            SetTargetPosition(linearPos, rotaryPos);
        }

        private void AnimateSmooth()
        {
            if (xAxisTransform != null)
            {
                var newPos = Vector3.SmoothDamp(
                    xAxisTransform.localPosition,
                    _targetPosition,
                    ref _currentVelocity,
                    dampingTime,
                    linearSpeed
                );

                xAxisTransform.localPosition = newPos;

                // Y and Z follow if they're separate transforms
                if (yAxisTransform != null && yAxisTransform != xAxisTransform)
                {
                    yAxisTransform.localPosition = new Vector3(0, 0, newPos.z);
                }
                if (zAxisTransform != null && zAxisTransform != xAxisTransform && zAxisTransform != yAxisTransform)
                {
                    zAxisTransform.localPosition = new Vector3(0, newPos.y, 0);
                }
            }

            if (aAxisTransform != null)
            {
                var currentRot = aAxisTransform.localEulerAngles;
                var newRot = SmoothDampAngle(
                    currentRot,
                    _targetRotation,
                    ref _rotationVelocity,
                    dampingTime,
                    rotarySpeed
                );

                aAxisTransform.localEulerAngles = new Vector3(newRot.x, currentRot.y, currentRot.z);

                if (bAxisTransform != null && bAxisTransform != aAxisTransform)
                {
                    bAxisTransform.localEulerAngles = new Vector3(currentRot.x, newRot.y, currentRot.z);
                }
                if (cAxisTransform != null && cAxisTransform != aAxisTransform && cAxisTransform != bAxisTransform)
                {
                    cAxisTransform.localEulerAngles = new Vector3(currentRot.x, currentRot.y, newRot.z);
                }
            }

            OnMotionUpdate?.Invoke(GetCurrentPosition(), GetCurrentRotation());

            // Check if target reached
            if (Vector3.Distance(GetCurrentPosition(), _targetPosition) < 0.1f &&
                Vector3.Distance(GetCurrentRotation(), _targetRotation) < 0.5f)
            {
                OnTargetReached?.Invoke();
            }
        }

        private void ApplyTargetImmediate()
        {
            if (xAxisTransform != null)
            {
                xAxisTransform.localPosition = _targetPosition;
            }
            if (aAxisTransform != null)
            {
                aAxisTransform.localEulerAngles = _targetRotation;
            }
        }

        private void ClampToLimits()
        {
            _limitViolation = false;

            if (!IsInRange(_targetPosition.x, xLimits))
            {
                _targetPosition.x = Mathf.Clamp(_targetPosition.x, xLimits.x, xLimits.y);
                _limitViolation = true;
                OnLimitViolation?.Invoke("X axis limit exceeded");
            }

            if (!IsInRange(_targetPosition.y, yLimits))
            {
                _targetPosition.y = Mathf.Clamp(_targetPosition.y, yLimits.x, yLimits.y);
                _limitViolation = true;
                OnLimitViolation?.Invoke("Y axis limit exceeded");
            }

            if (!IsInRange(_targetPosition.z, zLimits))
            {
                _targetPosition.z = Mathf.Clamp(_targetPosition.z, zLimits.x, zLimits.y);
                _limitViolation = true;
                OnLimitViolation?.Invoke("Z axis limit exceeded");
            }

            if (!IsInRange(_targetRotation.x, aLimits))
            {
                _targetRotation.x = Mathf.Clamp(_targetRotation.x, aLimits.x, aLimits.y);
                _limitViolation = true;
                OnLimitViolation?.Invoke("A axis limit exceeded");
            }

            if (!IsInRange(_targetRotation.y, bLimits))
            {
                _targetRotation.y = Mathf.Clamp(_targetRotation.y, bLimits.x, bLimits.y);
                _limitViolation = true;
                OnLimitViolation?.Invoke("B axis limit exceeded");
            }

            if (!IsInRange(_targetRotation.z, cLimits))
            {
                _targetRotation.z = Mathf.Clamp(_targetRotation.z, cLimits.x, cLimits.y);
                _limitViolation = true;
                OnLimitViolation?.Invoke("C axis limit exceeded");
            }
        }

        private bool IsInRange(float value, Vector2 limits)
        {
            return value >= limits.x && value <= limits.y;
        }

        private Vector3 SmoothDampAngle(Vector3 current, Vector3 target, ref Vector3 velocity, float smoothTime, float maxSpeed)
        {
            return new Vector3(
                Mathf.SmoothDampAngle(current.x, target.x, ref velocity.x, smoothTime, maxSpeed),
                Mathf.SmoothDampAngle(current.y, target.y, ref velocity.y, smoothTime, maxSpeed),
                Mathf.SmoothDampAngle(current.z, target.z, ref velocity.z, smoothTime, maxSpeed)
            );
        }

        #endregion

        #region Gizmos

        void OnDrawGizmosSelected()
        {
            // Draw axis limits
            Gizmos.color = Color.yellow;
            DrawLimitBox();

            // Draw soft limit margin
            Gizmos.color = Color.green;
            DrawSoftLimitBox();

            // Draw target position
            if (Application.isPlaying)
            {
                Gizmos.color = Color.cyan;
                Gizmos.DrawWireSphere(_targetPosition, 2f);
            }
        }

        private void DrawLimitBox()
        {
            Vector3 center = new Vector3(
                (xLimits.x + xLimits.y) / 2f,
                (zLimits.x + zLimits.y) / 2f,
                (yLimits.x + yLimits.y) / 2f
            );
            Vector3 size = new Vector3(
                xLimits.y - xLimits.x,
                zLimits.y - zLimits.x,
                yLimits.y - yLimits.x
            );
            Gizmos.DrawWireCube(center, size);
        }

        private void DrawSoftLimitBox()
        {
            Vector3 center = new Vector3(
                (xLimits.x + xLimits.y) / 2f,
                (zLimits.x + zLimits.y) / 2f,
                (yLimits.x + yLimits.y) / 2f
            );
            Vector3 size = new Vector3(
                xLimits.y - xLimits.x - 2 * softLimitMargin,
                zLimits.y - zLimits.x - 2 * softLimitMargin,
                yLimits.y - yLimits.x - 2 * softLimitMargin
            );
            Gizmos.DrawWireCube(center, size);
        }

        #endregion
    }
}
