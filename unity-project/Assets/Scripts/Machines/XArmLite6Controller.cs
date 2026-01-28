using System;
using System.IO;
using UnityEngine;
using CNC_SCADA.DigitalTwin.URDF;

namespace CNCScada.Machines
{
    /// <summary>
    /// Controller for UFactory xArm Lite 6 robot arm.
    ///
    /// Specifications:
    /// - 6 DOF collaborative robot
    /// - Payload: 3kg
    /// - Reach: 700mm
    /// - Repeatability: ±0.1mm
    /// - Weight: 12.2kg
    ///
    /// DH Parameters (approximate):
    /// Link | a(mm) | d(mm)  | alpha(deg) | theta offset
    /// 1    | 0     | 267    | -90        | 0
    /// 2    | 289   | 0      | 0          | -90
    /// 3    | 77.5  | 0      | -90        | 0
    /// 4    | 0     | 342.5  | 90         | 0
    /// 5    | 0     | 0      | -90        | 0
    /// 6    | 0     | 97     | 0          | 0
    /// </summary>
    public class XArmLite6Controller : MonoBehaviour
    {
        [Header("Robot Identification")]
        public string robotId = "xarm-lite6-001";
        public string robotName = "xArm Lite 6";

        [Header("Joint Configuration")]
        public Transform[] joints = new Transform[6];
        public Transform endEffector;
        public Transform gripperLeft;
        public Transform gripperRight;

        [Header("Joint Limits (degrees)")]
        public Vector2[] jointLimits = new Vector2[]
        {
            new Vector2(-360, 360),   // J1: Base
            new Vector2(-118, 120),   // J2: Shoulder
            new Vector2(-225, 11),    // J3: Elbow
            new Vector2(-360, 360),   // J4: Wrist 1
            new Vector2(-97, 180),    // J5: Wrist 2
            new Vector2(-360, 360)    // J6: Wrist 3
        };

        [Header("Current State")]
        [SerializeField] private float[] currentJointAngles = new float[6];
        [SerializeField] private float[] targetJointAngles = new float[6];
        [SerializeField] private float gripperPosition; // 0 = closed, 1 = open
        [SerializeField] private RobotStatus status = RobotStatus.Idle;

        [Header("Motion Settings")]
        public float jointSmoothTime = 0.1f;
        public float maxJointSpeed = 180f; // deg/s

        // Link lengths (meters) for xArm Lite 6
        private readonly float[] linkLengths = { 0.267f, 0.289f, 0.0775f, 0.3425f, 0f, 0.097f };

        // Joint rotation axes (local)
        private readonly Vector3[] jointAxes = {
            Vector3.up,      // J1
            Vector3.forward, // J2
            Vector3.forward, // J3
            Vector3.up,      // J4
            Vector3.forward, // J5
            Vector3.up       // J6
        };

        // Internal state
        private float[] jointVelocities = new float[6];
        private float gripperVelocity;

        // Events
        public event Action<float[]> OnJointsChanged;
        public event Action<RobotStatus> OnStatusChanged;

        public enum RobotStatus
        {
            Idle,
            Moving,
            Error,
            EmergencyStop,
            Teaching
        }

        private void Update()
        {
            UpdateJointPositions();
            UpdateGripper();
        }

        /// <summary>
        /// Set target joint angles (degrees)
        /// </summary>
        public void SetJointAngles(float[] angles)
        {
            if (angles == null || angles.Length != 6) return;

            for (int i = 0; i < 6; i++)
            {
                targetJointAngles[i] = Mathf.Clamp(angles[i], jointLimits[i].x, jointLimits[i].y);
            }
        }

        /// <summary>
        /// Set single joint angle (degrees)
        /// </summary>
        public void SetJointAngle(int jointIndex, float angle)
        {
            if (jointIndex < 0 || jointIndex >= 6) return;
            targetJointAngles[jointIndex] = Mathf.Clamp(angle, jointLimits[jointIndex].x, jointLimits[jointIndex].y);
        }

        /// <summary>
        /// Set gripper position (0 = closed, 1 = open)
        /// </summary>
        public void SetGripperPosition(float position)
        {
            gripperPosition = Mathf.Clamp01(position);
        }

