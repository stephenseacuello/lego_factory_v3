using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.XR;

namespace CNCDigitalTwin.XR
{
    /// <summary>
    /// AR/XR Overlay System for mixed reality experiences
    /// Provides AR overlays for maintenance, training, and remote assistance
    /// Supports HoloLens, Quest, Magic Leap, and mobile AR
    /// </summary>
    public class ARXROverlaySystem : MonoBehaviour
    {
        public static ARXROverlaySystem Instance { get; private set; }

        [Header("XR Configuration")]
        [SerializeField] private XRPlatform targetPlatform = XRPlatform.Auto;
        [SerializeField] private bool enableHandTracking = true;
        [SerializeField] private bool enableVoiceCommands = true;
        [SerializeField] private bool enableSpatialMapping = true;

        [Header("Overlay Settings")]
        [SerializeField] private float defaultOverlayDistance = 1.5f;
        [SerializeField] private float overlayScale = 1.0f;
        [SerializeField] private bool worldLocked = true;
        [SerializeField] private LayerMask overlayInteractionMask;

        [Header("Visual Settings")]
        [SerializeField] private Material hologramMaterial;
        [SerializeField] private Material outlineMaterial;
        [SerializeField] private Color highlightColor = new Color(0, 0.8f, 1f, 0.7f);
        [SerializeField] private Color warningColor = new Color(1f, 0.8f, 0, 0.7f);
        [SerializeField] private Color errorColor = new Color(1f, 0.2f, 0.2f, 0.7f);

        // XR State
        private XRPlatform currentPlatform;
        private bool isXRActive = false;
        private Transform xrCameraTransform;

        // Overlay registry
        private Dictionary<string, AROverlay> overlays = new Dictionary<string, AROverlay>();
        private Dictionary<string, ARAnnotation> annotations = new Dictionary<string, ARAnnotation>();
        private Dictionary<string, ARGuide> guides = new Dictionary<string, ARGuide>();

        // Tracked objects
        private Dictionary<string, TrackedObject> trackedObjects = new Dictionary<string, TrackedObject>();

        // Interaction
        private ARPointer currentPointer;
        private AROverlay focusedOverlay;
        private List<ARInteraction> activeInteractions = new List<ARInteraction>();

        // Remote assistance
        private RemoteSession activeRemoteSession;
        private List<RemoteAnnotation> remoteAnnotations = new List<RemoteAnnotation>();

        // Events
        public event Action<XRPlatform> OnXRPlatformDetected;
        public event Action OnXRSessionStarted;
        public event Action OnXRSessionEnded;
        public event Action<AROverlay> OnOverlayCreated;
        public event Action<AROverlay> OnOverlayFocused;
        public event Action<ARInteraction> OnInteractionStarted;
        public event Action<ARInteraction> OnInteractionCompleted;
        public event Action<string> OnVoiceCommand;
        public event Action<RemoteSession> OnRemoteSessionStarted;

        private Coroutine updateCoroutine;

        void Awake()
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

        void Start()
        {
            DetectXRPlatform();
            InitializeXR();
            updateCoroutine = StartCoroutine(UpdateLoop());
        }

        void OnDestroy()
        {
            if (updateCoroutine != null)
                StopCoroutine(updateCoroutine);

            CleanupXR();
        }

        #region XR Initialization

        private void DetectXRPlatform()
        {
            if (targetPlatform != XRPlatform.Auto)
            {
                currentPlatform = targetPlatform;
                return;
            }

            // Auto-detect platform
            var xrDisplays = new List<XRDisplaySubsystem>();
            SubsystemManager.GetInstances(xrDisplays);

            if (xrDisplays.Any(d => d.running))
            {
                // Check device name to determine platform
                string deviceName = XRSettings.loadedDeviceName?.ToLower() ?? "";

                if (deviceName.Contains("hololens") || deviceName.Contains("windowsmr"))
                {
                    currentPlatform = XRPlatform.HoloLens;
                }
                else if (deviceName.Contains("oculus") || deviceName.Contains("quest"))
                {
                    currentPlatform = XRPlatform.Quest;
                }
                else if (deviceName.Contains("magicleap"))
                {
                    currentPlatform = XRPlatform.MagicLeap;
                }
                else if (deviceName.Contains("vive"))
                {
                    currentPlatform = XRPlatform.ViveXR;
                }
                else
                {
                    currentPlatform = XRPlatform.Generic;
                }
            }
            else
            {
                // Check for mobile AR
#if UNITY_IOS
                currentPlatform = XRPlatform.ARKitMobile;
#elif UNITY_ANDROID
                currentPlatform = XRPlatform.ARCoreMobile;
#else
                currentPlatform = XRPlatform.Desktop;
#endif
            }

            OnXRPlatformDetected?.Invoke(currentPlatform);
            Debug.Log($"[ARXR] Detected platform: {currentPlatform}");
        }

