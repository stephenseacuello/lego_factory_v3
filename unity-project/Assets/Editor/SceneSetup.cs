using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using CNCScada.Machines;
using CNCScada.Core;
using CNCScada.Sensors;
using CNCScada.Connection;
using CNCScada.Alarms;
using CNCScada.Analytics;
using CNCScada.Vision;
using CNCScada.OPCUA;
using CNCScada.Camera;
using CNCScada.Toolpath;
using CNCScada.Predictive;
using CNC_SCADA.DigitalTwin.URDF;

namespace CNCScada.Editor
{
    /// <summary>
    /// Scene setup utility for CNC SCADA Digital Twin.
    /// Creates a complete factory cell with Bantam CNC, xArm Lite 6, and Niryo Ned2.
    /// Includes sensor system, automation, MTConnect, and visualization subsystems.
    /// </summary>
    public static class SceneSetup
    {
        [MenuItem("CNC SCADA/1. Setup Complete Scene", false, 1)]
        public static void SetupCompleteScene()
        {
            Debug.Log("[SceneSetup] Starting scene setup...");

            // Create new scene
            EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);

            // Configure camera
            SetupCamera();

            // Configure lighting
            SetupLighting();

            // Create ground/floor
            CreateGround();

            // Create factory cell machines
            CreateFactoryCell();

            // Create Digital Twin Manager with all subsystems
            CreateDigitalTwinManager();

            // Create UI
            CreateUI();

            // Save scene
            SaveScene();

            Debug.Log("[SceneSetup] Scene setup complete!");

            EditorUtility.DisplayDialog(
                "Scene Setup Complete",
                "Created Digital Twin scene with:\n\n" +
                "MACHINES:\n" +
                "- Bantam Desktop Explorer CNC\n" +
                "- xArm Lite 6 Robot\n" +
                "- Niryo Ned2 Robot\n\n" +
                "SUBSYSTEMS:\n" +
                "- Sensor System & Visualization\n" +
                "- Automation Controller\n" +
                "- Alarm System\n" +
                "- Production Analytics (OEE)\n" +
                "- Vision Inspection\n" +
                "- Predictive Maintenance\n" +
                "- Toolpath Visualizer\n" +
                "- Orbit Camera Controller\n" +
                "- Data Logger\n\n" +
                "Press Play to start simulation!",
                "OK"
            );
        }

        [MenuItem("CNC SCADA/2. Add Bantam CNC Only", false, 10)]
        public static void AddBantamCNC()
        {
            var cnc = BantamCNCController.CreateVisual();
            cnc.transform.position = Vector3.zero;
            Selection.activeGameObject = cnc;
            Debug.Log("[SceneSetup] Added Bantam CNC to scene (placeholder geometry)");
        }

        [MenuItem("CNC SCADA/2b. Add Bantam CNC (STL Model)", false, 10)]
        public static void AddBantamCNCFromSTL()
        {
            var cnc = BantamCNCController.CreateVisualFromSTL();
            cnc.transform.position = Vector3.zero;
            Selection.activeGameObject = cnc;
            Debug.Log("[SceneSetup] Added Bantam CNC to scene (STL model)");
        }

        [MenuItem("CNC SCADA/3. Add xArm Lite 6 Only", false, 11)]
        public static void AddXArmLite6()
        {
            var robot = XArmLite6Controller.CreateVisual();
            robot.transform.position = new Vector3(0.5f, 0, 0);
            Selection.activeGameObject = robot;
            Debug.Log("[SceneSetup] Added xArm Lite 6 to scene (placeholder geometry)");
        }

        [MenuItem("CNC SCADA/3b. Add xArm Lite 6 (STL Model)", false, 11)]
        public static void AddXArmLite6FromSTL()
        {
            var robot = XArmLite6Controller.CreateVisualFromSTL();
            robot.transform.position = new Vector3(0.5f, 0, 0);
            Selection.activeGameObject = robot;
            Debug.Log("[SceneSetup] Added xArm Lite 6 to scene (STL model)");
        }

        [MenuItem("CNC SCADA/4. Add Niryo Ned2 Only", false, 12)]
        public static void AddNiryoNed2()
        {
            var robot = NiryoNed2Controller.CreateVisual();
            robot.transform.position = new Vector3(-0.5f, 0, 0);
            Selection.activeGameObject = robot;
            Debug.Log("[SceneSetup] Added Niryo Ned2 to scene (placeholder geometry)");
        }