        /// <summary>
        /// Set gripper opening (alias for SetGripperPosition for compatibility)
        /// </summary>
        public void SetGripperOpening(float opening)
        {
            SetGripperPosition(opening);
        }

        /// <summary>
        /// Set target joint angles (alias for SetJointAngles for compatibility)
        /// </summary>
        public void SetTargetJointAngles(float[] angles)
        {
            SetJointAngles(angles);
        }

        /// <summary>
        /// Set joint angles in degrees
        /// </summary>
        public void SetJointAnglesDegrees(float[] degrees)
        {
            SetJointAngles(degrees);
        }

        /// <summary>
        /// Move to home position
        /// </summary>
        public void MoveToHome()
        {
            targetJointAngles = new float[] { 0, 0, 0, 0, 0, 0 };
        }

        private void UpdateJointPositions()
        {
            bool anyMoving = false;

            for (int i = 0; i < 6; i++)
            {
                float prev = currentJointAngles[i];
                currentJointAngles[i] = Mathf.SmoothDamp(
                    currentJointAngles[i],
                    targetJointAngles[i],
                    ref jointVelocities[i],
                    jointSmoothTime
                );

                if (Mathf.Abs(currentJointAngles[i] - targetJointAngles[i]) > 0.1f)
                {
                    anyMoving = true;
                }

                // Apply to joint transform
                if (joints != null && i < joints.Length && joints[i] != null)
                {
                    joints[i].localRotation = Quaternion.AngleAxis(currentJointAngles[i], jointAxes[i]);
                }
            }

            var newStatus = anyMoving ? RobotStatus.Moving : RobotStatus.Idle;
            if (newStatus != status)
            {
                status = newStatus;
                OnStatusChanged?.Invoke(status);
            }

            OnJointsChanged?.Invoke(currentJointAngles);
        }

        private void UpdateGripper()
        {
            if (gripperLeft == null || gripperRight == null) return;

            float openAngle = 25f; // degrees when fully open
            float currentAngle = gripperPosition * openAngle;

            gripperLeft.localRotation = Quaternion.Euler(0, 0, currentAngle);
            gripperRight.localRotation = Quaternion.Euler(0, 0, -currentAngle);
        }

        /// <summary>
        /// Get end effector world position
        /// </summary>
        public Vector3 GetEndEffectorPosition()
        {
            if (endEffector != null)
                return endEffector.position;
            if (joints != null && joints.Length > 5 && joints[5] != null)
                return joints[5].position;
            return transform.position;
        }