        private void InitializeXR()
        {
            xrCameraTransform = Camera.main?.transform;

            // Initialize platform-specific features
            switch (currentPlatform)
            {
                case XRPlatform.HoloLens:
                    InitializeHoloLens();
                    break;
                case XRPlatform.Quest:
                    InitializeQuest();
                    break;
                case XRPlatform.MagicLeap:
                    InitializeMagicLeap();
                    break;
                case XRPlatform.ARKitMobile:
                case XRPlatform.ARCoreMobile:
                    InitializeMobileAR();
                    break;
                default:
                    InitializeDesktop();
                    break;
            }

            isXRActive = true;
            OnXRSessionStarted?.Invoke();
        }

        private void InitializeHoloLens()
        {
            Debug.Log("[ARXR] Initializing HoloLens features");

            if (enableSpatialMapping)
            {
                // Would initialize spatial mapping here
            }

            if (enableHandTracking)
            {
                // Would initialize hand tracking here
            }

            if (enableVoiceCommands)
            {
                // Would initialize voice commands here
            }
        }

        private void InitializeQuest()
        {
            Debug.Log("[ARXR] Initializing Quest features");

            if (enableHandTracking)
            {
                // Would initialize Quest hand tracking
            }
        }

        private void InitializeMagicLeap()
        {
            Debug.Log("[ARXR] Initializing Magic Leap features");
        }

        private void InitializeMobileAR()
        {
            Debug.Log("[ARXR] Initializing Mobile AR");
        }

        private void InitializeDesktop()
        {
            Debug.Log("[ARXR] Running in Desktop mode");
        }

        private void CleanupXR()
        {
            // Cleanup overlays
            foreach (var overlay in overlays.Values)
            {
                if (overlay.GameObject != null)
                {
                    Destroy(overlay.GameObject);
                }
            }

            overlays.Clear();
            annotations.Clear();
            guides.Clear();

            isXRActive = false;
            OnXRSessionEnded?.Invoke();
        }

        #endregion

        #region Overlay Management

        public AROverlay CreateOverlay(OverlayConfig config)
        {
            var overlay = new AROverlay
            {
                OverlayId = config.OverlayId ?? Guid.NewGuid().ToString(),
                OverlayType = config.OverlayType,
                Title = config.Title,
                Position = config.Position,
                Rotation = config.Rotation,
                Scale = config.Scale * overlayScale,
                IsWorldLocked = config.IsWorldLocked ?? worldLocked,
                AnchorId = config.AnchorId,
                IsVisible = true,
                CreatedAt = DateTime.UtcNow
            };

            // Create Unity GameObject
            overlay.GameObject = CreateOverlayGameObject(overlay, config);

            // Set up anchor if world locked
            if (overlay.IsWorldLocked && !string.IsNullOrEmpty(config.AnchorId))
            {
                AttachToAnchor(overlay, config.AnchorId);
            }

            overlays[overlay.OverlayId] = overlay;
            OnOverlayCreated?.Invoke(overlay);

            Debug.Log($"[ARXR] Created overlay: {overlay.Title} ({overlay.OverlayType})");
            return overlay;
        }

        private GameObject CreateOverlayGameObject(AROverlay overlay, OverlayConfig config)
        {
            var go = new GameObject($"AROverlay_{overlay.OverlayId}");
            go.transform.position = overlay.Position;
            go.transform.rotation = overlay.Rotation;
            go.transform.localScale = Vector3.one * overlay.Scale;

            switch (overlay.OverlayType)
            {
                case OverlayType.InfoPanel:
                    CreateInfoPanel(go, config);
                    break;
                case OverlayType.StatusIndicator:
                    CreateStatusIndicator(go, config);
                    break;
                case OverlayType.MeasurementDisplay:
                    CreateMeasurementDisplay(go, config);
                    break;
                case OverlayType.WorkInstruction:
                    CreateWorkInstruction(go, config);
                    break;
                case OverlayType.MaintenanceGuide:
                    CreateMaintenanceGuide(go, config);
                    break;
                case OverlayType.SafetyZone:
                    CreateSafetyZone(go, config);
                    break;
                case OverlayType.Hologram3D:
                    CreateHologram(go, config);
                    break;
                case OverlayType.PointerArrow:
                    CreatePointerArrow(go, config);
                    break;
            }

            return go;
        }

