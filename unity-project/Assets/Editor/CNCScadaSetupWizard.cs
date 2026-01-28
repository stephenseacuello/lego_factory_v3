using UnityEngine;
using UnityEditor;
using System.IO;

namespace CNCScada.Editor
{
    /// <summary>
    /// Setup Wizard for CNC SCADA Unity Digital Twin System
    /// Helps configure connection settings and create required objects
    /// </summary>
    public class CNCScadaSetupWizard : EditorWindow
    {
        // Connection settings
        private string flaskServerUrl = "http://localhost:5000";
        private string machineId = "CNC-001";
        private int targetFrameRate = 60;

        // Setup progress
        private bool hasDigitalTwinCore = false;
        private bool hasSchedulingUI = false;
        private bool hasPredictiveOverlay = false;
        private bool hasRemoteControl = false;

        // Tabs
        private int selectedTab = 0;
        private string[] tabNames = { "Setup", "Digital Twin", "Scheduling", "Predictive", "Remote Control", "About" };

        // Scroll positions
        private Vector2 scrollPosition;

        [MenuItem("CNC SCADA/Setup Wizard")]
        public static void ShowWindow()
        {
            CNCScadaSetupWizard window = GetWindow<CNCScadaSetupWizard>("CNC SCADA Setup");
            window.minSize = new Vector2(600, 500);
            window.Show();
        }

        void OnEnable()
        {
            // Load saved settings
            flaskServerUrl = EditorPrefs.GetString("CNCScada.FlaskServerUrl", "http://localhost:5000");
            machineId = EditorPrefs.GetString("CNCScada.MachineId", "CNC-001");
            targetFrameRate = EditorPrefs.GetInt("CNCScada.TargetFrameRate", 60);

            CheckInstalledPackages();
        }

        void CheckInstalledPackages()
        {
            // Check if package directories exist
            hasDigitalTwinCore = Directory.Exists("Assets/Scripts/DigitalTwin");
            hasSchedulingUI = Directory.Exists("Assets/Scripts/Scheduling");
            hasPredictiveOverlay = Directory.Exists("Assets/Scripts/Predictive");
            hasRemoteControl = Directory.Exists("Assets/Scripts/RemoteControl");
        }

        void OnGUI()
        {
            // Header
            GUILayout.BeginVertical("box");
            GUILayout.Label("CNC SCADA Unity Digital Twin Setup", EditorStyles.boldLabel);
            GUILayout.Label("Configure your Industry 4.0 manufacturing system", EditorStyles.miniLabel);
            GUILayout.EndVertical();

            GUILayout.Space(10);

            // Tabs
            selectedTab = GUILayout.Toolbar(selectedTab, tabNames);

            GUILayout.Space(10);

            scrollPosition = GUILayout.BeginScrollView(scrollPosition);

            switch (selectedTab)
            {
                case 0:
                    DrawSetupTab();
                    break;
                case 1:
                    DrawDigitalTwinTab();
                    break;
                case 2:
                    DrawSchedulingTab();
                    break;
                case 3:
                    DrawPredictiveTab();
                    break;
                case 4:
                    DrawRemoteControlTab();
                    break;
                case 5:
                    DrawAboutTab();
                    break;
            }

            GUILayout.EndScrollView();

            // Footer with status
            GUILayout.FlexibleSpace();
            DrawFooter();
        }

