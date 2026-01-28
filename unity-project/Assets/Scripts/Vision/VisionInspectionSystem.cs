using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;

namespace CNCScada.Vision
{
    /// <summary>
    /// Machine vision inspection system integration for quality control.
    /// Connects to vision systems for part inspection, measurement, and defect detection.
    /// Supports multiple camera views and inspection zones.
    /// </summary>
    public class VisionInspectionSystem : MonoBehaviour
    {
        [Header("Connection")]
        [SerializeField] private string visionServerUrl = "http://localhost:5001/api/vision";
        [SerializeField] private bool autoConnect = true;
        [SerializeField] private float reconnectInterval = 5f;

        [Header("Inspection Settings")]
        [SerializeField] private float inspectionInterval = 1f;
        [SerializeField] private bool continuousInspection = false;
        [SerializeField] private InspectionMode mode = InspectionMode.OnDemand;

        [Header("Cameras")]
        [SerializeField] private List<VisionCamera> cameras = new List<VisionCamera>();

        [Header("Inspection Zones")]
        [SerializeField] private List<InspectionZone> inspectionZones = new List<InspectionZone>();

        [Header("Status")]
        [SerializeField] private bool isConnected = false;
        [SerializeField] private int totalInspections;
        [SerializeField] private int passCount;
        [SerializeField] private int failCount;
        [SerializeField] private float passRate;

        // Current inspection data
        private InspectionResult lastResult;
        private Queue<InspectionResult> resultHistory = new Queue<InspectionResult>();
        private const int MaxHistorySize = 100;

        // Events
        public event Action<InspectionResult> OnInspectionComplete;
        public event Action<DefectInfo> OnDefectDetected;
        public event Action<MeasurementResult> OnMeasurementComplete;
        public event Action<bool> OnConnectionChanged;

        // Singleton
        public static VisionInspectionSystem Instance { get; private set; }

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
            }
            else
            {
                Destroy(gameObject);
                return;
            }