        /// <summary>
        /// Create visual representation of xArm Lite 6
        /// </summary>
        public static GameObject CreateVisual(Transform parent = null)
        {
            var robot = new GameObject("xArmLite6");
            if (parent != null) robot.transform.SetParent(parent);

            // Colors matching xArm design (white/light gray with blue accents)
            Color baseColor = new Color(0.9f, 0.9f, 0.92f);
            Color jointColor = new Color(0.3f, 0.3f, 0.35f);
            Color linkColor = new Color(0.95f, 0.95f, 0.97f);
            Color accentColor = new Color(0.2f, 0.5f, 0.85f); // xArm blue

            var joints = new Transform[6];

            // Base (J1)
            var baseObj = CreateCylinder(robot.transform, "Base", Vector3.zero,
                new Vector3(0.12f, 0.04f, 0.12f), jointColor);
            var j1 = CreateJointVisual(baseObj.transform, "J1",
                new Vector3(0, 0.04f, 0), 0.05f, 0.08f, jointColor);
            joints[0] = j1.transform;

            // Link 1 + J2
            var link1 = CreateCylinder(j1.transform, "Link1", new Vector3(0, 0.1f, 0),
                new Vector3(0.04f, 0.08f, 0.04f), linkColor);
            var j2 = CreateJointVisual(link1.transform, "J2",
                new Vector3(0, 0.09f, 0), 0.045f, 0.05f, jointColor);
            joints[1] = j2.transform;

            // Link 2 (upper arm) + J3
            var link2 = CreateCapsule(j2.transform, "Link2", new Vector3(0, 0.12f, 0),
                new Vector3(0.035f, 0.12f, 0.035f), linkColor);
            var j3 = CreateJointVisual(link2.transform, "J3",
                new Vector3(0, 0.12f, 0), 0.04f, 0.045f, jointColor);
            joints[2] = j3.transform;

            // Link 3 (forearm) + J4
            var link3 = CreateCapsule(j3.transform, "Link3", new Vector3(0, 0.10f, 0),
                new Vector3(0.03f, 0.10f, 0.03f), linkColor);
            var j4 = CreateJointVisual(link3.transform, "J4",
                new Vector3(0, 0.10f, 0), 0.035f, 0.04f, jointColor);
            joints[3] = j4.transform;

            // Link 4 + J5
            var link4 = CreateCylinder(j4.transform, "Link4", new Vector3(0, 0.05f, 0),
                new Vector3(0.025f, 0.04f, 0.025f), linkColor);
            var j5 = CreateJointVisual(link4.transform, "J5",
                new Vector3(0, 0.05f, 0), 0.03f, 0.035f, jointColor);
            joints[4] = j5.transform;

            // Link 5 + J6 (wrist)
            var link5 = CreateCylinder(j5.transform, "Link5", new Vector3(0, 0.03f, 0),
                new Vector3(0.022f, 0.025f, 0.022f), linkColor);
            var j6 = CreateJointVisual(link5.transform, "J6",
                new Vector3(0, 0.03f, 0), 0.025f, 0.02f, accentColor);
            joints[5] = j6.transform;

            // End effector / Gripper
            var eeBase = CreateCube(j6.transform, "EE_Base", new Vector3(0, 0.025f, 0),
                new Vector3(0.05f, 0.015f, 0.03f), jointColor);

            var gripperL = CreateCube(eeBase.transform, "GripperLeft", new Vector3(-0.018f, 0.02f, 0),
                new Vector3(0.008f, 0.025f, 0.015f), accentColor);
            var gripperR = CreateCube(eeBase.transform, "GripperRight", new Vector3(0.018f, 0.02f, 0),
                new Vector3(0.008f, 0.025f, 0.015f), accentColor);

            // Add controller
            var controller = robot.AddComponent<XArmLite6Controller>();
            controller.joints = joints;
            controller.endEffector = eeBase.transform;
            controller.gripperLeft = gripperL.transform;
            controller.gripperRight = gripperR.transform;

            return robot;
        }