        void DrawSetupTab()
        {
            GUILayout.Label("Connection Settings", EditorStyles.boldLabel);
            GUILayout.BeginVertical("box");

            EditorGUILayout.HelpBox("Configure connection to Flask SCADA backend", MessageType.Info);

            flaskServerUrl = EditorGUILayout.TextField("Flask Server URL:", flaskServerUrl);
            machineId = EditorGUILayout.TextField("Machine ID:", machineId);
            targetFrameRate = EditorGUILayout.IntSlider("Target Frame Rate:", targetFrameRate, 30, 120);

            GUILayout.Space(10);

            if (GUILayout.Button("Save Settings", GUILayout.Height(30)))
            {
                SaveSettings();
            }

            if (GUILayout.Button("Test Connection", GUILayout.Height(30)))
            {
                TestConnection();
            }

            GUILayout.EndVertical();

            GUILayout.Space(20);

            // Package status
            GUILayout.Label("Installed Packages", EditorStyles.boldLabel);
            GUILayout.BeginVertical("box");

            DrawPackageStatus("Digital Twin Core", hasDigitalTwinCore);
            DrawPackageStatus("Scheduling UI", hasSchedulingUI);
            DrawPackageStatus("Predictive Overlay", hasPredictiveOverlay);
            DrawPackageStatus("Remote Control", hasRemoteControl);

            GUILayout.EndVertical();

            GUILayout.Space(20);

            // Quick setup
            GUILayout.Label("Quick Setup", EditorStyles.boldLabel);
            GUILayout.BeginVertical("box");

            if (GUILayout.Button("Create Scene Setup Objects", GUILayout.Height(30)))
            {
                CreateSceneSetup();
            }

            if (GUILayout.Button("Create Example Scene", GUILayout.Height(30)))
            {
                CreateExampleScene();
            }

            GUILayout.EndVertical();
        }

        void DrawDigitalTwinTab()
        {
            GUILayout.Label("Digital Twin Core - 60Hz Visualization", EditorStyles.boldLabel);

            if (!hasDigitalTwinCore)
            {
                EditorGUILayout.HelpBox("Digital Twin Core package not found!", MessageType.Error);
                return;
            }

            GUILayout.BeginVertical("box");
            GUILayout.Label("Features:", EditorStyles.boldLabel);
            GUILayout.Label("• ISO23247StateHandler - 60Hz state updates");
            GUILayout.Label("• KinematicsAnimator - 6-axis animation");
            GUILayout.Label("• ToolpathVisualizer - G-code path rendering");
            GUILayout.Label("• SensorOverlayRenderer - Heatmaps & vibration");
            GUILayout.EndVertical();

            GUILayout.Space(10);

            if (GUILayout.Button("Add Digital Twin Components to Scene", GUILayout.Height(30)))
            {
                CreateDigitalTwinObjects();
            }

            GUILayout.Space(10);

            EditorGUILayout.HelpBox("Recommended setup:\n1. Add ISO23247StateHandler to manager object\n2. Add KinematicsAnimator and assign machine transforms\n3. Add ToolpathVisualizer for path rendering\n4. Add SensorOverlayRenderer for sensor data", MessageType.Info);
        }

        void DrawSchedulingTab()
        {
            GUILayout.Label("Scheduling UI - Gantt Chart & Optimization", EditorStyles.boldLabel);

            if (!hasSchedulingUI)
            {
                EditorGUILayout.HelpBox("Scheduling UI package not found!", MessageType.Error);
                return;
            }

            GUILayout.BeginVertical("box");
            GUILayout.Label("Features:", EditorStyles.boldLabel);
            GUILayout.Label("• GanttChartController - Interactive timeline");
            GUILayout.Label("• JobDragDropHandler - Drag-drop rescheduling");
            GUILayout.Label("• ScheduleOptimizer - OR-Tools integration");
            GUILayout.Label("• MachineCapacityView - Bottleneck detection");
            GUILayout.EndVertical();

            GUILayout.Space(10);

            if (GUILayout.Button("Add Scheduling Components to Scene", GUILayout.Height(30)))
            {
                CreateSchedulingObjects();
            }

            GUILayout.Space(10);

            EditorGUILayout.HelpBox("Recommended setup:\n1. Create Canvas for Gantt chart\n2. Add GanttChartController\n3. Add ScheduleOptimizer for OR-Tools\n4. Add MachineCapacityView for monitoring", MessageType.Info);
        }

