using System;
using System.Collections;
using System.Collections.Generic;
using System.Xml;
using System.IO;
using UnityEngine;
using CNC_SCADA.DigitalTwin.Kinematics;

namespace CNC_SCADA.DigitalTwin.URDF
{
    /// <summary>
    /// URDF (Unified Robot Description Format) Robot Loader
    /// Parses URDF XML files and creates Unity GameObjects with proper joint hierarchy
    /// Supports visual meshes, collision geometry, and joint dynamics
    /// </summary>
    public class URDFRobotLoader : MonoBehaviour
    {
        public static URDFRobotLoader Instance { get; private set; }

        [Header("Loading Configuration")]
        [SerializeField] private string urdfBasePath = "";
        [SerializeField] private bool loadVisualMeshes = true;
        [SerializeField] private bool loadCollisionMeshes = true;
        [SerializeField] private bool createJointControllers = true;
        [SerializeField] private float defaultMeshScale = 1f;

        [Header("Materials")]
        [SerializeField] private Material defaultLinkMaterial;
        [SerializeField] private Material collisionMaterial;
        [SerializeField] private bool useURDFMaterials = true;

        [Header("Physics")]
        [SerializeField] private bool enablePhysics = false;
        [SerializeField] private bool useArticulationBodies = true;
        [SerializeField] private float defaultJointDamping = 10f;
        [SerializeField] private float defaultJointFriction = 0.1f;

        // Events
        public event Action<URDFRobot> OnRobotLoaded;
        public event Action<string> OnLoadError;
        public event Action<string, float> OnLoadProgress;

        // Loaded robots
        private Dictionary<string, URDFRobot> loadedRobots = new Dictionary<string, URDFRobot>();
        private Dictionary<string, Material> urdfMaterials = new Dictionary<string, Material>();