        private void CreateInfoPanel(GameObject parent, OverlayConfig config)
        {
            // Create a quad for the info panel
            var quad = GameObject.CreatePrimitive(PrimitiveType.Quad);
            quad.transform.SetParent(parent.transform);
            quad.transform.localPosition = Vector3.zero;
            quad.transform.localScale = new Vector3(0.4f, 0.3f, 1f);

            // Apply hologram material
            if (hologramMaterial != null)
            {
                quad.GetComponent<Renderer>().material = hologramMaterial;
            }

            // Would add TextMeshPro for text display
        }

        private void CreateStatusIndicator(GameObject parent, OverlayConfig config)
        {
            // Create a sphere for status
            var sphere = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            sphere.transform.SetParent(parent.transform);
            sphere.transform.localPosition = Vector3.zero;
            sphere.transform.localScale = Vector3.one * 0.1f;

            // Set color based on status
            var renderer = sphere.GetComponent<Renderer>();
            if (config.StatusLevel == StatusLevel.Normal)
                renderer.material.color = Color.green;
            else if (config.StatusLevel == StatusLevel.Warning)
                renderer.material.color = warningColor;
            else
                renderer.material.color = errorColor;
        }

        private void CreateMeasurementDisplay(GameObject parent, OverlayConfig config)
        {
            // Create measurement visualization
            var line = parent.AddComponent<LineRenderer>();
            line.positionCount = 2;
            line.startWidth = 0.01f;
            line.endWidth = 0.01f;
            line.material = hologramMaterial;
        }

        private void CreateWorkInstruction(GameObject parent, OverlayConfig config)
        {
            // Create work instruction panel with step display
            var panel = GameObject.CreatePrimitive(PrimitiveType.Quad);
            panel.transform.SetParent(parent.transform);
            panel.transform.localPosition = Vector3.zero;
            panel.transform.localScale = new Vector3(0.5f, 0.4f, 1f);

            if (hologramMaterial != null)
            {
                panel.GetComponent<Renderer>().material = hologramMaterial;
            }
        }

        private void CreateMaintenanceGuide(GameObject parent, OverlayConfig config)
        {
            // Create maintenance guide with checklist
            CreateWorkInstruction(parent, config);

            // Add step indicators
            for (int i = 0; i < (config.Steps?.Count ?? 3); i++)
            {
                var stepIndicator = GameObject.CreatePrimitive(PrimitiveType.Cube);
                stepIndicator.transform.SetParent(parent.transform);
                stepIndicator.transform.localPosition = new Vector3(-0.2f, 0.15f - i * 0.05f, 0);
                stepIndicator.transform.localScale = Vector3.one * 0.02f;
            }
        }

        private void CreateSafetyZone(GameObject parent, OverlayConfig config)
        {
            // Create safety zone boundary
            var zone = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            zone.transform.SetParent(parent.transform);
            zone.transform.localPosition = Vector3.zero;
            zone.transform.localScale = new Vector3(
                config.ZoneRadius * 2,
                0.01f,
                config.ZoneRadius * 2
            );

            var renderer = zone.GetComponent<Renderer>();
            renderer.material.color = new Color(1f, 0f, 0f, 0.3f);

            // Remove collider (visual only)
            Destroy(zone.GetComponent<Collider>());
        }

        private void CreateHologram(GameObject parent, OverlayConfig config)
        {
            // Would load 3D model and apply hologram shader
            if (!string.IsNullOrEmpty(config.ModelPath))
            {
                // Load model async
            }
            else
            {
                // Create placeholder
                var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
                cube.transform.SetParent(parent.transform);
                cube.transform.localPosition = Vector3.zero;
                cube.transform.localScale = Vector3.one * 0.2f;

                if (hologramMaterial != null)
                {
                    cube.GetComponent<Renderer>().material = hologramMaterial;
                }
            }
        }

        private void CreatePointerArrow(GameObject parent, OverlayConfig config)
        {
            // Create arrow pointer
            var arrow = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            arrow.transform.SetParent(parent.transform);
            arrow.transform.localPosition = Vector3.zero;
            arrow.transform.localScale = new Vector3(0.02f, 0.15f, 0.02f);
            arrow.transform.localRotation = Quaternion.Euler(0, 0, 90);

            // Arrow head
            var head = GameObject.CreatePrimitive(PrimitiveType.Cube);
            head.transform.SetParent(parent.transform);
            head.transform.localPosition = new Vector3(0.2f, 0, 0);
            head.transform.localScale = new Vector3(0.05f, 0.05f, 0.05f);
            head.transform.localRotation = Quaternion.Euler(0, 0, 45);

            var material = hologramMaterial != null ? hologramMaterial :
                new Material(Shader.Find("Standard"));
            material.color = highlightColor;

            arrow.GetComponent<Renderer>().material = material;
            head.GetComponent<Renderer>().material = material;
        }

