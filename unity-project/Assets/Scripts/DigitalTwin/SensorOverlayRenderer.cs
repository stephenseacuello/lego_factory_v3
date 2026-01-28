using UnityEngine;
using System;
using System.Collections.Generic;

namespace CNCScada.DigitalTwin
{
    /// <summary>
    /// Sensor Overlay Renderer for Heatmaps and Vibration Visualization
    /// Displays thermal, vibration, and other sensor data as 3D overlays
    /// Part of Phase 2: Real-Time Visualization (60Hz)
    /// </summary>
    public class SensorOverlayRenderer : MonoBehaviour
    {
        [Header("Machine References")]
        [SerializeField] private Transform machineTransform;
        [SerializeField] private List<Transform> sensorLocations = new List<Transform>();

        [Header("Heatmap Settings")]
        [SerializeField] private bool enableThermalOverlay = true;
        [SerializeField] private Material heatmapMaterial;
        [SerializeField] private Gradient temperatureGradient;
        [SerializeField] private float minTemperature = 20f; // Celsius
        [SerializeField] private float maxTemperature = 150f; // Celsius
        [SerializeField] private float heatmapUpdateRate = 2f; // Hz

        [Header("Vibration Visualization")]
        [SerializeField] private bool enableVibrationOverlay = true;
        [SerializeField] private GameObject vibrationMarkerPrefab;
        [SerializeField] private float vibrationThreshold = 0.5f; // m/s²
        [SerializeField] private float vibrationScale = 0.01f;
        [SerializeField] private Color lowVibrationColor = Color.green;
        [SerializeField] private Color highVibrationColor = Color.red;

        [Header("Force Visualization")]
        [SerializeField] private bool enableForceVectors = true;
        [SerializeField] private float forceVectorScale = 0.001f;
        [SerializeField] private Color forceVectorColor = Color.yellow;
        [SerializeField] private float forceThreshold = 10f; // Newtons

        [Header("Pressure Mapping")]
        [SerializeField] private bool enablePressureMap = false;
        [SerializeField] private Material pressureMaterial;
        [SerializeField] private float minPressure = 0f; // bar
        [SerializeField] private float maxPressure = 10f; // bar

        [Header("Sound Level Visualization")]
        [SerializeField] private bool enableSoundLevel = false;
        [SerializeField] private GameObject soundWavePrefab;
        [SerializeField] private float soundLevelThreshold = 80f; // dB
        [SerializeField] private Color soundWaveColor = Color.cyan;

        [Header("Performance")]
        [SerializeField] private int maxParticles = 1000;
        [SerializeField] private bool enableParticlePooling = true;
        [SerializeField] private float cullingDistance = 20f;

        // Sensor data
        private Dictionary<string, SensorData> sensorReadings = new Dictionary<string, SensorData>();
        private List<GameObject> activeVibrationMarkers = new List<GameObject>();
        private List<GameObject> particlePool = new List<GameObject>();

        // Heatmap mesh
        private MeshRenderer heatmapRenderer;
        private Texture2D heatmapTexture;
        private int heatmapResolution = 128;

        // Update timing
        private float lastHeatmapUpdate = 0f;
        private float heatmapUpdateInterval;

        // Statistics
        private int totalSensors = 0;
        private int activeSensors = 0;
        private float averageSensorValue = 0f;

        // Events
        public event Action<string, float> OnSensorThresholdExceeded;
        public event Action<string, SensorData> OnSensorDataUpdated;

        [Serializable]
        public class SensorData
        {
            public string sensorId;
            public string sensorType; // temperature, vibration, force, pressure, sound
            public Vector3 position;
            public float value;
            public float timestamp;
            public bool isAbnormal;
            public string unit;
        }

