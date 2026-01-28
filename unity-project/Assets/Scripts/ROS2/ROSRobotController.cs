using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using CNCScada.DigitalTwin;

namespace CNCScada.ROS2
{
    /// <summary>
    /// Bridges ROS2 joint states to Unity robot visualization.
    /// Subscribes to /joint_states and updates robot transforms.
    /// </summary>
    public class ROSRobotController : MonoBehaviour
    {
        [Header("Robot Configuration")]
        [SerializeField] private string robotNamespace = "niryo_ned2";
        [SerializeField] private RobotController robotController;

        [Header("Joint Mapping")]
        [SerializeField] private string[] jointNames = new string[]
        {
            "joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6"
        };

        [Header("ROS2 Topics")]
        [SerializeField] private string jointStateTopic = "/joint_states";
        [SerializeField] private string jointCommandTopic = "/joint_trajectory_controller/command";
        [SerializeField] private string gripperTopic = "/gripper_controller/command";

        [Header("Settings")]
        [SerializeField] private bool useROS2 = true;
        [SerializeField] private float updateRate = 60f; // Hz

        // State
        private float[] lastJointPositions;
        private float lastUpdateTime;

        private void Start()
        {
            lastJointPositions = new float[jointNames.Length];

            // Subscribe to ROS2 joint states
            if (useROS2 && ROS2Connection.Instance != null)
            {
                ROS2Connection.Instance.OnJointStateReceived += HandleJointState;
            }

            // Find robot controller if not assigned
            if (robotController == null)
            {
                robotController = GetComponent<RobotController>();
            }
        }

        private void OnDestroy()
        {
            if (ROS2Connection.Instance != null)
            {
                ROS2Connection.Instance.OnJointStateReceived -= HandleJointState;
            }
        }

        /// <summary>
        /// Handle incoming joint state from ROS2
        /// </summary>
        private void HandleJointState(JointStateMsg msg)
        {
            if (msg.name == null || msg.position == null) return;
            if (robotController == null) return;

            // Map ROS joint names to our array indices
            float[] jointPositions = new float[jointNames.Length];

            for (int i = 0; i < jointNames.Length; i++)
            {
                // Find this joint in the ROS message
                int rosIndex = Array.IndexOf(msg.name, jointNames[i]);
                if (rosIndex >= 0 && rosIndex < msg.position.Length)
                {
                    // Convert from radians to degrees
                    jointPositions[i] = (float)(msg.position[rosIndex] * Mathf.Rad2Deg);
                }
                else
                {
                    jointPositions[i] = lastJointPositions[i];
                }
            }

            // Update robot controller
            robotController.SetJointAnglesDegrees(jointPositions);

            // Store for interpolation
            lastJointPositions = jointPositions;
            lastUpdateTime = Time.time;
        }

        /// <summary>
        /// Send joint trajectory command to ROS2
        /// </summary>
        public void SendJointCommand(float[] targetPositions, float duration = 1f)
        {
            if (!useROS2 || ROS2Connection.Instance == null) return;

            // Create trajectory message
            var trajectory = new JointTrajectoryMsg
            {
                joint_names = jointNames,
                points = new JointTrajectoryPoint[]
                {
                    new JointTrajectoryPoint
                    {
                        positions = ConvertToRadians(targetPositions),
                        time_from_start = duration
                    }
                }
            };

#if UNITY_ROBOTICS_ROS_TCP_CONNECTOR
            ROSConnection.GetOrCreateInstance().Publish(jointCommandTopic, trajectory);
#endif
            Debug.Log($"[ROSRobot] Sent trajectory command: {string.Join(", ", targetPositions)}");
        }

        /// <summary>
        /// Send gripper command
        /// </summary>
        public void SendGripperCommand(float opening)
        {
            if (!useROS2 || ROS2Connection.Instance == null) return;

            var cmd = new GripperCommandMsg
            {
                position = opening,
                max_effort = 100f
            };

#if UNITY_ROBOTICS_ROS_TCP_CONNECTOR
            ROSConnection.GetOrCreateInstance().Publish(gripperTopic, cmd);
#endif

            // Also update local visualization
            robotController?.SetGripperOpening(opening);
        }

        /// <summary>
        /// Move to home position via ROS2
        /// </summary>
        public void MoveToHome()
        {
            float[] homePosition = new float[jointNames.Length]; // All zeros
            SendJointCommand(homePosition, 3f);
            robotController?.MoveToHome();
        }

        /// <summary>
        /// Move to a named pose (predefined in ROS2)
        /// </summary>
        public void MoveToPose(string poseName)
        {
            var cmd = new CommandMsg
            {
                command_type = "move_to_pose",
                gcode = poseName,
                timestamp = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() / 1000.0
            };
            ROS2Connection.Instance?.PublishCommand(cmd);
        }

        private double[] ConvertToRadians(float[] degrees)
        {
            double[] radians = new double[degrees.Length];
            for (int i = 0; i < degrees.Length; i++)
            {
                radians[i] = degrees[i] * Mathf.Deg2Rad;
            }
            return radians;
        }

        // Public accessors
        public string RobotNamespace => robotNamespace;
        public string[] JointNames => jointNames;
        public float[] CurrentJointPositions => lastJointPositions;
    }

    // =========================================================================
    // Additional ROS2 Message Types for Robot Control
    // =========================================================================

    /// <summary>
    /// Joint trajectory message
    /// Matches: trajectory_msgs/msg/JointTrajectory
    /// </summary>
    [Serializable]
    public class JointTrajectoryMsg
    {
        public HeaderMsg header;
        public string[] joint_names;
        public JointTrajectoryPoint[] points;
    }

    [Serializable]
    public class JointTrajectoryPoint
    {
        public double[] positions;
        public double[] velocities;
        public double[] accelerations;
        public double[] effort;
        public double time_from_start;
    }

    [Serializable]
    public class HeaderMsg
    {
        public double stamp;
        public string frame_id;
    }

    /// <summary>
    /// Gripper command message
    /// </summary>
    [Serializable]
    public class GripperCommandMsg
    {
        public float position; // 0 = closed, 1 = open
        public float max_effort;
    }
}
