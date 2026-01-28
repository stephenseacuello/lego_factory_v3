using System;
using System.IO;
using UnityEngine;
using CNC_SCADA.DigitalTwin.URDF;

namespace CNCScada.Machines
{
    /// <summary>
    /// Controller for Niryo Ned2 collaborative robot arm.
    ///
    /// Specifications:
    /// - 6 DOF collaborative robot
    /// - Payload: 300g
    /// - Reach: 440mm
    /// - Repeatability: ±0.5mm
    /// - Weight: 5.8kg
    /// - Power: 12V DC
    ///
    /// DH Parameters:
    /// Link | a(mm) | d(mm) | alpha(deg) | theta offset
    /// 1    | 0     | 103   | -90        | 0
    /// 2    | 210   | 0     | 0          | -90
    /// 3    | 30    | 0     | -90        | 0
    /// 4    | 0     | 222   | 90         | 0
    /// 5    | 0     | 0     | -90        | 0
    /// 6    | 0     | 55    | 0          | 0
    /// </summary>
    public class NiryoNed2Controller : MonoBehaviour
    {
        [Header("Robot Identification")]
        public string robotId = "niryo-ned2-001";
        public string robotName = "Niryo Ned2";

        [Header("Joint Configuration")]
        public Transform[] joints = new Transform[6];
        public Transform endEffector;
        public Transform gripperLeft;
        public Transform gripperRight;

        [Header("Joint Limits (degrees)")]
        public Vector2[] jointLimits = new Vector2[]
        {
            new Vector2(-175, 175),   // J1: Base rotation
            new Vector2(-90, 36.7f),  // J2: Shoulder
            new Vector2(-80, 90),     // J3: Elbow
            new Vector2(-175, 175),   // J4: Wrist rotation
            new Vector2(-100, 110),   // J5: Wrist bend
            new Vector2(-145, 145)    // J6: End effector rotation
        };

        [Header("Current State")]
        [SerializeField] private float[] currentJointAngles = new float[6];
        [SerializeField] private float[] targetJointAngles = new float[6];
        [SerializeField] private float gripperPosition; // 0 = closed, 1 = open
        [SerializeField] private NedStatus status = NedStatus.Idle;

        [Header("Motion Settings")]
        public float jointSmoothTime = 0.15f;
        public float maxJointSpeed = 120f; // deg/s (Ned2 is slower than industrial arms)

        // Link lengths (meters) for Niryo Ned2
        private readonly float[] linkLengths = { 0.103f, 0.210f, 0.030f, 0.222f, 0f, 0.055f };

        // Joint rotation axes (local space)
        private readonly Vector3[] jointAxes = {
            Vector3.up,      // J1 - Base rotation (Y)
            Vector3.forward, // J2 - Shoulder (Z)
            Vector3.forward, // J3 - Elbow (Z)
            Vector3.up,      // J4 - Wrist rotation (Y)
            Vector3.forward, // J5 - Wrist bend (Z)
            Vector3.up       // J6 - EE rotation (Y)
        };

        // Internal state
        private float[] jointVelocities = new float[6];

        // Events
        public event Action<float[]> OnJointsChanged;
        public event Action<NedStatus> OnStatusChanged;
        public event Action<string> OnLearningModeChanged;

