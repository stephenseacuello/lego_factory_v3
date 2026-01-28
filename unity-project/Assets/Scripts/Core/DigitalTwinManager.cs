using System;
using System.Collections;
using UnityEngine;
using CNCScada.Machines;
using CNCScada.Sensors;
using CNCScada.MTConnect;
using CNCScada.Automation;
using CNCScada.Connection;
using CNCScada.Alarms;
using CNCScada.Analytics;
using CNCScada.Vision;
using CNCScada.OPCUA;
using CNCScada.Camera;
using CNCScada.Toolpath;
using CNCScada.Predictive;
using CNCScada.Energy;
using CNCScada.WorkOrder;
using CNCScada.Safety;
using CNCScada.Notifications;
using CNCScada.Replay;
using CNCScada.Inventory;
using CNCScada.Recipes;
using CNC_SCADA.DigitalTwin.Shifts;
using CNC_SCADA.DigitalTwin.Audit;
using CNC_SCADA.DigitalTwin.RemoteControl;
using CNC_SCADA.DigitalTwin.ROS2;
using CNC_SCADA.DigitalTwin.Sensors;
using CNC_SCADA.DigitalTwin.Kinematics;
using CNC_SCADA.DigitalTwin.Sync;
using CNC_SCADA.DigitalTwin.MTConnect;
using CNCScada.URDF;
using CNC_SCADA.DigitalTwin.URDF;
using CNC_SCADA.DigitalTwin.Conveyor;
using CNC_SCADA.DigitalTwin.PLC;
using CNCDigitalTwin.Historian;
using CNCDigitalTwin.HMI;

namespace CNCScada.Core
{
    /// <summary>
    /// Central manager for the CNC SCADA Digital Twin system.
    /// Coordinates all subsystems: machines, sensors, MTConnect, automation, and visualization.
    /// </summary>
    public class DigitalTwinManager : MonoBehaviour
    {
        [Header("System Configuration")]
        public string systemId = "cnc-scada-dt-001";
        public string systemName = "CNC SCADA Digital Twin";
        public SystemMode mode = SystemMode.Simulation;

        [Header("Connection Settings")]
        public string flaskServerUrl = "http://localhost:5001";
        public string mtConnectAgentUrl = "http://localhost:5000";
        public bool autoConnect = true;

        [Header("Subsystem References")]
        public SensorSystem sensorSystem;
        public SensorVisualization sensorVisualization;
        public MTConnectClient mtConnectClient;
        public AutomationController automationController;
        public DataLogger dataLogger;
        public FlaskSocketIOClient flaskClient;

        [Header("Extended Subsystems")]
        public AlarmSystem alarmSystem;
        public ProductionAnalytics productionAnalytics;
        public VisionInspectionSystem visionSystem;
        public OPCUAClient opcuaClient;
        public OrbitCameraController cameraController;
        public ToolpathVisualizer toolpathVisualizer;
        public PredictiveMaintenanceSystem predictiveMaintenance;

        [Header("Advanced Subsystems")]
        public EnergyMonitoringSystem energyMonitoring;
        public WorkOrderManager workOrderManager;
        public SafetyZoneMonitor safetyMonitor;
        public NotificationService notificationService;
        public DataReplaySystem replaySystem;

        [Header("Enterprise Subsystems")]
        public InventoryManager inventoryManager;
        public RecipeManager recipeManager;
        public ShiftManagementSystem shiftManagement;
        public AuditTrailSystem auditTrail;
        public RemoteControlPanel remoteControl;

        [Header("ROS2 & Robotics Subsystems")]
        public ROS2UnityBridge ros2Bridge;
        public AdvancedSensorSimulation advancedSensors;
        public RobotKinematicsSystem robotKinematics;
        public DigitalTwinSyncService twinSync;
        public MTConnectEnhanced mtConnectEnhanced;

        [Header("Factory Automation Subsystems")]
        public URDFRobotLoader urdfLoader;
        public ConveyorSystem conveyorSystem;
        public PLCIntegration plcIntegration;
        public DataHistorian dataHistorian;
        public HMIDashboard hmiDashboard;

