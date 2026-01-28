using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.Networking;

namespace CNCDigitalTwin.Vision
{
    /// <summary>
    /// Advanced Vision Inspection System for quality control and object detection
    /// Integrates with industrial cameras, ML inference, and AR overlays
    /// </summary>
    public class AdvancedVisionSystem : MonoBehaviour
    {
        public static AdvancedVisionSystem Instance { get; private set; }

        [Header("Vision Configuration")]
        [SerializeField] private string inferenceServerUrl = "http://localhost:8080";
        [SerializeField] private float inspectionInterval = 1.0f;
        [SerializeField] private int maxConcurrentInspections = 4;
        [SerializeField] private bool enableRealTimeProcessing = true;

        [Header("Camera Settings")]
        [SerializeField] private int captureWidth = 1920;
        [SerializeField] private int captureHeight = 1080;
        [SerializeField] private float exposureTime = 0.01f;

        [Header("Detection Settings")]
        [SerializeField] private float confidenceThreshold = 0.85f;
        [SerializeField] private float nmsThreshold = 0.45f;
        [SerializeField] private int maxDetections = 100;

        // Camera registry
        private Dictionary<string, VisionCamera> cameras = new Dictionary<string, VisionCamera>();
        private Dictionary<string, InspectionProfile> profiles = new Dictionary<string, InspectionProfile>();
        private Dictionary<string, InspectionZone> zones = new Dictionary<string, InspectionZone>();

        // Inspection queue and results
        private Queue<InspectionRequest> inspectionQueue = new Queue<InspectionRequest>();
        private List<InspectionResult> recentResults = new List<InspectionResult>();
        private int activeInspections = 0;

        // ML Models
        private Dictionary<string, MLModel> loadedModels = new Dictionary<string, MLModel>();

        // Statistics
        private VisionStats stats = new VisionStats();

        // Events
        public event Action<VisionCamera> OnCameraConnected;
        public event Action<VisionCamera> OnCameraDisconnected;
        public event Action<InspectionResult> OnInspectionComplete;
        public event Action<DefectDetection> OnDefectDetected;
        public event Action<ObjectDetection> OnObjectDetected;
        public event Action<string, float> OnMeasurementComplete;

        private bool isConnected = false;
        private Coroutine processingCoroutine;

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
            InitializeDefaultProfiles();
            InitializeDefaultModels();
            processingCoroutine = StartCoroutine(ProcessInspectionQueue());
            StartCoroutine(ConnectToInferenceServer());
        }

        void OnDestroy()
        {
            if (processingCoroutine != null)
                StopCoroutine(processingCoroutine);

            foreach (var camera in cameras.Values)
            {
                camera.Disconnect();
            }
        }

        #region Initialization

        private void InitializeDefaultProfiles()
        {
            // Surface inspection profile
            DefineProfile(new InspectionProfile
            {
                ProfileId = "surface_defect",
                Name = "Surface Defect Detection",
                ModelId = "defect_detection_v2",
                DefectTypes = new[] { "scratch", "dent", "crack", "corrosion", "contamination" },
                MinDefectSize = 0.1f,
                MaxDefectSize = 50f,
                SeverityThresholds = new Dictionary<string, float>
                {
                    { "scratch", 0.3f }, { "dent", 0.5f }, { "crack", 0.1f },
                    { "corrosion", 0.2f }, { "contamination", 0.4f }
                }
            });

            // Dimensional inspection profile
            DefineProfile(new InspectionProfile
            {
                ProfileId = "dimensional",
                Name = "Dimensional Measurement",
                ModelId = "measurement_v1",
                MeasurementTypes = new[] { "length", "width", "height", "diameter", "angle" },
                ToleranceClass = ToleranceClass.IT7,
                CalibrationRequired = true
            });

            // Part presence profile
            DefineProfile(new InspectionProfile
            {
                ProfileId = "part_presence",
                Name = "Part Presence Verification",
                ModelId = "object_detection_v3",
                RequiredParts = new string[] { },
                VerifyOrientation = true,
                VerifyCount = true
            });

            // Barcode/QR reading profile
            DefineProfile(new InspectionProfile
            {
                ProfileId = "code_reading",
                Name = "Barcode/QR Code Reading",
                ModelId = "code_reader_v1",
                CodeTypes = new[] { "QR", "DataMatrix", "Code128", "Code39", "EAN13" },
                MultiCodeEnabled = true
            });

            // Assembly verification profile
            DefineProfile(new InspectionProfile
            {
                ProfileId = "assembly_check",
                Name = "Assembly Verification",
                ModelId = "assembly_v1",
                CheckComponents = true,
                CheckOrientation = true,
                CheckConnections = true
            });
        }

