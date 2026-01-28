using System;
using System.Collections;
using System.IO;
using UnityEngine;
using CNCScada.DigitalTwin;

namespace CNCScada.URDF
{
    /// <summary>
    /// Runtime URDF loader for importing robot models.
    /// Works with Unity Robotics Hub URDF Importer package.
    /// </summary>
    public class URDFLoader : MonoBehaviour
    {
        [Header("Settings")]
        [SerializeField] private URDFImportSettings importSettings;

        [Header("Default Materials")]
        [SerializeField] private Material defaultRobotMaterial;
        [SerializeField] private Material collisionMaterial;

        // Singleton
        public static URDFLoader Instance { get; private set; }

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
            }
            else
            {
                Destroy(gameObject);
            }
        }

        /// <summary>
        /// Import a robot from URDF file
        /// </summary>
        public GameObject ImportRobot(string robotName, Vector3 position, Quaternion rotation)
        {
            if (importSettings == null)
            {
                Debug.LogError("[URDFLoader] Import settings not assigned");
                return null;
            }

            var config = importSettings.GetRobotConfig(robotName);
            if (config == null)
            {
                Debug.LogError($"[URDFLoader] Robot configuration not found: {robotName}");
                return null;
            }

            string urdfPath = Path.Combine(Application.dataPath, "..", importSettings.urdfBasePath, config.urdfFile);

            if (!File.Exists(urdfPath))
            {
                Debug.LogWarning($"[URDFLoader] URDF file not found: {urdfPath}");
                // Return a placeholder
                return CreatePlaceholderRobot(config, position, rotation);
            }

#if UNITY_ROBOTICS_URDF_IMPORTER
            // Use Unity Robotics Hub URDF Importer
            var importOptions = new Unity.Robotics.UrdfImporter.ImportOptions
            {
                convexDecomposer = Unity.Robotics.UrdfImporter.ImportOptions.ConvexDecomposer.Default,
                meshDecomposer = Unity.Robotics.UrdfImporter.ImportOptions.ConvexDecomposer.Default
            };

            var robot = Unity.Robotics.UrdfImporter.UrdfRobotExtensions.Create(urdfPath, importOptions);
            robot.transform.position = position;
            robot.transform.rotation = rotation;

            // Apply materials
            ApplyMaterials(robot);

            Debug.Log($"[URDFLoader] Imported robot from URDF: {robotName}");
            return robot;
#else
            Debug.LogWarning("[URDFLoader] URDF Importer package not installed. Creating placeholder.");
            return CreatePlaceholderRobot(config, position, rotation);
#endif
        }

        /// <summary>
        /// Create a placeholder robot when URDF is not available
        /// </summary>
        private GameObject CreatePlaceholderRobot(RobotConfig config, Vector3 position, Quaternion rotation)
        {
            var robot = new GameObject(config.name);
            robot.transform.position = position;
            robot.transform.rotation = rotation;

            // Create base
            var baseCylinder = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            baseCylinder.name = "base_link";
            baseCylinder.transform.SetParent(robot.transform);
            baseCylinder.transform.localPosition = new Vector3(0, 0.05f, 0);
            baseCylinder.transform.localScale = new Vector3(0.12f, 0.05f, 0.12f);
            ApplyPlaceholderMaterial(baseCylinder);

            // Create joint hierarchy
            Transform parent = baseCylinder.transform;
            float yOffset = 0.1f;

            for (int i = 0; i < config.numJoints; i++)
            {
                var joint = new GameObject($"joint_{i + 1}");
                joint.transform.SetParent(parent);
                joint.transform.localPosition = new Vector3(0, yOffset, 0);

                var link = GameObject.CreatePrimitive(PrimitiveType.Capsule);
                link.name = $"link_{i + 1}";
                link.transform.SetParent(joint.transform);
                link.transform.localPosition = new Vector3(0, 0.05f, 0);
                link.transform.localScale = new Vector3(0.04f, 0.05f, 0.04f);
                ApplyPlaceholderMaterial(link);

                parent = joint.transform;
                yOffset = 0.1f - (i * 0.01f); // Slightly decreasing link sizes
            }

            // Add gripper placeholder
            var gripper = new GameObject("gripper");
            gripper.transform.SetParent(parent);
            gripper.transform.localPosition = new Vector3(0, 0.05f, 0);

            var gripperMesh = GameObject.CreatePrimitive(PrimitiveType.Cube);
            gripperMesh.name = "gripper_mesh";
            gripperMesh.transform.SetParent(gripper.transform);
            gripperMesh.transform.localPosition = Vector3.zero;
            gripperMesh.transform.localScale = new Vector3(0.08f, 0.02f, 0.06f);
            ApplyPlaceholderMaterial(gripperMesh);

            // Add RobotController component
            var controller = robot.AddComponent<RobotController>();
            var robotType = config.name.Contains("niryo") ? RobotType.NiryoNed2 :
                           config.name.Contains("xarm") ? RobotType.XArm : RobotType.Generic6DOF;
            controller.Initialize(config.name, robotType);

            Debug.Log($"[URDFLoader] Created placeholder robot: {config.name}");
            return robot;
        }

        private void ApplyMaterials(GameObject robot)
        {
            if (defaultRobotMaterial == null) return;

            var renderers = robot.GetComponentsInChildren<Renderer>();
            foreach (var renderer in renderers)
            {
                renderer.material = defaultRobotMaterial;
            }
        }

        private void ApplyPlaceholderMaterial(GameObject obj)
        {
            var renderer = obj.GetComponent<Renderer>();
            if (renderer != null)
            {
                renderer.material = new Material(Shader.Find("Standard"));
                renderer.material.color = new Color(0.3f, 0.3f, 0.35f);
                renderer.material.SetFloat("_Metallic", 0.6f);
                renderer.material.SetFloat("_Glossiness", 0.4f);
            }
        }

        /// <summary>
        /// Load STL mesh file
        /// </summary>
        public Mesh LoadSTL(string filePath)
        {
            if (!File.Exists(filePath))
            {
                Debug.LogWarning($"[URDFLoader] STL file not found: {filePath}");
                return null;
            }

            // Simple binary STL parser
            try
            {
                byte[] data = File.ReadAllBytes(filePath);
                return ParseBinarySTL(data);
            }
            catch (Exception e)
            {
                Debug.LogError($"[URDFLoader] Error loading STL: {e.Message}");
                return null;
            }
        }

        private Mesh ParseBinarySTL(byte[] data)
        {
            // Skip 80-byte header
            int offset = 80;

            // Read triangle count (4 bytes, little-endian)
            uint triangleCount = BitConverter.ToUInt32(data, offset);
            offset += 4;

            var vertices = new Vector3[triangleCount * 3];
            var normals = new Vector3[triangleCount * 3];
            var triangles = new int[triangleCount * 3];

            for (int i = 0; i < triangleCount; i++)
            {
                // Normal (12 bytes)
                Vector3 normal = new Vector3(
                    BitConverter.ToSingle(data, offset),
                    BitConverter.ToSingle(data, offset + 4),
                    BitConverter.ToSingle(data, offset + 8)
                );
                offset += 12;

                // Three vertices (36 bytes total)
                for (int j = 0; j < 3; j++)
                {
                    int vertIndex = i * 3 + j;

                    vertices[vertIndex] = new Vector3(
                        BitConverter.ToSingle(data, offset),
                        BitConverter.ToSingle(data, offset + 4),
                        BitConverter.ToSingle(data, offset + 8)
                    );
                    offset += 12;

                    normals[vertIndex] = normal;
                    triangles[vertIndex] = vertIndex;
                }

                // Attribute byte count (2 bytes, usually 0)
                offset += 2;
            }

            var mesh = new Mesh();
            mesh.vertices = vertices;
            mesh.normals = normals;
            mesh.triangles = triangles;
            mesh.RecalculateBounds();

            return mesh;
        }
    }
}
