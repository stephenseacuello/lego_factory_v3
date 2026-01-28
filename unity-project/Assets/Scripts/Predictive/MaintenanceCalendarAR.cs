using UnityEngine;
using UnityEngine.UI;
using System;
using System.Collections;
using System.Collections.Generic;
using System.Net.Http;
using Newtonsoft.Json;

namespace CNCScada.Predictive
{
    /// <summary>
    /// AR Maintenance Calendar Overlay
    /// Displays predicted maintenance events in AR with 3D markers
    /// Part of Phase 4: Predictive Maintenance
    /// </summary>
    public class MaintenanceCalendarAR : MonoBehaviour
    {
        [Header("Connection Settings")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private float updateInterval = 30f;

        [Header("AR Settings")]
        [SerializeField] private Camera arCamera;
        [SerializeField] private Transform machineTransform;
        [SerializeField] private float markerDistance = 0.5f;
        [SerializeField] private float markerScale = 0.1f;

        [Header("Marker Prefabs")]
        [SerializeField] private GameObject urgentMaintenancePrefab;
        [SerializeField] private GameObject scheduledMaintenancePrefab;
        [SerializeField] private GameObject preventiveMaintenancePrefab;
        [SerializeField] private GameObject predictionMarkerPrefab;

        [Header("Visual Settings")]
        [SerializeField] private Color urgentColor = Color.red;
        [SerializeField] private Color scheduledColor = Color.yellow;
        [SerializeField] private Color preventiveColor = Color.green;
        [SerializeField] private Color predictionColor = Color.cyan;
        [SerializeField] private bool showLabels = true;
        [SerializeField] private bool showTimeline = true;
        [SerializeField] private bool enableAnimations = true;

        [Header("Prediction Settings")]
        [SerializeField] private int predictionHorizonDays = 30;
        [SerializeField] private float confidenceThreshold = 0.7f;
        [SerializeField] private bool showLowConfidence = false;

        [Header("UI References")]
        [SerializeField] private Canvas overlayCanvas;
        [SerializeField] private Text summaryText;
        [SerializeField] private ScrollRect eventListScrollRect;
        [SerializeField] private GameObject eventItemPrefab;

        // Data
        private HttpClient httpClient;
        private List<MaintenanceEvent> maintenanceEvents = new List<MaintenanceEvent>();
        private List<GameObject> activeMarkers = new List<GameObject>();
        private Dictionary<string, GameObject> markerCache = new Dictionary<string, GameObject>();

        // State
        private bool arModeEnabled = false;
        private float lastUpdateTime = 0f;

        // Statistics
        private int totalEvents = 0;
        private int urgentEvents = 0;
        private int scheduledEvents = 0;
        private int predictedEvents = 0;

        // Events
        public event Action<MaintenanceEvent> OnMaintenanceEventSelected;
        public event Action<MaintenanceEvent> OnUrgentMaintenanceDetected;

        [Serializable]
        public class MaintenancePredictionResponse
        {
            public bool success;
            public List<MaintenanceEvent> events;
            public MaintenanceSummary summary;
            public string error;
        }

        [Serializable]
        public class MaintenanceEvent
        {
            public string event_id;
            public string machine_id;
            public string event_type; // urgent, scheduled, preventive, predicted
            public string maintenance_type; // tool_change, lubrication, calibration, repair
            public DateTime predicted_date;
            public int days_until;
            public float confidence;
            public string description;
            public string severity; // low, medium, high, critical
            public Vector3 location; // 3D position on machine
            public List<string> components_affected;
            public float estimated_duration_hours;
            public float estimated_cost;
        }

        [Serializable]
        public class MaintenanceSummary
        {
            public int total_events;
            public int urgent_count;
            public int scheduled_count;
            public int predicted_count;
            public float total_estimated_downtime_hours;
            public float total_estimated_cost;
        }

        void Start()
        {
            httpClient = new HttpClient();
            httpClient.Timeout = TimeSpan.FromSeconds(15);

            if (arCamera == null)
            {
                arCamera = Camera.main;
            }

            StartCoroutine(UpdateMaintenanceDataPeriodically());

            Debug.Log("[MaintenanceCalendarAR] Initialized");
        }

        IEnumerator UpdateMaintenanceDataPeriodically()
        {
            while (true)
            {
                yield return new WaitForSeconds(updateInterval);
                FetchMaintenancePredictions();
            }
        }

        void FetchMaintenancePredictions()
        {
            StartCoroutine(FetchMaintenanceAsync());
        }

        IEnumerator FetchMaintenanceAsync()
        {
            string url = $"{flaskServerUrl}/api/v1/predictive/maintenance?horizon_days={predictionHorizonDays}";

            using (var request = new HttpRequestMessage(HttpMethod.Get, url))
            {
                var task = httpClient.SendAsync(request);
                while (!task.IsCompleted) yield return null;

                if (task.IsFaulted || task.Result == null || !task.Result.IsSuccessStatusCode)
                {
                    Debug.LogError("[MaintenanceCalendarAR] Failed to fetch maintenance data");
                    yield break;
                }

                var readTask = task.Result.Content.ReadAsStringAsync();
                while (!readTask.IsCompleted) yield return null;

                try
                {
                    MaintenancePredictionResponse response = JsonConvert.DeserializeObject<MaintenancePredictionResponse>(readTask.Result);

                    if (response.success)
                    {
                        UpdateMaintenanceDisplay(response);
                    }
                    else
                    {
                        Debug.LogError($"[MaintenanceCalendarAR] Error: {response.error}");
                    }
                }
                catch (Exception e)
                {
                    Debug.LogError($"[MaintenanceCalendarAR] Parse error: {e.Message}");
                }
            }

            lastUpdateTime = Time.time;
        }

        void UpdateMaintenanceDisplay(MaintenancePredictionResponse response)
        {
            maintenanceEvents = response.events;

            // Update statistics
            if (response.summary != null)
            {
                totalEvents = response.summary.total_events;
                urgentEvents = response.summary.urgent_count;
                scheduledEvents = response.summary.scheduled_count;
                predictedEvents = response.summary.predicted_count;

                UpdateSummaryText(response.summary);
            }

            // Clear old markers
            ClearMarkers();

            // Create AR markers for each event
            foreach (var evt in maintenanceEvents)
            {
                // Filter by confidence
                if (evt.event_type == "predicted" && evt.confidence < confidenceThreshold && !showLowConfidence)
                {
                    continue;
                }

                CreateEventMarker(evt);

                // Trigger urgent alerts
                if (evt.event_type == "urgent")
                {
                    OnUrgentMaintenanceDetected?.Invoke(evt);
                }
            }

            // Update UI list
            UpdateEventList();
        }

        void CreateEventMarker(MaintenanceEvent evt)
        {
            GameObject markerPrefab = GetMarkerPrefab(evt.event_type);
            if (markerPrefab == null) return;

            // Calculate world position
            Vector3 worldPosition = CalculateMarkerPosition(evt);

            // Instantiate marker
            GameObject marker = Instantiate(markerPrefab, worldPosition, Quaternion.identity);
            marker.transform.SetParent(transform);
            marker.transform.localScale = Vector3.one * markerScale;

            // Setup marker components
            SetupMarkerComponents(marker, evt);

            // Make marker face camera
            if (arCamera != null)
            {
                marker.transform.LookAt(arCamera.transform);
                marker.transform.Rotate(0, 180, 0);
            }

            // Add to active markers
            activeMarkers.Add(marker);
            markerCache[evt.event_id] = marker;

            // Animate if enabled
            if (enableAnimations)
            {
                StartCoroutine(AnimateMarkerAppearance(marker));
            }
        }

        GameObject GetMarkerPrefab(string eventType)
        {
            switch (eventType)
            {
                case "urgent":
                    return urgentMaintenancePrefab ?? CreateDefaultMarker(urgentColor);
                case "scheduled":
                    return scheduledMaintenancePrefab ?? CreateDefaultMarker(scheduledColor);
                case "preventive":
                    return preventiveMaintenancePrefab ?? CreateDefaultMarker(preventiveColor);
                case "predicted":
                    return predictionMarkerPrefab ?? CreateDefaultMarker(predictionColor);
                default:
                    return CreateDefaultMarker(Color.gray);
            }
        }

        GameObject CreateDefaultMarker(Color color)
        {
            GameObject marker = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            Renderer renderer = marker.GetComponent<Renderer>();
            if (renderer != null)
            {
                renderer.material.color = color;
            }
            Destroy(marker.GetComponent<Collider>());
            return marker;
        }

        Vector3 CalculateMarkerPosition(MaintenanceEvent evt)
        {
            if (machineTransform != null)
            {
                // Use event location if specified
                if (evt.location != Vector3.zero)
                {
                    return machineTransform.TransformPoint(evt.location);
                }

                // Otherwise position relative to machine
                return machineTransform.position + Vector3.up * markerDistance;
            }

            return transform.position + Vector3.up * markerDistance;
        }

        void SetupMarkerComponents(GameObject marker, MaintenanceEvent evt)
        {
            // Add label if enabled
            if (showLabels)
            {
                CreateMarkerLabel(marker, evt);
            }

            // Add click handler
            MaintenanceMarkerClickHandler clickHandler = marker.AddComponent<MaintenanceMarkerClickHandler>();
            clickHandler.Initialize(evt, OnMarkerClicked);

            // Add pulsing effect for urgent events
            if (evt.event_type == "urgent")
            {
                PulsingEffect pulseEffect = marker.AddComponent<PulsingEffect>();
                pulseEffect.Initialize(1.5f, 1f);
            }
        }

        void CreateMarkerLabel(GameObject marker, MaintenanceEvent evt)
        {
            GameObject labelObj = new GameObject("Label");
            labelObj.transform.SetParent(marker.transform);
            labelObj.transform.localPosition = Vector3.up * 0.15f;

            Canvas labelCanvas = labelObj.AddComponent<Canvas>();
            labelCanvas.renderMode = RenderMode.WorldSpace;

            RectTransform rect = labelObj.GetComponent<RectTransform>();
            rect.sizeDelta = new Vector2(0.3f, 0.1f);

            Text labelText = labelObj.AddComponent<Text>();
            labelText.text = $"{evt.maintenance_type}\n{evt.days_until} days";
            labelText.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            labelText.fontSize = 24;
            labelText.color = Color.white;
            labelText.alignment = TextAnchor.MiddleCenter;

            // Add background
            Image background = labelObj.AddComponent<Image>();
            background.color = new Color(0, 0, 0, 0.7f);
        }

        IEnumerator AnimateMarkerAppearance(GameObject marker)
        {
            Vector3 targetScale = marker.transform.localScale;
            marker.transform.localScale = Vector3.zero;

            float duration = 0.5f;
            float elapsed = 0f;

            while (elapsed < duration)
            {
                elapsed += Time.deltaTime;
                float t = elapsed / duration;
                t = Mathf.SmoothStep(0f, 1f, t);
                marker.transform.localScale = Vector3.Lerp(Vector3.zero, targetScale, t);
                yield return null;
            }

            marker.transform.localScale = targetScale;
        }

        void OnMarkerClicked(MaintenanceEvent evt)
        {
            OnMaintenanceEventSelected?.Invoke(evt);
            ShowEventDetails(evt);
            Debug.Log($"[MaintenanceCalendarAR] Marker clicked: {evt.event_id}");
        }

        void ShowEventDetails(MaintenanceEvent evt)
        {
            // Display detailed information in UI
            // This would open a detail panel in a full implementation
            Debug.Log($"Event: {evt.maintenance_type}, Date: {evt.predicted_date}, Confidence: {evt.confidence:F2}");
        }

        void UpdateEventList()
        {
            if (eventListScrollRect == null || eventItemPrefab == null) return;

            // Clear existing items
            foreach (Transform child in eventListScrollRect.content)
            {
                Destroy(child.gameObject);
            }

            // Create list items
            foreach (var evt in maintenanceEvents)
            {
                GameObject item = Instantiate(eventItemPrefab, eventListScrollRect.content);

                Text eventText = item.GetComponentInChildren<Text>();
                if (eventText != null)
                {
                    eventText.text = $"{evt.maintenance_type} - {evt.predicted_date:MM/dd} ({evt.days_until}d) - {evt.confidence:P0}";
                }

                Button button = item.GetComponent<Button>();
                if (button != null)
                {
                    MaintenanceEvent eventCopy = evt;
                    button.onClick.AddListener(() => OnMarkerClicked(eventCopy));
                }
            }
        }

        void UpdateSummaryText(MaintenanceSummary summary)
        {
            if (summaryText == null) return;

            string text = $"<b>Maintenance Forecast</b>\n\n";
            text += $"Total Events: {summary.total_events}\n";
            text += $"Urgent: {summary.urgent_count}\n";
            text += $"Scheduled: {summary.scheduled_count}\n";
            text += $"Predicted: {summary.predicted_count}\n\n";
            text += $"Est. Downtime: {summary.total_estimated_downtime_hours:F1}h\n";
            text += $"Est. Cost: ${summary.total_estimated_cost:F2}";

            summaryText.text = text;
        }

        void ClearMarkers()
        {
            foreach (var marker in activeMarkers)
            {
                if (marker != null)
                {
                    Destroy(marker);
                }
            }
            activeMarkers.Clear();
            markerCache.Clear();
        }

        /// <summary>
        /// Toggle AR mode on/off
        /// </summary>
        public void SetARMode(bool enabled)
        {
            arModeEnabled = enabled;
            foreach (var marker in activeMarkers)
            {
                if (marker != null)
                {
                    marker.SetActive(enabled);
                }
            }
        }

        public Dictionary<string, object> GetStatistics()
        {
            return new Dictionary<string, object>
            {
                {"total_events", totalEvents},
                {"urgent_events", urgentEvents},
                {"scheduled_events", scheduledEvents},
                {"predicted_events", predictedEvents},
                {"active_markers", activeMarkers.Count},
                {"ar_mode_enabled", arModeEnabled},
                {"last_update", lastUpdateTime}
            };
        }

        void OnDestroy()
        {
            if (httpClient != null) httpClient.Dispose();
        }
    }

    /// <summary>
    /// Helper component for marker click handling
    /// </summary>
    public class MaintenanceMarkerClickHandler : MonoBehaviour
    {
        private MaintenanceCalendarAR.MaintenanceEvent eventData;
        private Action<MaintenanceCalendarAR.MaintenanceEvent> clickCallback;

        public void Initialize(MaintenanceCalendarAR.MaintenanceEvent evt, Action<MaintenanceCalendarAR.MaintenanceEvent> callback)
        {
            eventData = evt;
            clickCallback = callback;
        }

        void OnMouseDown()
        {
            clickCallback?.Invoke(eventData);
        }
    }

    /// <summary>
    /// Pulsing animation effect for urgent markers
    /// </summary>
    public class PulsingEffect : MonoBehaviour
    {
        private Vector3 baseScale;
        private float pulseScale;
        private float pulseSpeed;

        public void Initialize(float scale, float speed)
        {
            baseScale = transform.localScale;
            pulseScale = scale;
            pulseSpeed = speed;
        }

        void Update()
        {
            float pulse = 1f + Mathf.Sin(Time.time * pulseSpeed) * (pulseScale - 1f) * 0.5f;
            transform.localScale = baseScale * pulse;
        }
    }
}
