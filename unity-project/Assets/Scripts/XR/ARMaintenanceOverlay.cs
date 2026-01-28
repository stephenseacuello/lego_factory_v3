using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.XR.ARFoundation;

namespace CNCScada.XR
{
    /// <summary>
    /// AR Maintenance Overlay - Augmented reality guidance for maintenance tasks.
    /// Part of Feature 4.4: AR Maintenance Overlay (Phase 4)
    ///
    /// Provides:
    /// - AR markers for maintenance points
    /// - Step-by-step AR instructions
    /// - Tool identification and guidance
    /// - Safety zone visualization
    /// - Parts explosion view
    /// - Remote expert annotation support
    /// </summary>
    public class ARMaintenanceOverlay : MonoBehaviour
    {
        [Header("AR Configuration")]
        [SerializeField] private string machineId = "CNC-001";
        [SerializeField] private bool enableAutoDetection = true;
        [SerializeField] private float markerScale = 0.1f;
        [SerializeField] private float instructionDisplayDistance = 0.5f;

        [Header("AR Prefabs")]
        [SerializeField] private GameObject maintenancePointPrefab;
        [SerializeField] private GameObject instructionPanelPrefab;
        [SerializeField] private GameObject safetyZonePrefab;
        [SerializeField] private GameObject toolHighlightPrefab;
        [SerializeField] private GameObject annotationPrefab;

        [Header("Visual Settings")]
        [SerializeField] private Color normalColor = Color.green;
        [SerializeField] private Color warningColor = Color.yellow;
        [SerializeField] private Color criticalColor = Color.red;
        [SerializeField] private Color safetyZoneColor = new Color(1f, 0f, 0f, 0.3f);

        // AR Foundation components
        private ARSessionOrigin arSessionOrigin;
        private ARRaycastManager arRaycastManager;
        private ARPlaneManager arPlaneManager;

        // Maintenance data
        private MaintenanceProcedure currentProcedure;
        private int currentStepIndex = 0;
        private bool procedureActive = false;
        private DateTime procedureStartTime;

        // AR Objects
        private Dictionary<string, GameObject> maintenanceMarkers = new Dictionary<string, GameObject>();
        private GameObject activeInstructionPanel;
        private List<GameObject> safetyZones = new List<GameObject>();
        private List<GameObject> toolHighlights = new List<GameObject>();
        private List<GameObject> annotations = new List<GameObject>();

        // Tracking
        private Vector3 machineAnchorPosition;
        private Quaternion machineAnchorRotation;
        private bool machineAnchored = false;

        // Events
        public event Action<MaintenanceProcedure> OnProcedureStarted;
        public event Action<MaintenanceStep> OnStepStarted;
        public event Action<MaintenanceStep> OnStepCompleted;
        public event Action<MaintenanceProcedure> OnProcedureCompleted;
        public event Action<string> OnSafetyWarning;

        // Statistics
        private int totalProcedures = 0;
        private int completedProcedures = 0;
        private float avgCompletionTime = 0f;

        void Start()
        {
            InitializeAR();
            Debug.Log("[AR Maintenance] Overlay initialized");
        }

        void Update()
        {
            if (procedureActive && machineAnchored)
            {
                UpdateInstructionPanel();
                UpdateSafetyZones();
            }
        }

        /// <summary>
        /// Initialize AR components
        /// </summary>
        private void InitializeAR()
        {
            arSessionOrigin = FindObjectOfType<ARSessionOrigin>();
            arRaycastManager = FindObjectOfType<ARRaycastManager>();
            arPlaneManager = FindObjectOfType<ARPlaneManager>();

            if (arSessionOrigin == null || arRaycastManager == null)
            {
                Debug.LogWarning("[AR Maintenance] AR Foundation components not found. AR features disabled.");
            }
        }

        /// <summary>
        /// Anchor AR overlay to machine
        /// </summary>
        public void AnchorToMachine(Vector3 position, Quaternion rotation)
        {
            machineAnchorPosition = position;
            machineAnchorRotation = rotation;
            machineAnchored = true;

            Debug.Log($"[AR Maintenance] Anchored to machine at {position}");
        }