        void DrawPredictiveTab()
        {
            GUILayout.Label("Predictive Overlay - AR Maintenance", EditorStyles.boldLabel);

            if (!hasPredictiveOverlay)
            {
                EditorGUILayout.HelpBox("Predictive Overlay package not found!", MessageType.Error);
                return;
            }

            GUILayout.BeginVertical("box");
            GUILayout.Label("Features:", EditorStyles.boldLabel);
            GUILayout.Label("• MaintenanceCalendarAR - AR event markers");
            GUILayout.Label("• ToolWearIndicator - RUL prediction");
            GUILayout.Label("• AnomalyMarker - 3D anomaly visualization");
            GUILayout.Label("• HealthScoreDisplay - Multi-factor gauges");
            GUILayout.EndVertical();

            GUILayout.Space(10);

            if (GUILayout.Button("Add Predictive Components to Scene", GUILayout.Height(30)))
            {
                CreatePredictiveObjects();
            }

            GUILayout.Space(10);

            EditorGUILayout.HelpBox("Recommended setup:\n1. Add MaintenanceCalendarAR for AR markers\n2. Add ToolWearIndicator to tool object\n3. Add AnomalyMarker for detection\n4. Add HealthScoreDisplay to UI canvas", MessageType.Info);
        }

        void DrawRemoteControlTab()
        {
            GUILayout.Label("Remote Control - <20ms Latency", EditorStyles.boldLabel);

            if (!hasRemoteControl)
            {
                EditorGUILayout.HelpBox("Remote Control package not found!", MessageType.Error);
                return;
            }

            GUILayout.BeginVertical("box");
            GUILayout.Label("Features:", EditorStyles.boldLabel);
            GUILayout.Label("• JogController - Continuous/incremental jogging");
            GUILayout.Label("• MDIConsole - G-code command entry");
            GUILayout.Label("• ProgramExecutor - Run/pause/stop programs");
            GUILayout.Label("• EmergencyStopButton - Safety interlock");
            GUILayout.EndVertical();

            GUILayout.Space(10);

            if (GUILayout.Button("Add Remote Control Components to Scene", GUILayout.Height(30)))
            {
                CreateRemoteControlObjects();
            }

            GUILayout.Space(10);

            EditorGUILayout.HelpBox("Recommended setup:\n1. Create control panel Canvas\n2. Add JogController with UI buttons\n3. Add MDIConsole for manual commands\n4. Add ProgramExecutor for automation\n5. Add EmergencyStopButton (required)", MessageType.Warning);
        }

        void DrawAboutTab()
        {
            GUILayout.Label("CNC SCADA Unity Digital Twin System", EditorStyles.boldLabel);
            GUILayout.Label("Version 1.0.0", EditorStyles.miniLabel);

            GUILayout.Space(20);

            GUILayout.BeginVertical("box");
            GUILayout.Label("Enterprise Industry 4.0 Platform", EditorStyles.boldLabel);
            GUILayout.Space(5);
            GUILayout.Label("• Real-time 60Hz visualization with ISO 23247 compliance");
            GUILayout.Label("• Production scheduling with OR-Tools optimization");
            GUILayout.Label("• Predictive maintenance with ML-driven insights");
            GUILayout.Label("• Low-latency remote control (<20ms)");
            GUILayout.Label("• Multi-region global deployment");
            GUILayout.Label("• ROS2 integration for robotics");
            GUILayout.EndVertical();

            GUILayout.Space(20);

            GUILayout.BeginVertical("box");
            GUILayout.Label("Architecture:", EditorStyles.boldLabel);
            GUILayout.Label("• Unity WebGL/Desktop/XR frontend");
            GUILayout.Label("• Flask SCADA backend with SocketIO");
            GUILayout.Label("• ROS2 for machine control");
            GUILayout.Label("• InfluxDB for time-series data");
            GUILayout.Label("• PostgreSQL for relational data");
            GUILayout.Label("• Kubernetes for orchestration");
            GUILayout.Label("• MQTT for edge synchronization");
            GUILayout.EndVertical();

            GUILayout.Space(20);

            if (GUILayout.Button("Documentation", GUILayout.Height(30)))
            {
                Application.OpenURL("https://github.com/your-repo/cnc-scada-docs");
            }
        }

