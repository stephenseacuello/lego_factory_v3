using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using CNCScada.Core;
using CNCScada.Machines;
using CNCScada.Sensors;
using CNCScada.Automation;
using CNCScada.Connection;

namespace CNCScada.UI
{
    /// <summary>
    /// Real-time dashboard UI for the CNC SCADA Digital Twin.
    /// Displays machine status, sensor readings, and system health.
    /// </summary>
    public class DashboardUI : MonoBehaviour
    {
        [Header("UI References")]
        public Canvas mainCanvas;
        public RectTransform dashboardPanel;

        [Header("Machine Status Panels")]
        public MachineStatusPanel cncPanel;
        public MachineStatusPanel xArmPanel;
        public MachineStatusPanel niryoPanel;

        [Header("Sensor Displays")]
        public SensorDisplayPanel temperaturePanel;
        public SensorDisplayPanel vibrationPanel;
        public SensorDisplayPanel loadPanel;

        [Header("System Status")]
        public Text systemStatusText;
        public Text connectionStatusText;
        public Text uptimeText;
        public Image systemStatusIndicator;

        [Header("Control Buttons")]
        public Button emergencyStopButton;
        public Button startDemoButton;
        public Button connectButton;

        [Header("Settings")]
        public float updateRate = 10f; // Hz
        public bool autoCreate = true;

        [Header("Colors")]
        public Color normalColor = new Color(0.2f, 0.8f, 0.2f);
        public Color warningColor = new Color(1f, 0.8f, 0f);
        public Color criticalColor = new Color(1f, 0.2f, 0.2f);
        public Color offlineColor = new Color(0.5f, 0.5f, 0.5f);

        // Internal state
        private float lastUpdateTime;
        private bool isInitialized = false;

        // Singleton
        public static DashboardUI Instance { get; private set; }

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

        private void Start()
        {
            if (autoCreate)
            {
                StartCoroutine(CreateDashboard());
            }
        }

        private void Update()
        {
            if (!isInitialized) return;

            if (Time.time - lastUpdateTime >= 1f / updateRate)
            {
                UpdateDashboard();
                lastUpdateTime = Time.time;
            }
        }