        private void InitializeDefaultModels()
        {
            // Register ML models
            RegisterModel(new MLModel
            {
                ModelId = "defect_detection_v2",
                Name = "Defect Detection YOLOv8",
                Type = ModelType.ObjectDetection,
                InputSize = new Vector2Int(640, 640),
                OutputClasses = new[] { "scratch", "dent", "crack", "corrosion", "contamination", "good" },
                Version = "2.1.0",
                Framework = "ONNX"
            });

            RegisterModel(new MLModel
            {
                ModelId = "measurement_v1",
                Name = "Dimensional Measurement CNN",
                Type = ModelType.Segmentation,
                InputSize = new Vector2Int(1024, 1024),
                Version = "1.3.0",
                Framework = "ONNX"
            });

            RegisterModel(new MLModel
            {
                ModelId = "object_detection_v3",
                Name = "Part Detection YOLOv8",
                Type = ModelType.ObjectDetection,
                InputSize = new Vector2Int(640, 640),
                Version = "3.0.0",
                Framework = "ONNX"
            });

            RegisterModel(new MLModel
            {
                ModelId = "code_reader_v1",
                Name = "Code Reader",
                Type = ModelType.Classification,
                InputSize = new Vector2Int(512, 512),
                Version = "1.0.0",
                Framework = "Custom"
            });

            RegisterModel(new MLModel
            {
                ModelId = "assembly_v1",
                Name = "Assembly Verification",
                Type = ModelType.ObjectDetection,
                InputSize = new Vector2Int(800, 800),
                Version = "1.2.0",
                Framework = "ONNX"
            });
        }