        /// <summary>
        /// Start maintenance procedure
        /// </summary>
        public void StartProcedure(MaintenanceProcedure procedure)
        {
            if (procedureActive)
            {
                Debug.LogWarning("[AR Maintenance] Procedure already active");
                return;
            }

            if (!machineAnchored)
            {
                Debug.LogError("[AR Maintenance] Machine not anchored. Cannot start procedure.");
                return;
            }

            currentProcedure = procedure;
            currentStepIndex = 0;
            procedureActive = true;
            procedureStartTime = DateTime.UtcNow;
            totalProcedures++;

            OnProcedureStarted?.Invoke(procedure);

            // Create maintenance markers
            CreateMaintenanceMarkers(procedure);

            // Show safety zones
            ShowSafetyZones(procedure.SafetyZones);

            // Start first step
            StartStep(0);

            Debug.Log($"[AR Maintenance] Started procedure: {procedure.Title}");
        }

        /// <summary>
        /// Start specific maintenance step
        /// </summary>
        private void StartStep(int stepIndex)
        {
            if (stepIndex >= currentProcedure.Steps.Count)
            {
                CompleteProcedure();
                return;
            }

            currentStepIndex = stepIndex;
            var step = currentProcedure.Steps[stepIndex];

            OnStepStarted?.Invoke(step);

            // Show instruction panel
            ShowInstruction(step);

            // Highlight relevant maintenance point
            HighlightMaintenancePoint(step.MaintenancePointId);

            // Highlight required tools
            HighlightTools(step.RequiredTools);

            // Check safety requirements
            CheckSafetyRequirements(step);

            Debug.Log($"[AR Maintenance] Step {stepIndex + 1}/{currentProcedure.Steps.Count}: {step.Title}");
        }

        /// <summary>
        /// Complete current step
        /// </summary>
        public void CompleteStep()
        {
            if (!procedureActive || currentStepIndex >= currentProcedure.Steps.Count)
            {
                return;
            }

            var step = currentProcedure.Steps[currentStepIndex];
            OnStepCompleted?.Invoke(step);

            // Clear highlights
            ClearToolHighlights();

            // Move to next step
            StartStep(currentStepIndex + 1);
        }

        /// <summary>
        /// Complete maintenance procedure
        /// </summary>
        private void CompleteProcedure()
        {
            if (!procedureActive) return;

            var duration = (float)(DateTime.UtcNow - procedureStartTime).TotalSeconds;
            currentProcedure.CompletionTime = duration;

            completedProcedures++;
            avgCompletionTime = ((avgCompletionTime * (completedProcedures - 1)) + duration) / completedProcedures;

            procedureActive = false;

            OnProcedureCompleted?.Invoke(currentProcedure);

            // Cleanup
            ClearAllMarkers();
            ClearAllHighlights();
            ClearSafetyZones();

            if (activeInstructionPanel != null)
            {
                Destroy(activeInstructionPanel);
                activeInstructionPanel = null;
            }

            Debug.Log($"[AR Maintenance] Procedure completed in {duration:F1}s");
        }

        /// <summary>
        /// Create AR markers for maintenance points
        /// </summary>
        private void CreateMaintenanceMarkers(MaintenanceProcedure procedure)
        {
            foreach (var point in procedure.MaintenancePoints)
            {
                if (maintenancePointPrefab != null)
                {
                    Vector3 worldPosition = machineAnchorPosition + machineAnchorRotation * point.LocalPosition;

                    GameObject marker = Instantiate(maintenancePointPrefab, worldPosition, Quaternion.identity);
                    marker.transform.localScale = Vector3.one * markerScale;

                    // Set marker color based on priority
                    var renderer = marker.GetComponent<Renderer>();
                    if (renderer != null)
                    {
                        Color markerColor = point.Priority switch
                        {
                            MaintenancePriority.Critical => criticalColor,
                            MaintenancePriority.High => warningColor,
                            _ => normalColor
                        };
                        renderer.material.color = markerColor;
                    }

                    maintenanceMarkers[point.Id] = marker;
                }
            }

            Debug.Log($"[AR Maintenance] Created {maintenanceMarkers.Count} maintenance markers");
        }

        /// <summary>
        /// Show AR instruction panel
        /// </summary>
        private void ShowInstruction(MaintenanceStep step)
        {
            if (activeInstructionPanel != null)
            {
                Destroy(activeInstructionPanel);
            }

            if (instructionPanelPrefab != null)
            {
                // Position panel near maintenance point
                Vector3 pointPosition = machineAnchorPosition;
                if (maintenanceMarkers.ContainsKey(step.MaintenancePointId))
                {
                    pointPosition = maintenanceMarkers[step.MaintenancePointId].transform.position;
                }

                Vector3 panelPosition = pointPosition + Vector3.up * instructionDisplayDistance;
                activeInstructionPanel = Instantiate(instructionPanelPrefab, panelPosition, Quaternion.identity);

                // Update panel content (would be handled by panel script)
                // SetPanelContent(activeInstructionPanel, step);
            }
        }