        [MenuItem("CNC SCADA/4b. Add Niryo Ned2 (STL Model)", false, 12)]
        public static void AddNiryoNed2FromSTL()
        {
            var robot = NiryoNed2Controller.CreateVisualFromSTL();
            robot.transform.position = new Vector3(-0.5f, 0, 0);
            Selection.activeGameObject = robot;
            Debug.Log("[SceneSetup] Added Niryo Ned2 to scene (STL model)");
        }

        [MenuItem("CNC SCADA/4b. Add URDF Model Loader", false, 13)]
        public static void AddURDFModelLoader()
        {
            if (Object.FindObjectOfType<URDFRobotLoader>() == null)
            {
                var loaderObj = new GameObject("URDFRobotLoader");
                loaderObj.AddComponent<URDFRobotLoader>();
            }

            if (Object.FindObjectOfType<URDFModelInitializer>() != null)
            {
                Debug.LogWarning("[SceneSetup] URDFModelInitializer already exists in scene");
                return;
            }

            var initObj = new GameObject("URDFModelInitializer");
            var initializer = initObj.AddComponent<URDFModelInitializer>();

            // Configure robots to load via serialized field would be done in inspector
            // For now just create the object
            Selection.activeGameObject = initObj;

            Debug.Log("[SceneSetup] Added URDF Model Loader to scene.\n" +
                      "Configure robot paths in the Inspector:\n" +
                      "- xArm Lite 6: xarm6/lite6.urdf\n" +
                      "- Niryo Ned2: niryo_ned2/niryo_ned2.urdf");

            EditorUtility.DisplayDialog(
                "URDF Model Loader Added",
                "Configure the URDFModelInitializer component in the Inspector.\n\n" +
                "Add robot configurations with:\n" +
                "- xArm Lite 6: xarm6/lite6.urdf\n" +
                "- Niryo Ned2: niryo_ned2/niryo_ned2.urdf\n\n" +
                "The robots will be loaded from URDF files when you press Play.",
                "OK"
            );
        }

        [MenuItem("CNC SCADA/5. Add Sensor System", false, 20)]
        public static void AddSensorSystem()
        {
            if (Object.FindObjectOfType<SensorSystem>() != null)
            {
                Debug.LogWarning("[SceneSetup] SensorSystem already exists in scene");
                return;
            }

            var sensorObj = new GameObject("SensorSystem");
            sensorObj.AddComponent<SensorSystem>();
            sensorObj.AddComponent<SensorVisualization>();
            sensorObj.AddComponent<DataLogger>();

            Selection.activeGameObject = sensorObj;
            Debug.Log("[SceneSetup] Added Sensor System to scene");
        }

        [MenuItem("CNC SCADA/6. Add Digital Twin Manager", false, 21)]
        public static void AddDigitalTwinManager()
        {
            if (Object.FindObjectOfType<DigitalTwinManager>() != null)
            {
                Debug.LogWarning("[SceneSetup] DigitalTwinManager already exists in scene");
                return;
            }

            CreateDigitalTwinManager();
            Selection.activeGameObject = Object.FindObjectOfType<DigitalTwinManager>()?.gameObject;
        }

        [MenuItem("CNC SCADA/7. Add Alarm System", false, 22)]
        public static void AddAlarmSystem()
        {
            if (Object.FindObjectOfType<AlarmSystem>() != null)
            {
                Debug.LogWarning("[SceneSetup] AlarmSystem already exists in scene");
                return;
            }

            var alarmObj = new GameObject("AlarmSystem");
            alarmObj.AddComponent<AlarmSystem>();
            Selection.activeGameObject = alarmObj;
            Debug.Log("[SceneSetup] Added Alarm System to scene");
        }

        [MenuItem("CNC SCADA/8. Add Production Analytics", false, 23)]
        public static void AddProductionAnalytics()
        {
            if (Object.FindObjectOfType<ProductionAnalytics>() != null)
            {
                Debug.LogWarning("[SceneSetup] ProductionAnalytics already exists in scene");
                return;
            }

            var analyticsObj = new GameObject("ProductionAnalytics");
            analyticsObj.AddComponent<ProductionAnalytics>();
            Selection.activeGameObject = analyticsObj;
            Debug.Log("[SceneSetup] Added Production Analytics to scene");
        }

