using System;
using UnityEngine;

namespace CNCScada.URDF
{
    /// <summary>
    /// URDF import settings for robot models.
    /// Used by Unity Robotics Hub URDF Importer.
    /// </summary>
    [CreateAssetMenu(fileName = "URDFImportSettings", menuName = "CNC SCADA/URDF Import Settings")]
    public class URDFImportSettings : ScriptableObject
    {
        [Header("Import Paths")]
        [Tooltip("Path to URDF files relative to project root")]
        public string urdfBasePath = "../../ros2_ws/src/robot_description/urdf/";

        [Tooltip("Path to mesh files (STL/DAE)")]
        public string meshBasePath = "../../ros2_ws/src/robot_description/meshes/";

        [Header("Import Options")]
        [Tooltip("Scale factor for imported models (1 = meters)")]
        public float importScale = 1f;

        [Tooltip("Flip Y and Z axes for coordinate system conversion")]
        public bool flipYZ = true;

        [Tooltip("Create physics colliders for links")]
        public bool createColliders = true;

        [Tooltip("Use simplified collision meshes if available")]
        public bool useCollisionMeshes = true;

        [Header("Joint Settings")]
        [Tooltip("Create ArticulationBody components for joints")]
        public bool useArticulationBodies = true;

        [Tooltip("Enable joint limits")]
        public bool enableJointLimits = true;

        [Tooltip("Joint damping coefficient")]
        public float jointDamping = 10f;

        [Tooltip("Joint stiffness coefficient")]
        public float jointStiffness = 10000f;

        [Header("Robot Configurations")]
        public RobotConfig[] robots = new RobotConfig[]
        {
            new RobotConfig
            {
                name = "niryo_ned2",
                urdfFile = "niryo_ned2/ned2.urdf",
                baseLink = "base_link",
                toolLink = "tool_link",
                jointPrefix = "joint_",
                numJoints = 6
            },
            new RobotConfig
            {
                name = "xarm_lite6",
                urdfFile = "xarm/xarm6_robot.urdf",
                baseLink = "link_base",
                toolLink = "link_eef",
                jointPrefix = "joint",
                numJoints = 6
            }
        };

        /// <summary>
        /// Get configuration for a specific robot
        /// </summary>
        public RobotConfig GetRobotConfig(string robotName)
        {
            foreach (var config in robots)
            {
                if (config.name == robotName)
                {
                    return config;
                }
            }
            return null;
        }
    }

    [Serializable]
    public class RobotConfig
    {
        [Tooltip("Robot identifier")]
        public string name;

        [Tooltip("URDF file path relative to urdfBasePath")]
        public string urdfFile;

        [Tooltip("Name of the base link")]
        public string baseLink;

        [Tooltip("Name of the end effector link")]
        public string toolLink;

        [Tooltip("Prefix for joint names")]
        public string jointPrefix;

        [Tooltip("Number of joints")]
        public int numJoints;

        [Tooltip("Joint axis definitions (local)")]
        public Vector3[] jointAxes;

        [Tooltip("Default home position (degrees)")]
        public float[] homePosition;
    }
}