        public void RemoveOverlay(string overlayId)
        {
            if (overlays.TryGetValue(overlayId, out var overlay))
            {
                if (overlay.GameObject != null)
                {
                    Destroy(overlay.GameObject);
                }
                overlays.Remove(overlayId);
            }
        }

        public void SetOverlayVisibility(string overlayId, bool visible)
        {
            if (overlays.TryGetValue(overlayId, out var overlay))
            {
                overlay.IsVisible = visible;
                if (overlay.GameObject != null)
                {
                    overlay.GameObject.SetActive(visible);
                }
            }
        }

        public void UpdateOverlayPosition(string overlayId, Vector3 newPosition)
        {
            if (overlays.TryGetValue(overlayId, out var overlay))
            {
                overlay.Position = newPosition;
                if (overlay.GameObject != null)
                {
                    overlay.GameObject.transform.position = newPosition;
                }
            }
        }

        #endregion

        #region Annotation System

        public ARAnnotation CreateAnnotation(AnnotationConfig config)
        {
            var annotation = new ARAnnotation
            {
                AnnotationId = config.AnnotationId ?? Guid.NewGuid().ToString(),
                AnnotationType = config.AnnotationType,
                Content = config.Content,
                Position = config.Position,
                AttachedObjectId = config.AttachedObjectId,
                Author = config.Author,
                CreatedAt = DateTime.UtcNow,
                IsVisible = true
            };

            // Create visual
            annotation.GameObject = CreateAnnotationVisual(annotation, config);

            annotations[annotation.AnnotationId] = annotation;
            return annotation;
        }

        private GameObject CreateAnnotationVisual(ARAnnotation annotation, AnnotationConfig config)
        {
            var go = new GameObject($"Annotation_{annotation.AnnotationId}");
            go.transform.position = annotation.Position;

            switch (annotation.AnnotationType)
            {
                case AnnotationType.TextNote:
                    CreateTextAnnotation(go, config);
                    break;
                case AnnotationType.Arrow:
                    CreateArrowAnnotation(go, config);
                    break;
                case AnnotationType.Circle:
                    CreateCircleAnnotation(go, config);
                    break;
                case AnnotationType.Highlight:
                    CreateHighlightAnnotation(go, config);
                    break;
                case AnnotationType.Measurement:
                    CreateMeasurementAnnotation(go, config);
                    break;
            }

            return go;
        }

        private void CreateTextAnnotation(GameObject parent, AnnotationConfig config)
        {
            // Would use TextMeshPro
            var label = new GameObject("Label");
            label.transform.SetParent(parent.transform);
        }

        private void CreateArrowAnnotation(GameObject parent, AnnotationConfig config)
        {
            var line = parent.AddComponent<LineRenderer>();
            line.positionCount = 2;
            line.SetPosition(0, config.Position);
            line.SetPosition(1, config.TargetPosition);
            line.startWidth = 0.02f;
            line.endWidth = 0.005f;
            line.material = hologramMaterial;
        }

        private void CreateCircleAnnotation(GameObject parent, AnnotationConfig config)
        {
            // Create ring/circle highlight
            var ring = new GameObject("Ring");
            ring.transform.SetParent(parent.transform);

            var line = ring.AddComponent<LineRenderer>();
            line.positionCount = 32;
            line.loop = true;
            line.startWidth = 0.01f;
            line.endWidth = 0.01f;

            float radius = config.Radius > 0 ? config.Radius : 0.1f;
            for (int i = 0; i < 32; i++)
            {
                float angle = i * 2f * Mathf.PI / 32f;
                float x = Mathf.Cos(angle) * radius;
                float z = Mathf.Sin(angle) * radius;
                line.SetPosition(i, new Vector3(x, 0, z));
            }
        }

        private void CreateHighlightAnnotation(GameObject parent, AnnotationConfig config)
        {
            // Create highlight effect
            var highlight = GameObject.CreatePrimitive(PrimitiveType.Quad);
            highlight.transform.SetParent(parent.transform);
            highlight.transform.localScale = Vector3.one * (config.Radius > 0 ? config.Radius * 2 : 0.2f);

            var renderer = highlight.GetComponent<Renderer>();
            renderer.material.color = highlightColor;

            Destroy(highlight.GetComponent<Collider>());
        }

