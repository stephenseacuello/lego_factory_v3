using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace CNCScada.Sensors
{
    /// <summary>
    /// Sensor visualization system for Digital Twin.
    /// Provides heatmaps, gauges, 3D overlays, and alert indicators.
    /// </summary>
    public class SensorVisualization : MonoBehaviour
    {
        [Header("Visualization Settings")]
        public bool enableHeatmaps = true;
        public bool enableGauges = true;
        public bool enable3DOverlays = true;
        public bool enableAlertIndicators = true;

        [Header("Heatmap Settings")]
        public Gradient temperatureGradient;
        public Gradient vibrationGradient;
        public Gradient loadGradient;
        public float heatmapUpdateRate = 0.1f;

        [Header("Gauge Prefabs")]
        public GameObject radialGaugePrefab;
        public GameObject linearGaugePrefab;
        public GameObject digitalDisplayPrefab;

        [Header("3D Overlay Settings")]
        public Material overlayMaterial;
        public float overlayOpacity = 0.5f;
        public bool showVibrationParticles = true;

        [Header("Alert Settings")]
        public Color normalColor = new Color(0.2f, 0.8f, 0.2f);
        public Color warningColor = new Color(1f, 0.8f, 0f);
        public Color criticalColor = new Color(1f, 0.2f, 0.2f);
        public float alertPulseSpeed = 2f;

        // Internal state
        private Dictionary<string, SensorGauge> activeGauges = new Dictionary<string, SensorGauge>();
        private Dictionary<string, HeatmapOverlay> activeHeatmaps = new Dictionary<string, HeatmapOverlay>();
        private Dictionary<string, AlertIndicator> activeAlerts = new Dictionary<string, AlertIndicator>();
        private float lastHeatmapUpdate;

        // Singleton
        public static SensorVisualization Instance { get; private set; }

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

            InitializeGradients();
        }

        private void Start()
        {
            // Subscribe to sensor system events
            if (SensorSystem.Instance != null)
            {
                SensorSystem.Instance.OnSensorReading += HandleSensorReading;
                SensorSystem.Instance.OnSensorAlert += HandleSensorAlert;
            }
        }

        private void Update()
        {
            // Update heatmaps at configured rate
            if (enableHeatmaps && Time.time - lastHeatmapUpdate >= heatmapUpdateRate)
            {
                UpdateAllHeatmaps();
                lastHeatmapUpdate = Time.time;
            }

            // Update alert indicators
            if (enableAlertIndicators)
            {
                UpdateAlertIndicators();
            }
        }

        private void OnDestroy()
        {
            if (SensorSystem.Instance != null)
            {
                SensorSystem.Instance.OnSensorReading -= HandleSensorReading;
                SensorSystem.Instance.OnSensorAlert -= HandleSensorAlert;
            }
        }

        private void InitializeGradients()
        {
            // Temperature gradient: Blue (cold) -> Green (normal) -> Yellow (warm) -> Red (hot)
            if (temperatureGradient == null || temperatureGradient.colorKeys.Length == 0)
            {
                temperatureGradient = new Gradient();
                temperatureGradient.SetKeys(
                    new GradientColorKey[]
                    {
                        new GradientColorKey(new Color(0.2f, 0.4f, 1f), 0f),    // Cold (blue)
                        new GradientColorKey(new Color(0.2f, 0.8f, 0.2f), 0.3f), // Normal (green)
                        new GradientColorKey(new Color(1f, 1f, 0.2f), 0.6f),    // Warm (yellow)
                        new GradientColorKey(new Color(1f, 0.2f, 0.2f), 1f)     // Hot (red)
                    },
                    new GradientAlphaKey[] { new GradientAlphaKey(1f, 0f), new GradientAlphaKey(1f, 1f) }
                );
            }

            // Vibration gradient: Green (low) -> Yellow (medium) -> Red (high)
            if (vibrationGradient == null || vibrationGradient.colorKeys.Length == 0)
            {
                vibrationGradient = new Gradient();
                vibrationGradient.SetKeys(
                    new GradientColorKey[]
                    {
                        new GradientColorKey(new Color(0.2f, 0.8f, 0.2f), 0f),
                        new GradientColorKey(new Color(1f, 0.8f, 0.2f), 0.5f),
                        new GradientColorKey(new Color(1f, 0.2f, 0.2f), 1f)
                    },
                    new GradientAlphaKey[] { new GradientAlphaKey(1f, 0f), new GradientAlphaKey(1f, 1f) }
                );
            }

            // Load gradient: Green (low) -> Yellow (medium) -> Red (high)
            if (loadGradient == null || loadGradient.colorKeys.Length == 0)
            {
                loadGradient = new Gradient();
                loadGradient.SetKeys(
                    new GradientColorKey[]
                    {
                        new GradientColorKey(new Color(0.2f, 0.8f, 0.2f), 0f),
                        new GradientColorKey(new Color(0.8f, 0.8f, 0.2f), 0.6f),
                        new GradientColorKey(new Color(1f, 0.4f, 0.2f), 0.8f),
                        new GradientColorKey(new Color(1f, 0.2f, 0.2f), 1f)
                    },
                    new GradientAlphaKey[] { new GradientAlphaKey(1f, 0f), new GradientAlphaKey(1f, 1f) }
                );
            }
        }

        // =========================================================================
        // Gauge Management
        // =========================================================================

        /// <summary>
        /// Create a radial gauge for a sensor
        /// </summary>
        public SensorGauge CreateRadialGauge(string sensorId, Vector3 worldPosition, float minValue, float maxValue, string label)
        {
            var gaugeObj = new GameObject($"RadialGauge_{sensorId}");
            gaugeObj.transform.position = worldPosition;

            var gauge = gaugeObj.AddComponent<RadialGauge>();
            gauge.Initialize(sensorId, minValue, maxValue, label);

            activeGauges[sensorId] = gauge;
            return gauge;
        }

        /// <summary>
        /// Create a linear gauge for a sensor
        /// </summary>
        public SensorGauge CreateLinearGauge(string sensorId, Vector3 worldPosition, float minValue, float maxValue, string label, bool vertical = true)
        {
            var gaugeObj = new GameObject($"LinearGauge_{sensorId}");
            gaugeObj.transform.position = worldPosition;

            var gauge = gaugeObj.AddComponent<LinearGauge>();
            gauge.Initialize(sensorId, minValue, maxValue, label);
            ((LinearGauge)gauge).isVertical = vertical;

            activeGauges[sensorId] = gauge;
            return gauge;
        }

        /// <summary>
        /// Create a digital display for a sensor
        /// </summary>
        public SensorGauge CreateDigitalDisplay(string sensorId, Vector3 worldPosition, string label, string unit)
        {
            var displayObj = new GameObject($"DigitalDisplay_{sensorId}");
            displayObj.transform.position = worldPosition;

            var display = displayObj.AddComponent<DigitalDisplay>();
            display.Initialize(sensorId, 0, 100, label);
            display.unit = unit;

            activeGauges[sensorId] = display;
            return display;
        }

        // =========================================================================
        // Heatmap Management
        // =========================================================================

        /// <summary>
        /// Create a temperature heatmap overlay on a mesh
        /// </summary>
        public HeatmapOverlay CreateTemperatureHeatmap(string id, MeshRenderer targetMesh, float minTemp, float maxTemp)
        {
            var heatmap = targetMesh.gameObject.AddComponent<HeatmapOverlay>();
            heatmap.Initialize(id, HeatmapType.Temperature, targetMesh, temperatureGradient);
            heatmap.minValue = minTemp;
            heatmap.maxValue = maxTemp;

            activeHeatmaps[id] = heatmap;
            return heatmap;
        }

        /// <summary>
        /// Create a vibration heatmap overlay
        /// </summary>
        public HeatmapOverlay CreateVibrationHeatmap(string id, MeshRenderer targetMesh, float maxVibration)
        {
            var heatmap = targetMesh.gameObject.AddComponent<HeatmapOverlay>();
            heatmap.Initialize(id, HeatmapType.Vibration, targetMesh, vibrationGradient);
            heatmap.minValue = 0;
            heatmap.maxValue = maxVibration;

            activeHeatmaps[id] = heatmap;
            return heatmap;
        }

        /// <summary>
        /// Create a load heatmap overlay
        /// </summary>
        public HeatmapOverlay CreateLoadHeatmap(string id, MeshRenderer targetMesh, float maxLoad)
        {
            var heatmap = targetMesh.gameObject.AddComponent<HeatmapOverlay>();
            heatmap.Initialize(id, HeatmapType.Load, targetMesh, loadGradient);
            heatmap.minValue = 0;
            heatmap.maxValue = maxLoad;

            activeHeatmaps[id] = heatmap;
            return heatmap;
        }

        private void UpdateAllHeatmaps()
        {
            foreach (var heatmap in activeHeatmaps.Values)
            {
                heatmap.UpdateVisualization();
            }
        }

        // =========================================================================
        // Alert Indicators
        // =========================================================================

        /// <summary>
        /// Create an alert indicator at a position
        /// </summary>
        public AlertIndicator CreateAlertIndicator(string sensorId, Vector3 worldPosition)
        {
            var indicatorObj = new GameObject($"AlertIndicator_{sensorId}");
            indicatorObj.transform.position = worldPosition;

            var indicator = indicatorObj.AddComponent<AlertIndicator>();
            indicator.Initialize(sensorId, normalColor, warningColor, criticalColor);

            activeAlerts[sensorId] = indicator;
            return indicator;
        }

        private void UpdateAlertIndicators()
        {
            float pulse = (Mathf.Sin(Time.time * alertPulseSpeed * Mathf.PI) + 1f) * 0.5f;

            foreach (var alert in activeAlerts.Values)
            {
                alert.UpdatePulse(pulse);
            }
        }

        // =========================================================================
        // Event Handlers
        // =========================================================================

        private void HandleSensorReading(SensorReading reading)
        {
            // Update associated gauge
            if (activeGauges.TryGetValue(reading.sensorId, out var gauge))
            {
                gauge.UpdateValue(reading.value);
            }

            // Update associated heatmap
            if (activeHeatmaps.TryGetValue(reading.sensorId, out var heatmap))
            {
                heatmap.UpdateValue(reading.value);
            }

            // Update alert indicator
            if (activeAlerts.TryGetValue(reading.sensorId, out var alert))
            {
                alert.UpdateStatus(reading.status);
            }
        }

        private void HandleSensorAlert(SensorAlert alert)
        {
            // Show alert notification
            ShowAlertNotification(alert);

            // Update alert indicator
            if (activeAlerts.TryGetValue(alert.sensorId, out var indicator))
            {
                indicator.TriggerAlert(alert.alertLevel);
            }
        }

        /// <summary>
        /// Display an alert notification in the UI
        /// </summary>
        public void ShowAlertNotification(SensorAlert alert)
        {
            Debug.LogWarning($"[SensorViz] ALERT: {alert.message}");

            // Create floating alert if in 3D mode
            if (enable3DOverlays)
            {
                CreateFloatingAlert(alert);
            }
        }

        private void CreateFloatingAlert(SensorAlert alert)
        {
            // Create a floating text alert in 3D space
            var alertObj = new GameObject($"FloatingAlert_{alert.sensorId}");

            // Position near the sensor (if we have its location)
            if (activeAlerts.TryGetValue(alert.sensorId, out var indicator))
            {
                alertObj.transform.position = indicator.transform.position + Vector3.up * 0.2f;
            }

            var textMesh = alertObj.AddComponent<TextMesh>();
            textMesh.text = alert.message;
            textMesh.fontSize = 12;
            textMesh.color = alert.alertLevel == AlertLevel.Critical ? criticalColor : warningColor;
            textMesh.alignment = TextAlignment.Center;
            textMesh.anchor = TextAnchor.MiddleCenter;

            // Face camera
            alertObj.AddComponent<FaceCamera>();

            // Auto-destroy after 5 seconds
            Destroy(alertObj, 5f);
        }

        // =========================================================================
        // Utility Methods
        // =========================================================================

        /// <summary>
        /// Create visualization setup for a machine
        /// </summary>
        public void SetupMachineVisualization(GameObject machine, string machineId)
        {
            // Create temperature heatmap on spindle
            var spindle = machine.transform.Find("Spindle");
            if (spindle != null)
            {
                var spindleRenderer = spindle.GetComponent<MeshRenderer>();
                if (spindleRenderer != null)
                {
                    CreateTemperatureHeatmap($"{machineId}_spindle_temp", spindleRenderer, 20f, 80f);
                }
            }

            // Create load gauges for axes
            CreateDigitalDisplay($"{machineId}_x_load", machine.transform.position + new Vector3(0.3f, 0.4f, 0), "X Load", "%");
            CreateDigitalDisplay($"{machineId}_y_load", machine.transform.position + new Vector3(0.3f, 0.35f, 0), "Y Load", "%");
            CreateDigitalDisplay($"{machineId}_z_load", machine.transform.position + new Vector3(0.3f, 0.3f, 0), "Z Load", "%");

            // Create spindle speed gauge
            CreateRadialGauge($"{machineId}_spindle_rpm", machine.transform.position + new Vector3(-0.3f, 0.4f, 0), 0, 10000, "RPM");

            // Create alert indicators
            CreateAlertIndicator($"{machineId}_temp_alert", machine.transform.position + new Vector3(0, 0.5f, 0));
        }

        /// <summary>
        /// Remove all visualizations for a machine
        /// </summary>
        public void RemoveMachineVisualization(string machineId)
        {
            var keysToRemove = new List<string>();

            foreach (var key in activeGauges.Keys)
            {
                if (key.StartsWith(machineId))
                {
                    if (activeGauges[key] != null)
                    {
                        Destroy(activeGauges[key].gameObject);
                    }
                    keysToRemove.Add(key);
                }
            }
            foreach (var key in keysToRemove) activeGauges.Remove(key);

            keysToRemove.Clear();
            foreach (var key in activeHeatmaps.Keys)
            {
                if (key.StartsWith(machineId))
                {
                    if (activeHeatmaps[key] != null)
                    {
                        Destroy(activeHeatmaps[key]);
                    }
                    keysToRemove.Add(key);
                }
            }
            foreach (var key in keysToRemove) activeHeatmaps.Remove(key);

            keysToRemove.Clear();
            foreach (var key in activeAlerts.Keys)
            {
                if (key.StartsWith(machineId))
                {
                    if (activeAlerts[key] != null)
                    {
                        Destroy(activeAlerts[key].gameObject);
                    }
                    keysToRemove.Add(key);
                }
            }
            foreach (var key in keysToRemove) activeAlerts.Remove(key);
        }
    }

    // =========================================================================
    // Gauge Components
    // =========================================================================

    public abstract class SensorGauge : MonoBehaviour
    {
        public string sensorId;
        public string label;
        public float minValue;
        public float maxValue;
        public float currentValue;

        public virtual void Initialize(string sensorId, float min, float max, string label)
        {
            this.sensorId = sensorId;
            this.minValue = min;
            this.maxValue = max;
            this.label = label;
        }

        public abstract void UpdateValue(float value);

        protected float GetNormalizedValue()
        {
            return Mathf.InverseLerp(minValue, maxValue, currentValue);
        }
    }

    public class RadialGauge : SensorGauge
    {
        [Header("Radial Settings")]
        public float needleAngleMin = -135f;
        public float needleAngleMax = 135f;
        public Transform needle;

        private float needleVelocity;

        public override void Initialize(string sensorId, float min, float max, string label)
        {
            base.Initialize(sensorId, min, max, label);
            CreateGaugeVisual();
        }

        private void CreateGaugeVisual()
        {
            // Create gauge face
            var face = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            face.name = "GaugeFace";
            face.transform.SetParent(transform);
            face.transform.localPosition = Vector3.zero;
            face.transform.localScale = new Vector3(0.08f, 0.002f, 0.08f);
            face.transform.localRotation = Quaternion.Euler(90, 0, 0);

            var faceMat = new Material(Shader.Find("Standard"));
            faceMat.color = new Color(0.9f, 0.9f, 0.92f);
            face.GetComponent<Renderer>().material = faceMat;

            // Create needle
            var needleObj = GameObject.CreatePrimitive(PrimitiveType.Cube);
            needleObj.name = "Needle";
            needleObj.transform.SetParent(transform);
            needleObj.transform.localPosition = new Vector3(0, 0.003f, 0.015f);
            needleObj.transform.localScale = new Vector3(0.004f, 0.002f, 0.035f);

            var needleMat = new Material(Shader.Find("Standard"));
            needleMat.color = Color.red;
            needleObj.GetComponent<Renderer>().material = needleMat;

            needle = needleObj.transform;

            // Face the camera
            gameObject.AddComponent<FaceCamera>();
        }

        public override void UpdateValue(float value)
        {
            currentValue = Mathf.Clamp(value, minValue, maxValue);

            if (needle != null)
            {
                float targetAngle = Mathf.Lerp(needleAngleMin, needleAngleMax, GetNormalizedValue());
                float currentAngle = needle.localEulerAngles.y;

                // Smooth needle movement
                float newAngle = Mathf.SmoothDampAngle(currentAngle, targetAngle, ref needleVelocity, 0.1f);
                needle.localRotation = Quaternion.Euler(0, newAngle, 0);
            }
        }
    }

    public class LinearGauge : SensorGauge
    {
        [Header("Linear Settings")]
        public bool isVertical = true;
        public Transform fillBar;

        public override void Initialize(string sensorId, float min, float max, string label)
        {
            base.Initialize(sensorId, min, max, label);
            CreateGaugeVisual();
        }

        private void CreateGaugeVisual()
        {
            // Create background bar
            var bgBar = GameObject.CreatePrimitive(PrimitiveType.Cube);
            bgBar.name = "Background";
            bgBar.transform.SetParent(transform);
            bgBar.transform.localPosition = Vector3.zero;
            bgBar.transform.localScale = isVertical ? new Vector3(0.02f, 0.1f, 0.005f) : new Vector3(0.1f, 0.02f, 0.005f);

            var bgMat = new Material(Shader.Find("Standard"));
            bgMat.color = new Color(0.2f, 0.2f, 0.22f);
            bgBar.GetComponent<Renderer>().material = bgMat;

            // Create fill bar
            var fill = GameObject.CreatePrimitive(PrimitiveType.Cube);
            fill.name = "Fill";
            fill.transform.SetParent(transform);
            fill.transform.localPosition = isVertical ? new Vector3(0, -0.045f, -0.001f) : new Vector3(-0.045f, 0, -0.001f);
            fill.transform.localScale = isVertical ? new Vector3(0.015f, 0.01f, 0.005f) : new Vector3(0.01f, 0.015f, 0.005f);

            var fillMat = new Material(Shader.Find("Standard"));
            fillMat.color = new Color(0.2f, 0.8f, 0.2f);
            fill.GetComponent<Renderer>().material = fillMat;

            fillBar = fill.transform;

            // Face the camera
            gameObject.AddComponent<FaceCamera>();
        }

        public override void UpdateValue(float value)
        {
            currentValue = Mathf.Clamp(value, minValue, maxValue);

            if (fillBar != null)
            {
                float normalizedValue = GetNormalizedValue();
                float fillSize = 0.09f * normalizedValue;

                if (isVertical)
                {
                    fillBar.localScale = new Vector3(0.015f, fillSize + 0.01f, 0.005f);
                    fillBar.localPosition = new Vector3(0, -0.045f + fillSize * 0.5f, -0.001f);
                }
                else
                {
                    fillBar.localScale = new Vector3(fillSize + 0.01f, 0.015f, 0.005f);
                    fillBar.localPosition = new Vector3(-0.045f + fillSize * 0.5f, 0, -0.001f);
                }

                // Update color based on value
                var renderer = fillBar.GetComponent<Renderer>();
                if (renderer != null && SensorVisualization.Instance != null)
                {
                    renderer.material.color = SensorVisualization.Instance.loadGradient.Evaluate(normalizedValue);
                }
            }
        }
    }

    public class DigitalDisplay : SensorGauge
    {
        public string unit = "";
        public int decimalPlaces = 1;
        private TextMesh textMesh;

        public override void Initialize(string sensorId, float min, float max, string label)
        {
            base.Initialize(sensorId, min, max, label);
            CreateDisplayVisual();
        }

        private void CreateDisplayVisual()
        {
            // Create background
            var bg = GameObject.CreatePrimitive(PrimitiveType.Cube);
            bg.name = "Background";
            bg.transform.SetParent(transform);
            bg.transform.localPosition = Vector3.zero;
            bg.transform.localScale = new Vector3(0.06f, 0.025f, 0.002f);

            var bgMat = new Material(Shader.Find("Standard"));
            bgMat.color = new Color(0.1f, 0.1f, 0.12f);
            bg.GetComponent<Renderer>().material = bgMat;

            // Create text
            var textObj = new GameObject("DisplayText");
            textObj.transform.SetParent(transform);
            textObj.transform.localPosition = new Vector3(0, 0, -0.002f);

            textMesh = textObj.AddComponent<TextMesh>();
            textMesh.text = $"{label}: --";
            textMesh.fontSize = 24;
            textMesh.characterSize = 0.003f;
            textMesh.color = new Color(0.2f, 0.9f, 0.2f);
            textMesh.alignment = TextAlignment.Center;
            textMesh.anchor = TextAnchor.MiddleCenter;

            // Face the camera
            gameObject.AddComponent<FaceCamera>();
        }

        public override void UpdateValue(float value)
        {
            currentValue = value;

            if (textMesh != null)
            {
                string format = $"F{decimalPlaces}";
                textMesh.text = $"{label}: {value.ToString(format)} {unit}";
            }
        }
    }

    // =========================================================================
    // Heatmap and Alert Components
    // =========================================================================

    public enum HeatmapType
    {
        Temperature,
        Vibration,
        Load,
        Stress
    }

    public class HeatmapOverlay : MonoBehaviour
    {
        public string overlayId;
        public HeatmapType heatmapType;
        public float minValue;
        public float maxValue;
        public float currentValue;

        private MeshRenderer targetRenderer;
        private Gradient colorGradient;
        private Material originalMaterial;
        private Material heatmapMaterial;

        public void Initialize(string id, HeatmapType type, MeshRenderer renderer, Gradient gradient)
        {
            overlayId = id;
            heatmapType = type;
            targetRenderer = renderer;
            colorGradient = gradient;

            // Store original material
            originalMaterial = renderer.material;

            // Create heatmap material
            heatmapMaterial = new Material(Shader.Find("Standard"));
            heatmapMaterial.SetFloat("_Mode", 3); // Transparent
            heatmapMaterial.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
            heatmapMaterial.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
            heatmapMaterial.SetInt("_ZWrite", 0);
            heatmapMaterial.DisableKeyword("_ALPHATEST_ON");
            heatmapMaterial.EnableKeyword("_ALPHABLEND_ON");
            heatmapMaterial.DisableKeyword("_ALPHAPREMULTIPLY_ON");
            heatmapMaterial.renderQueue = 3000;
        }

        public void UpdateValue(float value)
        {
            currentValue = Mathf.Clamp(value, minValue, maxValue);
        }

        public void UpdateVisualization()
        {
            if (targetRenderer == null || colorGradient == null) return;

            float normalizedValue = Mathf.InverseLerp(minValue, maxValue, currentValue);
            Color heatColor = colorGradient.Evaluate(normalizedValue);
            heatColor.a = 0.6f;

            heatmapMaterial.color = heatColor;
            targetRenderer.material = heatmapMaterial;
        }

        public void DisableHeatmap()
        {
            if (targetRenderer != null && originalMaterial != null)
            {
                targetRenderer.material = originalMaterial;
            }
        }

        private void OnDestroy()
        {
            DisableHeatmap();
        }
    }

    public class AlertIndicator : MonoBehaviour
    {
        public string sensorId;
        public SensorStatus currentStatus = SensorStatus.Normal;

        private Light alertLight;
        private MeshRenderer sphereRenderer;
        private Color normalColor;
        private Color warningColor;
        private Color criticalColor;
        private float targetIntensity;
        private bool isAlerting;

        public void Initialize(string sensorId, Color normal, Color warning, Color critical)
        {
            this.sensorId = sensorId;
            this.normalColor = normal;
            this.warningColor = warning;
            this.criticalColor = critical;

            CreateIndicatorVisual();
        }

        private void CreateIndicatorVisual()
        {
            // Create indicator sphere
            var sphere = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            sphere.name = "IndicatorSphere";
            sphere.transform.SetParent(transform);
            sphere.transform.localPosition = Vector3.zero;
            sphere.transform.localScale = new Vector3(0.015f, 0.015f, 0.015f);

            sphereRenderer = sphere.GetComponent<Renderer>() as MeshRenderer;
            var mat = new Material(Shader.Find("Standard"));
            mat.EnableKeyword("_EMISSION");
            mat.SetColor("_EmissionColor", normalColor * 0.5f);
            mat.color = normalColor;
            sphereRenderer.material = mat;

            // Remove collider
            var collider = sphere.GetComponent<Collider>();
            if (collider != null) Destroy(collider);

            // Create point light
            var lightObj = new GameObject("AlertLight");
            lightObj.transform.SetParent(transform);
            lightObj.transform.localPosition = Vector3.zero;

            alertLight = lightObj.AddComponent<Light>();
            alertLight.type = LightType.Point;
            alertLight.color = normalColor;
            alertLight.intensity = 0.5f;
            alertLight.range = 0.1f;
        }

        public void UpdateStatus(SensorStatus status)
        {
            currentStatus = status;

            Color targetColor = status switch
            {
                SensorStatus.Warning => warningColor,
                SensorStatus.Critical => criticalColor,
                _ => normalColor
            };

            isAlerting = status == SensorStatus.Warning || status == SensorStatus.Critical;
            targetIntensity = isAlerting ? 2f : 0.5f;

            if (sphereRenderer != null)
            {
                sphereRenderer.material.color = targetColor;
            }

            if (alertLight != null)
            {
                alertLight.color = targetColor;
            }
        }

        public void TriggerAlert(AlertLevel level)
        {
            var status = level switch
            {
                AlertLevel.Warning => SensorStatus.Warning,
                AlertLevel.Critical => SensorStatus.Critical,
                _ => SensorStatus.Normal
            };
            UpdateStatus(status);
        }

        public void UpdatePulse(float pulse)
        {
            if (!isAlerting) return;

            float intensity = Mathf.Lerp(0.5f, targetIntensity, pulse);

            if (alertLight != null)
            {
                alertLight.intensity = intensity;
            }

            if (sphereRenderer != null)
            {
                Color currentColor = currentStatus == SensorStatus.Critical ? criticalColor : warningColor;
                sphereRenderer.material.SetColor("_EmissionColor", currentColor * intensity);
            }
        }
    }

    // =========================================================================
    // Utility Components
    // =========================================================================

    /// <summary>
    /// Makes an object always face the main camera
    /// </summary>
    public class FaceCamera : MonoBehaviour
    {
        private UnityEngine.Camera mainCamera;

        private void Start()
        {
            mainCamera = UnityEngine.Camera.main;
        }

        private void LateUpdate()
        {
            if (mainCamera != null)
            {
                transform.LookAt(transform.position + mainCamera.transform.forward);
            }
        }
    }
}