        /// <summary>
        /// Create the dashboard UI programmatically
        /// </summary>
        private IEnumerator CreateDashboard()
        {
            yield return null; // Wait one frame

            // Create canvas if needed
            if (mainCanvas == null)
            {
                var canvasObj = new GameObject("DashboardCanvas");
                mainCanvas = canvasObj.AddComponent<Canvas>();
                mainCanvas.renderMode = RenderMode.ScreenSpaceOverlay;
                mainCanvas.sortingOrder = 100;
                canvasObj.AddComponent<CanvasScaler>().uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
                canvasObj.AddComponent<GraphicRaycaster>();
            }

            // Create main dashboard panel
            dashboardPanel = CreatePanel(mainCanvas.transform, "DashboardPanel",
                new Vector2(0, 1), new Vector2(0, 1), new Vector2(0, 1),
                new Vector2(20, -20), new Vector2(320, 500));

            // Add background
            var bg = dashboardPanel.gameObject.AddComponent<Image>();
            bg.color = new Color(0.08f, 0.08f, 0.1f, 0.95f);

            // Title
            CreateText(dashboardPanel, "Title", "CNC SCADA Dashboard",
                new Vector2(160, -20), 20, Color.white, TextAnchor.MiddleCenter);

            // System status section
            CreateText(dashboardPanel, "SystemLabel", "System Status",
                new Vector2(15, -50), 14, new Color(0.7f, 0.7f, 0.75f), TextAnchor.MiddleLeft);

            var statusPanel = CreatePanel(dashboardPanel, "StatusPanel",
                new Vector2(0, 1), new Vector2(1, 1), new Vector2(0.5f, 1),
                new Vector2(0, -70), new Vector2(-20, 60));
            statusPanel.gameObject.AddComponent<Image>().color = new Color(0.12f, 0.12f, 0.14f);

            systemStatusText = CreateText(statusPanel, "SystemStatus", "Initializing...",
                new Vector2(10, -15), 12, normalColor, TextAnchor.MiddleLeft).GetComponent<Text>();

            connectionStatusText = CreateText(statusPanel, "ConnectionStatus", "Connection: Offline",
                new Vector2(10, -32), 11, offlineColor, TextAnchor.MiddleLeft).GetComponent<Text>();

            uptimeText = CreateText(statusPanel, "Uptime", "Uptime: 0:00:00",
                new Vector2(10, -48), 11, new Color(0.6f, 0.6f, 0.65f), TextAnchor.MiddleLeft).GetComponent<Text>();

            // Machine status section
            float yOffset = -145;
            CreateText(dashboardPanel, "MachinesLabel", "Machines",
                new Vector2(15, yOffset), 14, new Color(0.7f, 0.7f, 0.75f), TextAnchor.MiddleLeft);

            yOffset -= 25;
            cncPanel = CreateMachineStatusPanel(dashboardPanel, "CNC", "Bantam CNC", yOffset);
            yOffset -= 55;
            xArmPanel = CreateMachineStatusPanel(dashboardPanel, "XArm", "xArm Lite 6", yOffset);
            yOffset -= 55;
            niryoPanel = CreateMachineStatusPanel(dashboardPanel, "Niryo", "Niryo Ned2", yOffset);

            // Sensors section
            yOffset -= 30;
            CreateText(dashboardPanel, "SensorsLabel", "Sensors",
                new Vector2(15, yOffset), 14, new Color(0.7f, 0.7f, 0.75f), TextAnchor.MiddleLeft);

            yOffset -= 25;
            temperaturePanel = CreateSensorPanel(dashboardPanel, "Temp", "Temperature", yOffset, "°C");
            yOffset -= 40;
            vibrationPanel = CreateSensorPanel(dashboardPanel, "Vib", "Vibration", yOffset, "mm/s");
            yOffset -= 40;
            loadPanel = CreateSensorPanel(dashboardPanel, "Load", "Axis Load", yOffset, "%");

            // Control buttons
            yOffset -= 45;
            emergencyStopButton = CreateButton(dashboardPanel, "EStopBtn", "E-STOP",
                new Vector2(85, yOffset), new Vector2(140, 35), criticalColor);
            emergencyStopButton.onClick.AddListener(OnEmergencyStop);

            startDemoButton = CreateButton(dashboardPanel, "DemoBtn", "Start Demo",
                new Vector2(235, yOffset), new Vector2(140, 35), new Color(0.2f, 0.5f, 0.8f));
            startDemoButton.onClick.AddListener(OnStartDemo);

            isInitialized = true;
            Debug.Log("[DashboardUI] Dashboard created");
        }

        private MachineStatusPanel CreateMachineStatusPanel(Transform parent, string id, string name, float yPos)
        {
            var panel = CreatePanel(parent as RectTransform, $"{id}Panel",
                new Vector2(0, 1), new Vector2(1, 1), new Vector2(0.5f, 1),
                new Vector2(0, yPos), new Vector2(-20, 50));
            panel.gameObject.AddComponent<Image>().color = new Color(0.12f, 0.12f, 0.14f);

            var statusPanel = new MachineStatusPanel();
            statusPanel.panel = panel;

            // Status indicator
            var indicatorObj = new GameObject("Indicator");
            indicatorObj.transform.SetParent(panel);
            var indicatorRect = indicatorObj.AddComponent<RectTransform>();
            indicatorRect.anchorMin = new Vector2(0, 0.5f);
            indicatorRect.anchorMax = new Vector2(0, 0.5f);
            indicatorRect.pivot = new Vector2(0, 0.5f);
            indicatorRect.anchoredPosition = new Vector2(10, 0);
            indicatorRect.sizeDelta = new Vector2(12, 12);
            statusPanel.statusIndicator = indicatorObj.AddComponent<Image>();
            statusPanel.statusIndicator.color = offlineColor;

            // Name
            statusPanel.nameText = CreateText(panel, "Name", name,
                new Vector2(30, -8), 13, Color.white, TextAnchor.MiddleLeft).GetComponent<Text>();

            // Status text
            statusPanel.statusText = CreateText(panel, "Status", "Offline",
                new Vector2(30, -28), 11, offlineColor, TextAnchor.MiddleLeft).GetComponent<Text>();

            // Position text
            statusPanel.positionText = CreateText(panel, "Position", "X:0.00 Y:0.00 Z:0.00",
                new Vector2(180, -28), 10, new Color(0.5f, 0.5f, 0.55f), TextAnchor.MiddleRight).GetComponent<Text>();

            return statusPanel;
        }

