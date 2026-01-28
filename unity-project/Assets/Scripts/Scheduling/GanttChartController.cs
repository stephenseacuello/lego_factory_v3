using UnityEngine;
using UnityEngine.UI;
using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Text;
using Newtonsoft.Json;

namespace CNCScada.Scheduling
{
    /// <summary>
    /// Interactive Gantt Chart Controller
    /// Displays production schedule with drag-drop job rescheduling
    /// Part of Phase 3: Production Scheduling
    /// </summary>
    public class GanttChartController : MonoBehaviour
    {
        [Header("Connection Settings")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private float scheduleRefreshInterval = 5f;

        [Header("UI References")]
        [SerializeField] private ScrollRect scrollRect;
        [SerializeField] private Transform machineRowContainer;
        [SerializeField] private Transform timelineContainer;
        [SerializeField] private GameObject machineRowPrefab;
        [SerializeField] private GameObject jobBlockPrefab;
        [SerializeField] private Text statusText;
        [SerializeField] private Button refreshButton;
        [SerializeField] private Button optimizeButton;

        [Header("Timeline Configuration")]
        [SerializeField] private float pixelsPerHour = 100f;
        [SerializeField] private int timelineHours = 24;
        [SerializeField] private DateTime scheduleStartTime;
        [SerializeField] private bool useCurrentTime = true;

        [Header("Visual Settings")]
        [SerializeField] private Color scheduledColor = Color.cyan;
        [SerializeField] private Color runningColor = Color.green;
        [SerializeField] private Color completedColor = Color.gray;
        [SerializeField] private Color delayedColor = Color.red;
        [SerializeField] private Color selectedColor = Color.yellow;
        [SerializeField] private float jobBlockHeight = 40f;
        [SerializeField] private float machineRowHeight = 60f;

        // Data
        private HttpClient httpClient;
        private List<MachineRow> machineRows = new List<MachineRow>();
        private List<JobBlock> jobBlocks = new List<JobBlock>();
        private JobBlock selectedJob = null;
        private float lastRefreshTime = 0f;

        // Drag state
        private bool isDragging = false;
        private Vector2 dragStartPosition;
        private JobBlock draggedJob = null;

        // Statistics
        private int totalJobs = 0;
        private int scheduledJobs = 0;
        private int completedJobs = 0;
        private int delayedJobs = 0;

        // Events
        public event Action<string> OnJobSelected;
        public event Action<string, string, DateTime> OnJobRescheduled;
        public event Action OnScheduleUpdated;

        [Serializable]
        public class ScheduleResponse
        {
            public bool success;
            public List<MachineSchedule> machines;
            public DateTime schedule_start;
            public DateTime schedule_end;
            public string error;
        }

        [Serializable]
        public class MachineSchedule
        {
            public string machine_id;
            public string machine_name;
            public List<ScheduledJob> jobs;
            public float utilization_percent;
        }

        [Serializable]
        public class ScheduledJob
        {
            public string job_id;
            public string job_name;
            public string machine_id;
            public DateTime start_time;
            public DateTime end_time;
            public float duration_hours;
            public string status; // scheduled, running, completed, delayed
            public int priority;
            public string part_number;
            public int quantity;
        }

        public class MachineRow
        {
            public string machineId;
            public GameObject rowObject;
            public Text machineLabel;
            public Transform jobContainer;
            public float utilizationPercent;
        }

        public class JobBlock
        {
            public string jobId;
            public ScheduledJob jobData;
            public GameObject blockObject;
            public Image backgroundImage;
            public Text jobLabel;
            public MachineRow parentRow;
            public RectTransform rectTransform;
        }

        void Start()
        {
            httpClient = new HttpClient();
            httpClient.Timeout = TimeSpan.FromSeconds(30);

            if (useCurrentTime)
            {
                scheduleStartTime = DateTime.Now;
            }

            SetupUI();
            StartCoroutine(RefreshSchedulePeriodically());

            Debug.Log("[GanttChartController] Initialized - Timeline: " + timelineHours + " hours");
        }

        void SetupUI()
        {
            if (refreshButton != null)
            {
                refreshButton.onClick.AddListener(OnRefreshButtonClicked);
            }

            if (optimizeButton != null)
            {
                optimizeButton.onClick.AddListener(OnOptimizeButtonClicked);
            }

            // Create timeline markers
            CreateTimelineMarkers();
        }

        void CreateTimelineMarkers()
        {
            if (timelineContainer == null) return;

            // Clear existing markers
            foreach (Transform child in timelineContainer)
            {
                Destroy(child.gameObject);
            }

            // Create hour markers
            for (int hour = 0; hour <= timelineHours; hour++)
            {
                GameObject markerObj = new GameObject($"Hour_{hour}");
                markerObj.transform.SetParent(timelineContainer);

                RectTransform rect = markerObj.AddComponent<RectTransform>();
                rect.anchorMin = new Vector2(0, 0);
                rect.anchorMax = new Vector2(0, 1);
                rect.anchoredPosition = new Vector2(hour * pixelsPerHour, 0);
                rect.sizeDelta = new Vector2(2, 0);

                Image line = markerObj.AddComponent<Image>();
                line.color = new Color(0.3f, 0.3f, 0.3f, 0.5f);

                // Time label
                GameObject labelObj = new GameObject("Label");
                labelObj.transform.SetParent(markerObj.transform);

                RectTransform labelRect = labelObj.AddComponent<RectTransform>();
                labelRect.anchoredPosition = new Vector2(0, -20);
                labelRect.sizeDelta = new Vector2(100, 20);

                Text timeText = labelObj.AddComponent<Text>();
                DateTime labelTime = scheduleStartTime.AddHours(hour);
                timeText.text = labelTime.ToString("HH:mm");
                timeText.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
                timeText.fontSize = 12;
                timeText.color = Color.white;
                timeText.alignment = TextAnchor.MiddleCenter;
            }
        }

        System.Collections.IEnumerator RefreshSchedulePeriodically()
        {
            while (true)
            {
                yield return new WaitForSeconds(scheduleRefreshInterval);
                FetchSchedule();
            }
        }

        void OnRefreshButtonClicked()
        {
            FetchSchedule();
        }

        void OnOptimizeButtonClicked()
        {
            StartCoroutine(TriggerOptimization());
        }

        void FetchSchedule()
        {
            StartCoroutine(FetchScheduleAsync());
        }

        System.Collections.IEnumerator FetchScheduleAsync()
        {
            string url = $"{flaskServerUrl}/api/v1/scheduler/schedule";

            using (var request = new HttpRequestMessage(HttpMethod.Get, url))
            {
                var task = httpClient.SendAsync(request);
                while (!task.IsCompleted) yield return null;

                if (task.IsFaulted || task.Result == null || !task.Result.IsSuccessStatusCode)
                {
                    UpdateStatus("Failed to fetch schedule", true);
                    yield break;
                }

                var readTask = task.Result.Content.ReadAsStringAsync();
                while (!readTask.IsCompleted) yield return null;

                try
                {
                    ScheduleResponse response = JsonConvert.DeserializeObject<ScheduleResponse>(readTask.Result);

                    if (response.success)
                    {
                        UpdateScheduleDisplay(response);
                        UpdateStatus($"Schedule updated - {totalJobs} jobs", false);
                        OnScheduleUpdated?.Invoke();
                    }
                    else
                    {
                        UpdateStatus($"Error: {response.error}", true);
                    }
                }
                catch (Exception e)
                {
                    UpdateStatus($"Parse error: {e.Message}", true);
                }
            }

            lastRefreshTime = Time.time;
        }

        System.Collections.IEnumerator TriggerOptimization()
        {
            UpdateStatus("Optimizing schedule...", false);

            string url = $"{flaskServerUrl}/api/v1/scheduler/optimize";

            var optimizeRequest = new { algorithm = "or_tools", objective = "minimize_makespan" };
            string jsonData = JsonConvert.SerializeObject(optimizeRequest);

            using (var request = new HttpRequestMessage(HttpMethod.Post, url))
            {
                request.Content = new StringContent(jsonData, Encoding.UTF8, "application/json");

                var task = httpClient.SendAsync(request);
                while (!task.IsCompleted) yield return null;

                if (task.IsFaulted || task.Result == null || !task.Result.IsSuccessStatusCode)
                {
                    UpdateStatus("Optimization failed", true);
                    yield break;
                }

                var readTask = task.Result.Content.ReadAsStringAsync();
                while (!readTask.IsCompleted) yield return null;

                try
                {
                    var response = JsonConvert.DeserializeObject<Dictionary<string, object>>(readTask.Result);
                    bool success = response.ContainsKey("success") && (bool)response["success"];

                    if (success)
                    {
                        UpdateStatus("Schedule optimized", false);
                        FetchSchedule(); // Refresh to show optimized schedule
                    }
                    else
                    {
                        UpdateStatus("Optimization failed", true);
                    }
                }
                catch
                {
                    UpdateStatus("Optimization error", true);
                }
            }
        }

        void UpdateScheduleDisplay(ScheduleResponse response)
        {
            // Clear existing display
            ClearScheduleDisplay();

            // Update schedule time range
            scheduleStartTime = response.schedule_start;

            // Create machine rows
            foreach (var machine in response.machines)
            {
                CreateMachineRow(machine);
            }

            // Count statistics
            totalJobs = 0;
            scheduledJobs = 0;
            completedJobs = 0;
            delayedJobs = 0;

            foreach (var job in jobBlocks)
            {
                totalJobs++;
                switch (job.jobData.status)
                {
                    case "scheduled": scheduledJobs++; break;
                    case "completed": completedJobs++; break;
                    case "delayed": delayedJobs++; break;
                }
            }
        }

        void ClearScheduleDisplay()
        {
            foreach (var row in machineRows)
            {
                if (row.rowObject != null)
                {
                    Destroy(row.rowObject);
                }
            }
            machineRows.Clear();
            jobBlocks.Clear();
        }

        void CreateMachineRow(MachineSchedule machine)
        {
            if (machineRowContainer == null || machineRowPrefab == null) return;

            GameObject rowObj = Instantiate(machineRowPrefab, machineRowContainer);
            RectTransform rowRect = rowObj.GetComponent<RectTransform>();
            rowRect.sizeDelta = new Vector2(timelineHours * pixelsPerHour, machineRowHeight);

            MachineRow row = new MachineRow
            {
                machineId = machine.machine_id,
                rowObject = rowObj,
                utilizationPercent = machine.utilization_percent
            };

            // Setup machine label
            Text label = rowObj.GetComponentInChildren<Text>();
            if (label != null)
            {
                label.text = $"{machine.machine_name} ({machine.utilization_percent:F1}%)";
                row.machineLabel = label;
            }

            // Find job container
            Transform container = rowObj.transform.Find("JobContainer");
            if (container != null)
            {
                row.jobContainer = container;
            }
            else
            {
                GameObject containerObj = new GameObject("JobContainer");
                containerObj.transform.SetParent(rowObj.transform);
                row.jobContainer = containerObj.transform;
            }

            machineRows.Add(row);

            // Create job blocks
            foreach (var job in machine.jobs)
            {
                CreateJobBlock(job, row);
            }
        }

        void CreateJobBlock(ScheduledJob job, MachineRow parentRow)
        {
            if (jobBlockPrefab == null || parentRow.jobContainer == null) return;

            GameObject blockObj = Instantiate(jobBlockPrefab, parentRow.jobContainer);
            RectTransform blockRect = blockObj.GetComponent<RectTransform>();

            // Calculate position and size
            float startOffset = (float)(job.start_time - scheduleStartTime).TotalHours * pixelsPerHour;
            float width = job.duration_hours * pixelsPerHour;

            blockRect.anchoredPosition = new Vector2(startOffset, 0);
            blockRect.sizeDelta = new Vector2(width, jobBlockHeight);

            JobBlock jobBlock = new JobBlock
            {
                jobId = job.job_id,
                jobData = job,
                blockObject = blockObj,
                parentRow = parentRow,
                rectTransform = blockRect
            };

            // Setup visual components
            Image background = blockObj.GetComponent<Image>();
            if (background != null)
            {
                background.color = GetJobColor(job.status);
                jobBlock.backgroundImage = background;
            }

            Text jobLabel = blockObj.GetComponentInChildren<Text>();
            if (jobLabel != null)
            {
                jobLabel.text = $"{job.job_name}\n{job.part_number} (x{job.quantity})";
                jobBlock.jobLabel = jobLabel;
            }

            // Add click handler
            Button button = blockObj.GetComponent<Button>();
            if (button == null)
            {
                button = blockObj.AddComponent<Button>();
            }
            button.onClick.AddListener(() => OnJobBlockClicked(jobBlock));

            jobBlocks.Add(jobBlock);
        }

        Color GetJobColor(string status)
        {
            switch (status)
            {
                case "running": return runningColor;
                case "completed": return completedColor;
                case "delayed": return delayedColor;
                default: return scheduledColor;
            }
        }

        void OnJobBlockClicked(JobBlock job)
        {
            // Deselect previous
            if (selectedJob != null && selectedJob.backgroundImage != null)
            {
                selectedJob.backgroundImage.color = GetJobColor(selectedJob.jobData.status);
            }

            // Select new
            selectedJob = job;
            if (selectedJob.backgroundImage != null)
            {
                selectedJob.backgroundImage.color = selectedColor;
            }

            OnJobSelected?.Invoke(job.jobId);
            Debug.Log($"[GanttChart] Selected job: {job.jobData.job_name}");
        }

        void UpdateStatus(string message, bool isError)
        {
            if (statusText != null)
            {
                statusText.text = message;
                statusText.color = isError ? Color.red : Color.white;
            }
        }

        public Dictionary<string, object> GetStatistics()
        {
            return new Dictionary<string, object>
            {
                {"total_jobs", totalJobs},
                {"scheduled_jobs", scheduledJobs},
                {"completed_jobs", completedJobs},
                {"delayed_jobs", delayedJobs},
                {"total_machines", machineRows.Count},
                {"timeline_hours", timelineHours},
                {"schedule_start", scheduleStartTime.ToString()},
                {"last_refresh", lastRefreshTime}
            };
        }

        void OnDestroy()
        {
            if (httpClient != null) httpClient.Dispose();
        }
    }
}