        private void CreateMeasurementAnnotation(GameObject parent, AnnotationConfig config)
        {
            var line = parent.AddComponent<LineRenderer>();
            line.positionCount = 2;
            line.SetPosition(0, config.Position);
            line.SetPosition(1, config.TargetPosition);
            line.startWidth = 0.005f;
            line.endWidth = 0.005f;
            line.material = hologramMaterial;

            // Add end markers
            foreach (var pos in new[] { config.Position, config.TargetPosition })
            {
                var marker = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                marker.transform.SetParent(parent.transform);
                marker.transform.position = pos;
                marker.transform.localScale = Vector3.one * 0.01f;
            }
        }

        public void RemoveAnnotation(string annotationId)
        {
            if (annotations.TryGetValue(annotationId, out var annotation))
            {
                if (annotation.GameObject != null)
                {
                    Destroy(annotation.GameObject);
                }
                annotations.Remove(annotationId);
            }
        }

        #endregion

        #region Guide System

        public ARGuide CreateGuide(GuideConfig config)
        {
            var guide = new ARGuide
            {
                GuideId = config.GuideId ?? Guid.NewGuid().ToString(),
                GuideName = config.GuideName,
                Description = config.Description,
                Steps = config.Steps ?? new List<GuideStep>(),
                CurrentStepIndex = 0,
                Status = GuideStatus.NotStarted
            };

            guides[guide.GuideId] = guide;
            Debug.Log($"[ARXR] Created guide: {guide.GuideName} with {guide.Steps.Count} steps");

            return guide;
        }

        public void StartGuide(string guideId)
        {
            if (!guides.TryGetValue(guideId, out var guide))
                return;

            guide.Status = GuideStatus.InProgress;
            guide.StartTime = DateTime.UtcNow;
            guide.CurrentStepIndex = 0;

            ShowGuideStep(guide, 0);
        }

        public void NextGuideStep(string guideId)
        {
            if (!guides.TryGetValue(guideId, out var guide))
                return;

            if (guide.CurrentStepIndex < guide.Steps.Count - 1)
            {
                HideGuideStep(guide, guide.CurrentStepIndex);
                guide.CurrentStepIndex++;
                ShowGuideStep(guide, guide.CurrentStepIndex);
            }
            else
            {
                CompleteGuide(guideId);
            }
        }

        public void PreviousGuideStep(string guideId)
        {
            if (!guides.TryGetValue(guideId, out var guide))
                return;

            if (guide.CurrentStepIndex > 0)
            {
                HideGuideStep(guide, guide.CurrentStepIndex);
                guide.CurrentStepIndex--;
                ShowGuideStep(guide, guide.CurrentStepIndex);
            }
        }

        private void ShowGuideStep(ARGuide guide, int stepIndex)
        {
            if (stepIndex < 0 || stepIndex >= guide.Steps.Count)
                return;

            var step = guide.Steps[stepIndex];

            // Create instruction overlay
            var overlayConfig = new OverlayConfig
            {
                OverlayType = OverlayType.WorkInstruction,
                Title = step.Title,
                Position = step.OverlayPosition != Vector3.zero ? step.OverlayPosition :
                    (xrCameraTransform != null ?
                        xrCameraTransform.position + xrCameraTransform.forward * defaultOverlayDistance :
                        Vector3.forward * defaultOverlayDistance),
                Content = step.Instruction
            };

            step.OverlayId = CreateOverlay(overlayConfig).OverlayId;

            // Create highlight on target if specified
            if (!string.IsNullOrEmpty(step.TargetObjectId))
            {
                HighlightObject(step.TargetObjectId, true);
            }

            // Show pointer arrow if target position specified
            if (step.TargetPosition != Vector3.zero)
            {
                CreateOverlay(new OverlayConfig
                {
                    OverlayId = $"pointer_{step.StepId}",
                    OverlayType = OverlayType.PointerArrow,
                    Position = step.TargetPosition
                });
            }
        }

        private void HideGuideStep(ARGuide guide, int stepIndex)
        {
            if (stepIndex < 0 || stepIndex >= guide.Steps.Count)
                return;

            var step = guide.Steps[stepIndex];

            // Remove overlays
            if (!string.IsNullOrEmpty(step.OverlayId))
            {
                RemoveOverlay(step.OverlayId);
            }

            RemoveOverlay($"pointer_{step.StepId}");

            // Remove highlight
            if (!string.IsNullOrEmpty(step.TargetObjectId))
            {
                HighlightObject(step.TargetObjectId, false);
            }
        }

        public void CompleteGuide(string guideId)
        {
            if (!guides.TryGetValue(guideId, out var guide))
                return;

            HideGuideStep(guide, guide.CurrentStepIndex);

            guide.Status = GuideStatus.Completed;
            guide.EndTime = DateTime.UtcNow;

            Debug.Log($"[ARXR] Guide completed: {guide.GuideName}");
        }