        private SensorDisplayPanel CreateSensorPanel(Transform parent, string id, string name, float yPos, string unit)
        {
            var panel = CreatePanel(parent as RectTransform, $"{id}Panel",
                new Vector2(0, 1), new Vector2(1, 1), new Vector2(0.5f, 1),
                new Vector2(0, yPos), new Vector2(-20, 35));
            panel.gameObject.AddComponent<Image>().color = new Color(0.12f, 0.12f, 0.14f);

            var sensorPanel = new SensorDisplayPanel();
            sensorPanel.panel = panel;
            sensorPanel.unit = unit;

            // Name
            sensorPanel.nameText = CreateText(panel, "Name", name,
                new Vector2(10, -10), 11, new Color(0.8f, 0.8f, 0.85f), TextAnchor.MiddleLeft).GetComponent<Text>();

            // Value
            sensorPanel.valueText = CreateText(panel, "Value", $"-- {unit}",
                new Vector2(-10, -10), 12, normalColor, TextAnchor.MiddleRight).GetComponent<Text>();

            // Progress bar background
            var barBg = CreatePanel(panel, "BarBg",
                new Vector2(0, 0), new Vector2(1, 0), new Vector2(0.5f, 0),
                new Vector2(0, 5), new Vector2(-20, 6));
            barBg.gameObject.AddComponent<Image>().color = new Color(0.2f, 0.2f, 0.22f);

            // Progress bar fill
            var barFill = CreatePanel(barBg, "BarFill",
                new Vector2(0, 0), new Vector2(0, 1), new Vector2(0, 0.5f),
                new Vector2(0, 0), new Vector2(0, 0));
            sensorPanel.progressBar = barFill.gameObject.AddComponent<Image>();
            sensorPanel.progressBar.color = normalColor;

            return sensorPanel;
        }

        private RectTransform CreatePanel(Transform parent, string name,
            Vector2 anchorMin, Vector2 anchorMax, Vector2 pivot,
            Vector2 anchoredPos, Vector2 sizeDelta)
        {
            var obj = new GameObject(name);
            obj.transform.SetParent(parent, false);
            var rect = obj.AddComponent<RectTransform>();
            rect.anchorMin = anchorMin;
            rect.anchorMax = anchorMax;
            rect.pivot = pivot;
            rect.anchoredPosition = anchoredPos;
            rect.sizeDelta = sizeDelta;
            return rect;
        }

        private GameObject CreateText(Transform parent, string name, string text,
            Vector2 position, int fontSize, Color color, TextAnchor alignment)
        {
            var obj = new GameObject(name);
            obj.transform.SetParent(parent, false);

            var rect = obj.AddComponent<RectTransform>();
            rect.anchorMin = new Vector2(0, 1);
            rect.anchorMax = new Vector2(1, 1);
            rect.pivot = new Vector2(0, 1);
            rect.anchoredPosition = new Vector2(position.x, position.y);
            rect.sizeDelta = new Vector2(-position.x * 2, 25);

            var textComp = obj.AddComponent<Text>();
            textComp.text = text;
            textComp.fontSize = fontSize;
            textComp.color = color;
            textComp.alignment = alignment;
            textComp.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");

            return obj;
        }

