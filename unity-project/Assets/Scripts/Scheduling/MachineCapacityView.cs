using UnityEngine;
using UnityEngine.UI;
using System;
using System.Collections;
using System.Collections.Generic;
using System.Net.Http;
using Newtonsoft.Json;

namespace CNCScada.Scheduling
{
    /// <summary>
    /// Machine Capacity Visualization
    /// Displays real-time machine capacity, utilization, and bottlenecks
    /// Part of Phase 3: Production Scheduling
    /// </summary>
    public class MachineCapacityView : MonoBehaviour
    {
        [Header("Connection Settings")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private float updateInterval = 2f;

        [Header("UI References")]
        [SerializeField] private Transform machineListContainer;
        [SerializeField] private GameObject machineCapacityItemPrefab;
        [SerializeField] private Text summaryText;
        [SerializeField] private Button refreshButton;
        [SerializeField] private Toggle showBottlenecksOnlyToggle;

        [Header("Visualization Settings")]
        [SerializeField] private Color lowUtilizationColor = Color.green;
        [SerializeField] private Color mediumUtilizationColor = Color.yellow;
        [SerializeField] private Color highUtilizationColor = Color.red;
        [SerializeField] private Color bottleneckColor = new Color(1f, 0f, 0f, 0.8f);
        [SerializeField] private float utilizationThreshold = 0.85f;
        [SerializeField] private float bottleneckThreshold = 0.95f;

        [Header("Chart Settings")]
        [SerializeField] private bool enableCapacityChart = true;
        [SerializeField] private bool enableUtilizationTrend = true;
        [SerializeField] private int trendDataPoints = 24; // hours
        [SerializeField] private GameObject chartPrefab;

        // Data
        private HttpClient httpClient;
        private List<MachineCapacityItem> capacityItems = new List<MachineCapacityItem>();
        private Dictionary<string, List<float>> utilizationHistory = new Dictionary<string, List<float>>();

        // State
        private bool showBottlenecksOnly = false;
        private float lastUpdateTime = 0f;

        // Statistics
        private int totalMachines = 0;
        private int availableMachines = 0;
        private int bottleneckedMachines = 0;
        private float averageUtilization = 0f;
        private float totalCapacityHours = 0f;
        private float usedCapacityHours = 0f;

        // Events
        public event Action<string> OnBottleneckDetected;
        public event Action<CapacitySummary> OnCapacityUpdated;

        [Serializable]
        public class CapacityResponse
        {
            public bool success;
            public List<MachineCapacity> machines;
            public CapacitySummary summary;
            public string error;
        }

        [Serializable]
        public class MachineCapacity
        {
            public string machine_id;
            public string machine_name;
            public string status; // available, busy, maintenance, offline
            public float current_utilization_percent;
            public float capacity_hours;
            public float used_hours;
            public float available_hours;
            public bool is_bottleneck;
            public int pending_jobs;
            public int running_jobs;
            public List<string> capabilities;
            public DateTime next_available_time;
        }

        [Serializable]
        public class CapacitySummary
        {
            public int total_machines;
            public int available_machines;
            public int bottlenecked_machines;
            public float average_utilization_percent;
            public float total_capacity_hours;
            public float used_capacity_hours;
            public float available_capacity_hours;
        }

        public class MachineCapacityItem
        {
            public string machineId;
            public GameObject itemObject;
            public Text machineNameText;
            public Text statusText;
            public Slider utilizationSlider;
            public Text utilizationText;
            public Text capacityText;
            public Image statusIndicator;
            public GameObject bottleneckWarning;
            public MachineCapacity data;
        }

        void Start()
        {
            httpClient = new HttpClient();
            httpClient.Timeout = TimeSpan.FromSeconds(10);

            SetupUI();
            StartCoroutine(UpdateCapacityPeriodically());

            Debug.Log("[MachineCapacityView] Initialized");
        }

        void SetupUI()
        {
            if (refreshButton != null)
            {
                refreshButton.onClick.AddListener(OnRefreshButtonClicked);
            }

            if (showBottlenecksOnlyToggle != null)
            {
                showBottlenecksOnlyToggle.onValueChanged.AddListener(OnShowBottlenecksToggled);
            }
        }

        IEnumerator UpdateCapacityPeriodically()
        {
            while (true)
            {
                yield return new WaitForSeconds(updateInterval);
                FetchCapacityData();
            }
        }

        void OnRefreshButtonClicked()
        {
            FetchCapacityData();
        }

        void OnShowBottlenecksToggled(bool isOn)
        {
            showBottlenecksOnly = isOn;
            UpdateVisibleItems();
        }

        void FetchCapacityData()
        {
            StartCoroutine(FetchCapacityAsync());
        }

        IEnumerator FetchCapacityAsync()
        {
            string url = $"{flaskServerUrl}/api/v1/scheduler/capacity";

            using (var request = new HttpRequestMessage(HttpMethod.Get, url))
            {
                var task = httpClient.SendAsync(request);
                while (!task.IsCompleted) yield return null;

                if (task.IsFaulted || task.Result == null || !task.Result.IsSuccessStatusCode)
                {
                    Debug.LogError("[MachineCapacityView] Failed to fetch capacity data");
                    yield break;
                }

                var readTask = task.Result.Content.ReadAsStringAsync();
                while (!readTask.IsCompleted) yield return null;

                try
                {
                    CapacityResponse response = JsonConvert.DeserializeObject<CapacityResponse>(readTask.Result);

                    if (response.success)
                    {
                        UpdateCapacityDisplay(response);
                    }
                    else
                    {
                        Debug.LogError($"[MachineCapacityView] Error: {response.error}");
                    }
                }
                catch (Exception e)
                {
                    Debug.LogError($"[MachineCapacityView] Parse error: {e.Message}");
                }
            }

            lastUpdateTime = Time.time;
        }

        void UpdateCapacityDisplay(CapacityResponse response)
        {
            // Update summary statistics
            if (response.summary != null)
            {
                totalMachines = response.summary.total_machines;
                availableMachines = response.summary.available_machines;
                bottleneckedMachines = response.summary.bottlenecked_machines;
                averageUtilization = response.summary.average_utilization_percent;
                totalCapacityHours = response.summary.total_capacity_hours;
                usedCapacityHours = response.summary.used_capacity_hours;

                UpdateSummaryText();
                OnCapacityUpdated?.Invoke(response.summary);
            }

            // Clear existing items
            ClearCapacityItems();

            // Create capacity items for each machine
            foreach (var machine in response.machines)
            {
                CreateCapacityItem(machine);

                // Record utilization history
                RecordUtilizationHistory(machine.machine_id, machine.current_utilization_percent);

                // Check for bottlenecks
                if (machine.is_bottleneck)
                {
                    OnBottleneckDetected?.Invoke(machine.machine_id);
                }
            }

            UpdateVisibleItems();
        }

        void ClearCapacityItems()
        {
            foreach (var item in capacityItems)
            {
                if (item.itemObject != null)
                {
                    Destroy(item.itemObject);
                }
            }
            capacityItems.Clear();
        }

        void CreateCapacityItem(MachineCapacity machine)
        {
            if (machineListContainer == null || machineCapacityItemPrefab == null) return;

            GameObject itemObj = Instantiate(machineCapacityItemPrefab, machineListContainer);

            MachineCapacityItem item = new MachineCapacityItem
            {
                machineId = machine.machine_id,
                itemObject = itemObj,
                data = machine
            };

            // Find UI components
            item.machineNameText = FindChildComponent<Text>(itemObj, "MachineName");
            item.statusText = FindChildComponent<Text>(itemObj, "Status");
            item.utilizationSlider = FindChildComponent<Slider>(itemObj, "UtilizationSlider");
            item.utilizationText = FindChildComponent<Text>(itemObj, "UtilizationText");
            item.capacityText = FindChildComponent<Text>(itemObj, "CapacityText");
            item.statusIndicator = FindChildComponent<Image>(itemObj, "StatusIndicator");
            item.bottleneckWarning = FindChildGameObject(itemObj, "BottleneckWarning");

            // Update UI
            UpdateCapacityItem(item);

            capacityItems.Add(item);
        }

        void UpdateCapacityItem(MachineCapacityItem item)
        {
            MachineCapacity machine = item.data;

            // Machine name
            if (item.machineNameText != null)
            {
                item.machineNameText.text = machine.machine_name;
            }

            // Status
            if (item.statusText != null)
            {
                item.statusText.text = $"{machine.status.ToUpper()} - {machine.running_jobs}/{machine.pending_jobs} jobs";
            }

            // Utilization slider
            if (item.utilizationSlider != null)
            {
                item.utilizationSlider.value = machine.current_utilization_percent / 100f;

                // Color based on utilization
                ColorBlock colors = item.utilizationSlider.colors;
                colors.disabledColor = GetUtilizationColor(machine.current_utilization_percent / 100f);
                item.utilizationSlider.colors = colors;
            }

            // Utilization text
            if (item.utilizationText != null)
            {
                item.utilizationText.text = $"{machine.current_utilization_percent:F1}%";
            }

            // Capacity text
            if (item.capacityText != null)
            {
                item.capacityText.text = $"{machine.used_hours:F1}h / {machine.capacity_hours:F1}h ({machine.available_hours:F1}h available)";
            }

            // Status indicator
            if (item.statusIndicator != null)
            {
                item.statusIndicator.color = GetStatusColor(machine.status);
            }

            // Bottleneck warning
            if (item.bottleneckWarning != null)
            {
                item.bottleneckWarning.SetActive(machine.is_bottleneck);
            }
        }

        Color GetUtilizationColor(float utilization)
        {
            if (utilization >= bottleneckThreshold)
            {
                return bottleneckColor;
            }
            else if (utilization >= utilizationThreshold)
            {
                return highUtilizationColor;
            }
            else if (utilization >= 0.5f)
            {
                return mediumUtilizationColor;
            }
            else
            {
                return lowUtilizationColor;
            }
        }

        Color GetStatusColor(string status)
        {
            switch (status.ToLower())
            {
                case "available":
                    return Color.green;
                case "busy":
                    return Color.yellow;
                case "maintenance":
                    return Color.blue;
                case "offline":
                    return Color.red;
                default:
                    return Color.gray;
            }
        }

        void RecordUtilizationHistory(string machineId, float utilization)
        {
            if (!utilizationHistory.ContainsKey(machineId))
            {
                utilizationHistory[machineId] = new List<float>();
            }

            utilizationHistory[machineId].Add(utilization);

            // Keep only recent data points
            if (utilizationHistory[machineId].Count > trendDataPoints)
            {
                utilizationHistory[machineId].RemoveAt(0);
            }
        }

        void UpdateVisibleItems()
        {
            foreach (var item in capacityItems)
            {
                bool shouldShow = !showBottlenecksOnly || item.data.is_bottleneck;
                item.itemObject.SetActive(shouldShow);
            }
        }

        void UpdateSummaryText()
        {
            if (summaryText == null) return;

            string summary = $"<b>Capacity Overview</b>\n\n";
            summary += $"Total Machines: {totalMachines}\n";
            summary += $"Available: {availableMachines}\n";
            summary += $"Bottlenecks: {bottleneckedMachines}\n";
            summary += $"Avg Utilization: {averageUtilization:F1}%\n\n";
            summary += $"Capacity: {usedCapacityHours:F1}h / {totalCapacityHours:F1}h\n";
            summary += $"Available: {(totalCapacityHours - usedCapacityHours):F1}h";

            summaryText.text = summary;
        }

        T FindChildComponent<T>(GameObject parent, string childName) where T : Component
        {
            Transform child = parent.transform.Find(childName);
            if (child != null)
            {
                return child.GetComponent<T>();
            }
            return null;
        }

        GameObject FindChildGameObject(GameObject parent, string childName)
        {
            Transform child = parent.transform.Find(childName);
            return child != null ? child.gameObject : null;
        }

        /// <summary>
        /// Get utilization history for a specific machine
        /// </summary>
        public List<float> GetUtilizationHistory(string machineId)
        {
            if (utilizationHistory.ContainsKey(machineId))
            {
                return new List<float>(utilizationHistory[machineId]);
            }
            return new List<float>();
        }

        /// <summary>
        /// Get all bottlenecked machines
        /// </summary>
        public List<string> GetBottleneckedMachines()
        {
            List<string> bottlenecks = new List<string>();
            foreach (var item in capacityItems)
            {
                if (item.data.is_bottleneck)
                {
                    bottlenecks.Add(item.machineId);
                }
            }
            return bottlenecks;
        }

        public Dictionary<string, object> GetStatistics()
        {
            return new Dictionary<string, object>
            {
                {"total_machines", totalMachines},
                {"available_machines", availableMachines},
                {"bottlenecked_machines", bottleneckedMachines},
                {"average_utilization_percent", averageUtilization},
                {"total_capacity_hours", totalCapacityHours},
                {"used_capacity_hours", usedCapacityHours},
                {"available_capacity_hours", totalCapacityHours - usedCapacityHours},
                {"capacity_utilization_percent", totalCapacityHours > 0 ? (usedCapacityHours / totalCapacityHours) * 100f : 0f},
                {"last_update", lastUpdateTime}
            };
        }

        void OnDestroy()
        {
            if (httpClient != null) httpClient.Dispose();
        }
    }
}