        [Header("Machine References")]
        public BantamCNCController bantamCNC;
        public XArmLite6Controller xArmLite6;
        public NiryoNed2Controller niryoNed2;

        [Header("Status")]
        [SerializeField] private SystemStatus status = SystemStatus.Initializing;
        [SerializeField] private int connectedSubsystems = 0;
        [SerializeField] private float uptime = 0f;

        // Events
        public event Action<SystemStatus> OnStatusChanged;
        public event Action<string> OnSystemMessage;
        public event Action OnSystemReady;

        // Singleton
        public static DigitalTwinManager Instance { get; private set; }

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
                return;
            }
        }

        private void Start()
        {
            StartCoroutine(InitializeSystem());
        }

        private void Update()
        {
            uptime += Time.deltaTime;
        }

        /// <summary>
        /// Initialize all subsystems in the correct order
        /// </summary>
        private IEnumerator InitializeSystem()
        {
            SetStatus(SystemStatus.Initializing);
            LogMessage($"[{systemName}] Starting initialization...");

            // Step 1: Initialize core subsystems
            yield return InitializeSubsystems();

            // Step 2: Find or create machines
            yield return InitializeMachines();

            // Step 3: Connect to external systems
            if (autoConnect)
            {
                yield return ConnectToExternalSystems();
            }

            // Step 4: Setup visualization
            yield return SetupVisualization();

            // Step 5: Final status check
            if (connectedSubsystems >= 3)
            {
                SetStatus(SystemStatus.Running);
                LogMessage($"[{systemName}] System ready with {connectedSubsystems} subsystems active");
                OnSystemReady?.Invoke();
            }
            else
            {
                SetStatus(SystemStatus.Degraded);
                LogMessage($"[{systemName}] Running in degraded mode ({connectedSubsystems} subsystems)");
            }
        }

        private IEnumerator InitializeSubsystems()
        {
            LogMessage("Initializing subsystems...");

            // Sensor System
            if (sensorSystem == null)
            {
                var sensorObj = new GameObject("SensorSystem");
                sensorObj.transform.SetParent(transform);
                sensorSystem = sensorObj.AddComponent<SensorSystem>();
                connectedSubsystems++;
            }
            yield return null;

            // Sensor Visualization
            if (sensorVisualization == null)
            {
                var vizObj = new GameObject("SensorVisualization");
                vizObj.transform.SetParent(transform);
                sensorVisualization = vizObj.AddComponent<SensorVisualization>();
                connectedSubsystems++;
            }
            yield return null;

            // Data Logger
            if (dataLogger == null)
            {
                var loggerObj = new GameObject("DataLogger");
                loggerObj.transform.SetParent(transform);
                dataLogger = loggerObj.AddComponent<DataLogger>();
                connectedSubsystems++;
            }
            yield return null;

            // Automation Controller
            if (automationController == null)
            {
                var autoObj = new GameObject("AutomationController");
                autoObj.transform.SetParent(transform);
                automationController = autoObj.AddComponent<AutomationController>();
            }
            yield return null;

            // Alarm System
            if (alarmSystem == null)
            {
                var alarmObj = new GameObject("AlarmSystem");
                alarmObj.transform.SetParent(transform);
                alarmSystem = alarmObj.AddComponent<AlarmSystem>();
                connectedSubsystems++;
            }
            yield return null;

            // Production Analytics
            if (productionAnalytics == null)
            {
                var analyticsObj = new GameObject("ProductionAnalytics");
                analyticsObj.transform.SetParent(transform);
                productionAnalytics = analyticsObj.AddComponent<ProductionAnalytics>();
                connectedSubsystems++;
            }
            yield return null;

            // Vision Inspection System
            if (visionSystem == null)
            {
                var visionObj = new GameObject("VisionInspectionSystem");
                visionObj.transform.SetParent(transform);
                visionSystem = visionObj.AddComponent<VisionInspectionSystem>();
            }
            yield return null;

            // Predictive Maintenance
            if (predictiveMaintenance == null)
            {
                var predictiveObj = new GameObject("PredictiveMaintenance");
                predictiveObj.transform.SetParent(transform);
                predictiveMaintenance = predictiveObj.AddComponent<PredictiveMaintenanceSystem>();
                connectedSubsystems++;
            }
            yield return null;

            // Toolpath Visualizer
            if (toolpathVisualizer == null)
            {
                var toolpathObj = new GameObject("ToolpathVisualizer");
                toolpathObj.transform.SetParent(transform);
                toolpathVisualizer = toolpathObj.AddComponent<ToolpathVisualizer>();
            }
            yield return null;

            // Energy Monitoring System
            if (energyMonitoring == null)
            {
                var energyObj = new GameObject("EnergyMonitoring");
                energyObj.transform.SetParent(transform);
                energyMonitoring = energyObj.AddComponent<EnergyMonitoringSystem>();
                connectedSubsystems++;
            }
            yield return null;

            // Work Order Manager
            if (workOrderManager == null)
            {
                var workOrderObj = new GameObject("WorkOrderManager");
                workOrderObj.transform.SetParent(transform);
                workOrderManager = workOrderObj.AddComponent<WorkOrderManager>();
                connectedSubsystems++;
            }
            yield return null;

            // Safety Zone Monitor
            if (safetyMonitor == null)
            {
                var safetyObj = new GameObject("SafetyZoneMonitor");
                safetyObj.transform.SetParent(transform);
                safetyMonitor = safetyObj.AddComponent<SafetyZoneMonitor>();
                connectedSubsystems++;
            }
            yield return null;

            // Notification Service
            if (notificationService == null)
            {
                var notifyObj = new GameObject("NotificationService");
                notifyObj.transform.SetParent(transform);
                notificationService = notifyObj.AddComponent<NotificationService>();
                connectedSubsystems++;
            }
            yield return null;

            // Data Replay System
            if (replaySystem == null)
            {
                var replayObj = new GameObject("DataReplaySystem");
                replayObj.transform.SetParent(transform);
                replaySystem = replayObj.AddComponent<DataReplaySystem>();
            }
            yield return null;

            // Inventory Manager
            if (inventoryManager == null)
            {
                var invObj = new GameObject("InventoryManager");
                invObj.transform.SetParent(transform);
                inventoryManager = invObj.AddComponent<InventoryManager>();
                connectedSubsystems++;
            }
            yield return null;

            // Recipe Manager
            if (recipeManager == null)
            {
                var recipeObj = new GameObject("RecipeManager");
                recipeObj.transform.SetParent(transform);
                recipeManager = recipeObj.AddComponent<RecipeManager>();
                connectedSubsystems++;
            }
            yield return null;

            // Shift Management System
            if (shiftManagement == null)
            {
                var shiftObj = new GameObject("ShiftManagement");
                shiftObj.transform.SetParent(transform);
                shiftManagement = shiftObj.AddComponent<ShiftManagementSystem>();
                connectedSubsystems++;
            }
            yield return null;

            // Audit Trail System
            if (auditTrail == null)
            {
                var auditObj = new GameObject("AuditTrail");
                auditObj.transform.SetParent(transform);
                auditTrail = auditObj.AddComponent<AuditTrailSystem>();
                connectedSubsystems++;
            }
            yield return null;

            // Remote Control Panel
            if (remoteControl == null)
            {
                var controlObj = new GameObject("RemoteControlPanel");
                controlObj.transform.SetParent(transform);
                remoteControl = controlObj.AddComponent<RemoteControlPanel>();
                connectedSubsystems++;
            }
            yield return null;

            // ROS2 Unity Bridge
            if (ros2Bridge == null)
            {
                var ros2Obj = new GameObject("ROS2UnityBridge");
                ros2Obj.transform.SetParent(transform);
                ros2Bridge = ros2Obj.AddComponent<ROS2UnityBridge>();
                connectedSubsystems++;
            }
            yield return null;

            // Advanced Sensor Simulation
            if (advancedSensors == null)
            {
                var sensorObj = new GameObject("AdvancedSensorSimulation");
                sensorObj.transform.SetParent(transform);
                advancedSensors = sensorObj.AddComponent<AdvancedSensorSimulation>();
                connectedSubsystems++;
            }
            yield return null;

            // Robot Kinematics System
            if (robotKinematics == null)
            {
                var kinObj = new GameObject("RobotKinematics");
                kinObj.transform.SetParent(transform);
                robotKinematics = kinObj.AddComponent<RobotKinematicsSystem>();
                connectedSubsystems++;
            }
            yield return null;

            // Digital Twin Sync Service
            if (twinSync == null)
            {
                var syncObj = new GameObject("DigitalTwinSync");
                syncObj.transform.SetParent(transform);
                twinSync = syncObj.AddComponent<DigitalTwinSyncService>();
                connectedSubsystems++;
            }
            yield return null;

            // Enhanced MTConnect Client
            if (mtConnectEnhanced == null)
            {
                var mtcObj = new GameObject("MTConnectEnhanced");
                mtcObj.transform.SetParent(transform);
                mtConnectEnhanced = mtcObj.AddComponent<MTConnectEnhanced>();
                connectedSubsystems++;
            }
            yield return null;

            // URDF Robot Loader
            if (urdfLoader == null)
            {
                var urdfObj = new GameObject("URDFRobotLoader");
                urdfObj.transform.SetParent(transform);
                urdfLoader = urdfObj.AddComponent<URDFRobotLoader>();
                connectedSubsystems++;
            }
            yield return null;

            // Conveyor System
            if (conveyorSystem == null)
            {
                var conveyorObj = new GameObject("ConveyorSystem");
                conveyorObj.transform.SetParent(transform);
                conveyorSystem = conveyorObj.AddComponent<ConveyorSystem>();
                connectedSubsystems++;
            }
            yield return null;

            // PLC Integration
            if (plcIntegration == null)
            {
                var plcObj = new GameObject("PLCIntegration");
                plcObj.transform.SetParent(transform);
                plcIntegration = plcObj.AddComponent<PLCIntegration>();
                connectedSubsystems++;
            }
            yield return null;

            // Data Historian
            if (dataHistorian == null)
            {
                var historianObj = new GameObject("DataHistorian");
                historianObj.transform.SetParent(transform);
                dataHistorian = historianObj.AddComponent<DataHistorian>();
                connectedSubsystems++;
            }
            yield return null;

            // HMI Dashboard
            if (hmiDashboard == null)
            {
                var hmiObj = new GameObject("HMIDashboard");
                hmiObj.transform.SetParent(transform);
                hmiDashboard = hmiObj.AddComponent<HMIDashboard>();
                connectedSubsystems++;
            }
            yield return null;

            LogMessage($"Subsystems initialized: {connectedSubsystems}");
        }

        private IEnumerator InitializeMachines()
        {
            LogMessage("Initializing machines...");

            // Find existing machines or create them
            if (bantamCNC == null)
            {
                bantamCNC = FindObjectOfType<BantamCNCController>();
            }

            if (xArmLite6 == null)
            {
                xArmLite6 = FindObjectOfType<XArmLite6Controller>();
            }

            if (niryoNed2 == null)
            {
                niryoNed2 = FindObjectOfType<NiryoNed2Controller>();
            }

            // Link machines to automation controller
            if (automationController != null)
            {
                automationController.bantamCNC = bantamCNC;
                automationController.xArmLite6 = xArmLite6;
                automationController.niryoNed2 = niryoNed2;
            }

            int machineCount = 0;
            if (bantamCNC != null) machineCount++;
            if (xArmLite6 != null) machineCount++;
            if (niryoNed2 != null) machineCount++;

            LogMessage($"Machines found: {machineCount}");
            yield return null;
        }

        private IEnumerator ConnectToExternalSystems()
        {
            LogMessage("Connecting to external systems...");

            // Flask SocketIO
            if (flaskClient == null)
            {
                flaskClient = FindObjectOfType<FlaskSocketIOClient>();
            }

            if (flaskClient != null)
            {
                flaskClient.Connect();
                yield return new WaitForSeconds(1f);

                if (flaskClient.IsConnected)
                {
                    connectedSubsystems++;
                    LogMessage("Connected to Flask backend");
                }
            }

            // MTConnect
            if (mode == SystemMode.Live || mode == SystemMode.Hybrid)
            {
                if (mtConnectClient == null)
                {
                    var mtcObj = new GameObject("MTConnectClient");
                    mtcObj.transform.SetParent(transform);
                    mtConnectClient = mtcObj.AddComponent<MTConnectClient>();
                }

                mtConnectClient.Connect();
                yield return new WaitForSeconds(2f);

                if (mtConnectClient.IsConnected)
                {
                    connectedSubsystems++;
                    LogMessage("Connected to MTConnect agent");
                }
            }

            // OPC UA Client
            if (mode == SystemMode.Live || mode == SystemMode.Hybrid)
            {
                if (opcuaClient == null)
                {
                    var opcuaObj = new GameObject("OPCUAClient");
                    opcuaObj.transform.SetParent(transform);
                    opcuaClient = opcuaObj.AddComponent<OPCUAClient>();
                }

                opcuaClient.Connect();
                yield return new WaitForSeconds(2f);

                if (opcuaClient.IsConnected)
                {
                    connectedSubsystems++;
                    LogMessage("Connected to OPC UA server");
                }
            }

            yield return null;
        }

        private IEnumerator SetupVisualization()
        {
            LogMessage("Setting up visualization...");

            if (sensorVisualization != null && bantamCNC != null)
            {
                sensorVisualization.SetupMachineVisualization(bantamCNC.gameObject, bantamCNC.machineId);
            }

            // Setup orbit camera
            if (cameraController == null)
            {
                var mainCamera = UnityEngine.Camera.main;
                if (mainCamera != null)
                {
                    cameraController = mainCamera.gameObject.AddComponent<OrbitCameraController>();

                    // Find factory cell as default target
                    var factoryCell = GameObject.Find("FactoryCell");
                    if (factoryCell != null)
                    {
                        cameraController.SetTarget(factoryCell.transform, false);
                    }
                }
            }

            // Setup toolpath visualizer target
            if (toolpathVisualizer != null && bantamCNC != null)
            {
                toolpathVisualizer.workpieceOrigin = bantamCNC.transform;
            }

            yield return null;
        }

        // =========================================================================
        // Public API
        // =========================================================================

        /// <summary>
        /// Start simulation mode with mock data
        /// </summary>
        public void StartSimulation()
        {
            mode = SystemMode.Simulation;
            LogMessage("Simulation mode started");

            // Start demo sequences
            if (automationController != null)
            {
                StartCoroutine(DemoSequence());
            }
        }

        /// <summary>
        /// Connect to live machine data
        /// </summary>
        public void ConnectToLive()
        {
            mode = SystemMode.Live;
            LogMessage("Switching to live mode...");

            if (mtConnectClient != null)
            {
                mtConnectClient.Connect();
            }

            if (flaskClient != null)
            {
                flaskClient.Connect();
            }
        }

        /// <summary>
        /// Emergency stop all machines
        /// </summary>
        public void EmergencyStopAll()
        {
            SetStatus(SystemStatus.EmergencyStop);
            LogMessage("EMERGENCY STOP ACTIVATED");

            automationController?.EmergencyStop();
            flaskClient?.EmergencyStop();

            bantamCNC?.SetSpindleSpeed(0);
            xArmLite6?.MoveToHome();
            niryoNed2?.MoveToHome();
        }

        /// <summary>
        /// Reset emergency stop and resume
        /// </summary>
        public void ResetEmergencyStop()
        {
            automationController?.ResetEmergencyStop();
            SetStatus(SystemStatus.Running);
            LogMessage("Emergency stop reset");
        }

        /// <summary>
        /// Get system health report
        /// </summary>
        public SystemHealthReport GetHealthReport()
        {
            return new SystemHealthReport
            {
                systemId = systemId,
                status = status,
                uptime = uptime,
                connectedSubsystems = connectedSubsystems,
                sensorSystemActive = sensorSystem != null,
                mtConnectActive = mtConnectClient != null && mtConnectClient.IsConnected,
                flaskConnected = flaskClient != null && flaskClient.IsConnected,
                automationActive = automationController != null,
                alarmSystemActive = alarmSystem != null,
                analyticsActive = productionAnalytics != null,
                visionSystemActive = visionSystem != null && visionSystem.IsConnected,
                opcuaActive = opcuaClient != null && opcuaClient.IsConnected,
                predictiveMaintenanceActive = predictiveMaintenance != null,
                energyMonitoringActive = energyMonitoring != null,
                workOrderActive = workOrderManager != null,
                safetyMonitorActive = safetyMonitor != null,
                notificationActive = notificationService != null,
                replaySystemActive = replaySystem != null,
                inventoryActive = inventoryManager != null,
                recipeManagerActive = recipeManager != null,
                shiftManagementActive = shiftManagement != null,
                auditTrailActive = auditTrail != null,
                remoteControlActive = remoteControl != null,
                machinesOnline = GetOnlineMachineCount(),
                activeAlarms = alarmSystem != null ? alarmSystem.ActiveAlarmCount : 0,
                currentOEE = productionAnalytics != null ? productionAnalytics.OEE : 0f,
                currentPowerWatts = energyMonitoring != null ? energyMonitoring.TotalPowerWatts : 0f,
                activeWorkOrders = workOrderManager != null ? workOrderManager.OrdersInProgress : 0,
                safetyViolations = safetyMonitor != null ? safetyMonitor.ActiveViolationCount : 0,
                totalInventoryItems = inventoryManager != null ? inventoryManager.TotalItemCount : 0,
                activeRecipes = recipeManager != null ? recipeManager.ApprovedRecipes : 0,
                currentShift = shiftManagement?.CurrentShift?.Name ?? "None",
                auditRecordCount = auditTrail != null ? auditTrail.TotalRecords : 0,
                remoteControlConnected = remoteControl != null && remoteControl.IsConnected,
                ros2BridgeConnected = ros2Bridge != null && ros2Bridge.IsConnected,
                advancedSensorsActive = advancedSensors != null,
                kinematicsActive = robotKinematics != null,
                twinSyncActive = twinSync != null && twinSync.Status == SyncStatus.Synchronized,
                mtConnectEnhancedActive = mtConnectEnhanced != null && mtConnectEnhanced.IsConnected,
                syncLatencyMs = twinSync != null ? twinSync.CurrentLatency : 0f,
                trackedEntities = twinSync != null ? twinSync.TrackedEntityCount : 0,
                // Factory Automation
                urdfLoaderActive = urdfLoader != null,
                conveyorSystemActive = conveyorSystem != null,
                plcIntegrationActive = plcIntegration != null,
                dataHistorianActive = dataHistorian != null,
                hmiDashboardActive = hmiDashboard != null,
                conveyorSegments = conveyorSystem != null ? conveyorSystem.SegmentCount : 0,
                plcConnectionCount = plcIntegration != null ? plcIntegration.ConnectionCount : 0,
                historianPointsWritten = dataHistorian != null ? dataHistorian.GetStatistics().TotalPointsWritten : 0,
                activeHmiAlarms = hmiDashboard != null ? hmiDashboard.GetStatistics().ActiveAlarmCount : 0,
                timestamp = DateTime.UtcNow
            };
        }

        private int GetOnlineMachineCount()
        {
            int count = 0;
            if (bantamCNC != null) count++;
            if (xArmLite6 != null) count++;
            if (niryoNed2 != null) count++;
            return count;
        }

        /// <summary>
        /// Run a demo sequence
        /// </summary>
        private IEnumerator DemoSequence()
        {
            yield return new WaitForSeconds(2f);

            LogMessage("Starting demo sequence...");

            // Demo CNC movement
            if (bantamCNC != null)
            {
                bantamCNC.SetTargetPosition(70, 50, 76);
                bantamCNC.SetSpindleSpeed(5000);
                yield return new WaitForSeconds(2f);

                bantamCNC.SetTargetPosition(20, 80, 100);
                yield return new WaitForSeconds(2f);

                bantamCNC.SetTargetPosition(120, 30, 50);
                yield return new WaitForSeconds(2f);
            }

            // Demo robot movement
            if (xArmLite6 != null)
            {
                xArmLite6.SetJointAngles(new float[] { 30, -20, -40, 0, 60, 0 });
                yield return new WaitForSeconds(2f);

                xArmLite6.SetGripperPosition(1f); // Open
                yield return new WaitForSeconds(1f);

                xArmLite6.SetGripperPosition(0f); // Close
                yield return new WaitForSeconds(1f);
            }

            if (niryoNed2 != null)
            {
                niryoNed2.SetJointAngles(new float[] { -45, 20, 30, 0, -60, 0 });
                yield return new WaitForSeconds(2f);
            }

            LogMessage("Demo sequence complete");
        }

        // =========================================================================
        // Internal Methods
        // =========================================================================

        private void SetStatus(SystemStatus newStatus)
        {
            if (status != newStatus)
            {
                status = newStatus;
                OnStatusChanged?.Invoke(status);
            }
        }

        private void LogMessage(string message)
        {
            Debug.Log($"[DigitalTwin] {message}");
            OnSystemMessage?.Invoke(message);

            if (dataLogger != null)
            {
                dataLogger.LogEvent("System", message);
            }
        }

        // Properties
        public SystemStatus Status => status;
        public float Uptime => uptime;
        public int ConnectedSubsystems => connectedSubsystems;
        public SystemMode Mode => mode;
    }

    // =========================================================================
    // Enums and Data Classes
    // =========================================================================

    public enum SystemMode
    {
        Simulation,  // All data is simulated
        Live,        // Connected to real machines
        Hybrid,      // Mix of simulated and real
        Playback     // Replaying recorded data
    }

    public enum SystemStatus
    {
        Initializing,
        Running,
        Degraded,
        Maintenance,
        EmergencyStop,
        Offline
    }

    [Serializable]
    public class SystemHealthReport
    {
        public string systemId;
        public SystemStatus status;
        public float uptime;
        public int connectedSubsystems;
        public bool sensorSystemActive;
        public bool mtConnectActive;
        public bool flaskConnected;
        public bool automationActive;
        public bool alarmSystemActive;
        public bool analyticsActive;
        public bool visionSystemActive;
        public bool opcuaActive;
        public bool predictiveMaintenanceActive;
        public bool energyMonitoringActive;
        public bool workOrderActive;
        public bool safetyMonitorActive;
        public bool notificationActive;
        public bool replaySystemActive;
        public bool inventoryActive;
        public bool recipeManagerActive;
        public bool shiftManagementActive;
        public bool auditTrailActive;
        public bool remoteControlActive;
        public int machinesOnline;
        public int activeAlarms;
        public float currentOEE;
        public float currentPowerWatts;
        public int activeWorkOrders;
        public int safetyViolations;
        public int totalInventoryItems;
        public int activeRecipes;
        public string currentShift;
        public int auditRecordCount;
        public bool remoteControlConnected;
        public bool ros2BridgeConnected;
        public bool advancedSensorsActive;
        public bool kinematicsActive;
        public bool twinSyncActive;
        public bool mtConnectEnhancedActive;
        public float syncLatencyMs;
        public int trackedEntities;
        // Factory Automation
        public bool urdfLoaderActive;
        public bool conveyorSystemActive;
        public bool plcIntegrationActive;
        public bool dataHistorianActive;
        public bool hmiDashboardActive;
        public int conveyorSegments;
        public int plcConnectionCount;
        public long historianPointsWritten;
        public int activeHmiAlarms;
        public DateTime timestamp;
    }
}
