using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace CNC_SCADA.DigitalTwin.URDF
{
    /// <summary>
    /// Initializes URDF robot models at scene startup.
    /// Add this component to a GameObject and configure robots in Inspector.
    /// </summary>
    public class URDFModelInitializer : MonoBehaviour
    {
        [System.Serializable]
        public class RobotConfig
        {
            public string robotName = "Robot";
            public string urdfPath = "";
            public Vector3 position = Vector3.zero;
            public Vector3 rotation = Vector3.zero;
            public bool loadOnStart = true;
        }

        [Header("Robots to Load")]
        [SerializeField] private List<RobotConfig> robots = new List<RobotConfig>
        {
            new RobotConfig
            {
                robotName = "xArm Lite 6",
                urdfPath = "xarm6/lite6.urdf",
                position = new Vector3(0.5f, 0, 0),
                rotation = Vector3.zero,
                loadOnStart = true
            },
            new RobotConfig
            {
                robotName = "Niryo Ned2",
                urdfPath = "niryo_ned2/niryo_ned2.urdf",
                position = new Vector3(-0.5f, 0, 0),
                rotation = Vector3.zero,
                loadOnStart = true
            }
        };

        [Header("References")]
        [SerializeField] private URDFRobotLoader loader;

        private Dictionary<string, URDFRobot> loadedRobots = new Dictionary<string, URDFRobot>();

        private void Start()
        {
            // Find or create loader
            if (loader == null)
            {
                loader = FindObjectOfType<URDFRobotLoader>();
                if (loader == null)
                {
                    var loaderObj = new GameObject("URDFRobotLoader");
                    loader = loaderObj.AddComponent<URDFRobotLoader>();
                }
            }

            // Load all configured robots
            foreach (var config in robots)
            {
                if (config.loadOnStart && !string.IsNullOrEmpty(config.urdfPath))
                {
                    StartCoroutine(LoadRobot(config));
                }
            }
        }

        private IEnumerator LoadRobot(RobotConfig config)
        {
            Debug.Log($"[URDFInitializer] Loading {config.robotName} from {config.urdfPath}");

            // Create parent transform for the robot
            var robotParent = new GameObject(config.robotName);
            robotParent.transform.SetParent(transform);
            robotParent.transform.position = config.position;
            robotParent.transform.rotation = Quaternion.Euler(config.rotation);

            // Load the URDF
            URDFRobot loadedRobot = null;
            yield return loader.LoadRobotFromFile(config.urdfPath, robotParent.transform, (robot) =>
            {
                loadedRobot = robot;
            });

            if (loadedRobot != null)
            {
                loadedRobots[config.robotName] = loadedRobot;
                Debug.Log($"[URDFInitializer] Successfully loaded {config.robotName}");
            }
            else
            {
                Debug.LogError($"[URDFInitializer] Failed to load {config.robotName}");
            }
        }

        /// <summary>
        /// Get a loaded robot by name
        /// </summary>
        public URDFRobot GetRobot(string name)
        {
            return loadedRobots.ContainsKey(name) ? loadedRobots[name] : null;
        }

        /// <summary>
        /// Get all loaded robots
        /// </summary>
        public Dictionary<string, URDFRobot> GetAllRobots()
        {
            return loadedRobots;
        }

        /// <summary>
        /// Set joint angles for a robot (in degrees)
        /// </summary>
        public void SetJointAngles(string robotName, float[] angles)
        {
            if (!loadedRobots.ContainsKey(robotName))
            {
                Debug.LogWarning($"[URDFInitializer] Robot {robotName} not found");
                return;
            }

            var robot = loadedRobots[robotName];
            var joints = new List<URDFJointObject>(robot.Joints.Values);

            for (int i = 0; i < angles.Length && i < joints.Count; i++)
            {
                var joint = joints[i];
                if (joint.Definition.Type == JointType.Revolute || joint.Definition.Type == JointType.Continuous)
                {
                    joint.CurrentPosition = angles[i] * Mathf.Deg2Rad;
                }
            }
        }

        /// <summary>
        /// Get current joint angles for a robot (in degrees)
        /// </summary>
        public float[] GetJointAngles(string robotName)
        {
            if (!loadedRobots.ContainsKey(robotName))
            {
                Debug.LogWarning($"[URDFInitializer] Robot {robotName} not found");
                return null;
            }

            var robot = loadedRobots[robotName];
            var joints = new List<URDFJointObject>(robot.Joints.Values);
            var angles = new float[joints.Count];

            for (int i = 0; i < joints.Count; i++)
            {
                angles[i] = joints[i].CurrentPosition * Mathf.Rad2Deg;
            }
            return angles;
        }
    }
}