        public int LoadedRobotCount => loadedRobots.Count;

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
                DontDestroyOnLoad(gameObject);
            }
            else
            {
                Destroy(gameObject);
            }
        }

        #region Public API

        /// <summary>
        /// Load a robot from a URDF file
        /// </summary>
        public IEnumerator LoadRobotFromFile(string urdfPath, Transform parent = null, Action<URDFRobot> callback = null)
        {
            OnLoadProgress?.Invoke("Loading URDF file...", 0f);

            // Use StreamingAssets path if no custom path set
            string basePath = string.IsNullOrEmpty(urdfBasePath)
                ? Path.Combine(Application.streamingAssetsPath, "URDF")
                : urdfBasePath;

            string fullPath = Path.Combine(basePath, urdfPath);

            Debug.Log($"[URDFLoader] Attempting to load URDF from: {fullPath}");

            if (!File.Exists(fullPath))
            {
                OnLoadError?.Invoke($"URDF file not found: {fullPath}");
                callback?.Invoke(null);
                yield break;
            }

            string urdfContent = File.ReadAllText(fullPath);
            string urdfDirectory = Path.GetDirectoryName(fullPath);

            yield return LoadRobotFromString(urdfContent, urdfDirectory, parent, callback);
        }

        /// <summary>
        /// Load a robot from URDF XML string
        /// </summary>
        public IEnumerator LoadRobotFromString(string urdfXml, string meshBasePath, Transform parent = null, Action<URDFRobot> callback = null)
        {
            URDFRobot robot = null;
            URDFModel urdfModel = null;
            bool hasError = false;

            // Parse URDF (non-yielding part in try-catch)
            OnLoadProgress?.Invoke("Parsing URDF...", 0.1f);
            try
            {
                urdfModel = ParseURDF(urdfXml);
            }
            catch (Exception ex)
            {
                OnLoadError?.Invoke($"Error parsing URDF: {ex.Message}");
                Debug.LogError($"[URDFLoader] {ex}");
                hasError = true;
            }

            if (hasError || urdfModel == null)
            {
                if (!hasError) OnLoadError?.Invoke("Failed to parse URDF");
                callback?.Invoke(null);
                yield break;
            }

            OnLoadProgress?.Invoke("Creating robot hierarchy...", 0.3f);
            yield return null;

            // Create robot GameObject hierarchy
            try
            {
                robot = CreateRobotHierarchy(urdfModel, meshBasePath, parent);
            }
            catch (Exception ex)
            {
                OnLoadError?.Invoke($"Error creating robot hierarchy: {ex.Message}");
                Debug.LogError($"[URDFLoader] {ex}");
                callback?.Invoke(null);
                yield break;
            }

            OnLoadProgress?.Invoke("Loading meshes...", 0.5f);
            yield return null;

            // Load visual meshes
            if (loadVisualMeshes)
            {
                yield return LoadMeshes(robot, meshBasePath, false);
            }

            OnLoadProgress?.Invoke("Loading collision meshes...", 0.7f);
            yield return null;

            // Load collision meshes
            if (loadCollisionMeshes)
            {
                yield return LoadMeshes(robot, meshBasePath, true);
            }

            OnLoadProgress?.Invoke("Configuring joints...", 0.9f);
            yield return null;

            // Setup joint controllers
            if (createJointControllers)
            {
                SetupJointControllers(robot);
            }

            // Register robot
            loadedRobots[robot.Name] = robot;

            OnLoadProgress?.Invoke("Complete", 1f);
            OnRobotLoaded?.Invoke(robot);

            Debug.Log($"[URDFLoader] Loaded robot: {robot.Name} with {robot.Links.Count} links and {robot.Joints.Count} joints");

            callback?.Invoke(robot);
        }

        /// <summary>
        /// Get a loaded robot by name
        /// </summary>
        public URDFRobot GetRobot(string name)
        {
            return loadedRobots.TryGetValue(name, out var robot) ? robot : null;
        }

        /// <summary>
        /// Unload and destroy a robot
        /// </summary>
        public void UnloadRobot(string name)
        {
            if (loadedRobots.TryGetValue(name, out var robot))
            {
                if (robot.RootObject != null)
                {
                    Destroy(robot.RootObject);
                }
                loadedRobots.Remove(name);
                Debug.Log($"[URDFLoader] Unloaded robot: {name}");
            }
        }

        #endregion

        #region URDF Parsing

        private URDFModel ParseURDF(string urdfXml)
        {
            var model = new URDFModel();

            try
            {
                var doc = new XmlDocument();
                doc.LoadXml(urdfXml);

                var robotNode = doc.SelectSingleNode("/robot");
                if (robotNode == null)
                {
                    Debug.LogError("[URDFLoader] No <robot> element found");
                    return null;
                }

                model.Name = robotNode.Attributes["name"]?.Value ?? "unnamed_robot";

                // Parse materials
                foreach (XmlNode materialNode in doc.SelectNodes("/robot/material"))
                {
                    var material = ParseMaterial(materialNode);
                    if (material != null)
                    {
                        model.Materials[material.Name] = material;
                    }
                }

                // Parse links
                foreach (XmlNode linkNode in doc.SelectNodes("/robot/link"))
                {
                    var link = ParseLink(linkNode);
                    if (link != null)
                    {
                        model.Links[link.Name] = link;
                    }
                }

                // Parse joints
                foreach (XmlNode jointNode in doc.SelectNodes("/robot/joint"))
                {
                    var joint = ParseJoint(jointNode);
                    if (joint != null)
                    {
                        model.Joints[joint.Name] = joint;
                    }
                }

                // Build parent-child relationships
                foreach (var joint in model.Joints.Values)
                {
                    if (model.Links.TryGetValue(joint.ParentLink, out var parentLink))
                    {
                        parentLink.ChildJoints.Add(joint.Name);
                    }
                    if (model.Links.TryGetValue(joint.ChildLink, out var childLink))
                    {
                        childLink.ParentJoint = joint.Name;
                    }
                }

                // Find root link (link with no parent)
                foreach (var link in model.Links.Values)
                {
                    if (string.IsNullOrEmpty(link.ParentJoint))
                    {
                        model.RootLink = link.Name;
                        break;
                    }
                }

                Debug.Log($"[URDFLoader] Parsed URDF: {model.Name} - {model.Links.Count} links, {model.Joints.Count} joints");
            }
            catch (Exception ex)
            {
                Debug.LogError($"[URDFLoader] Parse error: {ex.Message}");
                return null;
            }

            return model;
        }

        private URDFMaterial ParseMaterial(XmlNode node)
        {
            var material = new URDFMaterial
            {
                Name = node.Attributes["name"]?.Value
            };

            var colorNode = node.SelectSingleNode("color");
            if (colorNode != null)
            {
                string rgba = colorNode.Attributes["rgba"]?.Value;
                if (!string.IsNullOrEmpty(rgba))
                {
                    string[] values = rgba.Split(' ');
                    if (values.Length >= 4)
                    {
                        material.Color = new Color(
                            float.Parse(values[0]),
                            float.Parse(values[1]),
                            float.Parse(values[2]),
                            float.Parse(values[3])
                        );
                    }
                }
            }

            var textureNode = node.SelectSingleNode("texture");
            if (textureNode != null)
            {
                material.TexturePath = textureNode.Attributes["filename"]?.Value;
            }

            return material;
        }

        private URDFLink ParseLink(XmlNode node)
        {
            var link = new URDFLink
            {
                Name = node.Attributes["name"]?.Value,
                ChildJoints = new List<string>()
            };

            // Parse inertial
            var inertialNode = node.SelectSingleNode("inertial");
            if (inertialNode != null)
            {
                link.Inertial = ParseInertial(inertialNode);
            }

            // Parse visual
            var visualNode = node.SelectSingleNode("visual");
            if (visualNode != null)
            {
                link.Visual = ParseGeometryElement(visualNode);
            }

            // Parse collision
            var collisionNode = node.SelectSingleNode("collision");
            if (collisionNode != null)
            {
                link.Collision = ParseGeometryElement(collisionNode);
            }

            return link;
        }

        private URDFInertial ParseInertial(XmlNode node)
        {
            var inertial = new URDFInertial();

            var originNode = node.SelectSingleNode("origin");
            if (originNode != null)
            {
                inertial.Origin = ParseOrigin(originNode);
            }

            var massNode = node.SelectSingleNode("mass");
            if (massNode != null)
            {
                inertial.Mass = float.Parse(massNode.Attributes["value"]?.Value ?? "1");
            }

            var inertiaNode = node.SelectSingleNode("inertia");
            if (inertiaNode != null)
            {
                inertial.Ixx = float.Parse(inertiaNode.Attributes["ixx"]?.Value ?? "0");
                inertial.Ixy = float.Parse(inertiaNode.Attributes["ixy"]?.Value ?? "0");
                inertial.Ixz = float.Parse(inertiaNode.Attributes["ixz"]?.Value ?? "0");
                inertial.Iyy = float.Parse(inertiaNode.Attributes["iyy"]?.Value ?? "0");
                inertial.Iyz = float.Parse(inertiaNode.Attributes["iyz"]?.Value ?? "0");
                inertial.Izz = float.Parse(inertiaNode.Attributes["izz"]?.Value ?? "0");
            }

            return inertial;
        }

        private URDFGeometryElement ParseGeometryElement(XmlNode node)
        {
            var element = new URDFGeometryElement();

            var originNode = node.SelectSingleNode("origin");
            if (originNode != null)
            {
                element.Origin = ParseOrigin(originNode);
            }

            var geometryNode = node.SelectSingleNode("geometry");
            if (geometryNode != null)
            {
                element.Geometry = ParseGeometry(geometryNode);
            }

            var materialNode = node.SelectSingleNode("material");
            if (materialNode != null)
            {
                element.MaterialName = materialNode.Attributes["name"]?.Value;

                // Check for inline material definition
                var colorNode = materialNode.SelectSingleNode("color");
                if (colorNode != null)
                {
                    string rgba = colorNode.Attributes["rgba"]?.Value;
                    if (!string.IsNullOrEmpty(rgba))
                    {
                        string[] values = rgba.Split(' ');
                        if (values.Length >= 4)
                        {
                            element.InlineColor = new Color(
                                float.Parse(values[0]),
                                float.Parse(values[1]),
                                float.Parse(values[2]),
                                float.Parse(values[3])
                            );
                        }
                    }
                }
            }

            return element;
        }

        private URDFGeometry ParseGeometry(XmlNode node)
        {
            var geometry = new URDFGeometry();

            var boxNode = node.SelectSingleNode("box");
            if (boxNode != null)
            {
                geometry.Type = GeometryType.Box;
                string size = boxNode.Attributes["size"]?.Value ?? "1 1 1";
                string[] values = size.Split(' ');
                geometry.Size = new Vector3(
                    float.Parse(values[0]),
                    float.Parse(values[1]),
                    float.Parse(values[2])
                );
                return geometry;
            }

            var cylinderNode = node.SelectSingleNode("cylinder");
            if (cylinderNode != null)
            {
                geometry.Type = GeometryType.Cylinder;
                geometry.Radius = float.Parse(cylinderNode.Attributes["radius"]?.Value ?? "0.1");
                geometry.Length = float.Parse(cylinderNode.Attributes["length"]?.Value ?? "1");
                return geometry;
            }

            var sphereNode = node.SelectSingleNode("sphere");
            if (sphereNode != null)
            {
                geometry.Type = GeometryType.Sphere;
                geometry.Radius = float.Parse(sphereNode.Attributes["radius"]?.Value ?? "0.1");
                return geometry;
            }

            var meshNode = node.SelectSingleNode("mesh");
            if (meshNode != null)
            {
                geometry.Type = GeometryType.Mesh;
                geometry.MeshPath = meshNode.Attributes["filename"]?.Value;

                string scale = meshNode.Attributes["scale"]?.Value;
                if (!string.IsNullOrEmpty(scale))
                {
                    string[] values = scale.Split(' ');
                    geometry.Scale = new Vector3(
                        float.Parse(values[0]),
                        values.Length > 1 ? float.Parse(values[1]) : float.Parse(values[0]),
                        values.Length > 2 ? float.Parse(values[2]) : float.Parse(values[0])
                    );
                }
                else
                {
                    geometry.Scale = Vector3.one;
                }
                return geometry;
            }

            return geometry;
        }

        private URDFJoint ParseJoint(XmlNode node)
        {
            var joint = new URDFJoint
            {
                Name = node.Attributes["name"]?.Value,
                Type = ParseJointType(node.Attributes["type"]?.Value)
            };

            var parentNode = node.SelectSingleNode("parent");
            if (parentNode != null)
            {
                joint.ParentLink = parentNode.Attributes["link"]?.Value;
            }

            var childNode = node.SelectSingleNode("child");
            if (childNode != null)
            {
                joint.ChildLink = childNode.Attributes["link"]?.Value;
            }

            var originNode = node.SelectSingleNode("origin");
            if (originNode != null)
            {
                joint.Origin = ParseOrigin(originNode);
            }

            var axisNode = node.SelectSingleNode("axis");
            if (axisNode != null)
            {
                string xyz = axisNode.Attributes["xyz"]?.Value ?? "0 0 1";
                string[] values = xyz.Split(' ');
                joint.Axis = new Vector3(
                    float.Parse(values[0]),
                    float.Parse(values[1]),
                    float.Parse(values[2])
                );
            }
            else
            {
                joint.Axis = Vector3.forward; // Default Z axis
            }

            var limitNode = node.SelectSingleNode("limit");
            if (limitNode != null)
            {
                joint.LowerLimit = float.Parse(limitNode.Attributes["lower"]?.Value ?? "-3.14159");
                joint.UpperLimit = float.Parse(limitNode.Attributes["upper"]?.Value ?? "3.14159");
                joint.VelocityLimit = float.Parse(limitNode.Attributes["velocity"]?.Value ?? "1");
                joint.EffortLimit = float.Parse(limitNode.Attributes["effort"]?.Value ?? "100");
            }

            var dynamicsNode = node.SelectSingleNode("dynamics");
            if (dynamicsNode != null)
            {
                joint.Damping = float.Parse(dynamicsNode.Attributes["damping"]?.Value ?? "0");
                joint.Friction = float.Parse(dynamicsNode.Attributes["friction"]?.Value ?? "0");
            }

            var mimicNode = node.SelectSingleNode("mimic");
            if (mimicNode != null)
            {
                joint.MimicJoint = mimicNode.Attributes["joint"]?.Value;
                joint.MimicMultiplier = float.Parse(mimicNode.Attributes["multiplier"]?.Value ?? "1");
                joint.MimicOffset = float.Parse(mimicNode.Attributes["offset"]?.Value ?? "0");
            }

            return joint;
        }

        private URDFOrigin ParseOrigin(XmlNode node)
        {
            var origin = new URDFOrigin();

            string xyz = node.Attributes["xyz"]?.Value;
            if (!string.IsNullOrEmpty(xyz))
            {
                string[] values = xyz.Split(' ');
                origin.Position = new Vector3(
                    float.Parse(values[0]),
                    float.Parse(values[1]),
                    float.Parse(values[2])
                );
            }

            string rpy = node.Attributes["rpy"]?.Value;
            if (!string.IsNullOrEmpty(rpy))
            {
                string[] values = rpy.Split(' ');
                origin.RPY = new Vector3(
                    float.Parse(values[0]),
                    float.Parse(values[1]),
                    float.Parse(values[2])
                );
            }

            return origin;
        }

        private JointType ParseJointType(string type)
        {
            return type?.ToLower() switch
            {
                "revolute" => JointType.Revolute,
                "continuous" => JointType.Continuous,
                "prismatic" => JointType.Prismatic,
                "fixed" => JointType.Fixed,
                "floating" => JointType.Floating,
                "planar" => JointType.Planar,
                _ => JointType.Fixed
            };
        }

        #endregion

        #region GameObject Creation

        private URDFRobot CreateRobotHierarchy(URDFModel model, string meshBasePath, Transform parent)
        {
            var robot = new URDFRobot
            {
                Name = model.Name,
                Model = model,
                Links = new Dictionary<string, URDFLinkObject>(),
                Joints = new Dictionary<string, URDFJointObject>(),
                MeshBasePath = meshBasePath
            };

            // Create root GameObject
            robot.RootObject = new GameObject(model.Name);
            if (parent != null)
            {
                robot.RootObject.transform.SetParent(parent);
            }
            robot.RootObject.transform.localPosition = Vector3.zero;
            robot.RootObject.transform.localRotation = Quaternion.identity;

            // Create links recursively starting from root
            if (!string.IsNullOrEmpty(model.RootLink) && model.Links.TryGetValue(model.RootLink, out var rootLink))
            {
                CreateLinkHierarchy(robot, rootLink, robot.RootObject.transform, model);
            }

            return robot;
        }

        private void CreateLinkHierarchy(URDFRobot robot, URDFLink linkDef, Transform parent, URDFModel model)
        {
            // Create link GameObject
            var linkObj = new GameObject(linkDef.Name);
            linkObj.transform.SetParent(parent);
            linkObj.transform.localPosition = Vector3.zero;
            linkObj.transform.localRotation = Quaternion.identity;

            var linkObject = new URDFLinkObject
            {
                Name = linkDef.Name,
                GameObject = linkObj,
                Definition = linkDef
            };

            robot.Links[linkDef.Name] = linkObject;

            // Add physics if enabled
            if (enablePhysics && linkDef.Inertial != null)
            {
                if (useArticulationBodies)
                {
                    var artBody = linkObj.AddComponent<ArticulationBody>();
                    artBody.mass = linkDef.Inertial.Mass;
                    // Configure inertia tensor
                }
                else
                {
                    var rb = linkObj.AddComponent<Rigidbody>();
                    rb.mass = linkDef.Inertial.Mass;
                }
            }

            // Create child joints and links
            foreach (var childJointName in linkDef.ChildJoints)
            {
                if (!model.Joints.TryGetValue(childJointName, out var jointDef)) continue;
                if (!model.Links.TryGetValue(jointDef.ChildLink, out var childLinkDef)) continue;

                // Create joint transform
                var jointObj = new GameObject($"joint_{jointDef.Name}");
                jointObj.transform.SetParent(linkObj.transform);

                // Apply joint origin (URDF uses ROS coordinate system)
                Vector3 position = URDFToUnityPosition(jointDef.Origin.Position);
                Quaternion rotation = URDFToUnityRotation(jointDef.Origin.RPY);
                jointObj.transform.localPosition = position;
                jointObj.transform.localRotation = rotation;

                var jointObject = new URDFJointObject
                {
                    Name = jointDef.Name,
                    GameObject = jointObj,
                    Definition = jointDef,
                    CurrentPosition = 0f
                };

                robot.Joints[jointDef.Name] = jointObject;

                // Create child link under joint
                CreateLinkHierarchy(robot, childLinkDef, jointObj.transform, model);
            }
        }

        #endregion

        #region Mesh Loading

        private IEnumerator LoadMeshes(URDFRobot robot, string basePath, bool isCollision)
        {
            foreach (var linkObj in robot.Links.Values)
            {
                var geometryElement = isCollision ? linkObj.Definition.Collision : linkObj.Definition.Visual;
                if (geometryElement?.Geometry == null) continue;

                var geometry = geometryElement.Geometry;
                GameObject meshObj = null;

                switch (geometry.Type)
                {
                    case GeometryType.Box:
                        meshObj = CreateBoxMesh(geometry.Size, isCollision);
                        break;

                    case GeometryType.Cylinder:
                        meshObj = CreateCylinderMesh(geometry.Radius, geometry.Length, isCollision);
                        break;

                    case GeometryType.Sphere:
                        meshObj = CreateSphereMesh(geometry.Radius, isCollision);
                        break;

                    case GeometryType.Mesh:
                        meshObj = LoadMeshFile(geometry.MeshPath, basePath, geometry.Scale, isCollision);
                        break;
                }

                if (meshObj != null)
                {
                    meshObj.transform.SetParent(linkObj.GameObject.transform);
                    meshObj.transform.localPosition = URDFToUnityPosition(geometryElement.Origin.Position);
                    meshObj.transform.localRotation = URDFToUnityRotation(geometryElement.Origin.RPY);

                    // Apply material
                    if (!isCollision && useURDFMaterials)
                    {
                        ApplyMaterial(meshObj, geometryElement, robot.Model);
                    }

                    if (isCollision)
                    {
                        linkObj.CollisionObject = meshObj;
                        meshObj.layer = LayerMask.NameToLayer("Collision");
                    }
                    else
                    {
                        linkObj.VisualObject = meshObj;
                    }
                }

                yield return null;
            }
        }

        private GameObject CreateBoxMesh(Vector3 size, bool isCollision)
        {
            var obj = GameObject.CreatePrimitive(PrimitiveType.Cube);
            obj.name = isCollision ? "collision_box" : "visual_box";
            obj.transform.localScale = URDFToUnityScale(size);

            if (isCollision)
            {
                var renderer = obj.GetComponent<Renderer>();
                if (renderer != null) renderer.enabled = false;
            }
            else
            {
                var collider = obj.GetComponent<Collider>();
                if (collider != null) Destroy(collider);
            }

            return obj;
        }

        private GameObject CreateCylinderMesh(float radius, float length, bool isCollision)
        {
            var obj = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            obj.name = isCollision ? "collision_cylinder" : "visual_cylinder";
            obj.transform.localScale = new Vector3(radius * 2, length / 2, radius * 2);

            if (isCollision)
            {
                var renderer = obj.GetComponent<Renderer>();
                if (renderer != null) renderer.enabled = false;
            }
            else
            {
                var collider = obj.GetComponent<Collider>();
                if (collider != null) Destroy(collider);
            }

            return obj;
        }

        private GameObject CreateSphereMesh(float radius, bool isCollision)
        {
            var obj = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            obj.name = isCollision ? "collision_sphere" : "visual_sphere";
            obj.transform.localScale = Vector3.one * radius * 2;

            if (isCollision)
            {
                var renderer = obj.GetComponent<Renderer>();
                if (renderer != null) renderer.enabled = false;
            }
            else
            {
                var collider = obj.GetComponent<Collider>();
                if (collider != null) Destroy(collider);
            }

            return obj;
        }

        private GameObject LoadMeshFile(string meshPath, string basePath, Vector3 scale, bool isCollision)
        {
            // Handle package:// URLs
            if (meshPath.StartsWith("package://"))
            {
                meshPath = meshPath.Replace("package://", "");
                // Find first slash after package name
                int slashIndex = meshPath.IndexOf('/');
                if (slashIndex > 0)
                {
                    meshPath = meshPath.Substring(slashIndex + 1);
                }
            }

            string fullPath = Path.Combine(basePath, meshPath);

            // DIAGNOSTIC: Log full path being checked
            Debug.Log($"[URDFLoader] Attempting to load mesh from: {fullPath}");
            Debug.Log($"[URDFLoader] File exists: {File.Exists(fullPath)}");

            // Check file extension
            string extension = Path.GetExtension(meshPath).ToLower();

            GameObject meshObj = new GameObject(isCollision ? "collision_mesh" : "visual_mesh");

            // Try to load actual mesh file
            bool meshLoaded = false;

            if (File.Exists(fullPath))
            {
                switch (extension)
                {
                    case ".stl":
                        var stlMesh = STLMeshLoader.LoadMesh(fullPath);
                        if (stlMesh != null)
                        {
                            var meshFilter = meshObj.AddComponent<MeshFilter>();
                            meshFilter.mesh = stlMesh;

                            var meshRenderer = meshObj.AddComponent<MeshRenderer>();
                            if (!isCollision)
                            {
                                // Apply default material
                                var mat = defaultLinkMaterial != null ? defaultLinkMaterial :
                                    new Material(Shader.Find("Standard"));
                                if (defaultLinkMaterial == null)
                                {
                                    mat.color = new Color(0.85f, 0.85f, 0.88f);
                                    mat.SetFloat("_Metallic", 0.3f);
                                    mat.SetFloat("_Glossiness", 0.5f);
                                }
                                meshRenderer.material = mat;
                            }

                            // Apply scale
                            meshObj.transform.localScale = URDFToUnityScale(scale) * defaultMeshScale;
                            meshLoaded = true;
                            Debug.Log($"[URDFLoader] Loaded STL mesh: {meshPath}");
                        }
                        break;

                    case ".dae":
                        // DAE (COLLADA) files need a specialized loader
                        // For now, try loading as OBJ or create placeholder
                        Debug.Log($"[URDFLoader] DAE format not yet supported, using placeholder: {meshPath}");
                        break;

                    case ".obj":
                        // OBJ files would need an OBJ parser
                        Debug.Log($"[URDFLoader] OBJ format not yet supported, using placeholder: {meshPath}");
                        break;
                }
            }
            else
            {
                Debug.LogError($"[URDFLoader] *** MESH FILE NOT FOUND ***");
                Debug.LogError($"[URDFLoader] Full path: {fullPath}");
                Debug.LogError($"[URDFLoader] Base path: {basePath}");
                Debug.LogError($"[URDFLoader] Mesh path: {meshPath}");
            }

            // Create placeholder if mesh wasn't loaded
            if (!meshLoaded)
            {
                Debug.LogWarning($"[URDFLoader] Creating placeholder geometry for: {meshPath}");
                var placeholder = GameObject.CreatePrimitive(PrimitiveType.Cube);
                placeholder.name = "placeholder";
                placeholder.transform.SetParent(meshObj.transform);
                placeholder.transform.localPosition = Vector3.zero;
                placeholder.transform.localScale = Vector3.one * 0.02f * defaultMeshScale;

                if (isCollision)
                {
                    var renderer = placeholder.GetComponent<Renderer>();
                    if (renderer != null) renderer.enabled = false;
                }
                else
                {
                    var collider = placeholder.GetComponent<Collider>();
                    if (collider != null) Destroy(collider);

                    // Apply material to show it's a placeholder
                    var mat = new Material(Shader.Find("Standard"));
                    mat.color = new Color(1f, 0.5f, 0.5f, 0.5f);
                    placeholder.GetComponent<Renderer>().material = mat;
                }
            }

            // Handle collision mesh
            if (isCollision && meshLoaded)
            {
                var renderer = meshObj.GetComponent<MeshRenderer>();
                if (renderer != null) renderer.enabled = false;

                // Add mesh collider
                var meshFilter = meshObj.GetComponent<MeshFilter>();
                if (meshFilter != null && meshFilter.mesh != null)
                {
                    var meshCollider = meshObj.AddComponent<MeshCollider>();
                    meshCollider.sharedMesh = meshFilter.mesh;
                    meshCollider.convex = true; // For robot physics
                }
            }

            return meshObj;
        }

        private void ApplyMaterial(GameObject obj, URDFGeometryElement element, URDFModel model)
        {
            var renderer = obj.GetComponentInChildren<Renderer>();
            if (renderer == null) return;

            Material mat = null;

            // Check for inline color
            if (element.InlineColor.HasValue)
            {
                mat = new Material(Shader.Find("Standard"));
                mat.color = element.InlineColor.Value;
            }
            // Check for material reference
            else if (!string.IsNullOrEmpty(element.MaterialName) &&
                     model.Materials.TryGetValue(element.MaterialName, out var urdfMat))
            {
                mat = new Material(Shader.Find("Standard"));
                mat.color = urdfMat.Color;
            }
            // Use default
            else if (defaultLinkMaterial != null)
            {
                mat = defaultLinkMaterial;
            }

            if (mat != null)
            {
                renderer.material = mat;
            }
        }

        #endregion

        #region Joint Control

        private void SetupJointControllers(URDFRobot robot)
        {
            foreach (var jointObj in robot.Joints.Values)
            {
                if (jointObj.Definition.Type == JointType.Fixed) continue;

                var controller = jointObj.GameObject.AddComponent<URDFJointController>();
                controller.Initialize(jointObj);
                jointObj.Controller = controller;
            }
        }

        #endregion

        #region Coordinate Conversion

        // URDF uses ROS coordinate system (X-forward, Y-left, Z-up)
        // Unity uses (X-right, Y-up, Z-forward)
        private Vector3 URDFToUnityPosition(Vector3 urdfPos)
        {
            return new Vector3(-urdfPos.y, urdfPos.z, urdfPos.x);
        }

        private Vector3 URDFToUnityScale(Vector3 urdfScale)
        {
            return new Vector3(urdfScale.y, urdfScale.z, urdfScale.x);
        }

        private Quaternion URDFToUnityRotation(Vector3 rpy)
        {
            // RPY is Roll-Pitch-Yaw in radians
            // Convert to Unity quaternion
            Quaternion qx = Quaternion.AngleAxis(rpy.x * Mathf.Rad2Deg, Vector3.right);
            Quaternion qy = Quaternion.AngleAxis(rpy.y * Mathf.Rad2Deg, Vector3.up);
            Quaternion qz = Quaternion.AngleAxis(rpy.z * Mathf.Rad2Deg, Vector3.forward);

            // Apply coordinate system transformation
            return Quaternion.Euler(-rpy.y * Mathf.Rad2Deg, rpy.z * Mathf.Rad2Deg, rpy.x * Mathf.Rad2Deg);
        }

        #endregion
    }

    #region Data Classes

    [Serializable]
    public class URDFModel
    {
        public string Name;
        public string RootLink;
        public Dictionary<string, URDFLink> Links = new Dictionary<string, URDFLink>();
        public Dictionary<string, URDFJoint> Joints = new Dictionary<string, URDFJoint>();
        public Dictionary<string, URDFMaterial> Materials = new Dictionary<string, URDFMaterial>();
    }

    [Serializable]
    public class URDFLink
    {
        public string Name;
        public string ParentJoint;
        public List<string> ChildJoints;
        public URDFInertial Inertial;
        public URDFGeometryElement Visual;
        public URDFGeometryElement Collision;
    }

    [Serializable]
    public class URDFJoint
    {
        public string Name;
        public JointType Type;
        public string ParentLink;
        public string ChildLink;
        public URDFOrigin Origin = new URDFOrigin();
        public Vector3 Axis = Vector3.forward;
        public float LowerLimit = -Mathf.PI;
        public float UpperLimit = Mathf.PI;
        public float VelocityLimit = 1f;
        public float EffortLimit = 100f;
        public float Damping;
        public float Friction;
        public string MimicJoint;
        public float MimicMultiplier = 1f;
        public float MimicOffset;
    }

    public enum JointType
    {
        Fixed,
        Revolute,
        Continuous,
        Prismatic,
        Floating,
        Planar
    }

    [Serializable]
    public class URDFOrigin
    {
        public Vector3 Position = Vector3.zero;
        public Vector3 RPY = Vector3.zero; // Roll, Pitch, Yaw in radians
    }

    [Serializable]
    public class URDFInertial
    {
        public URDFOrigin Origin = new URDFOrigin();
        public float Mass = 1f;
        public float Ixx, Ixy, Ixz, Iyy, Iyz, Izz;
    }

    [Serializable]
    public class URDFGeometryElement
    {
        public URDFOrigin Origin = new URDFOrigin();
        public URDFGeometry Geometry;
        public string MaterialName;
        public Color? InlineColor;
    }

    [Serializable]
    public class URDFGeometry
    {
        public GeometryType Type;
        public Vector3 Size; // For box
        public float Radius; // For cylinder/sphere
        public float Length; // For cylinder
        public string MeshPath; // For mesh
        public Vector3 Scale = Vector3.one; // For mesh
    }

    public enum GeometryType
    {
        Box,
        Cylinder,
        Sphere,
        Mesh
    }

    [Serializable]
    public class URDFMaterial
    {
        public string Name;
        public Color Color = Color.gray;
        public string TexturePath;
    }

    [Serializable]
    public class URDFRobot
    {
        public string Name;
        public URDFModel Model;
        public GameObject RootObject;
        public Dictionary<string, URDFLinkObject> Links;
        public Dictionary<string, URDFJointObject> Joints;
        public string MeshBasePath;
    }

    [Serializable]
    public class URDFLinkObject
    {
        public string Name;
        public GameObject GameObject;
        public URDFLink Definition;
        public GameObject VisualObject;
        public GameObject CollisionObject;
    }

    [Serializable]
    public class URDFJointObject
    {
        public string Name;
        public GameObject GameObject;
        public URDFJoint Definition;
        public URDFJointController Controller;
        public float CurrentPosition;
        public float CurrentVelocity;
    }

    #endregion

    /// <summary>
    /// Controller component for URDF joints
    /// </summary>
    public class URDFJointController : MonoBehaviour
    {
        private URDFJointObject jointObject;
        private float targetPosition;
        private float positionSpeed = 2f;

        public float Position => jointObject?.CurrentPosition ?? 0f;
        public float TargetPosition => targetPosition;

        public void Initialize(URDFJointObject joint)
        {
            jointObject = joint;
            targetPosition = 0f;
        }

        public void SetPosition(float position)
        {
            if (jointObject == null) return;

            // Clamp to limits
            var def = jointObject.Definition;
            targetPosition = Mathf.Clamp(position, def.LowerLimit, def.UpperLimit);
        }

        public void SetPositionImmediate(float position)
        {
            SetPosition(position);
            jointObject.CurrentPosition = targetPosition;
            ApplyRotation();
        }

        private void Update()
        {
            if (jointObject == null) return;

            // Smooth movement to target
            jointObject.CurrentPosition = Mathf.MoveTowards(
                jointObject.CurrentPosition,
                targetPosition,
                positionSpeed * Time.deltaTime
            );

            ApplyRotation();
        }

        private void ApplyRotation()
        {
            var def = jointObject.Definition;
            Vector3 axis = def.Axis;

            switch (def.Type)
            {
                case JointType.Revolute:
                case JointType.Continuous:
                    transform.localRotation = Quaternion.AngleAxis(
                        jointObject.CurrentPosition * Mathf.Rad2Deg,
                        axis
                    );
                    break;

                case JointType.Prismatic:
                    transform.localPosition = axis * jointObject.CurrentPosition;
                    break;
            }
        }
    }
}