        #endregion

        #region Object Tracking

        public void TrackObject(string objectId, Transform transform, TrackedObjectConfig config = null)
        {
            var tracked = new TrackedObject
            {
                ObjectId = objectId,
                Transform = transform,
                InitialPosition = transform.position,
                InitialRotation = transform.rotation,
                TrackingMode = config?.TrackingMode ?? TrackingMode.Continuous,
                HighlightOnFocus = config?.HighlightOnFocus ?? true
            };

            trackedObjects[objectId] = tracked;
        }

        public void UntrackObject(string objectId)
        {
            trackedObjects.Remove(objectId);
        }

        public void HighlightObject(string objectId, bool highlight)
        {
            if (!trackedObjects.TryGetValue(objectId, out var tracked))
            {
                // Try to find by name
                var go = GameObject.Find(objectId);
                if (go == null) return;

                tracked = new TrackedObject { ObjectId = objectId, Transform = go.transform };
            }

            if (tracked.Transform == null) return;

            var renderer = tracked.Transform.GetComponent<Renderer>();
            if (renderer == null) return;

            if (highlight)
            {
                tracked.OriginalMaterials = renderer.materials;
                var highlightMats = new Material[renderer.materials.Length];
                for (int i = 0; i < highlightMats.Length; i++)
                {
                    highlightMats[i] = outlineMaterial != null ? outlineMaterial :
                        new Material(renderer.materials[i]) { color = highlightColor };
                }
                renderer.materials = highlightMats;
            }
            else if (tracked.OriginalMaterials != null)
            {
                renderer.materials = tracked.OriginalMaterials;
            }
        }

        #endregion

        #region Remote Assistance

        public RemoteSession StartRemoteSession(string sessionId, string expertId)
        {
            var session = new RemoteSession
            {
                SessionId = sessionId ?? Guid.NewGuid().ToString(),
                ExpertId = expertId,
                StartTime = DateTime.UtcNow,
                Status = SessionStatus.Connecting,
                SharedAnnotations = new List<string>()
            };

            activeRemoteSession = session;

            // Would establish WebRTC/signaling connection here
            StartCoroutine(ConnectRemoteSession(session));

            return session;
        }

        private IEnumerator ConnectRemoteSession(RemoteSession session)
        {
            yield return new WaitForSeconds(1f); // Simulate connection

            session.Status = SessionStatus.Connected;
            OnRemoteSessionStarted?.Invoke(session);

            Debug.Log($"[ARXR] Remote session connected: {session.SessionId}");
        }

        public void EndRemoteSession()
        {
            if (activeRemoteSession != null)
            {
                activeRemoteSession.Status = SessionStatus.Ended;
                activeRemoteSession.EndTime = DateTime.UtcNow;

                // Clean up remote annotations
                foreach (var annotationId in activeRemoteSession.SharedAnnotations)
                {
                    RemoveAnnotation(annotationId);
                }

                activeRemoteSession = null;
            }
        }

        public void ShareAnnotation(string annotationId)
        {
            if (activeRemoteSession == null) return;

            if (annotations.TryGetValue(annotationId, out var annotation))
            {
                activeRemoteSession.SharedAnnotations.Add(annotationId);

                // Would send annotation data to remote expert
                var data = new RemoteAnnotation
                {
                    AnnotationId = annotationId,
                    Type = annotation.AnnotationType,
                    Position = annotation.Position,
                    Content = annotation.Content,
                    Timestamp = DateTime.UtcNow
                };

                remoteAnnotations.Add(data);
            }
        }

        public void ReceiveRemoteAnnotation(RemoteAnnotation data)
        {
            // Create annotation from remote data
            var config = new AnnotationConfig
            {
                AnnotationId = data.AnnotationId,
                AnnotationType = data.Type,
                Position = data.Position,
                Content = data.Content,
                Author = "Remote Expert"
            };

            var annotation = CreateAnnotation(config);
            annotation.IsRemote = true;

            if (activeRemoteSession != null)
            {
                activeRemoteSession.SharedAnnotations.Add(annotation.AnnotationId);
            }
        }

        #endregion

        #region Spatial Anchors

        public string CreateSpatialAnchor(Vector3 position, Quaternion rotation, string anchorName = null)
        {
            string anchorId = anchorName ?? Guid.NewGuid().ToString();

            // Would create platform-specific spatial anchor
            // HoloLens: WorldAnchor
            // Quest: OVRSpatialAnchor
            // ARCore/ARKit: ARAnchor

            Debug.Log($"[ARXR] Created spatial anchor: {anchorId}");
            return anchorId;
        }