        private IEnumerator ConnectToInferenceServer()
        {
            Debug.Log($"[Vision] Connecting to inference server at {inferenceServerUrl}");

            using (var request = UnityWebRequest.Get($"{inferenceServerUrl}/health"))
            {
                request.timeout = 5;
                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.Success)
                {
                    isConnected = true;
                    Debug.Log("[Vision] Connected to inference server");
                }
                else
                {
                    Debug.LogWarning($"[Vision] Failed to connect to inference server: {request.error}");
                }
            }
        }

        #endregion

        #region Camera Management

        public VisionCamera RegisterCamera(VisionCameraConfig config)
        {
            var camera = new VisionCamera
            {
                CameraId = config.CameraId,
                Name = config.Name,
                Type = config.Type,
                ConnectionString = config.ConnectionString,
                Position = config.Position,
                Rotation = config.Rotation,
                FieldOfView = config.FieldOfView,
                Resolution = new Vector2Int(captureWidth, captureHeight),
                CalibrationMatrix = config.CalibrationMatrix,
                DistortionCoefficients = config.DistortionCoefficients
            };

            cameras[config.CameraId] = camera;
            Debug.Log($"[Vision] Registered camera: {config.Name} ({config.Type})");

            StartCoroutine(ConnectCamera(camera));
            return camera;
        }

        private IEnumerator ConnectCamera(VisionCamera camera)
        {
            Debug.Log($"[Vision] Connecting camera: {camera.Name}");

            // Simulate camera connection
            yield return new WaitForSeconds(0.5f);

            switch (camera.Type)
            {
                case CameraType.GigE:
                    yield return ConnectGigECamera(camera);
                    break;
                case CameraType.USB3:
                    yield return ConnectUSB3Camera(camera);
                    break;
                case CameraType.RTSP:
                    yield return ConnectRTSPCamera(camera);
                    break;
                case CameraType.Virtual:
                    camera.IsConnected = true;
                    break;
            }

            if (camera.IsConnected)
            {
                OnCameraConnected?.Invoke(camera);
                stats.CamerasConnected++;
                Debug.Log($"[Vision] Camera connected: {camera.Name}");
            }
        }

        private IEnumerator ConnectGigECamera(VisionCamera camera)
        {
            // GigE Vision protocol connection
            Debug.Log($"[Vision] Connecting GigE camera at {camera.ConnectionString}");
            yield return new WaitForSeconds(1f);
            camera.IsConnected = true;
        }

        private IEnumerator ConnectUSB3Camera(VisionCamera camera)
        {
            // USB3 Vision connection
            Debug.Log($"[Vision] Connecting USB3 camera");
            yield return new WaitForSeconds(0.5f);
            camera.IsConnected = true;
        }

        private IEnumerator ConnectRTSPCamera(VisionCamera camera)
        {
            // RTSP stream connection
            Debug.Log($"[Vision] Connecting RTSP stream at {camera.ConnectionString}");
            yield return new WaitForSeconds(0.3f);
            camera.IsConnected = true;
        }

        public void DisconnectCamera(string cameraId)
        {
            if (cameras.TryGetValue(cameraId, out var camera))
            {
                camera.Disconnect();
                OnCameraDisconnected?.Invoke(camera);
                stats.CamerasConnected--;
            }
        }

        public VisionCamera GetCamera(string cameraId)
        {
            return cameras.TryGetValue(cameraId, out var camera) ? camera : null;
        }

        public IEnumerator CaptureImage(string cameraId, Action<CapturedImage> callback)
        {
            if (!cameras.TryGetValue(cameraId, out var camera) || !camera.IsConnected)
            {
                callback?.Invoke(null);
                yield break;
            }

            var image = new CapturedImage
            {
                CameraId = cameraId,
                CaptureTime = DateTime.UtcNow,
                Width = camera.Resolution.x,
                Height = camera.Resolution.y,
                Format = ImageFormat.RGB24,
                ExposureTime = exposureTime
            };

            // Simulate image capture
            yield return new WaitForSeconds(0.05f);

            // In production, this would capture from actual camera
            image.Data = new byte[image.Width * image.Height * 3];
            stats.ImagesCaptures++;

            callback?.Invoke(image);
        }

        #endregion

        #region Inspection Zone Management

        public InspectionZone CreateZone(InspectionZoneConfig config)
        {
            var zone = new InspectionZone
            {
                ZoneId = config.ZoneId,
                Name = config.Name,
                Cameras = config.CameraIds.Select(id => cameras.GetValueOrDefault(id)).Where(c => c != null).ToList(),
                Profile = profiles.GetValueOrDefault(config.ProfileId),
                TriggerMode = config.TriggerMode,
                Bounds = config.Bounds,
                IsActive = true
            };

            zones[config.ZoneId] = zone;
            Debug.Log($"[Vision] Created inspection zone: {config.Name}");

            if (config.TriggerMode == TriggerMode.Continuous)
            {
                StartCoroutine(ContinuousInspection(zone));
            }

            return zone;
        }

        private IEnumerator ContinuousInspection(InspectionZone zone)
        {
            while (zone.IsActive)
            {
                yield return new WaitForSeconds(inspectionInterval);

                if (zone.Cameras.Count > 0 && zone.Profile != null)
                {
                    QueueInspection(new InspectionRequest
                    {
                        RequestId = Guid.NewGuid().ToString(),
                        ZoneId = zone.ZoneId,
                        ProfileId = zone.Profile.ProfileId,
                        CameraId = zone.Cameras[0].CameraId,
                        Priority = InspectionPriority.Normal
                    });
                }
            }
        }

        public void TriggerInspection(string zoneId, string partId = null)
        {
            if (!zones.TryGetValue(zoneId, out var zone) || !zone.IsActive)
            {
                Debug.LogWarning($"[Vision] Zone not found or inactive: {zoneId}");
                return;
            }

            foreach (var camera in zone.Cameras)
            {
                QueueInspection(new InspectionRequest
                {
                    RequestId = Guid.NewGuid().ToString(),
                    ZoneId = zoneId,
                    ProfileId = zone.Profile.ProfileId,
                    CameraId = camera.CameraId,
                    PartId = partId,
                    Priority = InspectionPriority.High
                });
            }
        }

        #endregion

        #region Inspection Processing

        public void QueueInspection(InspectionRequest request)
        {
            inspectionQueue.Enqueue(request);
            stats.InspectionsQueued++;
        }

        private IEnumerator ProcessInspectionQueue()
        {
            while (true)
            {
                yield return new WaitForSeconds(0.05f);

                while (inspectionQueue.Count > 0 && activeInspections < maxConcurrentInspections)
                {
                    var request = inspectionQueue.Dequeue();
                    activeInspections++;
                    StartCoroutine(ProcessInspection(request));
                }
            }
        }

        private IEnumerator ProcessInspection(InspectionRequest request)
        {
            var startTime = DateTime.UtcNow;
            var result = new InspectionResult
            {
                RequestId = request.RequestId,
                ZoneId = request.ZoneId,
                ProfileId = request.ProfileId,
                CameraId = request.CameraId,
                PartId = request.PartId,
                StartTime = startTime
            };

            // Capture image
            CapturedImage image = null;
            yield return CaptureImage(request.CameraId, img => image = img);

            if (image == null)
            {
                result.Status = InspectionStatus.Failed;
                result.ErrorMessage = "Image capture failed";
                CompleteInspection(result);
                yield break;
            }

            result.ImageId = Guid.NewGuid().ToString();

            // Get profile
            if (!profiles.TryGetValue(request.ProfileId, out var profile))
            {
                result.Status = InspectionStatus.Failed;
                result.ErrorMessage = "Profile not found";
                CompleteInspection(result);
                yield break;
            }

            // Run inference
            if (isConnected)
            {
                yield return RunRemoteInference(image, profile, result);
            }
            else
            {
                // Local/simulated inference
                yield return RunLocalInference(image, profile, result);
            }

            // Calculate overall result
            result.EndTime = DateTime.UtcNow;
            result.ProcessingTimeMs = (float)(result.EndTime - result.StartTime).TotalMilliseconds;

            DetermineOverallResult(result, profile);
            CompleteInspection(result);
        }

        private IEnumerator RunRemoteInference(CapturedImage image, InspectionProfile profile, InspectionResult result)
        {
            // Prepare request to inference server
            var inferenceUrl = $"{inferenceServerUrl}/infer/{profile.ModelId}";

            // In production, send image data to inference server
            yield return new WaitForSeconds(0.1f); // Simulate network latency

            // Parse inference results
            result.Detections = new List<ObjectDetection>();
            result.Defects = new List<DefectDetection>();
            result.Measurements = new Dictionary<string, MeasurementResult>();
        }

        private IEnumerator RunLocalInference(CapturedImage image, InspectionProfile profile, InspectionResult result)
        {
            // Simulate local inference
            yield return new WaitForSeconds(0.05f);

            result.Detections = new List<ObjectDetection>();
            result.Defects = new List<DefectDetection>();
            result.Measurements = new Dictionary<string, MeasurementResult>();

            // Simulate detections based on profile
            if (profile.DefectTypes != null && profile.DefectTypes.Length > 0)
            {
                // Simulate random defect detection (for demo)
                if (UnityEngine.Random.value < 0.1f) // 10% defect rate
                {
                    var defectType = profile.DefectTypes[UnityEngine.Random.Range(0, profile.DefectTypes.Length)];
                    var defect = new DefectDetection
                    {
                        DefectId = Guid.NewGuid().ToString(),
                        DefectType = defectType,
                        Confidence = UnityEngine.Random.Range(0.85f, 0.99f),
                        BoundingBox = new Rect(
                            UnityEngine.Random.Range(0.1f, 0.8f),
                            UnityEngine.Random.Range(0.1f, 0.8f),
                            UnityEngine.Random.Range(0.05f, 0.2f),
                            UnityEngine.Random.Range(0.05f, 0.2f)
                        ),
                        Area = UnityEngine.Random.Range(1f, 10f),
                        Severity = DetermineSeverity(defectType, profile)
                    };

                    result.Defects.Add(defect);
                    OnDefectDetected?.Invoke(defect);
                }
            }

            // Simulate measurements
            if (profile.MeasurementTypes != null)
            {
                foreach (var measureType in profile.MeasurementTypes)
                {
                    var nominal = 100f;
                    var tolerance = GetToleranceForClass(profile.ToleranceClass, nominal);

                    result.Measurements[measureType] = new MeasurementResult
                    {
                        MeasurementType = measureType,
                        Value = nominal + UnityEngine.Random.Range(-tolerance * 0.8f, tolerance * 0.8f),
                        Unit = "mm",
                        Nominal = nominal,
                        UpperTolerance = tolerance,
                        LowerTolerance = tolerance,
                        InTolerance = true
                    };

                    OnMeasurementComplete?.Invoke(measureType, result.Measurements[measureType].Value);
                }
            }
        }

        private DefectSeverity DetermineSeverity(string defectType, InspectionProfile profile)
        {
            if (profile.SeverityThresholds.TryGetValue(defectType, out var threshold))
            {
                if (threshold < 0.2f) return DefectSeverity.Critical;
                if (threshold < 0.4f) return DefectSeverity.Major;
                if (threshold < 0.6f) return DefectSeverity.Minor;
                return DefectSeverity.Cosmetic;
            }
            return DefectSeverity.Minor;
        }

        private float GetToleranceForClass(ToleranceClass toleranceClass, float nominal)
        {
            // ISO tolerance grades (simplified)
            float factor = toleranceClass switch
            {
                ToleranceClass.IT5 => 0.007f,
                ToleranceClass.IT6 => 0.010f,
                ToleranceClass.IT7 => 0.016f,
                ToleranceClass.IT8 => 0.025f,
                ToleranceClass.IT9 => 0.040f,
                ToleranceClass.IT10 => 0.064f,
                _ => 0.025f
            };
            return nominal * factor;
        }

        private void DetermineOverallResult(InspectionResult result, InspectionProfile profile)
        {
            // Check for critical defects
            if (result.Defects.Any(d => d.Severity == DefectSeverity.Critical))
            {
                result.OverallResult = InspectionVerdict.Reject;
                result.Status = InspectionStatus.Completed;
                return;
            }

            // Check for out-of-tolerance measurements
            if (result.Measurements.Values.Any(m => !m.InTolerance))
            {
                result.OverallResult = InspectionVerdict.Reject;
                result.Status = InspectionStatus.Completed;
                return;
            }

            // Check for major defects beyond threshold
            int majorDefects = result.Defects.Count(d => d.Severity == DefectSeverity.Major);
            if (majorDefects > 0)
            {
                result.OverallResult = InspectionVerdict.Review;
                result.Status = InspectionStatus.Completed;
                return;
            }

            result.OverallResult = InspectionVerdict.Pass;
            result.Status = InspectionStatus.Completed;
        }

        private void CompleteInspection(InspectionResult result)
        {
            activeInspections--;
            recentResults.Insert(0, result);

            // Trim results list
            if (recentResults.Count > 1000)
            {
                recentResults.RemoveRange(1000, recentResults.Count - 1000);
            }

            // Update statistics
            stats.InspectionsCompleted++;
            if (result.OverallResult == InspectionVerdict.Pass) stats.PassCount++;
            else if (result.OverallResult == InspectionVerdict.Reject) stats.RejectCount++;
            else stats.ReviewCount++;

            stats.TotalProcessingTimeMs += result.ProcessingTimeMs;
            stats.AverageProcessingTimeMs = stats.TotalProcessingTimeMs / stats.InspectionsCompleted;

            OnInspectionComplete?.Invoke(result);

            Debug.Log($"[Vision] Inspection complete: {result.OverallResult} ({result.ProcessingTimeMs:F1}ms)");
        }

        #endregion

        #region Profile & Model Management

        public void DefineProfile(InspectionProfile profile)
        {
            profiles[profile.ProfileId] = profile;
            Debug.Log($"[Vision] Defined profile: {profile.Name}");
        }

        public void RegisterModel(MLModel model)
        {
            loadedModels[model.ModelId] = model;
            Debug.Log($"[Vision] Registered model: {model.Name} ({model.Framework})");
        }

        public InspectionProfile GetProfile(string profileId)
        {
            return profiles.TryGetValue(profileId, out var profile) ? profile : null;
        }

        #endregion

        #region Calibration

        public IEnumerator CalibrateCamera(string cameraId, CalibrationTarget target, Action<CalibrationResult> callback)
        {
            if (!cameras.TryGetValue(cameraId, out var camera))
            {
                callback?.Invoke(new CalibrationResult { Success = false, ErrorMessage = "Camera not found" });
                yield break;
            }

            Debug.Log($"[Vision] Starting calibration for camera: {camera.Name}");

            var result = new CalibrationResult { CameraId = cameraId };

            // Capture calibration images
            List<CapturedImage> calibrationImages = new List<CapturedImage>();
            for (int i = 0; i < target.RequiredCaptures; i++)
            {
                yield return CaptureImage(cameraId, img => calibrationImages.Add(img));
                yield return new WaitForSeconds(0.5f);
            }

            // Process calibration (simplified)
            yield return new WaitForSeconds(1f);

            result.Success = true;
            result.ReprojectionError = UnityEngine.Random.Range(0.1f, 0.5f);
            result.CalibrationMatrix = Matrix4x4.identity;
            result.DistortionCoefficients = new float[] { 0, 0, 0, 0, 0 };

            camera.CalibrationMatrix = result.CalibrationMatrix;
            camera.DistortionCoefficients = result.DistortionCoefficients;
            camera.LastCalibration = DateTime.UtcNow;

            Debug.Log($"[Vision] Calibration complete. Reprojection error: {result.ReprojectionError:F3}");
            callback?.Invoke(result);
        }

        #endregion

        #region AR Overlay

        public void EnableAROverlay(string cameraId, AROverlayConfig config)
        {
            if (!cameras.TryGetValue(cameraId, out var camera))
            {
                Debug.LogWarning($"[Vision] Camera not found for AR overlay: {cameraId}");
                return;
            }

            camera.AROverlay = new AROverlay
            {
                Enabled = true,
                ShowDetections = config.ShowDetections,
                ShowMeasurements = config.ShowMeasurements,
                ShowDefects = config.ShowDefects,
                DetectionColor = config.DetectionColor,
                DefectColor = config.DefectColor,
                MeasurementColor = config.MeasurementColor,
                LabelFontSize = config.LabelFontSize,
                LineThickness = config.LineThickness
            };

            Debug.Log($"[Vision] AR overlay enabled for camera: {camera.Name}");
        }

        public void DisableAROverlay(string cameraId)
        {
            if (cameras.TryGetValue(cameraId, out var camera) && camera.AROverlay != null)
            {
                camera.AROverlay.Enabled = false;
            }
        }

        public Texture2D RenderAROverlay(string cameraId, CapturedImage image, InspectionResult result)
        {
            if (!cameras.TryGetValue(cameraId, out var camera) || camera.AROverlay == null || !camera.AROverlay.Enabled)
            {
                return null;
            }

            // Create texture from captured image
            var texture = new Texture2D(image.Width, image.Height, TextureFormat.RGB24, false);

            // Draw detections
            if (camera.AROverlay.ShowDetections && result.Detections != null)
            {
                foreach (var detection in result.Detections)
                {
                    DrawBoundingBox(texture, detection.BoundingBox, camera.AROverlay.DetectionColor);
                }
            }

            // Draw defects
            if (camera.AROverlay.ShowDefects && result.Defects != null)
            {
                foreach (var defect in result.Defects)
                {
                    DrawBoundingBox(texture, defect.BoundingBox, camera.AROverlay.DefectColor);
                }
            }

            texture.Apply();
            return texture;
        }

        private void DrawBoundingBox(Texture2D texture, Rect normalizedRect, Color color)
        {
            int x = (int)(normalizedRect.x * texture.width);
            int y = (int)(normalizedRect.y * texture.height);
            int w = (int)(normalizedRect.width * texture.width);
            int h = (int)(normalizedRect.height * texture.height);

            // Draw rectangle edges
            for (int i = 0; i < w; i++)
            {
                texture.SetPixel(x + i, y, color);
                texture.SetPixel(x + i, y + h, color);
            }
            for (int j = 0; j < h; j++)
            {
                texture.SetPixel(x, y + j, color);
                texture.SetPixel(x + w, y + j, color);
            }
        }

        #endregion

        #region Statistics & Reporting

        public VisionStats GetStatistics()
        {
            stats.ActiveCameras = cameras.Values.Count(c => c.IsConnected);
            stats.ActiveZones = zones.Values.Count(z => z.IsActive);
            stats.QueuedInspections = inspectionQueue.Count;
            stats.ActiveInspections = activeInspections;
            stats.IsConnected = isConnected;

            if (stats.InspectionsCompleted > 0)
            {
                stats.PassRate = (float)stats.PassCount / stats.InspectionsCompleted * 100f;
                stats.RejectRate = (float)stats.RejectCount / stats.InspectionsCompleted * 100f;
            }

            return stats;
        }

        public List<InspectionResult> GetRecentResults(int count = 100)
        {
            return recentResults.Take(count).ToList();
        }

        public InspectionSummary GetSummary(DateTime start, DateTime end)
        {
            var filteredResults = recentResults
                .Where(r => r.StartTime >= start && r.StartTime <= end)
                .ToList();

            return new InspectionSummary
            {
                StartTime = start,
                EndTime = end,
                TotalInspections = filteredResults.Count,
                PassCount = filteredResults.Count(r => r.OverallResult == InspectionVerdict.Pass),
                RejectCount = filteredResults.Count(r => r.OverallResult == InspectionVerdict.Reject),
                ReviewCount = filteredResults.Count(r => r.OverallResult == InspectionVerdict.Review),
                TotalDefects = filteredResults.Sum(r => r.Defects?.Count ?? 0),
                DefectsByType = filteredResults
                    .SelectMany(r => r.Defects ?? new List<DefectDetection>())
                    .GroupBy(d => d.DefectType)
                    .ToDictionary(g => g.Key, g => g.Count()),
                AverageProcessingTime = filteredResults.Average(r => r.ProcessingTimeMs)
            };
        }

        #endregion
    }

    #region Enums

    public enum CameraType
    {
        GigE,
        USB3,
        RTSP,
        Virtual,
        CoaXPress,
        CameraLink
    }

    public enum TriggerMode
    {
        Manual,
        Continuous,
        External,
        Software
    }

    public enum ModelType
    {
        Classification,
        ObjectDetection,
        Segmentation,
        Regression,
        OCR
    }

    public enum ImageFormat
    {
        RGB24,
        RGBA32,
        Grayscale,
        Bayer
    }

    public enum ToleranceClass
    {
        IT5, IT6, IT7, IT8, IT9, IT10, IT11, IT12
    }

    public enum InspectionStatus
    {
        Pending,
        Processing,
        Completed,
        Failed,
        Timeout
    }

    public enum InspectionVerdict
    {
        Pass,
        Reject,
        Review,
        Inconclusive
    }

    public enum InspectionPriority
    {
        Low,
        Normal,
        High,
        Critical
    }

    public enum DefectSeverity
    {
        Cosmetic,
        Minor,
        Major,
        Critical
    }

    #endregion

    #region Data Classes

    [System.Serializable]
    public class VisionCamera
    {
        public string CameraId;
        public string Name;
        public CameraType Type;
        public string ConnectionString;
        public Vector3 Position;
        public Quaternion Rotation;
        public float FieldOfView;
        public Vector2Int Resolution;
        public Matrix4x4 CalibrationMatrix;
        public float[] DistortionCoefficients;
        public DateTime LastCalibration;
        public bool IsConnected;
        public AROverlay AROverlay;

        public void Disconnect()
        {
            IsConnected = false;
        }
    }

    [System.Serializable]
    public class VisionCameraConfig
    {
        public string CameraId;
        public string Name;
        public CameraType Type;
        public string ConnectionString;
        public Vector3 Position;
        public Quaternion Rotation;
        public float FieldOfView;
        public Matrix4x4 CalibrationMatrix;
        public float[] DistortionCoefficients;
    }

    [System.Serializable]
    public class InspectionProfile
    {
        public string ProfileId;
        public string Name;
        public string ModelId;
        public string[] DefectTypes;
        public float MinDefectSize;
        public float MaxDefectSize;
        public Dictionary<string, float> SeverityThresholds;
        public string[] MeasurementTypes;
        public ToleranceClass ToleranceClass;
        public bool CalibrationRequired;
        public string[] RequiredParts;
        public bool VerifyOrientation;
        public bool VerifyCount;
        public string[] CodeTypes;
        public bool MultiCodeEnabled;
        public bool CheckComponents;
        public bool CheckOrientation;
        public bool CheckConnections;
    }

    [System.Serializable]
    public class InspectionZone
    {
        public string ZoneId;
        public string Name;
        public List<VisionCamera> Cameras;
        public InspectionProfile Profile;
        public TriggerMode TriggerMode;
        public Bounds Bounds;
        public bool IsActive;
    }

    [System.Serializable]
    public class InspectionZoneConfig
    {
        public string ZoneId;
        public string Name;
        public string[] CameraIds;
        public string ProfileId;
        public TriggerMode TriggerMode;
        public Bounds Bounds;
    }

    [System.Serializable]
    public class InspectionRequest
    {
        public string RequestId;
        public string ZoneId;
        public string ProfileId;
        public string CameraId;
        public string PartId;
        public InspectionPriority Priority;
    }

    [System.Serializable]
    public class InspectionResult
    {
        public string RequestId;
        public string ZoneId;
        public string ProfileId;
        public string CameraId;
        public string PartId;
        public string ImageId;
        public DateTime StartTime;
        public DateTime EndTime;
        public float ProcessingTimeMs;
        public InspectionStatus Status;
        public InspectionVerdict OverallResult;
        public string ErrorMessage;
        public List<ObjectDetection> Detections;
        public List<DefectDetection> Defects;
        public Dictionary<string, MeasurementResult> Measurements;
        public List<CodeReading> CodeReadings;
    }

    [System.Serializable]
    public class CapturedImage
    {
        public string CameraId;
        public DateTime CaptureTime;
        public int Width;
        public int Height;
        public ImageFormat Format;
        public float ExposureTime;
        public byte[] Data;
    }

    [System.Serializable]
    public class ObjectDetection
    {
        public string DetectionId;
        public string ClassName;
        public float Confidence;
        public Rect BoundingBox;
        public Vector2 Center;
        public float Angle;
    }

    [System.Serializable]
    public class DefectDetection
    {
        public string DefectId;
        public string DefectType;
        public float Confidence;
        public Rect BoundingBox;
        public float Area;
        public DefectSeverity Severity;
        public string Description;
    }

    [System.Serializable]
    public class MeasurementResult
    {
        public string MeasurementType;
        public float Value;
        public string Unit;
        public float Nominal;
        public float UpperTolerance;
        public float LowerTolerance;
        public bool InTolerance;
        public float Deviation;
    }

    [System.Serializable]
    public class CodeReading
    {
        public string CodeType;
        public string Data;
        public float Confidence;
        public Rect BoundingBox;
    }

    [System.Serializable]
    public class MLModel
    {
        public string ModelId;
        public string Name;
        public ModelType Type;
        public Vector2Int InputSize;
        public string[] OutputClasses;
        public string Version;
        public string Framework;
        public bool IsLoaded;
    }

    [System.Serializable]
    public class CalibrationTarget
    {
        public string TargetType; // Checkerboard, CircleGrid, etc.
        public int Rows;
        public int Columns;
        public float SquareSize;
        public int RequiredCaptures;
    }

    [System.Serializable]
    public class CalibrationResult
    {
        public string CameraId;
        public bool Success;
        public string ErrorMessage;
        public float ReprojectionError;
        public Matrix4x4 CalibrationMatrix;
        public float[] DistortionCoefficients;
    }

    [System.Serializable]
    public class AROverlay
    {
        public bool Enabled;
        public bool ShowDetections;
        public bool ShowMeasurements;
        public bool ShowDefects;
        public Color DetectionColor;
        public Color DefectColor;
        public Color MeasurementColor;
        public int LabelFontSize;
        public float LineThickness;
    }

    [System.Serializable]
    public class AROverlayConfig
    {
        public bool ShowDetections;
        public bool ShowMeasurements;
        public bool ShowDefects;
        public Color DetectionColor;
        public Color DefectColor;
        public Color MeasurementColor;
        public int LabelFontSize;
        public float LineThickness;
    }

    [System.Serializable]
    public class VisionStats
    {
        public int CamerasConnected;
        public int ActiveCameras;
        public int ActiveZones;
        public int QueuedInspections;
        public int ActiveInspections;
        public long InspectionsQueued;
        public long InspectionsCompleted;
        public long ImagesCaptures;
        public int PassCount;
        public int RejectCount;
        public int ReviewCount;
        public float PassRate;
        public float RejectRate;
        public float TotalProcessingTimeMs;
        public float AverageProcessingTimeMs;
        public bool IsConnected;
    }

    [System.Serializable]
    public class InspectionSummary
    {
        public DateTime StartTime;
        public DateTime EndTime;
        public int TotalInspections;
        public int PassCount;
        public int RejectCount;
        public int ReviewCount;
        public int TotalDefects;
        public Dictionary<string, int> DefectsByType;
        public float AverageProcessingTime;
    }

    #endregion
}
