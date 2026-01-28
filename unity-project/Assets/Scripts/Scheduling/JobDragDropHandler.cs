using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
using System;
using System.Collections;
using System.Collections.Generic;
using System.Net.Http;
using System.Text;
using Newtonsoft.Json;

namespace CNCScada.Scheduling
{
    /// <summary>
    /// Job Drag-Drop Handler for Schedule Rescheduling
    /// Enables drag-and-drop job rescheduling with validation and conflict detection
    /// Part of Phase 3: Production Scheduling
    /// </summary>
    public class JobDragDropHandler : MonoBehaviour, IBeginDragHandler, IDragHandler, IEndDragHandler, IPointerEnterHandler, IPointerExitHandler
    {
        [Header("Connection Settings")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";

        [Header("References")]
        [SerializeField] private GanttChartController ganttController;
        [SerializeField] private RectTransform canvasRectTransform;

        [Header("Drag Settings")]
        [SerializeField] private bool enableDragDrop = true;
        [SerializeField] private float snapToGrid = 15f; // minutes
        [SerializeField] private bool enableMachineChange = true;
        [SerializeField] private bool requireConfirmation = true;

        [Header("Visual Feedback")]
        [SerializeField] private Color dragColor = new Color(1f, 1f, 0f, 0.5f);
        [SerializeField] private Color validDropColor = Color.green;
        [SerializeField] private Color invalidDropColor = Color.red;
        [SerializeField] private GameObject ghostImagePrefab;
        [SerializeField] private GameObject conflictIndicatorPrefab;

        [Header("Validation")]
        [SerializeField] private bool checkConflicts = true;
        [SerializeField] private bool checkCapacity = true;
        [SerializeField] private bool checkDependencies = true;
        [SerializeField] private float conflictBuffer = 5f; // minutes

        // Drag state
        private bool isDragging = false;
        private Vector2 dragStartPosition;
        private Vector2 currentDragPosition;
        private Image jobImage;
        private Color originalColor;
        private GameObject ghostImage;
        private Canvas dragCanvas;

        // Job data
        private string jobId;
        private string originalMachineId;
        private DateTime originalStartTime;
        private DateTime originalEndTime;
        private float jobDurationHours;

        // Drop validation
        private bool isValidDrop = false;
        private string targetMachineId;
        private DateTime targetStartTime;
        private List<GameObject> conflictIndicators = new List<GameObject>();

        // HTTP client
        private HttpClient httpClient;

        // Statistics
        private int totalDrags = 0;
        private int successfulDrops = 0;
        private int failedDrops = 0;
        private int conflictDetections = 0;

        // Events
        public event Action<string, string, DateTime> OnJobDropped;
        public event Action<string> OnDragStarted;
        public event Action<bool> OnDragEnded;
        public event Action<List<string>> OnConflictDetected;

        [Serializable]
        public class RescheduleRequest
        {
            public string job_id;
            public string new_machine_id;
            public string new_start_time; // ISO 8601 format
            public bool validate_only;
        }

        [Serializable]
        public class RescheduleResponse
        {
            public bool success;
            public bool has_conflicts;
            public List<string> conflicts;
            public string error;
        }

        void Start()
        {
            httpClient = new HttpClient();
            httpClient.Timeout = TimeSpan.FromSeconds(10);

            jobImage = GetComponent<Image>();
            if (jobImage != null)
            {
                originalColor = jobImage.color;
            }

            if (canvasRectTransform == null)
            {
                Canvas parentCanvas = GetComponentInParent<Canvas>();
                if (parentCanvas != null)
                {
                    canvasRectTransform = parentCanvas.GetComponent<RectTransform>();
                }
            }

            // Create drag canvas for ghost image
            CreateDragCanvas();

            Debug.Log("[JobDragDropHandler] Initialized for job: " + jobId);
        }

        void CreateDragCanvas()
        {
            GameObject canvasObj = new GameObject("DragCanvas");
            dragCanvas = canvasObj.AddComponent<Canvas>();
            dragCanvas.renderMode = RenderMode.ScreenSpaceOverlay;
            dragCanvas.sortingOrder = 1000;

            canvasObj.AddComponent<GraphicRaycaster>();
        }

        public void Initialize(string id, string machineId, DateTime startTime, DateTime endTime)
        {
            jobId = id;
            originalMachineId = machineId;
            originalStartTime = startTime;
            originalEndTime = endTime;
            jobDurationHours = (float)(endTime - startTime).TotalHours;
        }

        public void OnPointerEnter(PointerEventData eventData)
        {
            if (!enableDragDrop) return;

            if (jobImage != null && !isDragging)
            {
                jobImage.color = Color.Lerp(originalColor, Color.white, 0.3f);
            }
        }

        public void OnPointerExit(PointerEventData eventData)
        {
            if (!enableDragDrop) return;

            if (jobImage != null && !isDragging)
            {
                jobImage.color = originalColor;
            }
        }

        public void OnBeginDrag(PointerEventData eventData)
        {
            if (!enableDragDrop) return;

            isDragging = true;
            totalDrags++;
            dragStartPosition = transform.position;

            if (jobImage != null)
            {
                jobImage.color = dragColor;
            }

            CreateGhostImage();
            OnDragStarted?.Invoke(jobId);

            Debug.Log($"[JobDragDrop] Started dragging job: {jobId}");
        }

        public void OnDrag(PointerEventData eventData)
        {
            if (!enableDragDrop || !isDragging) return;

            currentDragPosition = eventData.position;

            // Update ghost image position
            if (ghostImage != null)
            {
                ghostImage.transform.position = currentDragPosition;
            }

            // Validate drop position
            ValidateDropPosition();

            // Update visual feedback
            UpdateDragFeedback();
        }

        public void OnEndDrag(PointerEventData eventData)
        {
            if (!enableDragDrop) return;

            isDragging = false;

            DestroyGhostImage();
            ClearConflictIndicators();

            if (isValidDrop)
            {
                if (requireConfirmation)
                {
                    // Show confirmation dialog (implement separately)
                    ConfirmReschedule();
                }
                else
                {
                    ExecuteReschedule();
                }
            }
            else
            {
                // Revert to original position
                RevertPosition();
                failedDrops++;
            }

            if (jobImage != null)
            {
                jobImage.color = originalColor;
            }

            OnDragEnded?.Invoke(isValidDrop);
            Debug.Log($"[JobDragDrop] Ended drag - Valid: {isValidDrop}");
        }

        void CreateGhostImage()
        {
            if (ghostImagePrefab != null)
            {
                ghostImage = Instantiate(ghostImagePrefab, dragCanvas.transform);
            }
            else
            {
                GameObject ghostObj = new GameObject("GhostImage");
                ghostObj.transform.SetParent(dragCanvas.transform);

                Image ghostImg = ghostObj.AddComponent<Image>();
                if (jobImage != null)
                {
                    ghostImg.sprite = jobImage.sprite;
                    ghostImg.color = new Color(dragColor.r, dragColor.g, dragColor.b, 0.5f);
                }

                RectTransform ghostRect = ghostObj.GetComponent<RectTransform>();
                RectTransform thisRect = GetComponent<RectTransform>();
                if (thisRect != null)
                {
                    ghostRect.sizeDelta = thisRect.sizeDelta;
                }

                ghostImage = ghostObj;
            }

            ghostImage.transform.position = dragStartPosition;
        }

        void DestroyGhostImage()
        {
            if (ghostImage != null)
            {
                Destroy(ghostImage);
                ghostImage = null;
            }
        }

        void ValidateDropPosition()
        {
            // Calculate new machine and time from drag position
            CalculateDropTarget();

            // Check for conflicts
            if (checkConflicts)
            {
                DetectConflicts();
            }

            // Validate capacity
            if (checkCapacity)
            {
                ValidateCapacity();
            }

            // Check dependencies
            if (checkDependencies)
            {
                ValidateDependencies();
            }
        }

        void CalculateDropTarget()
        {
            // Convert screen position to timeline position
            // This is a simplified version - actual implementation would use
            // the Gantt chart's coordinate system

            // Calculate time offset from drag distance
            float dragDeltaX = currentDragPosition.x - dragStartPosition.x;
            float pixelsPerHour = 100f; // Should be fetched from GanttController
            float hoursDelta = dragDeltaX / pixelsPerHour;

            // Snap to grid
            if (snapToGrid > 0)
            {
                float minutesGrid = snapToGrid;
                hoursDelta = Mathf.Round(hoursDelta * 60f / minutesGrid) * minutesGrid / 60f;
            }

            targetStartTime = originalStartTime.AddHours(hoursDelta);

            // Detect machine change (vertical drag)
            float dragDeltaY = currentDragPosition.y - dragStartPosition.y;
            if (enableMachineChange && Mathf.Abs(dragDeltaY) > 50f)
            {
                // Determine target machine based on Y position
                targetMachineId = DetectTargetMachine(currentDragPosition.y);
            }
            else
            {
                targetMachineId = originalMachineId;
            }
        }

        string DetectTargetMachine(float yPosition)
        {
            // Raycast to detect machine row under cursor
            // Simplified - actual implementation would use proper raycasting
            return originalMachineId; // Placeholder
        }

        void DetectConflicts()
        {
            ClearConflictIndicators();

            // This would query the backend for conflicts
            // For now, we'll use a simplified local check
            StartCoroutine(CheckConflictsAsync());
        }

        IEnumerator CheckConflictsAsync()
        {
            string url = $"{flaskServerUrl}/api/v1/scheduler/validate-reschedule";

            RescheduleRequest request = new RescheduleRequest
            {
                job_id = jobId,
                new_machine_id = targetMachineId,
                new_start_time = targetStartTime.ToString("o"),
                validate_only = true
            };

            string jsonData = JsonConvert.SerializeObject(request);

            using (var httpRequest = new HttpRequestMessage(HttpMethod.Post, url))
            {
                httpRequest.Content = new StringContent(jsonData, Encoding.UTF8, "application/json");

                var task = httpClient.SendAsync(httpRequest);
                while (!task.IsCompleted) yield return null;

                if (task.IsFaulted || task.Result == null || !task.Result.IsSuccessStatusCode)
                {
                    isValidDrop = false;
                    yield break;
                }

                var readTask = task.Result.Content.ReadAsStringAsync();
                while (!readTask.IsCompleted) yield return null;

                try
                {
                    RescheduleResponse response = JsonConvert.DeserializeObject<RescheduleResponse>(readTask.Result);

                    isValidDrop = response.success && !response.has_conflicts;

                    if (response.has_conflicts)
                    {
                        conflictDetections++;
                        OnConflictDetected?.Invoke(response.conflicts);
                        ShowConflictIndicators(response.conflicts);
                    }
                }
                catch
                {
                    isValidDrop = false;
                }
            }
        }

        void ShowConflictIndicators(List<string> conflicts)
        {
            // Create visual indicators for conflicts
            // This is simplified - actual implementation would position indicators accurately
            foreach (var conflict in conflicts)
            {
                GameObject indicator;
                if (conflictIndicatorPrefab != null)
                {
                    indicator = Instantiate(conflictIndicatorPrefab, dragCanvas.transform);
                }
                else
                {
                    indicator = GameObject.CreatePrimitive(PrimitiveType.Cube);
                    indicator.transform.SetParent(dragCanvas.transform);
                }

                conflictIndicators.Add(indicator);
            }
        }

        void ClearConflictIndicators()
        {
            foreach (var indicator in conflictIndicators)
            {
                if (indicator != null)
                {
                    Destroy(indicator);
                }
            }
            conflictIndicators.Clear();
        }

        void ValidateCapacity()
        {
            // Check if target machine has capacity
            // Simplified - would query actual capacity data
            isValidDrop = isValidDrop && true; // Placeholder
        }

        void ValidateDependencies()
        {
            // Check if job dependencies are satisfied
            // Simplified - would check actual dependency graph
            isValidDrop = isValidDrop && true; // Placeholder
        }

        void UpdateDragFeedback()
        {
            if (ghostImage != null)
            {
                Image ghostImg = ghostImage.GetComponent<Image>();
                if (ghostImg != null)
                {
                    ghostImg.color = isValidDrop ?
                        new Color(validDropColor.r, validDropColor.g, validDropColor.b, 0.5f) :
                        new Color(invalidDropColor.r, invalidDropColor.g, invalidDropColor.b, 0.5f);
                }
            }
        }

        void ConfirmReschedule()
        {
            // Show confirmation dialog
            // For now, directly execute
            ExecuteReschedule();
        }

        void ExecuteReschedule()
        {
            StartCoroutine(RescheduleJobAsync());
        }

        IEnumerator RescheduleJobAsync()
        {
            string url = $"{flaskServerUrl}/api/v1/scheduler/reschedule";

            RescheduleRequest request = new RescheduleRequest
            {
                job_id = jobId,
                new_machine_id = targetMachineId,
                new_start_time = targetStartTime.ToString("o"),
                validate_only = false
            };

            string jsonData = JsonConvert.SerializeObject(request);

            using (var httpRequest = new HttpRequestMessage(HttpMethod.Post, url))
            {
                httpRequest.Content = new StringContent(jsonData, Encoding.UTF8, "application/json");

                var task = httpClient.SendAsync(httpRequest);
                while (!task.IsCompleted) yield return null;

                if (task.IsFaulted || task.Result == null || !task.Result.IsSuccessStatusCode)
                {
                    Debug.LogError("[JobDragDrop] Reschedule failed");
                    RevertPosition();
                    failedDrops++;
                    yield break;
                }

                var readTask = task.Result.Content.ReadAsStringAsync();
                while (!readTask.IsCompleted) yield return null;

                try
                {
                    RescheduleResponse response = JsonConvert.DeserializeObject<RescheduleResponse>(readTask.Result);

                    if (response.success)
                    {
                        successfulDrops++;
                        OnJobDropped?.Invoke(jobId, targetMachineId, targetStartTime);
                        Debug.Log($"[JobDragDrop] Successfully rescheduled job {jobId}");

                        // Update internal state
                        originalMachineId = targetMachineId;
                        originalStartTime = targetStartTime;
                    }
                    else
                    {
                        Debug.LogError($"[JobDragDrop] Reschedule error: {response.error}");
                        RevertPosition();
                        failedDrops++;
                    }
                }
                catch (Exception e)
                {
                    Debug.LogError($"[JobDragDrop] Parse error: {e.Message}");
                    RevertPosition();
                    failedDrops++;
                }
            }
        }

        void RevertPosition()
        {
            transform.position = dragStartPosition;
        }

        public Dictionary<string, object> GetStatistics()
        {
            return new Dictionary<string, object>
            {
                {"total_drags", totalDrags},
                {"successful_drops", successfulDrops},
                {"failed_drops", failedDrops},
                {"conflict_detections", conflictDetections},
                {"success_rate", totalDrags > 0 ? (float)successfulDrops / totalDrags : 0f}
            };
        }

        void OnDestroy()
        {
            if (httpClient != null) httpClient.Dispose();
            if (dragCanvas != null) Destroy(dragCanvas.gameObject);
        }
    }
}