        public void AttachToAnchor(AROverlay overlay, string anchorId)
        {
            // Would attach overlay to spatial anchor
            overlay.AnchorId = anchorId;
        }

        public bool SaveAnchors(string filename)
        {
            // Would save anchors to persistent storage
            Debug.Log($"[ARXR] Saving anchors to: {filename}");
            return true;
        }

        public bool LoadAnchors(string filename)
        {
            // Would load anchors from persistent storage
            Debug.Log($"[ARXR] Loading anchors from: {filename}");
            return true;
        }

        #endregion

        #region Voice Commands

        public void RegisterVoiceCommand(string command, Action callback)
        {
            // Would register with platform voice recognition
            Debug.Log($"[ARXR] Registered voice command: {command}");
        }

        private void ProcessVoiceCommand(string command)
        {
            OnVoiceCommand?.Invoke(command);

            // Handle built-in commands
            switch (command.ToLower())
            {
                case "next step":
                    foreach (var guide in guides.Values.Where(g => g.Status == GuideStatus.InProgress))
                    {
                        NextGuideStep(guide.GuideId);
                    }
                    break;
                case "previous step":
                    foreach (var guide in guides.Values.Where(g => g.Status == GuideStatus.InProgress))
                    {
                        PreviousGuideStep(guide.GuideId);
                    }
                    break;
                case "hide overlays":
                    foreach (var overlay in overlays.Values)
                    {
                        SetOverlayVisibility(overlay.OverlayId, false);
                    }
                    break;
                case "show overlays":
                    foreach (var overlay in overlays.Values)
                    {
                        SetOverlayVisibility(overlay.OverlayId, true);
                    }
                    break;
            }
        }

        #endregion

        #region Update Loop

        private IEnumerator UpdateLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(0.1f);

                if (!isXRActive) continue;

