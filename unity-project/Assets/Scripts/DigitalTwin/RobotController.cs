using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace CNCScada.DigitalTwin
{
    /// <summary>
    /// Controller for robot arm visualization.
    /// Handles forward kinematics, joint animation, and gripper state.
    /// </summary>
    public class RobotController : MonoBehaviour
    {
        [Header("Robot Info")]
        [SerializeField] private string robotId;
        [SerializeField] private RobotType robotType;

        [Header("Joint References")]
        [SerializeField] private Transform[] joints;
        [SerializeField] private Transform gripper;
        [SerializeField] private Transform gripperLeft;
        [SerializeField] private Transform gripperRight;

        [Header("Joint Limits (degrees)")]
        [SerializeField] private Vector2[] jointLimits;

        [Header("Motion Settings")]
        [SerializeField] private float jointSmoothTime = 0.1f;
        [SerializeField] private float gripperOpenAngle = 45f;
        [SerializeField] private float gripperClosedAngle = 0f;

        // Joint state
        private float[] currentJointAngles;
        private float[] targetJointAngles;
        private float[] jointVelocities;
        private bool gripperClosed = false;

        // Robot configuration
        private int numJoints = 6;
        private Vector3[] jointAxes; // Rotation axis for each joint

        public string RobotId => robotId;
        public RobotType Type => robotType;
        public float[] JointAngles => currentJointAngles;

        /// <summary>
        /// Initialize the robot controller
        /// </summary>
        public void Initialize(string id, RobotType type)
        {
            robotId = id;
            robotType = type;

            // Configure based on robot type
            switch (type)
            {
                case RobotType.NiryoNed2:
                    numJoints = 6;
                    jointAxes = new Vector3[]
                    {
                        Vector3.up,      // J1 - Base rotation
                        Vector3.right,   // J2 - Shoulder
                        Vector3.right,   // J3 - Elbow
                        Vector3.up,      // J4 - Wrist rotation
                        Vector3.right,   // J5 - Wrist bend
                        Vector3.up       // J6 - End effector rotation
                    };
                    jointLimits = new Vector2[]
                    {
                        new Vector2(-175, 175),
                        new Vector2(-90, 36.7f),
                        new Vector2(-80, 90),
                        new Vector2(-175, 175),
                        new Vector2(-100, 110),
                        new Vector2(-145, 145)
                    };
                    break;

                case RobotType.XArm:
                    numJoints = 6;
                    jointAxes = new Vector3[]
                    {
                        Vector3.up,
                        Vector3.right,
                        Vector3.right,
                        Vector3.right,
                        Vector3.up,
                        Vector3.right
                    };
                    jointLimits = new Vector2[]
                    {
                        new Vector2(-360, 360),
                        new Vector2(-118, 120),
                        new Vector2(-225, 11),
                        new Vector2(-360, 360),
                        new Vector2(-97, 180),
                        new Vector2(-360, 360)
                    };
                    break;

                default:
                    numJoints = 6;
                    jointAxes = new Vector3[] { Vector3.up, Vector3.right, Vector3.right, Vector3.up, Vector3.right, Vector3.up };
                    jointLimits = new Vector2[6];
                    for (int i = 0; i < 6; i++) jointLimits[i] = new Vector2(-180, 180);
                    break;
            }

            // Initialize arrays
            currentJointAngles = new float[numJoints];
            targetJointAngles = new float[numJoints];
            jointVelocities = new float[numJoints];

            // Find joint transforms if not assigned
            if (joints == null || joints.Length == 0)
            {
                joints = new Transform[numJoints];
                for (int i = 0; i < numJoints; i++)
                {
                    joints[i] = transform.Find($"Joint{i + 1}");
                }
            }

            Debug.Log($"[RobotController] Initialized {robotId} as {robotType} with {numJoints} joints");
        }

        private void Update()
        {
            UpdateJointPositions();
            UpdateGripper();
        }

        /// <summary>
        /// Set target joint angles (radians)
        /// </summary>
        public void SetJointAngles(float[] angles)
        {
            if (angles == null || angles.Length != numJoints) return;

            for (int i = 0; i < numJoints; i++)
            {
                // Convert radians to degrees and clamp to limits
                float degrees = angles[i] * Mathf.Rad2Deg;
                targetJointAngles[i] = Mathf.Clamp(degrees, jointLimits[i].x, jointLimits[i].y);
            }
        }

        /// <summary>
        /// Set target joint angles (degrees)
        /// </summary>
        public void SetJointAnglesDegrees(float[] angles)
        {
            if (angles == null || angles.Length != numJoints) return;

            for (int i = 0; i < numJoints; i++)
            {
                targetJointAngles[i] = Mathf.Clamp(angles[i], jointLimits[i].x, jointLimits[i].y);
            }
        }

        /// <summary>
        /// Set a single joint angle
        /// </summary>
        public void SetJointAngle(int jointIndex, float angleDegrees)
        {
            if (jointIndex < 0 || jointIndex >= numJoints) return;
            targetJointAngles[jointIndex] = Mathf.Clamp(angleDegrees, jointLimits[jointIndex].x, jointLimits[jointIndex].y);
        }

        private void UpdateJointPositions()
        {
            for (int i = 0; i < numJoints; i++)
            {
                // Smooth interpolation
                currentJointAngles[i] = Mathf.SmoothDamp(
                    currentJointAngles[i],
                    targetJointAngles[i],
                    ref jointVelocities[i],
                    jointSmoothTime
                );

                // Apply rotation to joint transform
                if (joints != null && joints.Length > i && joints[i] != null)
                {
                    joints[i].localRotation = Quaternion.AngleAxis(currentJointAngles[i], jointAxes[i]);
                }
            }
        }

        /// <summary>
        /// Open or close the gripper
        /// </summary>
        public void SetGripperState(bool closed)
        {
            gripperClosed = closed;
        }

        /// <summary>
        /// Set gripper opening percentage (0 = closed, 1 = open)
        /// </summary>
        public void SetGripperOpening(float opening)
        {
            // This will be used in UpdateGripper for smooth animation
            gripperClosed = opening < 0.5f;
        }

        private void UpdateGripper()
        {
            float targetAngle = gripperClosed ? gripperClosedAngle : gripperOpenAngle;

            if (gripperLeft != null)
            {
                var euler = gripperLeft.localEulerAngles;
                euler.z = Mathf.LerpAngle(euler.z, targetAngle, Time.deltaTime * 10f);
                gripperLeft.localEulerAngles = euler;
            }

            if (gripperRight != null)
            {
                var euler = gripperRight.localEulerAngles;
                euler.z = Mathf.LerpAngle(euler.z, -targetAngle, Time.deltaTime * 10f);
                gripperRight.localEulerAngles = euler;
            }
        }

        /// <summary>
        /// Get the end effector world position
        /// </summary>
        public Vector3 GetEndEffectorPosition()
        {
            if (gripper != null)
            {
                return gripper.position;
            }
            else if (joints != null && joints.Length > 0 && joints[numJoints - 1] != null)
            {
                return joints[numJoints - 1].position;
            }
            return transform.position;
        }

        /// <summary>
        /// Get the end effector world rotation
        /// </summary>
        public Quaternion GetEndEffectorRotation()
        {
            if (gripper != null)
            {
                return gripper.rotation;
            }
            else if (joints != null && joints.Length > 0 && joints[numJoints - 1] != null)
            {
                return joints[numJoints - 1].rotation;
            }
            return transform.rotation;
        }

        /// <summary>
        /// Move to home position
        /// </summary>
        public void MoveToHome()
        {
            for (int i = 0; i < numJoints; i++)
            {
                targetJointAngles[i] = 0f;
            }
            Debug.Log($"[RobotController] {robotId} moving to home");
        }

        /// <summary>
        /// Check if robot is at target position
        /// </summary>
        public bool IsAtTarget(float tolerance = 0.5f)
        {
            for (int i = 0; i < numJoints; i++)
            {
                if (Mathf.Abs(currentJointAngles[i] - targetJointAngles[i]) > tolerance)
                {
                    return false;
                }
            }
            return true;
        }

        /// <summary>
        /// Get joint limits for UI display
        /// </summary>
        public Vector2 GetJointLimits(int jointIndex)
        {
            if (jointIndex < 0 || jointIndex >= numJoints)
            {
                return new Vector2(-180, 180);
            }
            return jointLimits[jointIndex];
        }

        /// <summary>
        /// Highlight the robot (for selection)
        /// </summary>
        public void SetHighlighted(bool highlighted)
        {
            var renderers = GetComponentsInChildren<Renderer>();
            foreach (var r in renderers)
            {
                var color = r.material.color;
                color.a = highlighted ? 1f : 0.8f;
                r.material.color = color;
            }
        }
    }
}