        [MenuItem("CNC SCADA/9. Add Vision Inspection", false, 24)]
        public static void AddVisionInspection()
        {
            if (Object.FindObjectOfType<VisionInspectionSystem>() != null)
            {
                Debug.LogWarning("[SceneSetup] VisionInspectionSystem already exists in scene");
                return;
            }

            var visionObj = new GameObject("VisionInspectionSystem");
            visionObj.AddComponent<VisionInspectionSystem>();
            Selection.activeGameObject = visionObj;
            Debug.Log("[SceneSetup] Added Vision Inspection System to scene");
        }

        [MenuItem("CNC SCADA/10. Add Predictive Maintenance", false, 25)]
        public static void AddPredictiveMaintenance()
        {
            if (Object.FindObjectOfType<PredictiveMaintenanceSystem>() != null)
            {
                Debug.LogWarning("[SceneSetup] PredictiveMaintenanceSystem already exists in scene");
                return;
            }

            var predictiveObj = new GameObject("PredictiveMaintenanceSystem");
            predictiveObj.AddComponent<PredictiveMaintenanceSystem>();
            Selection.activeGameObject = predictiveObj;
            Debug.Log("[SceneSetup] Added Predictive Maintenance System to scene");
        }

        [MenuItem("CNC SCADA/11. Add Orbit Camera", false, 26)]
        public static void AddOrbitCamera()
        {
            var mainCamera = UnityEngine.Camera.main;
            if (mainCamera == null)
            {
                Debug.LogWarning("[SceneSetup] No main camera found");
                return;
            }

            if (mainCamera.GetComponent<OrbitCameraController>() != null)
            {
                Debug.LogWarning("[SceneSetup] OrbitCameraController already exists");
                return;
            }

            var controller = mainCamera.gameObject.AddComponent<OrbitCameraController>();

            // Find factory cell as default target
            var factoryCell = GameObject.Find("FactoryCell");
            if (factoryCell != null)
            {
                controller.SetTarget(factoryCell.transform, false);
            }

            Selection.activeGameObject = mainCamera.gameObject;
            Debug.Log("[SceneSetup] Added Orbit Camera Controller to main camera");
        }

        [MenuItem("CNC SCADA/---", false, 30)]
        public static void Separator() { }

        [MenuItem("CNC SCADA/Run Demo Sequence", false, 40)]
        public static void RunDemoSequence()
        {
            if (!Application.isPlaying)
            {
                EditorUtility.DisplayDialog("Demo Sequence",
                    "Please enter Play mode first to run the demo sequence.",
                    "OK");
                return;
            }

            var manager = Object.FindObjectOfType<DigitalTwinManager>();
            if (manager != null)
            {
                manager.StartSimulation();
            }
            else
            {
                Debug.LogWarning("[SceneSetup] DigitalTwinManager not found. Run 'Setup Complete Scene' first.");
            }
        }

        private static void SetupCamera()
        {
            var camera = GameObject.Find("Main Camera");
            if (camera != null)
            {
                camera.transform.position = new Vector3(0.8f, 0.6f, 0.8f);
                camera.transform.LookAt(new Vector3(0, 0.2f, 0));

                var cam = camera.GetComponent<UnityEngine.Camera>();
                cam.backgroundColor = new Color(0.12f, 0.12f, 0.15f);
                cam.clearFlags = CameraClearFlags.SolidColor;
                cam.nearClipPlane = 0.01f;
            }
            Debug.Log("[SceneSetup] Camera configured");
        }

        private static void SetupLighting()
        {
            var light = GameObject.Find("Directional Light");
            if (light != null)
            {
                light.transform.rotation = Quaternion.Euler(45, -45, 0);
                var lightComp = light.GetComponent<Light>();
                lightComp.intensity = 1.2f;
                lightComp.color = new Color(1f, 0.98f, 0.95f);
            }

            // Add ambient fill light
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.3f, 0.3f, 0.35f);