        public enum NedStatus
        {
            Idle,
            Moving,
            LearningMode,
            Error,
            Calibrating
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
        /// Set joint angles from radians (ROS convention)
        /// </summary>
        public void SetJointAnglesRadians(double[] radians)
        {
            if (radians == null || radians.Length != 6) return;

            for (int i = 0; i < 6; i++)
            {
                float degrees = (float)(radians[i] * Mathf.Rad2Deg);
                targetJointAngles[i] = Mathf.Clamp(degrees, jointLimits[i].x, jointLimits[i].y);
            }
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
        /// Move to home/rest position
        /// </summary>
        public void MoveToHome()
        {
            targetJointAngles = new float[] { 0, 0, 0, 0, -90, 0 };
        }

        /// <summary>
        /// Move to learning mode pose
        /// </summary>
        public void MoveToLearningPose()
        {
            targetJointAngles = new float[] { 0, 15, -35, 0, 0, 0 };
        }

        private void UpdateJointPositions()
        {
            bool anyMoving = false;

            for (int i = 0; i < 6; i++)
            {
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

            var newStatus = anyMoving ? NedStatus.Moving : NedStatus.Idle;
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

            // Niryo gripper opens to about 30 degrees
            float openAngle = 30f * gripperPosition;

            gripperLeft.localRotation = Quaternion.Euler(0, 0, openAngle);
            gripperRight.localRotation = Quaternion.Euler(0, 0, -openAngle);
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
        /// Create visual representation of Niryo Ned2 from STL meshes
        /// Uses URDF joint transforms and visual mesh rotations for correct positioning
        /// </summary>
        public static GameObject CreateVisualFromSTL(Transform parent = null)
        {
            var robot = new GameObject("NiryoNed2");
            if (parent != null) robot.transform.SetParent(parent);

            string basePath = Path.Combine(Application.streamingAssetsPath, "URDF", "niryo_ned2", "meshes", "ned2", "stl");

            // Niryo colors
            Color baseColor = new Color(0.1f, 0.1f, 0.12f);       // Black base
            Color linkColor = new Color(0.9f, 0.9f, 0.92f);       // White/light gray
            Color jointColor = new Color(0.2f, 0.2f, 0.22f);      // Dark gray
            Color accentColor = new Color(0.95f, 0.5f, 0.1f);     // Niryo orange

            var joints = new Transform[6];
            Transform currentParent = robot.transform;

            // Link names from URDF
            string[] linkNames = { "base_link", "shoulder_link", "arm_link", "elbow_link", "forearm_link", "wrist_link", "hand_link" };

            // URDF positions in ROS coordinates - will be converted to Unity
            Vector3[] urdfPositions = {
                new Vector3(0, 0, 0),                // Base at origin
                new Vector3(0, 0, 0.1013f),          // joint_1: xyz="0 0 0.1013"
                new Vector3(0, 0, 0.065f),           // joint_2: xyz="0 0 0.065"
                new Vector3(0.012f, 0.221f, 0),      // joint_3: xyz="0.012 0.221 0"
                new Vector3(0.0325f, -0.065f, 0),    // joint_4: xyz="0.0325 -0.065 0"
                new Vector3(0, 0, 0.17f),            // joint_5: xyz="0 0 0.17"
                new Vector3(0.00925f, -0.0197f, 0)   // joint_6: xyz="0.00925 -0.0197 0"
            };

            // Convert URDF positions from ROS to Unity coordinate system
            Vector3[] jointPositions = new Vector3[urdfPositions.Length];
            for (int i = 0; i < urdfPositions.Length; i++)
            {
                jointPositions[i] = ROSToUnityPosition(urdfPositions[i]);
            }

            // Joint rotations from URDF rpy
            Quaternion[] jointRotations = {
                Quaternion.identity,                       // base
                Quaternion.identity,                       // joint_1: rpy="0 0 0"
                RPYToQuaternion(1.5708f, 0, 0),           // joint_2: rpy="1.5708 0 0"
                RPYToQuaternion(0, 0, 1.5708f),           // joint_3: rpy="0 0 1.5708"
                RPYToQuaternion(1.5708f, 0, 0),           // joint_4: rpy="1.5708 0 0"
                RPYToQuaternion(-1.5708f, 0, 0),          // joint_5: rpy="-1.5708 0 0"
                RPYToQuaternion(1.5708f, 0, 0)            // joint_6: rpy="1.5708 0 0"
            };

            // Visual mesh rotations from URDF (applied to mesh, not joint)
            Quaternion[] meshRotations = {
                RPYToQuaternion(-1.5708f, 0, 0),          // base_link: rpy="-1.5708 0 0"
                RPYToQuaternion(0, 0, -1.5708f),          // shoulder_link: rpy="0 0 -1.5708"
                RPYToQuaternion(0, 3.1416f, 0),           // arm_link: rpy="0 3.1416 0"
                RPYToQuaternion(0, 3.1416f, -1.5708f),    // elbow_link: rpy="0 3.1416 -1.5708"
                RPYToQuaternion(0, 0, -1.5708f),          // forearm_link: rpy="0 0 -1.5708"
                RPYToQuaternion(0, 0, -1.5708f),          // wrist_link: rpy="0 0 -1.5708"
                RPYToQuaternion(0, 0, -1.5708f)           // hand_link: rpy="0 0 -1.5708"
            };

            // Create base link (not a joint, just visual)
            string baseLinkPath = Path.Combine(basePath, "base_link.stl");
            if (File.Exists(baseLinkPath))
            {
                var baseMesh = STLMeshLoader.LoadMesh(baseLinkPath);
                if (baseMesh != null)
                {
                    var baseObj = new GameObject("Base");
                    baseObj.transform.SetParent(robot.transform);
                    baseObj.transform.localPosition = Vector3.zero;
                    baseObj.transform.localRotation = meshRotations[0];  // Apply base mesh rotation

                    var meshFilter = baseObj.AddComponent<MeshFilter>();
                    meshFilter.mesh = baseMesh;

                    var meshRenderer = baseObj.AddComponent<MeshRenderer>();
                    var mat = new Material(Shader.Find("Standard"));
                    mat.color = baseColor;
                    mat.SetFloat("_Metallic", 0.3f);
                    mat.SetFloat("_Glossiness", 0.5f);
                    meshRenderer.material = mat;

                    currentParent = baseObj.transform;
                }
            }

            // Create joints 1-6 with their link meshes
            for (int i = 1; i < linkNames.Length; i++)
            {
                string stlPath = Path.Combine(basePath, linkNames[i] + ".stl");

                // Create joint transform with URDF position and rotation
                var jointObj = new GameObject($"Joint{i}");
                jointObj.transform.SetParent(currentParent);
                jointObj.transform.localPosition = jointPositions[i];
                jointObj.transform.localRotation = jointRotations[i];

                joints[i - 1] = jointObj.transform;

                // Load and attach mesh
                if (File.Exists(stlPath))
                {
                    var mesh = STLMeshLoader.LoadMesh(stlPath);
                    if (mesh != null)
                    {
                        var meshObj = new GameObject(linkNames[i]);
                        meshObj.transform.SetParent(jointObj.transform);
                        meshObj.transform.localPosition = Vector3.zero;
                        meshObj.transform.localRotation = meshRotations[i];  // Apply visual mesh rotation

                        var meshFilter = meshObj.AddComponent<MeshFilter>();
                        meshFilter.mesh = mesh;

                        var meshRenderer = meshObj.AddComponent<MeshRenderer>();
                        var mat = new Material(Shader.Find("Standard"));

                        // Apply colors: darker for joints, lighter for links, orange for hand
                        if (i == linkNames.Length - 1) // hand_link
                            mat.color = accentColor;
                        else if (i % 2 == 0) // even indices are joints
                            mat.color = jointColor;
                        else // odd indices are links
                            mat.color = linkColor;

                        mat.SetFloat("_Metallic", 0.3f);
                        mat.SetFloat("_Glossiness", 0.5f);
                        meshRenderer.material = mat;
                    }
                }
                else
                {
                    Debug.LogWarning($"[NiryoNed2] STL file not found: {stlPath}");
                }

                currentParent = jointObj.transform;
            }

            // Create gripper base (end effector reference point)
            var gripperBase = new GameObject("GripperBase");
            gripperBase.transform.SetParent(currentParent);
            gripperBase.transform.localPosition = new Vector3(0, 0.03f, 0);

            // Create simple gripper fingers (placeholder - real gripper would be separate URDF)
            var fingerL = GameObject.CreatePrimitive(PrimitiveType.Cube);
            fingerL.name = "FingerLeft";
            fingerL.transform.SetParent(gripperBase.transform);
            fingerL.transform.localPosition = new Vector3(-0.015f, 0.02f, 0);
            fingerL.transform.localScale = new Vector3(0.006f, 0.025f, 0.012f);
            var matL = new Material(Shader.Find("Standard"));
            matL.color = accentColor;
            fingerL.GetComponent<Renderer>().material = matL;
            var colliderL = fingerL.GetComponent<Collider>();
            if (colliderL != null) UnityEngine.Object.DestroyImmediate(colliderL);

            var fingerR = GameObject.CreatePrimitive(PrimitiveType.Cube);
            fingerR.name = "FingerRight";
            fingerR.transform.SetParent(gripperBase.transform);
            fingerR.transform.localPosition = new Vector3(0.015f, 0.02f, 0);
            fingerR.transform.localScale = new Vector3(0.006f, 0.025f, 0.012f);
            var matR = new Material(Shader.Find("Standard"));
            matR.color = accentColor;
            fingerR.GetComponent<Renderer>().material = matR;
            var colliderR = fingerR.GetComponent<Collider>();
            if (colliderR != null) UnityEngine.Object.DestroyImmediate(colliderR);

            // Add controller component
            var controller = robot.AddComponent<NiryoNed2Controller>();
            controller.joints = joints;
            controller.endEffector = gripperBase.transform;
            controller.gripperLeft = fingerL.transform;
            controller.gripperRight = fingerR.transform;

            Debug.Log($"[NiryoNed2] Created robot with STL meshes from: {basePath}");
            return robot;
        }

        /// <summary>
        /// Create visual representation of Niryo Ned2
        /// </summary>
        public static GameObject CreateVisual(Transform parent = null)
        {
            var robot = new GameObject("NiryoNed2");
            if (parent != null) robot.transform.SetParent(parent);

            // Niryo colors (black base, white/gray links, orange accents)
            Color baseColor = new Color(0.1f, 0.1f, 0.12f);
            Color linkColor = new Color(0.9f, 0.9f, 0.92f);
            Color jointColor = new Color(0.2f, 0.2f, 0.22f);
            Color accentColor = new Color(0.95f, 0.5f, 0.1f); // Niryo orange

            var joints = new Transform[6];

            // Base
            var baseObj = CreateCylinder(robot.transform, "Base", Vector3.zero,
                new Vector3(0.09f, 0.025f, 0.09f), baseColor);

            // J1 housing
            var j1Housing = CreateCylinder(baseObj.transform, "J1_Housing", new Vector3(0, 0.035f, 0),
                new Vector3(0.065f, 0.03f, 0.065f), jointColor);
            var j1 = new GameObject("J1");
            j1.transform.SetParent(j1Housing.transform);
            j1.transform.localPosition = new Vector3(0, 0.03f, 0);
            joints[0] = j1.transform;

            // Shoulder bracket
            var shoulder = CreateCube(j1.transform, "Shoulder", new Vector3(0, 0.025f, 0),
                new Vector3(0.045f, 0.04f, 0.045f), linkColor);

            // J2
            var j2Visual = CreateCylinder(shoulder.transform, "J2_Visual", new Vector3(0, 0.035f, 0.015f),
                new Vector3(0.04f, 0.02f, 0.04f), jointColor);
            j2Visual.transform.localRotation = Quaternion.Euler(90, 0, 0);
            var j2 = new GameObject("J2");
            j2.transform.SetParent(shoulder.transform);
            j2.transform.localPosition = new Vector3(0, 0.035f, 0);
            joints[1] = j2.transform;

            // Upper arm
            var upperArm = CreateCapsule(j2.transform, "UpperArm", new Vector3(0, 0.09f, 0),
                new Vector3(0.03f, 0.085f, 0.03f), linkColor);

            // J3
            var j3Visual = CreateCylinder(upperArm.transform, "J3_Visual", new Vector3(0, 0.09f, 0),
                new Vector3(0.035f, 0.018f, 0.035f), jointColor);
            var j3 = new GameObject("J3");
            j3.transform.SetParent(upperArm.transform);
            j3.transform.localPosition = new Vector3(0, 0.09f, 0);
            joints[2] = j3.transform;

            // Forearm
            var forearm = CreateCapsule(j3.transform, "Forearm", new Vector3(0, 0.08f, 0),
                new Vector3(0.025f, 0.075f, 0.025f), linkColor);

            // J4
            var j4Visual = CreateCylinder(forearm.transform, "J4_Visual", new Vector3(0, 0.085f, 0),
                new Vector3(0.03f, 0.02f, 0.03f), jointColor);
            var j4 = new GameObject("J4");
            j4.transform.SetParent(forearm.transform);
            j4.transform.localPosition = new Vector3(0, 0.085f, 0);
            joints[3] = j4.transform;

            // Wrist housing
            var wrist = CreateCube(j4.transform, "Wrist", new Vector3(0, 0.03f, 0),
                new Vector3(0.028f, 0.04f, 0.028f), linkColor);

            // J5
            var j5Visual = CreateCylinder(wrist.transform, "J5_Visual", new Vector3(0, 0.03f, 0.01f),
                new Vector3(0.025f, 0.012f, 0.025f), jointColor);
            j5Visual.transform.localRotation = Quaternion.Euler(90, 0, 0);
            var j5 = new GameObject("J5");
            j5.transform.SetParent(wrist.transform);
            j5.transform.localPosition = new Vector3(0, 0.03f, 0);
            joints[4] = j5.transform;

            // J6 / End effector mount
            var j6Housing = CreateCylinder(j5.transform, "J6_Housing", new Vector3(0, 0.02f, 0),
                new Vector3(0.022f, 0.015f, 0.022f), accentColor);
            var j6 = new GameObject("J6");
            j6.transform.SetParent(j6Housing.transform);
            j6.transform.localPosition = new Vector3(0, 0.015f, 0);
            joints[5] = j6.transform;

            // Gripper base
            var gripperBase = CreateCube(j6.transform, "GripperBase", new Vector3(0, 0.015f, 0),
                new Vector3(0.04f, 0.012f, 0.025f), jointColor);

            // Gripper fingers
            var fingerL = CreateCube(gripperBase.transform, "FingerLeft", new Vector3(-0.015f, 0.02f, 0),
                new Vector3(0.006f, 0.025f, 0.012f), accentColor);
            var fingerR = CreateCube(gripperBase.transform, "FingerRight", new Vector3(0.015f, 0.02f, 0),
                new Vector3(0.006f, 0.025f, 0.012f), accentColor);

            // Add controller
            var controller = robot.AddComponent<NiryoNed2Controller>();
            controller.joints = joints;
            controller.endEffector = gripperBase.transform;
            controller.gripperLeft = fingerL.transform;
            controller.gripperRight = fingerR.transform;

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

        private static void SetupPrimitive(GameObject obj, Transform parent, string name, Vector3 pos, Vector3 scale, Color color)
        {
            obj.name = name;
            obj.transform.SetParent(parent);
            obj.transform.localPosition = pos;
            obj.transform.localScale = scale;

            var mat = new Material(Shader.Find("Standard"));
            mat.color = color;
            mat.SetFloat("_Metallic", 0.3f);
            mat.SetFloat("_Glossiness", 0.5f);
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
        public NedStatus CurrentStatus => status;
    }
}