        /// <summary>
        /// Create visual representation from actual STL mesh files
        /// Uses URDF joint transforms for correct positioning and orientation
        /// </summary>
        public static GameObject CreateVisualFromSTL(Transform parent = null)
        {
            var robot = new GameObject("xArmLite6");
            if (parent != null) robot.transform.SetParent(parent);

            string basePath = Path.Combine(Application.streamingAssetsPath, "URDF", "xarm6", "meshes", "lite6", "visual");

            // xArm colors
            Color linkColor = new Color(0.95f, 0.95f, 0.97f);  // White
            Color jointColor = new Color(0.3f, 0.3f, 0.35f);   // Dark gray

            var joints = new Transform[6];
            Transform currentParent = robot.transform;

            // URDF joint transforms (position and rotation from lite6.urdf)
            string[] linkNames = { "link_base", "link1", "link2", "link3", "link4", "link5", "link6" };

            // URDF positions in ROS coordinates - will be converted to Unity
            Vector3[] urdfPositions = {
                new Vector3(0, 0, 0),                  // base (no offset)
                new Vector3(0, 0, 0.2435f),            // joint1: xyz="0 0 0.2435"
                new Vector3(0, 0, 0),                  // joint2: xyz="0 0 0"
                new Vector3(0.2002f, 0, 0),            // joint3: xyz="0.2002 0 0"
                new Vector3(0.087f, -0.22761f, 0),     // joint4: xyz="0.087 -0.22761 0"
                new Vector3(0, 0, 0),                  // joint5: xyz="0 0 0"
                new Vector3(0, 0.0625f, 0)             // joint6: xyz="0 0.0625 0"
            };

            // Convert URDF positions from ROS to Unity coordinate system
            Vector3[] jointPositions = new Vector3[urdfPositions.Length];
            for (int i = 0; i < urdfPositions.Length; i++)
            {
                jointPositions[i] = ROSToUnityPosition(urdfPositions[i]);
            }

            // Joint rotations in ROS rpy (roll-pitch-yaw) converted to Unity Quaternions
            Quaternion[] jointRotations = {
                Quaternion.identity,                                           // base
                Quaternion.identity,                                           // joint1: rpy="0 0 0"
                RPYToQuaternion(1.5708f, -1.5708f, 3.1416f),                 // joint2: rpy="1.5708 -1.5708 3.1416"
                RPYToQuaternion(-3.1416f, 0, 1.5708f),                       // joint3: rpy="-3.1416 0 1.5708"
                RPYToQuaternion(1.5708f, 0, 0),                              // joint4: rpy="1.5708 0 0"
                RPYToQuaternion(1.5708f, 0, 0),                              // joint5: rpy="1.5708 0 0"
                RPYToQuaternion(-1.5708f, 0, 0)                              // joint6: rpy="-1.5708 0 0"
            };

            for (int i = 0; i < linkNames.Length; i++)
            {
                string stlPath = Path.Combine(basePath, linkNames[i] + ".stl");

                // Create joint transform with URDF position and rotation
                var jointObj = new GameObject($"Joint{i}");
                jointObj.transform.SetParent(currentParent);
                jointObj.transform.localPosition = jointPositions[i];
                jointObj.transform.localRotation = jointRotations[i];

                if (i > 0 && i <= 6)
                {
                    joints[i - 1] = jointObj.transform;
                }

                // Load mesh if exists
                if (File.Exists(stlPath))
                {
                    var mesh = STLMeshLoader.LoadMesh(stlPath);
                    if (mesh != null)
                    {
                        var meshObj = new GameObject(linkNames[i]);
                        meshObj.transform.SetParent(jointObj.transform);
                        meshObj.transform.localPosition = Vector3.zero;
                        meshObj.transform.localRotation = Quaternion.identity;
                        meshObj.transform.localScale = Vector3.one;

                        var meshFilter = meshObj.AddComponent<MeshFilter>();
                        meshFilter.mesh = mesh;

                        var meshRenderer = meshObj.AddComponent<MeshRenderer>();
                        var mat = new Material(Shader.Find("Standard"));
                        mat.color = (i == 0) ? jointColor : linkColor;
                        mat.SetFloat("_Metallic", 0.4f);
                        mat.SetFloat("_Glossiness", 0.6f);
                        meshRenderer.material = mat;

                        Debug.Log($"[xArmLite6] Loaded mesh: {linkNames[i]}");
                    }
                }
                else
                {
                    // Create small placeholder sphere for joint
                    var placeholder = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                    placeholder.name = linkNames[i] + "_placeholder";
                    placeholder.transform.SetParent(jointObj.transform);
                    placeholder.transform.localPosition = Vector3.zero;
                    placeholder.transform.localScale = Vector3.one * 0.03f;

                    var mat = new Material(Shader.Find("Standard"));
                    mat.color = jointColor;
                    placeholder.GetComponent<Renderer>().material = mat;

                    var col = placeholder.GetComponent<Collider>();
                    if (col != null) UnityEngine.Object.DestroyImmediate(col);

                    Debug.LogWarning($"[xArmLite6] Mesh not found: {stlPath}");
                }

                currentParent = jointObj.transform;
            }

            // Create end effector / gripper placeholder
            var eeBase = new GameObject("EndEffector");
            eeBase.transform.SetParent(currentParent);
            eeBase.transform.localPosition = new Vector3(0, 0.025f, 0);

            var gripperL = new GameObject("GripperLeft");
            gripperL.transform.SetParent(eeBase.transform);
            gripperL.transform.localPosition = new Vector3(-0.018f, 0.02f, 0);

            var gripperR = new GameObject("GripperRight");
            gripperR.transform.SetParent(eeBase.transform);
            gripperR.transform.localPosition = new Vector3(0.018f, 0.02f, 0);

            // Add controller
            var controller = robot.AddComponent<XArmLite6Controller>();
            controller.joints = joints;
            controller.endEffector = eeBase.transform;
            controller.gripperLeft = gripperL.transform;
            controller.gripperRight = gripperR.transform;

            Debug.Log("[xArmLite6] Created robot from STL meshes");
            return robot;
        }