        void Start()
        {
            heatmapUpdateInterval = 1f / heatmapUpdateRate;

            // Initialize temperature gradient if not set
            if (temperatureGradient == null)
            {
                temperatureGradient = new Gradient();
                GradientColorKey[] colorKeys = new GradientColorKey[5];
                colorKeys[0] = new GradientColorKey(Color.blue, 0f);       // Cold
                colorKeys[1] = new GradientColorKey(Color.cyan, 0.25f);    // Cool
                colorKeys[2] = new GradientColorKey(Color.green, 0.5f);    // Normal
                colorKeys[3] = new GradientColorKey(Color.yellow, 0.75f);  // Warm
                colorKeys[4] = new GradientColorKey(Color.red, 1f);        // Hot
                GradientAlphaKey[] alphaKeys = new GradientAlphaKey[2];
                alphaKeys[0] = new GradientAlphaKey(0.7f, 0f);
                alphaKeys[1] = new GradientAlphaKey(0.7f, 1f);
                temperatureGradient.SetKeys(colorKeys, alphaKeys);
            }

            SetupHeatmapRenderer();
            InitializeParticlePool();

            Debug.Log("[SensorOverlayRenderer] Initialized");
        }

        void SetupHeatmapRenderer()
        {
            if (!enableThermalOverlay || machineTransform == null) return;

            GameObject heatmapObj = new GameObject("ThermalHeatmap");
            heatmapObj.transform.SetParent(machineTransform);
            heatmapObj.transform.localPosition = Vector3.zero;
            heatmapObj.transform.localRotation = Quaternion.identity;

            // Create quad mesh for heatmap
            MeshFilter meshFilter = heatmapObj.AddComponent<MeshFilter>();
            heatmapRenderer = heatmapObj.AddComponent<MeshRenderer>();

            Mesh mesh = new Mesh();
            Vector3[] vertices = new Vector3[4]
            {
                new Vector3(-0.5f, 0, -0.5f),
                new Vector3(0.5f, 0, -0.5f),
                new Vector3(-0.5f, 0, 0.5f),
                new Vector3(0.5f, 0, 0.5f)
            };
            int[] triangles = new int[6] { 0, 2, 1, 2, 3, 1 };
            Vector2[] uvs = new Vector2[4]
            {
                new Vector2(0, 0),
                new Vector2(1, 0),
                new Vector2(0, 1),
                new Vector2(1, 1)
            };

            mesh.vertices = vertices;
            mesh.triangles = triangles;
            mesh.uv = uvs;
            mesh.RecalculateNormals();
            meshFilter.mesh = mesh;

            // Create heatmap texture
            heatmapTexture = new Texture2D(heatmapResolution, heatmapResolution, TextureFormat.RGBA32, false);
            heatmapTexture.filterMode = FilterMode.Bilinear;
            heatmapTexture.wrapMode = TextureWrapMode.Clamp;

            // Apply material
            if (heatmapMaterial != null)
            {
                heatmapRenderer.material = heatmapMaterial;
                heatmapRenderer.material.mainTexture = heatmapTexture;
            }
            else
            {
                heatmapRenderer.material = new Material(Shader.Find("Unlit/Transparent"));
                heatmapRenderer.material.mainTexture = heatmapTexture;
            }
        }

        void InitializeParticlePool()
        {
            if (!enableParticlePooling) return;

            for (int i = 0; i < maxParticles; i++)
            {
                GameObject particle = CreateParticle();
                particle.SetActive(false);
                particlePool.Add(particle);
            }
        }

        GameObject CreateParticle()
        {
            if (vibrationMarkerPrefab != null)
            {
                return Instantiate(vibrationMarkerPrefab, transform);
            }

            GameObject particle = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            particle.transform.SetParent(transform);
            particle.transform.localScale = Vector3.one * 0.02f;
            Destroy(particle.GetComponent<Collider>());
            return particle;
        }

        GameObject GetPooledParticle()
        {
            foreach (var particle in particlePool)
            {
                if (!particle.activeInHierarchy)
                {
                    particle.SetActive(true);
                    return particle;
                }
            }

            // Create new if pool exhausted
            if (particlePool.Count < maxParticles)
            {
                GameObject newParticle = CreateParticle();
                particlePool.Add(newParticle);
                return newParticle;
            }

            return null;
        }

        void Update()
        {
            // Update heatmap at configured rate
            if (enableThermalOverlay && Time.time - lastHeatmapUpdate > heatmapUpdateInterval)
            {
                UpdateHeatmap();
                lastHeatmapUpdate = Time.time;
            }

            // Update vibration markers
            if (enableVibrationOverlay)
            {
                UpdateVibrationVisualization();
            }

            // Cull distant overlays
            CullDistantOverlays();
        }