        /// <summary>
        /// Update instruction panel to face camera
        /// </summary>
        private void UpdateInstructionPanel()
        {
            if (activeInstructionPanel != null && Camera.main != null)
            {
                activeInstructionPanel.transform.LookAt(Camera.main.transform);
                activeInstructionPanel.transform.Rotate(0, 180, 0); // Face camera
            }
        }

        /// <summary>
        /// Highlight maintenance point
        /// </summary>
        private void HighlightMaintenancePoint(string pointId)
        {
            // Reset all markers
            foreach (var marker in maintenanceMarkers.Values)
            {
                marker.transform.localScale = Vector3.one * markerScale;
            }

            // Highlight active marker
            if (maintenanceMarkers.ContainsKey(pointId))
            {
                var marker = maintenanceMarkers[pointId];
                marker.transform.localScale = Vector3.one * markerScale * 1.5f;

                // Pulse animation could be added here
            }
        }

        /// <summary>
        /// Highlight required tools
        /// </summary>
        private void HighlightTools(List<string> toolIds)
        {
            ClearToolHighlights();

            foreach (var toolId in toolIds)
            {
                // In a real implementation, this would find the tool in the scene
                // and add a highlight effect
                if (toolHighlightPrefab != null)
                {
                    // Create tool highlight at tool location
                    // This is placeholder - would need actual tool tracking
                    GameObject highlight = Instantiate(toolHighlightPrefab);
                    toolHighlights.Add(highlight);
                }
            }
        }

        /// <summary>
        /// Clear tool highlights
        /// </summary>
        private void ClearToolHighlights()
        {
            foreach (var highlight in toolHighlights)
            {
                if (highlight != null)
                {
                    Destroy(highlight);
                }
            }
            toolHighlights.Clear();
        }

        /// <summary>
        /// Show safety zones in AR
        /// </summary>
        private void ShowSafetyZones(List<SafetyZone> zones)
        {
            ClearSafetyZones();

            foreach (var zone in zones)
            {
                if (safetyZonePrefab != null)
                {
                    Vector3 worldPosition = machineAnchorPosition + machineAnchorRotation * zone.Center;
                    GameObject safetyZone = Instantiate(safetyZonePrefab, worldPosition, Quaternion.identity);

                    // Set zone size
                    safetyZone.transform.localScale = zone.Size;

                    // Set zone color
                    var renderer = safetyZone.GetComponent<Renderer>();
                    if (renderer != null)
                    {
                        renderer.material.color = safetyZoneColor;
                    }

                    safetyZones.Add(safetyZone);
                }
            }
        }

        /// <summary>
        /// Update safety zone warnings
        /// </summary>
        private void UpdateSafetyZones()
        {
            if (Camera.main == null) return;

            Vector3 userPosition = Camera.main.transform.position;

            foreach (var zone in currentProcedure.SafetyZones)
            {
                Vector3 zoneWorldPos = machineAnchorPosition + machineAnchorRotation * zone.Center;
                float distance = Vector3.Distance(userPosition, zoneWorldPos);

                // Check if user is too close to safety zone
                float safeDistance = Mathf.Max(zone.Size.x, zone.Size.y, zone.Size.z) / 2f;
                if (distance < safeDistance)
                {
                    OnSafetyWarning?.Invoke($"Warning: Too close to {zone.Name}");
                }
            }
        }

        /// <summary>
        /// Clear safety zones
        /// </summary>
        private void ClearSafetyZones()
        {
            foreach (var zone in safetyZones)
            {
                if (zone != null)
                {
                    Destroy(zone);
                }
            }
            safetyZones.Clear();
        }

        /// <summary>
        /// Check safety requirements for step
        /// </summary>
        private void CheckSafetyRequirements(MaintenanceStep step)
        {
            foreach (var requirement in step.SafetyRequirements)
            {
                if (requirement.IsMandatory)
                {
                    Debug.LogWarning($"[AR Maintenance] Safety requirement: {requirement.Description}");
                    OnSafetyWarning?.Invoke(requirement.Description);
                }
            }
        }