        private static GameObject CreateCylinder(Transform parent, string name, Vector3 pos, Vector3 scale, Color color)
        {
            var obj = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            SetupPrimitive(obj, parent, name, pos, scale, color);
            return obj;
        }

        private static GameObject CreateCapsule(Transform parent, string name, Vector3 pos, Vector3 scale, Color color)
        {
            var obj = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            SetupPrimitive(obj, parent, name, pos, scale, color);
            return obj;
        }

        private static GameObject CreateCube(Transform parent, string name, Vector3 pos, Vector3 scale, Color color)
        {
            var obj = GameObject.CreatePrimitive(PrimitiveType.Cube);
            SetupPrimitive(obj, parent, name, pos, scale, color);
            return obj;
        }

        private static GameObject CreateJointVisual(Transform parent, string name, Vector3 pos, float radius, float height, Color color)
        {
            var joint = new GameObject(name);
            joint.transform.SetParent(parent);
            joint.transform.localPosition = pos;

            var visual = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            SetupPrimitive(visual, joint.transform, name + "_Visual", Vector3.zero,
                new Vector3(radius, height * 0.5f, radius), color);

            return joint;
        }

        private static void SetupPrimitive(GameObject obj, Transform parent, string name, Vector3 pos, Vector3 scale, Color color)
        {
            obj.name = name;
            obj.transform.SetParent(parent);
            obj.transform.localPosition = pos;
            obj.transform.localScale = scale;

            var mat = new Material(Shader.Find("Standard"));
            mat.color = color;
            mat.SetFloat("_Metallic", 0.4f);
            mat.SetFloat("_Glossiness", 0.6f);
            obj.GetComponent<Renderer>().material = mat;

            var collider = obj.GetComponent<Collider>();
            if (collider != null) UnityEngine.Object.DestroyImmediate(collider);
        }

        /// <summary>
        /// Convert ROS/URDF position to Unity coordinate system
        /// ROS: X-forward, Y-left, Z-up → Unity: X-right, Y-up, Z-forward
        /// Same conversion as STLMeshLoader uses for vertices
        /// </summary>
        private static Vector3 ROSToUnityPosition(Vector3 rosPos)
        {
            return new Vector3(rosPos.x, rosPos.z, rosPos.y);
        }

        /// <summary>
        /// Convert ROS roll-pitch-yaw (in radians) to Unity Quaternion
        /// ROS coordinate system: X-forward, Y-left, Z-up
        /// Unity coordinate system: X-right, Y-up, Z-forward
        /// </summary>
        private static Quaternion RPYToQuaternion(float roll, float pitch, float yaw)
        {
            // ROS axes to Unity axes mapping:
            // ROS X-forward → Unity Z-forward: roll around X → roll around Z
            // ROS Y-left → Unity X-right: pitch around Y → pitch around X
            // ROS Z-up → Unity Y-up: yaw around Z → yaw around Y

            // Create quaternions for each axis rotation in Unity coordinate system
            Quaternion qX = Quaternion.AngleAxis(pitch * Mathf.Rad2Deg, Vector3.right);   // ROS Y → Unity X
            Quaternion qY = Quaternion.AngleAxis(yaw * Mathf.Rad2Deg, Vector3.up);        // ROS Z → Unity Y
            Quaternion qZ = Quaternion.AngleAxis(roll * Mathf.Rad2Deg, Vector3.forward);  // ROS X → Unity Z

            // Apply in intrinsic ZYX order (ROS convention) but with Unity axes
            return qY * qX * qZ;
        }

        // Properties
        public float[] JointAngles => (float[])currentJointAngles.Clone();
        public float[] TargetAngles => (float[])targetJointAngles.Clone();
        public float GripperState => gripperPosition;
        public RobotStatus CurrentStatus => status;
    }
}