        void UpdateHeatmap()
        {
            if (heatmapTexture == null || sensorReadings.Count == 0) return;

            Color[] pixels = new Color[heatmapResolution * heatmapResolution];

            // Get temperature sensor readings
            List<SensorData> tempSensors = new List<SensorData>();
            foreach (var reading in sensorReadings.Values)
            {
                if (reading.sensorType == "temperature")
                {
                    tempSensors.Add(reading);
                }
            }

            // Generate heatmap using interpolation
            for (int y = 0; y < heatmapResolution; y++)
            {
                for (int x = 0; x < heatmapResolution; x++)
                {
                    Vector2 uv = new Vector2((float)x / heatmapResolution, (float)y / heatmapResolution);
                    float temperature = InterpolateTemperature(uv, tempSensors);
                    float t = Mathf.InverseLerp(minTemperature, maxTemperature, temperature);
                    pixels[y * heatmapResolution + x] = temperatureGradient.Evaluate(t);
                }
            }

            heatmapTexture.SetPixels(pixels);
            heatmapTexture.Apply();
        }

        float InterpolateTemperature(Vector2 uv, List<SensorData> sensors)
        {
            if (sensors.Count == 0) return minTemperature;

            float totalWeight = 0f;
            float weightedSum = 0f;

            foreach (var sensor in sensors)
            {
                // Convert sensor position to UV space
                Vector2 sensorUV = WorldToUV(sensor.position);
                float distance = Vector2.Distance(uv, sensorUV);

                // Inverse distance weighting
                float weight = 1f / (distance + 0.01f);
                totalWeight += weight;
                weightedSum += sensor.value * weight;
            }

            return weightedSum / totalWeight;
        }

        Vector2 WorldToUV(Vector3 worldPos)
        {
            if (machineTransform == null) return Vector2.zero;

            Vector3 localPos = machineTransform.InverseTransformPoint(worldPos);
            float u = Mathf.Clamp01(localPos.x + 0.5f);
            float v = Mathf.Clamp01(localPos.z + 0.5f);
            return new Vector2(u, v);
        }

        void UpdateVibrationVisualization()
        {
            // Clear old markers
            foreach (var marker in activeVibrationMarkers)
            {
                if (marker != null) marker.SetActive(false);
            }
            activeVibrationMarkers.Clear();

            // Create new markers for vibration data
            foreach (var reading in sensorReadings.Values)
            {
                if (reading.sensorType == "vibration" && reading.value > vibrationThreshold)
                {
                    GameObject marker = GetPooledParticle();
                    if (marker != null)
                    {
                        marker.transform.position = reading.position;
                        float intensity = Mathf.InverseLerp(vibrationThreshold, vibrationThreshold * 3f, reading.value);
                        marker.transform.localScale = Vector3.one * vibrationScale * (1f + intensity);

                        Renderer renderer = marker.GetComponent<Renderer>();
                        if (renderer != null)
                        {
                            renderer.material.color = Color.Lerp(lowVibrationColor, highVibrationColor, intensity);
                        }

                        activeVibrationMarkers.Add(marker);
                    }
                }
            }
        }

        void CullDistantOverlays()
        {
            Camera mainCamera = Camera.main;
            if (mainCamera == null) return;

            float distanceSqr = (mainCamera.transform.position - transform.position).sqrMagnitude;
            float cullingDistanceSqr = cullingDistance * cullingDistance;

            bool shouldRender = distanceSqr < cullingDistanceSqr;

            if (heatmapRenderer != null)
            {
                heatmapRenderer.enabled = shouldRender && enableThermalOverlay;
            }

            if (!shouldRender)
            {
                foreach (var marker in activeVibrationMarkers)
                {
                    if (marker != null) marker.SetActive(false);
                }
            }
        }

        /// <summary>
        /// Update sensor reading
        /// </summary>
        public void UpdateSensorData(SensorData data)
        {
            if (data == null) return;

            sensorReadings[data.sensorId] = data;

            // Check thresholds
            CheckThresholds(data);

            OnSensorDataUpdated?.Invoke(data.sensorId, data);

            // Update statistics
            UpdateStatistics();
        }