        /// <summary>
        /// Add remote expert annotation
        /// </summary>
        public void AddAnnotation(Vector3 worldPosition, string text, Color color)
        {
            if (annotationPrefab != null)
            {
                GameObject annotation = Instantiate(annotationPrefab, worldPosition, Quaternion.identity);

                // Set annotation properties (would be handled by annotation script)
                // SetAnnotationText(annotation, text);
                // SetAnnotationColor(annotation, color);

                annotations.Add(annotation);

                Debug.Log($"[AR Maintenance] Added annotation: {text}");
            }
        }

        /// <summary>
        /// Clear all annotations
        /// </summary>
        public void ClearAnnotations()
        {
            foreach (var annotation in annotations)
            {
                if (annotation != null)
                {
                    Destroy(annotation);
                }
            }
            annotations.Clear();
        }

        /// <summary>
        /// Clear all markers
        /// </summary>
        private void ClearAllMarkers()
        {
            foreach (var marker in maintenanceMarkers.Values)
            {
                if (marker != null)
                {
                    Destroy(marker);
                }
            }
            maintenanceMarkers.Clear();
        }

        /// <summary>
        /// Clear all highlights
        /// </summary>
        private void ClearAllHighlights()
        {
            ClearToolHighlights();
        }

        /// <summary>
        /// Get AR overlay statistics
        /// </summary>
        public AROverlayStatistics GetStatistics()
        {
            return new AROverlayStatistics
            {
                TotalProcedures = totalProcedures,
                CompletedProcedures = completedProcedures,
                AverageCompletionTime = avgCompletionTime,
                ProcedureActive = procedureActive,
                CurrentProcedureId = procedureActive ? currentProcedure?.Id : null,
                CurrentStep = procedureActive ? currentStepIndex + 1 : 0,
                TotalSteps = procedureActive ? currentProcedure?.Steps.Count ?? 0 : 0,
                MachineAnchored = machineAnchored
            };
        }

        #region Public Properties

        public bool IsProcedureActive => procedureActive;
        public bool IsMachineAnchored => machineAnchored;
        public int CurrentStepIndex => currentStepIndex;
        public string CurrentProcedureId => currentProcedure?.Id;

        #endregion
    }

    #region Data Structures

    /// <summary>
    /// Maintenance procedure definition
    /// </summary>
    [Serializable]
    public class MaintenanceProcedure
    {
        public string Id;
        public string Title;
        public string Description;
        public MaintenanceType Type;
        public MaintenancePriority Priority;
        public float EstimatedDuration;
        public List<MaintenancePoint> MaintenancePoints;
        public List<MaintenanceStep> Steps;
        public List<SafetyZone> SafetyZones;
        public float CompletionTime;
    }

    /// <summary>
    /// Maintenance point on machine
    /// </summary>
    [Serializable]
    public struct MaintenancePoint
    {
        public string Id;
        public string Name;
        public Vector3 LocalPosition;
        public MaintenancePriority Priority;
        public string ComponentId;
    }

    /// <summary>
    /// Maintenance step
    /// </summary>
    [Serializable]
    public struct MaintenanceStep
    {
        public string Id;
        public string Title;
        public string Instruction;
        public string MaintenancePointId;
        public List<string> RequiredTools;
        public float EstimatedTime;
        public List<SafetyRequirement> SafetyRequirements;
        public string ImageUrl;
        public string VideoUrl;
    }

    /// <summary>
    /// Safety zone definition
    /// </summary>
    [Serializable]
    public struct SafetyZone
    {
        public string Name;
        public Vector3 Center;
        public Vector3 Size;
        public string Description;
    }

    /// <summary>
    /// Safety requirement
    /// </summary>
    [Serializable]
    public struct SafetyRequirement
    {
        public string Description;
        public bool IsMandatory;
        public string PPERequired; // Personal Protective Equipment
    }

    /// <summary>
    /// AR overlay statistics
    /// </summary>
    [Serializable]
    public struct AROverlayStatistics
    {
        public int TotalProcedures;
        public int CompletedProcedures;
        public float AverageCompletionTime;
        public bool ProcedureActive;
        public string CurrentProcedureId;
        public int CurrentStep;
        public int TotalSteps;
        public bool MachineAnchored;
    }

    /// <summary>
    /// Maintenance types
    /// </summary>
    public enum MaintenanceType
    {
        Preventive,
        Corrective,
        Predictive,
        Inspection
    }

    /// <summary>
    /// Maintenance priority levels
    /// </summary>
    public enum MaintenancePriority
    {
        Low,
        Normal,
        High,
        Critical
    }

    #endregion
}