                UpdateFocusedOverlay();
                UpdateBillboarding();
            }
        }

        private void UpdateFocusedOverlay()
        {
            if (xrCameraTransform == null) return;

            // Check which overlay is in focus
            var gazeRay = new Ray(xrCameraTransform.position, xrCameraTransform.forward);

            AROverlay newFocused = null;
            float closestDistance = float.MaxValue;

            foreach (var overlay in overlays.Values)
            {
                if (!overlay.IsVisible || overlay.GameObject == null) continue;

                var collider = overlay.GameObject.GetComponent<Collider>();
                if (collider != null && collider.Raycast(gazeRay, out RaycastHit hit, 10f))
                {
                    if (hit.distance < closestDistance)
                    {
                        closestDistance = hit.distance;
                        newFocused = overlay;
                    }
                }
            }

            if (newFocused != focusedOverlay)
            {
                focusedOverlay = newFocused;
                if (newFocused != null)
                {
                    OnOverlayFocused?.Invoke(newFocused);
                }
            }
        }

        private void UpdateBillboarding()
        {
            if (xrCameraTransform == null) return;

            foreach (var overlay in overlays.Values)
            {
                if (overlay.GameObject == null || overlay.IsWorldLocked) continue;

                // Billboard toward camera
                overlay.GameObject.transform.LookAt(xrCameraTransform);
                overlay.GameObject.transform.Rotate(0, 180, 0); // Face correct direction
            }

            foreach (var annotation in annotations.Values)
            {
                if (annotation.GameObject == null) continue;

                annotation.GameObject.transform.LookAt(xrCameraTransform);
                annotation.GameObject.transform.Rotate(0, 180, 0);
            }
        }

        #endregion

        #region Statistics

        public ARXRStats GetStatistics()
        {
            return new ARXRStats
            {
                Platform = currentPlatform,
                IsXRActive = isXRActive,
                OverlayCount = overlays.Count,
                AnnotationCount = annotations.Count,
                GuideCount = guides.Count,
                ActiveGuides = guides.Values.Count(g => g.Status == GuideStatus.InProgress),
                TrackedObjects = trackedObjects.Count,
                HasActiveRemoteSession = activeRemoteSession != null,
                RemoteAnnotationCount = remoteAnnotations.Count
            };
        }

        public int OverlayCount => overlays.Count;

        #endregion
    }

    #region Enums

    public enum XRPlatform
    {
        Auto,
        HoloLens,
        Quest,
        MagicLeap,
        ViveXR,
        ARKitMobile,
        ARCoreMobile,
        Generic,
        Desktop
    }

    public enum OverlayType
    {
        InfoPanel,
        StatusIndicator,
        MeasurementDisplay,
        WorkInstruction,
        MaintenanceGuide,
        SafetyZone,
        Hologram3D,
        PointerArrow,
        Custom
    }

    public enum StatusLevel
    {
        Normal,
        Warning,
        Error,
        Critical
    }

    public enum AnnotationType
    {
        TextNote,
        Arrow,
        Circle,
        Highlight,
        Measurement,
        Sketch
    }

    public enum GuideStatus
    {
        NotStarted,
        InProgress,
        Paused,
        Completed,
        Cancelled
    }

    public enum TrackingMode
    {
        Continuous,
        OnDemand,
        MarkerBased
    }

    public enum SessionStatus
    {
        Connecting,
        Connected,
        Paused,
        Ended
    }

    #endregion

    #region Data Classes

    [System.Serializable]
    public class AROverlay
    {
        public string OverlayId;
        public OverlayType OverlayType;
        public string Title;
        public Vector3 Position;
        public Quaternion Rotation;
        public float Scale;
        public bool IsWorldLocked;
        public string AnchorId;
        public bool IsVisible;
        public DateTime CreatedAt;
        public GameObject GameObject;
    }

    [System.Serializable]
    public class OverlayConfig
    {
        public string OverlayId;
        public OverlayType OverlayType;
        public string Title;
        public string Content;
        public Vector3 Position;
        public Quaternion Rotation;
        public float Scale = 1f;
        public bool? IsWorldLocked;
        public string AnchorId;
        public StatusLevel StatusLevel;
        public float ZoneRadius;
        public string ModelPath;
        public List<GuideStep> Steps;
    }

    [System.Serializable]
    public class ARAnnotation
    {
        public string AnnotationId;
        public AnnotationType AnnotationType;
        public string Content;
        public Vector3 Position;
        public string AttachedObjectId;
        public string Author;
        public DateTime CreatedAt;
        public bool IsVisible;
        public bool IsRemote;
        public GameObject GameObject;
    }

    [System.Serializable]
    public class AnnotationConfig
    {
        public string AnnotationId;
        public AnnotationType AnnotationType;
        public string Content;
        public Vector3 Position;
        public Vector3 TargetPosition;
        public float Radius;
        public string AttachedObjectId;
        public string Author;
    }

    [System.Serializable]
    public class ARGuide
    {
        public string GuideId;
        public string GuideName;
        public string Description;
        public List<GuideStep> Steps;
        public int CurrentStepIndex;
        public GuideStatus Status;
        public DateTime? StartTime;
        public DateTime? EndTime;
    }

    [System.Serializable]
    public class GuideConfig
    {
        public string GuideId;
        public string GuideName;
        public string Description;
        public List<GuideStep> Steps;
    }

    [System.Serializable]
    public class GuideStep
    {
        public string StepId;
        public int StepNumber;
        public string Title;
        public string Instruction;
        public string TargetObjectId;
        public Vector3 TargetPosition;
        public Vector3 OverlayPosition;
        public string ImageUrl;
        public string VideoUrl;
        public float EstimatedTime;
        public string OverlayId;
    }

    [System.Serializable]
    public class TrackedObject
    {
        public string ObjectId;
        public Transform Transform;
        public Vector3 InitialPosition;
        public Quaternion InitialRotation;
        public TrackingMode TrackingMode;
        public bool HighlightOnFocus;
        public Material[] OriginalMaterials;
    }

    [System.Serializable]
    public class TrackedObjectConfig
    {
        public TrackingMode TrackingMode;
        public bool HighlightOnFocus;
    }

    [System.Serializable]
    public class ARPointer
    {
        public Vector3 Origin;
        public Vector3 Direction;
        public float Length;
        public bool IsActive;
    }

    [System.Serializable]
    public class ARInteraction
    {
        public string InteractionId;
        public string TargetId;
        public string InteractionType;
        public DateTime StartTime;
        public DateTime? EndTime;
        public bool Completed;
    }

    [System.Serializable]
    public class RemoteSession
    {
        public string SessionId;
        public string ExpertId;
        public DateTime StartTime;
        public DateTime? EndTime;
        public SessionStatus Status;
        public List<string> SharedAnnotations;
    }

    [System.Serializable]
    public class RemoteAnnotation
    {
        public string AnnotationId;
        public AnnotationType Type;
        public Vector3 Position;
        public string Content;
        public DateTime Timestamp;
    }

    [System.Serializable]
    public class ARXRStats
    {
        public XRPlatform Platform;
        public bool IsXRActive;
        public int OverlayCount;
        public int AnnotationCount;
        public int GuideCount;
        public int ActiveGuides;
        public int TrackedObjects;
        public bool HasActiveRemoteSession;
        public int RemoteAnnotationCount;
    }

    #endregion
}