        private Button CreateButton(Transform parent, string name, string text,
            Vector2 position, Vector2 size, Color color)
        {
            var obj = new GameObject(name);
            obj.transform.SetParent(parent, false);

            var rect = obj.AddComponent<RectTransform>();
            rect.anchorMin = new Vector2(0, 1);
            rect.anchorMax = new Vector2(0, 1);
            rect.pivot = new Vector2(0.5f, 0.5f);
            rect.anchoredPosition = position;
            rect.sizeDelta = size;

            var image = obj.AddComponent<Image>();
            image.color = color;

            var button = obj.AddComponent<Button>();
            button.targetGraphic = image;

            var textObj = new GameObject("Text");
            textObj.transform.SetParent(obj.transform, false);
            var textRect = textObj.AddComponent<RectTransform>();
            textRect.anchorMin = Vector2.zero;
            textRect.anchorMax = Vector2.one;
            textRect.sizeDelta = Vector2.zero;

            var textComp = textObj.AddComponent<Text>();
            textComp.text = text;
            textComp.fontSize = 14;
            textComp.color = Color.white;
            textComp.alignment = TextAnchor.MiddleCenter;
            textComp.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            textComp.fontStyle = FontStyle.Bold;

            return button;
        }

        /// <summary>
        /// Update all dashboard elements
        /// </summary>
        private void UpdateDashboard()
        {
            UpdateSystemStatus();
            UpdateMachineStatus();
            UpdateSensorDisplays();
        }

        private void UpdateSystemStatus()
        {
            var manager = DigitalTwinManager.Instance;

            if (manager != null)
            {
                // System status
                string statusStr = manager.Status.ToString();
                systemStatusText.text = $"System: {statusStr}";
                systemStatusText.color = GetStatusColor(manager.Status);

                // Connection
                bool isConnected = FlaskSocketIOClient.Instance?.IsConnected ?? false;
                connectionStatusText.text = $"Connection: {(isConnected ? "Online" : "Offline")}";
                connectionStatusText.color = isConnected ? normalColor : offlineColor;

                // Uptime
                TimeSpan uptime = TimeSpan.FromSeconds(manager.Uptime);
                uptimeText.text = $"Uptime: {uptime:hh\\:mm\\:ss}";
            }
        }

        private void UpdateMachineStatus()
        {
            // Update CNC panel
            var cnc = DigitalTwinManager.Instance?.bantamCNC;
            if (cnc != null && cncPanel != null)
            {
                cncPanel.statusText.text = cnc.Status.ToString();
                cncPanel.statusIndicator.color = GetMachineStatusColor(cnc.Status);
                cncPanel.positionText.text = $"X:{cnc.Position.x:F1} Y:{cnc.Position.y:F1} Z:{cnc.Position.z:F1}";
            }

            // Update xArm panel
            var xArm = DigitalTwinManager.Instance?.xArmLite6;
            if (xArm != null && xArmPanel != null)
            {
                xArmPanel.statusText.text = xArm.CurrentStatus.ToString();
                xArmPanel.statusIndicator.color = GetRobotStatusColor(xArm.CurrentStatus);
                var joints = xArm.JointAngles;
                xArmPanel.positionText.text = $"J1:{joints[0]:F0}° J2:{joints[1]:F0}°";
            }

            // Update Niryo panel
            var niryo = DigitalTwinManager.Instance?.niryoNed2;
            if (niryo != null && niryoPanel != null)
            {
                niryoPanel.statusText.text = niryo.CurrentStatus.ToString();
                niryoPanel.statusIndicator.color = GetNiryoStatusColor(niryo.CurrentStatus);
                var joints = niryo.JointAngles;
                niryoPanel.positionText.text = $"J1:{joints[0]:F0}° J2:{joints[1]:F0}°";
            }
        }