            InitializeDefaultZones();
        }

        private void Start()
        {
            if (autoConnect)
            {
                Connect();
            }

            if (continuousInspection)
            {
                StartContinuousInspection();
            }
        }

        private void InitializeDefaultZones()
        {
            if (inspectionZones.Count == 0)
            {
                // Add default inspection zone for CNC workpiece
                inspectionZones.Add(new InspectionZone
                {
                    zoneId = "cnc_workpiece",
                    zoneName = "CNC Workpiece Area",
                    position = new Vector3(0, 0.4f, -0.3f),
                    size = new Vector3(0.2f, 0.1f, 0.2f),
                    inspectionTypes = new List<InspectionType>
                    {
                        InspectionType.DimensionalMeasurement,
                        InspectionType.SurfaceDefect,
                        InspectionType.PresenceCheck
                    }
                });

                // Add inspection zone for parts bin
                inspectionZones.Add(new InspectionZone
                {
                    zoneId = "parts_bin_1",
                    zoneName = "Parts Bin 1",
                    position = new Vector3(0.4f, 0.15f, 0.3f),
                    size = new Vector3(0.2f, 0.15f, 0.15f),
                    inspectionTypes = new List<InspectionType>
                    {
                        InspectionType.PartCount,
                        InspectionType.PresenceCheck
                    }
                });
            }
        }

        // =========================================================================
        // Connection Management
        // =========================================================================

        public void Connect()
        {
            StartCoroutine(ConnectToVisionServer());
        }

        private IEnumerator ConnectToVisionServer()
        {
            Debug.Log($"[VisionInspection] Connecting to {visionServerUrl}");

            using (UnityWebRequest webRequest = UnityWebRequest.Get($"{visionServerUrl}/status"))
            {
                webRequest.timeout = 5;
                yield return webRequest.SendWebRequest();

                if (webRequest.result == UnityWebRequest.Result.Success)
                {
                    isConnected = true;
                    var status = JsonUtility.FromJson<VisionServerStatus>(webRequest.downloadHandler.text);

                    Debug.Log($"[VisionInspection] Connected - {status.cameraCount} cameras available");

                    // Update cameras from server
                    yield return StartCoroutine(LoadCameras());

                    OnConnectionChanged?.Invoke(true);
                }
                else
                {
                    isConnected = false;
                    Debug.LogWarning($"[VisionInspection] Connection failed: {webRequest.error}");
                    OnConnectionChanged?.Invoke(false);

                    // Schedule reconnect
                    yield return new WaitForSeconds(reconnectInterval);
                    Connect();
                }
            }
        }

        private IEnumerator LoadCameras()
        {
            using (UnityWebRequest webRequest = UnityWebRequest.Get($"{visionServerUrl}/cameras"))
            {
                webRequest.timeout = 5;
                yield return webRequest.SendWebRequest();

                if (webRequest.result == UnityWebRequest.Result.Success)
                {
                    var response = JsonUtility.FromJson<CameraListResponse>(webRequest.downloadHandler.text);

                    cameras.Clear();
                    foreach (var cam in response.cameras)
                    {
                        cameras.Add(cam);
                    }

                    Debug.Log($"[VisionInspection] Loaded {cameras.Count} cameras");
                }
            }
        }

        // =========================================================================
        // Inspection Operations
        // =========================================================================

        /// <summary>
        /// Trigger an inspection on a specific zone
        /// </summary>
        public void TriggerInspection(string zoneId)
        {
            var zone = inspectionZones.Find(z => z.zoneId == zoneId);
            if (zone != null)
            {
                StartCoroutine(PerformInspection(zone));
            }
            else
            {
                Debug.LogWarning($"[VisionInspection] Zone not found: {zoneId}");
            }
        }

        /// <summary>
        /// Trigger inspection on all zones
        /// </summary>
        public void TriggerFullInspection()
        {
            foreach (var zone in inspectionZones)
            {
                StartCoroutine(PerformInspection(zone));
            }
        }

        private IEnumerator PerformInspection(InspectionZone zone)
        {
            if (!isConnected)
            {
                Debug.LogWarning("[VisionInspection] Not connected to vision server");
                yield break;
            }

            Debug.Log($"[VisionInspection] Inspecting zone: {zone.zoneName}");

            var request = new InspectionRequest
            {
                zoneId = zone.zoneId,
                inspectionTypes = zone.inspectionTypes.ConvertAll(t => t.ToString()).ToArray(),
                timestamp = DateTime.Now.ToString("o")
            };

            string jsonBody = JsonUtility.ToJson(request);

            using (UnityWebRequest webRequest = new UnityWebRequest($"{visionServerUrl}/inspect", "POST"))
            {
                byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(jsonBody);
                webRequest.uploadHandler = new UploadHandlerRaw(bodyRaw);
                webRequest.downloadHandler = new DownloadHandlerBuffer();
                webRequest.SetRequestHeader("Content-Type", "application/json");
                webRequest.timeout = 10;

                yield return webRequest.SendWebRequest();

                if (webRequest.result == UnityWebRequest.Result.Success)
                {
                    var result = JsonUtility.FromJson<InspectionResult>(webRequest.downloadHandler.text);
                    ProcessInspectionResult(result);
                }
                else
                {
                    Debug.LogError($"[VisionInspection] Inspection failed: {webRequest.error}");

                    // Create a simulated result for demo purposes
                    var simulatedResult = SimulateInspection(zone);
                    ProcessInspectionResult(simulatedResult);
                }
            }
        }

        private InspectionResult SimulateInspection(InspectionZone zone)
        {
            // Simulate inspection for demo/offline mode
            var result = new InspectionResult
            {
                zoneId = zone.zoneId,
                zoneName = zone.zoneName,
                timestamp = DateTime.Now.ToString("o"),
                overallPass = UnityEngine.Random.value > 0.1f, // 90% pass rate simulation
                inspectionTimeMs = UnityEngine.Random.Range(50, 200),
                measurements = new List<MeasurementResult>(),
                defects = new List<DefectInfo>()
            };

            // Simulate measurements
            if (zone.inspectionTypes.Contains(InspectionType.DimensionalMeasurement))
            {
                result.measurements.Add(new MeasurementResult
                {
                    measurementId = "length",
                    measurementName = "Part Length",
                    measuredValue = 50.0f + UnityEngine.Random.Range(-0.5f, 0.5f),
                    nominalValue = 50.0f,
                    tolerance = 0.5f,
                    unit = "mm",
                    isInTolerance = true
                });

                result.measurements.Add(new MeasurementResult
                {
                    measurementId = "width",
                    measurementName = "Part Width",
                    measuredValue = 30.0f + UnityEngine.Random.Range(-0.3f, 0.3f),
                    nominalValue = 30.0f,
                    tolerance = 0.3f,
                    unit = "mm",
                    isInTolerance = true
                });
            }

            // Simulate occasional defect
            if (!result.overallPass && zone.inspectionTypes.Contains(InspectionType.SurfaceDefect))
            {
                result.defects.Add(new DefectInfo
                {
                    defectId = $"DEF_{DateTime.Now.Ticks}",
                    defectType = DefectType.Scratch,
                    severity = DefectSeverity.Minor,
                    location = new Vector2(25f, 15f),
                    size = 2.5f,
                    confidence = 0.85f
                });
            }

            return result;
        }

        private void ProcessInspectionResult(InspectionResult result)
        {
            lastResult = result;
            totalInspections++;

            if (result.overallPass)
            {
                passCount++;
            }
            else
            {
                failCount++;

                // Report defects
                foreach (var defect in result.defects)
                {
                    OnDefectDetected?.Invoke(defect);

                    // Raise alarm for critical defects
                    if (defect.severity == DefectSeverity.Critical)
                    {
                        var alarmSystem = FindObjectOfType<CNCScada.Alarms.AlarmSystem>();
                        alarmSystem?.RaiseCustomAlarm(
                            "Critical Defect Detected",
                            $"Critical {defect.defectType} defect found in {result.zoneName}",
                            CNCScada.Alarms.AlarmSeverity.High,
                            CNCScada.Alarms.AlarmCategory.Quality,
                            result.zoneId
                        );
                    }
                }
            }

            passRate = totalInspections > 0 ? (float)passCount / totalInspections * 100f : 0f;

            // Add to history
            resultHistory.Enqueue(result);
            while (resultHistory.Count > MaxHistorySize)
            {
                resultHistory.Dequeue();
            }

            // Report measurements
            foreach (var measurement in result.measurements)
            {
                OnMeasurementComplete?.Invoke(measurement);
            }

            OnInspectionComplete?.Invoke(result);

            string status = result.overallPass ? "PASS" : "FAIL";
            Debug.Log($"[VisionInspection] {result.zoneName}: {status} ({result.inspectionTimeMs}ms)");
        }

        /// <summary>
        /// Start continuous inspection mode
        /// </summary>
        public void StartContinuousInspection()
        {
            continuousInspection = true;
            StartCoroutine(ContinuousInspectionLoop());
        }

        /// <summary>
        /// Stop continuous inspection
        /// </summary>
        public void StopContinuousInspection()
        {
            continuousInspection = false;
        }

        private IEnumerator ContinuousInspectionLoop()
        {
            while (continuousInspection)
            {
                TriggerFullInspection();
                yield return new WaitForSeconds(inspectionInterval);
            }
        }

        // =========================================================================
        // Measurement Operations
        // =========================================================================

        /// <summary>
        /// Perform a specific measurement
        /// </summary>
        public void TakeMeasurement(string measurementType, string zoneId, Action<MeasurementResult> callback)
        {
            StartCoroutine(PerformMeasurement(measurementType, zoneId, callback));
        }

        private IEnumerator PerformMeasurement(string measurementType, string zoneId, Action<MeasurementResult> callback)
        {
            var request = new MeasurementRequest
            {
                measurementType = measurementType,
                zoneId = zoneId
            };

            string jsonBody = JsonUtility.ToJson(request);

            using (UnityWebRequest webRequest = new UnityWebRequest($"{visionServerUrl}/measure", "POST"))
            {
                byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(jsonBody);
                webRequest.uploadHandler = new UploadHandlerRaw(bodyRaw);
                webRequest.downloadHandler = new DownloadHandlerBuffer();
                webRequest.SetRequestHeader("Content-Type", "application/json");
                webRequest.timeout = 5;

                yield return webRequest.SendWebRequest();

                if (webRequest.result == UnityWebRequest.Result.Success)
                {
                    var result = JsonUtility.FromJson<MeasurementResult>(webRequest.downloadHandler.text);
                    callback?.Invoke(result);
                    OnMeasurementComplete?.Invoke(result);
                }
                else
                {
                    Debug.LogError($"[VisionInspection] Measurement failed: {webRequest.error}");
                    callback?.Invoke(null);
                }
            }
        }

        // =========================================================================
        // Camera Operations
        // =========================================================================

        /// <summary>
        /// Capture image from a camera
        /// </summary>
        public void CaptureImage(string cameraId, Action<Texture2D> callback)
        {
            StartCoroutine(CaptureImageFromCamera(cameraId, callback));
        }

        private IEnumerator CaptureImageFromCamera(string cameraId, Action<Texture2D> callback)
        {
            using (UnityWebRequest webRequest = UnityWebRequestTexture.GetTexture($"{visionServerUrl}/capture/{cameraId}"))
            {
                webRequest.timeout = 5;
                yield return webRequest.SendWebRequest();

                if (webRequest.result == UnityWebRequest.Result.Success)
                {
                    Texture2D texture = DownloadHandlerTexture.GetContent(webRequest);
                    callback?.Invoke(texture);
                }
                else
                {
                    Debug.LogError($"[VisionInspection] Capture failed: {webRequest.error}");
                    callback?.Invoke(null);
                }
            }
        }

        // =========================================================================
        // Visualization
        // =========================================================================

        private void OnDrawGizmos()
        {
            // Draw inspection zones
            Gizmos.color = new Color(0, 1, 1, 0.3f);

            foreach (var zone in inspectionZones)
            {
                Gizmos.DrawWireCube(zone.position, zone.size);

                // Color based on last result
                if (lastResult != null && lastResult.zoneId == zone.zoneId)
                {
                    Gizmos.color = lastResult.overallPass ?
                        new Color(0, 1, 0, 0.3f) :
                        new Color(1, 0, 0, 0.3f);

                    Gizmos.DrawCube(zone.position, zone.size);
                }
            }
        }

        // =========================================================================
        // Public API
        // =========================================================================

        public InspectionResult GetLastResult() => lastResult;
        public List<InspectionResult> GetResultHistory() => new List<InspectionResult>(resultHistory);
        public List<VisionCamera> GetCameras() => new List<VisionCamera>(cameras);
        public List<InspectionZone> GetInspectionZones() => new List<InspectionZone>(inspectionZones);

        public void AddInspectionZone(InspectionZone zone)
        {
            inspectionZones.Add(zone);
        }

        public void RemoveInspectionZone(string zoneId)
        {
            inspectionZones.RemoveAll(z => z.zoneId == zoneId);
        }

        // Properties
        public bool IsConnected => isConnected;
        public int TotalInspections => totalInspections;
        public int PassCount => passCount;
        public int FailCount => failCount;
        public float PassRate => passRate;
    }

    // =========================================================================
    // Data Types
    // =========================================================================

    public enum InspectionMode
    {
        OnDemand,
        Continuous,
        Triggered
    }

    public enum InspectionType
    {
        DimensionalMeasurement,
        SurfaceDefect,
        ColorCheck,
        PresenceCheck,
        PartCount,
        BarcodeScan,
        OCR,
        PatternMatch
    }

    public enum DefectType
    {
        Scratch,
        Dent,
        Crack,
        Discoloration,
        Burr,
        MissingFeature,
        Contamination,
        Deformation,
        Other
    }

    public enum DefectSeverity
    {
        Minor,
        Major,
        Critical
    }

    [Serializable]
    public class VisionCamera
    {
        public string cameraId;
        public string cameraName;
        public string cameraType;
        public int resolutionWidth;
        public int resolutionHeight;
        public bool isOnline;
        public Vector3 position;
        public Vector3 rotation;
    }

    [Serializable]
    public class InspectionZone
    {
        public string zoneId;
        public string zoneName;
        public Vector3 position;
        public Vector3 size;
        public List<InspectionType> inspectionTypes;
        public string linkedCameraId;
    }

    [Serializable]
    public class InspectionRequest
    {
        public string zoneId;
        public string[] inspectionTypes;
        public string timestamp;
    }

    [Serializable]
    public class InspectionResult
    {
        public string zoneId;
        public string zoneName;
        public string timestamp;
        public bool overallPass;
        public int inspectionTimeMs;
        public List<MeasurementResult> measurements;
        public List<DefectInfo> defects;
    }

    [Serializable]
    public class MeasurementRequest
    {
        public string measurementType;
        public string zoneId;
    }

    [Serializable]
    public class MeasurementResult
    {
        public string measurementId;
        public string measurementName;
        public float measuredValue;
        public float nominalValue;
        public float tolerance;
        public string unit;
        public bool isInTolerance;

        public float Deviation => measuredValue - nominalValue;
        public float DeviationPercent => nominalValue != 0 ? (Deviation / nominalValue) * 100f : 0f;
    }

    [Serializable]
    public class DefectInfo
    {
        public string defectId;
        public DefectType defectType;
        public DefectSeverity severity;
        public Vector2 location;
        public float size;
        public float confidence;
        public string description;
    }

    [Serializable]
    public class VisionServerStatus
    {
        public bool online;
        public int cameraCount;
        public string version;
    }

    [Serializable]
    public class CameraListResponse
    {
        public VisionCamera[] cameras;
    }
}