        /// <summary>
        /// Batch update multiple sensors
        /// </summary>
        public void UpdateSensorDataBatch(List<SensorData> dataList)
        {
            foreach (var data in dataList)
            {
                UpdateSensorData(data);
            }
        }

        void CheckThresholds(SensorData data)
        {
            bool thresholdExceeded = false;

            switch (data.sensorType)
            {
                case "temperature":
                    if (data.value > maxTemperature * 0.9f)
                    {
                        thresholdExceeded = true;
                        data.isAbnormal = true;
                    }
                    break;

                case "vibration":
                    if (data.value > vibrationThreshold * 2f)
                    {
                        thresholdExceeded = true;
                        data.isAbnormal = true;
                    }
                    break;

                case "force":
                    if (data.value > forceThreshold * 1.5f)
                    {
                        thresholdExceeded = true;
                        data.isAbnormal = true;
                    }
                    break;

                case "sound":
                    if (data.value > soundLevelThreshold)
                    {
                        thresholdExceeded = true;
                        data.isAbnormal = true;
                    }
                    break;
            }

            if (thresholdExceeded)
            {
                OnSensorThresholdExceeded?.Invoke(data.sensorId, data.value);
            }
        }

        void UpdateStatistics()
        {
            totalSensors = sensorReadings.Count;
            activeSensors = 0;
            float sum = 0f;

            foreach (var reading in sensorReadings.Values)
            {
                if (Time.time - reading.timestamp < 5f) // Active in last 5 seconds
                {
                    activeSensors++;
                    sum += reading.value;
                }
            }

            averageSensorValue = activeSensors > 0 ? sum / activeSensors : 0f;
        }

        /// <summary>
        /// Clear all sensor data
        /// </summary>
        public void ClearSensorData()
        {
            sensorReadings.Clear();
            foreach (var marker in activeVibrationMarkers)
            {
                if (marker != null) marker.SetActive(false);
            }
            activeVibrationMarkers.Clear();

            Debug.Log("[SensorOverlayRenderer] Sensor data cleared");
        }

        /// <summary>
        /// Get sensor data by ID
        /// </summary>
        public SensorData GetSensorData(string sensorId)
        {
            return sensorReadings.ContainsKey(sensorId) ? sensorReadings[sensorId] : null;
        }

        /// <summary>
        /// Get all sensors of a specific type
        /// </summary>
        public List<SensorData> GetSensorsByType(string sensorType)
        {
            List<SensorData> result = new List<SensorData>();
            foreach (var reading in sensorReadings.Values)
            {
                if (reading.sensorType == sensorType)
                {
                    result.Add(reading);
                }
            }
            return result;
        }

        public Dictionary<string, object> GetStatistics()
        {
            return new Dictionary<string, object>
            {
                {"total_sensors", totalSensors},
                {"active_sensors", activeSensors},
                {"average_sensor_value", averageSensorValue},
                {"thermal_overlay_enabled", enableThermalOverlay},
                {"vibration_overlay_enabled", enableVibrationOverlay},
                {"active_vibration_markers", activeVibrationMarkers.Count},
                {"heatmap_resolution", heatmapResolution},
                {"update_rate_hz", heatmapUpdateRate}
            };
        }

        void OnDrawGizmos()
        {
            if (!Application.isPlaying) return;

            // Draw sensor locations
            foreach (var location in sensorLocations)
            {
                if (location != null)
                {
                    Gizmos.color = Color.yellow;
                    Gizmos.DrawWireSphere(location.position, 0.02f);
                }
            }

            // Draw force vectors
            if (enableForceVectors)
            {
                foreach (var reading in sensorReadings.Values)
                {
                    if (reading.sensorType == "force" && reading.value > forceThreshold)
                    {
                        Gizmos.color = forceVectorColor;
                        Vector3 forceVector = Vector3.up * reading.value * forceVectorScale;
                        Gizmos.DrawRay(reading.position, forceVector);
                    }
                }
            }

            // Draw abnormal sensor warnings
            foreach (var reading in sensorReadings.Values)
            {
                if (reading.isAbnormal)
                {
                    Gizmos.color = Color.red;
                    Gizmos.DrawWireSphere(reading.position, 0.05f);
                }
            }
        }
    }
}