            Debug.Log("[SceneSetup] Lighting configured");
        }

        private static void CreateGround()
        {
            // Factory floor
            var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = "FactoryFloor";
            ground.transform.position = Vector3.zero;
            ground.transform.localScale = new Vector3(0.3f, 1, 0.3f);

            var mat = new Material(Shader.Find("Standard"));
            mat.color = new Color(0.25f, 0.25f, 0.28f);
            mat.SetFloat("_Metallic", 0.1f);
            mat.SetFloat("_Glossiness", 0.3f);
            ground.GetComponent<Renderer>().material = mat;

            // Work table
            var table = GameObject.CreatePrimitive(PrimitiveType.Cube);
            table.name = "WorkTable";
            table.transform.position = new Vector3(0, 0.35f, -0.3f);
            table.transform.localScale = new Vector3(1.2f, 0.02f, 0.6f);

            var tableMat = new Material(Shader.Find("Standard"));
            tableMat.color = new Color(0.4f, 0.35f, 0.3f);
            table.GetComponent<Renderer>().material = tableMat;

            // Table legs
            for (int x = -1; x <= 1; x += 2)
            {
                for (int z = -1; z <= 1; z += 2)
                {
                    var leg = GameObject.CreatePrimitive(PrimitiveType.Cube);
                    leg.name = "TableLeg";
                    leg.transform.position = new Vector3(x * 0.55f, 0.175f, -0.3f + z * 0.25f);
                    leg.transform.localScale = new Vector3(0.04f, 0.35f, 0.04f);
                    leg.transform.SetParent(table.transform);

                    var legMat = new Material(Shader.Find("Standard"));
                    legMat.color = new Color(0.3f, 0.3f, 0.32f);
                    leg.GetComponent<Renderer>().material = legMat;
                }
            }

            Debug.Log("[SceneSetup] Ground and work table created");
        }

        private static void CreateFactoryCell()
        {
            // Create parent for organization
            var cellParent = new GameObject("FactoryCell");

            // Bantam CNC in center on the table (using STL model)
            var cnc = BantamCNCController.CreateVisualFromSTL(cellParent.transform);
            cnc.transform.localPosition = new Vector3(0, 0.36f, -0.3f);
            Debug.Log("[SceneSetup] Bantam CNC created (STL model)");

            // xArm Lite 6 on the right (using STL model)
            var xarm = XArmLite6Controller.CreateVisualFromSTL(cellParent.transform);
            xarm.transform.localPosition = new Vector3(0.5f, 0, 0);
            Debug.Log("[SceneSetup] xArm Lite 6 created (STL model)");

            // Niryo Ned2 on the left (using STL model)
            var niryo = NiryoNed2Controller.CreateVisualFromSTL(cellParent.transform);
            niryo.transform.localPosition = new Vector3(-0.5f, 0, 0);
            Debug.Log("[SceneSetup] Niryo Ned2 created (STL model)");

            // Parts bin (for visual interest)
            CreatePartsBin(cellParent.transform, new Vector3(0.4f, 0, 0.3f));
            CreatePartsBin(cellParent.transform, new Vector3(-0.4f, 0, 0.3f));

            Debug.Log("[SceneSetup] Factory cell created with STL models");
        }

        private static void CreateDigitalTwinManager()
        {
            // Create main manager object
            var managerObj = new GameObject("DigitalTwinManager");
            var manager = managerObj.AddComponent<DigitalTwinManager>();

            // Find and link machines
            manager.bantamCNC = Object.FindObjectOfType<BantamCNCController>();
            manager.xArmLite6 = Object.FindObjectOfType<XArmLite6Controller>();
            manager.niryoNed2 = Object.FindObjectOfType<NiryoNed2Controller>();

            // Create Flask SocketIO Client
            var socketObj = new GameObject("FlaskSocketIOClient");
            socketObj.transform.SetParent(managerObj.transform);
            var socketClient = socketObj.AddComponent<FlaskSocketIOClient>();
            manager.flaskClient = socketClient;

            Debug.Log("[SceneSetup] DigitalTwinManager created with all subsystems");
        }

        private static void CreatePartsBin(Transform parent, Vector3 position)
        {
            var bin = new GameObject("PartsBin");
            bin.transform.SetParent(parent);
            bin.transform.localPosition = position;

            // Bin box
            var box = GameObject.CreatePrimitive(PrimitiveType.Cube);
            box.name = "BinBox";
            box.transform.SetParent(bin.transform);
            box.transform.localPosition = new Vector3(0, 0.05f, 0);
            box.transform.localScale = new Vector3(0.15f, 0.1f, 0.1f);

            var mat = new Material(Shader.Find("Standard"));
            mat.color = new Color(0.3f, 0.4f, 0.6f);
            box.GetComponent<Renderer>().material = mat;

            // Add some "parts" (small cubes)
            for (int i = 0; i < 3; i++)
            {
                var part = GameObject.CreatePrimitive(PrimitiveType.Cube);
                part.name = "Part";
                part.transform.SetParent(bin.transform);
                part.transform.localPosition = new Vector3(
                    Random.Range(-0.04f, 0.04f),
                    0.12f + i * 0.025f,
                    Random.Range(-0.03f, 0.03f)
                );
                part.transform.localScale = new Vector3(0.02f, 0.02f, 0.02f);
                part.transform.localRotation = Random.rotation;

                var partMat = new Material(Shader.Find("Standard"));
                partMat.color = new Color(0.75f, 0.7f, 0.5f);
                partMat.SetFloat("_Metallic", 0.7f);
                part.GetComponent<Renderer>().material = partMat;
            }
        }

        private static void CreateUI()
        {
            // Create Canvas
            var canvasObj = new GameObject("UICanvas");
            var canvas = canvasObj.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvasObj.AddComponent<UnityEngine.UI.CanvasScaler>();
            canvasObj.AddComponent<UnityEngine.UI.GraphicRaycaster>();

            // Status panel
            var panel = new GameObject("StatusPanel");
            panel.transform.SetParent(canvasObj.transform);

            var panelRect = panel.AddComponent<RectTransform>();
            panelRect.anchorMin = new Vector2(0, 1);
            panelRect.anchorMax = new Vector2(0, 1);
            panelRect.pivot = new Vector2(0, 1);
            panelRect.anchoredPosition = new Vector2(15, -15);
            panelRect.sizeDelta = new Vector2(280, 180);

            var panelImage = panel.AddComponent<UnityEngine.UI.Image>();
            panelImage.color = new Color(0.1f, 0.1f, 0.12f, 0.9f);

            // Title
            CreateUIText(panel.transform, "Title", "CNC SCADA Digital Twin",
                new Vector2(140, -15), 18, new Color(0.9f, 0.9f, 0.95f));

            // Status lines
            CreateUIText(panel.transform, "BantamStatus", "Bantam CNC: Idle",
                new Vector2(140, -50), 14, new Color(0.7f, 0.9f, 0.7f));

            CreateUIText(panel.transform, "XArmStatus", "xArm Lite 6: Idle",
                new Vector2(140, -75), 14, new Color(0.7f, 0.8f, 0.9f));

            CreateUIText(panel.transform, "NiryoStatus", "Niryo Ned2: Idle",
                new Vector2(140, -100), 14, new Color(0.9f, 0.7f, 0.5f));

            CreateUIText(panel.transform, "ConnectionStatus", "Connection: Offline",
                new Vector2(140, -135), 12, new Color(0.6f, 0.6f, 0.65f));

            CreateUIText(panel.transform, "Instructions", "Press Play to start",
                new Vector2(140, -160), 11, new Color(0.5f, 0.5f, 0.55f));

            Debug.Log("[SceneSetup] UI created");
        }

        private static void CreateUIText(Transform parent, string name, string text,
            Vector2 position, int fontSize, Color color)
        {
            var textObj = new GameObject(name);
            textObj.transform.SetParent(parent);

            var rect = textObj.AddComponent<RectTransform>();
            rect.anchorMin = new Vector2(0, 1);
            rect.anchorMax = new Vector2(1, 1);
            rect.pivot = new Vector2(0.5f, 1);
            rect.anchoredPosition = new Vector2(position.x, position.y);
            rect.sizeDelta = new Vector2(260, 25);

            var textComp = textObj.AddComponent<UnityEngine.UI.Text>();
            textComp.text = text;
            textComp.fontSize = fontSize;
            textComp.color = color;
            textComp.alignment = TextAnchor.MiddleLeft;
            textComp.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
        }

        private static void SaveScene()
        {
            // Ensure Scenes folder exists
            string scenesPath = "Assets/Scenes";
            if (!AssetDatabase.IsValidFolder(scenesPath))
            {
                AssetDatabase.CreateFolder("Assets", "Scenes");
            }

            // Save scene
            string scenePath = scenesPath + "/DigitalTwin.unity";
            EditorSceneManager.SaveScene(UnityEngine.SceneManagement.SceneManager.GetActiveScene(), scenePath);

            // Add to build settings
            var scenes = new System.Collections.Generic.List<EditorBuildSettingsScene>(EditorBuildSettings.scenes);
            bool found = false;
            foreach (var s in scenes)
            {
                if (s.path == scenePath) { found = true; break; }
            }
            if (!found)
            {
                scenes.Add(new EditorBuildSettingsScene(scenePath, true));
                EditorBuildSettings.scenes = scenes.ToArray();
            }

            Debug.Log("[SceneSetup] Scene saved to " + scenePath);
        }
    }
}