        private void UpdateSensorDisplays()
        {
            var cnc = DigitalTwinManager.Instance?.bantamCNC;
            if (cnc == null) return;

            // Temperature
            if (temperaturePanel != null)
            {
                float temp = cnc.SpindleTemperature;
                temperaturePanel.valueText.text = $"{temp:F1} {temperaturePanel.unit}";
                float normalizedTemp = Mathf.InverseLerp(20, 80, temp);
                UpdateProgressBar(temperaturePanel, normalizedTemp, 0.7f, 0.85f);
            }

            // Vibration
            if (vibrationPanel != null)
            {
                float vib = cnc.Vibration.magnitude;
                vibrationPanel.valueText.text = $"{vib:F2} {vibrationPanel.unit}";
                float normalizedVib = Mathf.InverseLerp(0, 10, vib);
                UpdateProgressBar(vibrationPanel, normalizedVib, 0.4f, 0.7f);
            }

            // Load
            if (loadPanel != null)
            {
                float[] loads = cnc.AxisLoads;
                float avgLoad = (loads[0] + loads[1] + loads[2]) / 3f;
                loadPanel.valueText.text = $"{avgLoad:F1} {loadPanel.unit}";
                float normalizedLoad = Mathf.InverseLerp(0, 100, avgLoad);
                UpdateProgressBar(loadPanel, normalizedLoad, 0.6f, 0.8f);
            }
        }

        private void UpdateProgressBar(SensorDisplayPanel panel, float normalized, float warnThreshold, float critThreshold)
        {
            if (panel.progressBar == null) return;

            // Update bar width
            var rect = panel.progressBar.rectTransform;
            rect.anchorMax = new Vector2(Mathf.Clamp01(normalized), 1);

            // Update color
            Color barColor;
            if (normalized >= critThreshold)
            {
                barColor = criticalColor;
            }
            else if (normalized >= warnThreshold)
            {
                barColor = warningColor;
            }
            else
            {
                barColor = normalColor;
            }

            panel.progressBar.color = barColor;
            panel.valueText.color = barColor;
        }

        private Color GetStatusColor(SystemStatus status)
        {
            return status switch
            {
                SystemStatus.Running => normalColor,
                SystemStatus.Degraded => warningColor,
                SystemStatus.EmergencyStop => criticalColor,
                SystemStatus.Offline => offlineColor,
                _ => Color.white
            };
        }

        private Color GetMachineStatusColor(BantamCNCController.MachineStatus status)
        {
            return status switch
            {
                BantamCNCController.MachineStatus.Idle => normalColor,
                BantamCNCController.MachineStatus.Running => new Color(0.2f, 0.6f, 1f),
                BantamCNCController.MachineStatus.Alarm => criticalColor,
                _ => offlineColor
            };
        }

        private Color GetRobotStatusColor(XArmLite6Controller.RobotStatus status)
        {
            return status switch
            {
                XArmLite6Controller.RobotStatus.Idle => normalColor,
                XArmLite6Controller.RobotStatus.Moving => new Color(0.2f, 0.6f, 1f),
                XArmLite6Controller.RobotStatus.Error => criticalColor,
                XArmLite6Controller.RobotStatus.EmergencyStop => criticalColor,
                _ => offlineColor
            };
        }

        private Color GetNiryoStatusColor(NiryoNed2Controller.NedStatus status)
        {
            return status switch
            {
                NiryoNed2Controller.NedStatus.Idle => normalColor,
                NiryoNed2Controller.NedStatus.Moving => new Color(0.95f, 0.5f, 0.1f),
                NiryoNed2Controller.NedStatus.Error => criticalColor,
                _ => offlineColor
            };
        }

        // Button handlers
        private void OnEmergencyStop()
        {
            Debug.LogWarning("[DashboardUI] Emergency Stop pressed!");
            DigitalTwinManager.Instance?.EmergencyStopAll();
        }

        private void OnStartDemo()
        {
            Debug.Log("[DashboardUI] Starting demo sequence...");
            DigitalTwinManager.Instance?.StartSimulation();
        }
    }

    // =========================================================================
    // UI Panel Data Classes
    // =========================================================================

    [Serializable]
    public class MachineStatusPanel
    {
        public RectTransform panel;
        public Image statusIndicator;
        public Text nameText;
        public Text statusText;
        public Text positionText;
    }

    [Serializable]
    public class SensorDisplayPanel
    {
        public RectTransform panel;
        public Text nameText;
        public Text valueText;
        public Image progressBar;
        public string unit;
    }
}