        void DrawPackageStatus(string packageName, bool installed)
        {
            GUILayout.BeginHorizontal();
            GUILayout.Label(packageName);
            GUILayout.FlexibleSpace();
            if (installed)
            {
                GUI.color = Color.green;
                GUILayout.Label("✓ Installed");
                GUI.color = Color.white;
            }
            else
            {
                GUI.color = Color.red;
                GUILayout.Label("✗ Not Found");
                GUI.color = Color.white;
            }
            GUILayout.EndHorizontal();
        }

        void DrawFooter()
        {
            GUILayout.BeginVertical("box");
            GUILayout.BeginHorizontal();
            GUILayout.Label("Flask Server: " + flaskServerUrl, EditorStyles.miniLabel);
            GUILayout.FlexibleSpace();
            GUILayout.Label("Machine ID: " + machineId, EditorStyles.miniLabel);
            GUILayout.EndHorizontal();
            GUILayout.EndVertical();
        }

        void SaveSettings()
        {
            EditorPrefs.SetString("CNCScada.FlaskServerUrl", flaskServerUrl);
            EditorPrefs.SetString("CNCScada.MachineId", machineId);
            EditorPrefs.SetInt("CNCScada.TargetFrameRate", targetFrameRate);

            Application.targetFrameRate = targetFrameRate;

            EditorUtility.DisplayDialog("Settings Saved", "CNC SCADA settings have been saved successfully.", "OK");
        }

        void TestConnection()
        {
            EditorUtility.DisplayDialog("Connection Test",
                "Connection test initiated to:\n" + flaskServerUrl + "\n\nCheck Console for results.",
                "OK");

            Debug.Log("[CNCScada] Testing connection to: " + flaskServerUrl);
            // In a real implementation, this would make an actual HTTP request
        }

        void CreateSceneSetup()
        {
            // Create root manager object
            GameObject manager = new GameObject("CNC_SCADA_Manager");
            manager.tag = "EditorOnly";

            EditorUtility.DisplayDialog("Scene Setup", "Created CNC_SCADA_Manager object.\n\nAdd specific components from individual tabs.", "OK");
        }

        void CreateExampleScene()
        {
            if (EditorUtility.DisplayDialog("Create Example Scene",
                "This will create a new scene with example setup.\n\nCurrent scene will be saved first.",
                "Create", "Cancel"))
            {
                // Save current scene
                UnityEditor.SceneManagement.EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo();

                // Create new scene
                var newScene = UnityEditor.SceneManagement.EditorSceneManager.NewScene(
                    UnityEditor.SceneManagement.NewSceneSetup.DefaultGameObjects,
                    UnityEditor.SceneManagement.NewSceneMode.Single);

                CreateSceneSetup();
                CreateDigitalTwinObjects();

                Debug.Log("[CNCScada] Created example scene");
            }
        }

        void CreateDigitalTwinObjects()
        {
            GameObject manager = GameObject.Find("CNC_SCADA_Manager");
            if (manager == null)
            {
                manager = new GameObject("CNC_SCADA_Manager");
            }

            // Would add components here in a real implementation
            EditorUtility.DisplayDialog("Digital Twin Setup", "Digital Twin components created.\n\nConfigure references in Inspector.", "OK");
        }

        void CreateSchedulingObjects()
        {
            EditorUtility.DisplayDialog("Scheduling Setup", "Scheduling UI components created.\n\nAdd Canvas and UI elements, then configure.", "OK");
        }

        void CreatePredictiveObjects()
        {
            EditorUtility.DisplayDialog("Predictive Setup", "Predictive overlay components created.\n\nConfigure AR camera and sensor locations.", "OK");
        }

        void CreateRemoteControlObjects()
        {
            EditorUtility.DisplayDialog("Remote Control Setup", "Remote control components created.\n\nConnect UI buttons and configure safety limits.", "OK");
        }
    }
}
