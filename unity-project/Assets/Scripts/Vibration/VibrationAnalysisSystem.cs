using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CNCDigitalTwin.Vibration
{
    /// <summary>
    /// Advanced Vibration Analysis System with FFT
    /// Provides real-time vibration monitoring, frequency analysis, and fault detection
    /// for CNC machine predictive maintenance
    /// </summary>
    public class VibrationAnalysisSystem : MonoBehaviour
    {
        public static VibrationAnalysisSystem Instance { get; private set; }

        [Header("Analysis Configuration")]
        [SerializeField] private int sampleRate = 10000; // Hz
        [SerializeField] private int fftSize = 4096; // FFT window size
        [SerializeField] private float analysisInterval = 0.1f; // 100ms
        [SerializeField] private int averagingCount = 4; // Spectral averaging

        [Header("Accelerometer Settings")]
        [SerializeField] private float maxAcceleration = 50f; // g
        [SerializeField] private float sensitivityMvPerG = 100f;
        [SerializeField] private VibrationUnits displayUnits = VibrationUnits.Velocity_mmps;

        // Events
        public event Action<VibrationSensor, VibrationData> OnVibrationDataReceived;
        public event Action<VibrationSensor, FrequencySpectrum> OnSpectrumComputed;
        public event Action<VibrationFault> OnFaultDetected;
        public event Action<VibrationSensor, TrendAlert> OnTrendAlert;

        // Sensors and data
        private Dictionary<string, VibrationSensor> sensors = new Dictionary<string, VibrationSensor>();
        private Dictionary<string, List<float>> sampleBuffers = new Dictionary<string, List<float>>();
        private Dictionary<string, List<FrequencySpectrum>> spectrumHistory = new Dictionary<string, List<FrequencySpectrum>>();
        private Dictionary<string, BaselineProfile> baselines = new Dictionary<string, BaselineProfile>();
        private Dictionary<string, List<TrendPoint>> trendData = new Dictionary<string, List<TrendPoint>>();

        // Fault detection
        private List<FaultSignature> knownFaultSignatures = new List<FaultSignature>();
        private List<VibrationFault> activeFaults = new List<VibrationFault>();

        // FFT precomputed values
        private float[] hannWindow;
        private Complex[] fftBuffer;
        private float[] magnitudeSpectrum;
        private float frequencyResolution;

        // Statistics
        private VibrationSystemStats stats = new VibrationSystemStats();

        #region Data Structures

        public enum VibrationUnits
        {
            Acceleration_g,
            Acceleration_mps2,
            Velocity_mmps,
            Velocity_ips,
            Displacement_um,
            Displacement_mils
        }

        public enum MountingOrientation
        {
            Axial,
            Radial_Horizontal,
            Radial_Vertical
        }

        public enum SensorType
        {
            Accelerometer_IEPE,
            Accelerometer_MEMS,
            VelocitySensor,
            ProximitySensor,
            Laser_Vibrometer
        }

        public enum WindowFunction
        {
            Hann,
            Hamming,
            Blackman,
            FlatTop,
            Kaiser
        }

        public enum FaultType
        {
            Unbalance,
            Misalignment_Angular,
            Misalignment_Parallel,
            Bearing_InnerRace,
            Bearing_OuterRace,
            Bearing_BallDefect,
            Bearing_CageDefect,
            Looseness_Mechanical,
            Looseness_Structural,
            Gear_ToothWear,
            Gear_Eccentricity,
            Resonance,
            Cavitation,
            Oil_Whirl,
            Electrical_RotorBar,
            Electrical_Eccentricity,
            Belt_Defect,
            Unknown
        }

        public class VibrationSensor
        {
            public string SensorId { get; set; }
            public string MachineName { get; set; }
            public string ComponentName { get; set; }
            public SensorType Type { get; set; }
            public MountingOrientation Orientation { get; set; }
            public Vector3 Position { get; set; }
            public float SensitivityMvPerG { get; set; }
            public float FrequencyRangeMin { get; set; }
            public float FrequencyRangeMax { get; set; }
            public bool IsEnabled { get; set; }
            public DateTime LastDataTime { get; set; }
            public VibrationData LastData { get; set; }
            public FrequencySpectrum LastSpectrum { get; set; }
        }

        public class VibrationData
        {
            public DateTime Timestamp { get; set; }
            public float[] RawSamples { get; set; }
            public float RMS { get; set; }
            public float Peak { get; set; }
            public float PeakToPeak { get; set; }
            public float CrestFactor { get; set; }
            public float Kurtosis { get; set; }
            public float Skewness { get; set; }
            public VibrationUnits Units { get; set; }
        }

        public class FrequencySpectrum
        {
            public DateTime Timestamp { get; set; }
            public float[] Frequencies { get; set; }
            public float[] Magnitudes { get; set; }
            public float[] Phases { get; set; }
            public float FrequencyResolution { get; set; }
            public float DominantFrequency { get; set; }
            public float DominantMagnitude { get; set; }
            public List<SpectralPeak> Peaks { get; set; } = new List<SpectralPeak>();
            public float OverallLevel { get; set; }
            public VibrationUnits Units { get; set; }
        }

        public class SpectralPeak
        {
            public int BinIndex { get; set; }
            public float Frequency { get; set; }
            public float Magnitude { get; set; }
            public float Phase { get; set; }
            public float Bandwidth { get; set; }
            public string HarmonicLabel { get; set; }
        }

        public class BaselineProfile
        {
            public string SensorId { get; set; }
            public DateTime CaptureDate { get; set; }
            public float RPM { get; set; }
            public float Load { get; set; }
            public float[] BaselineSpectrum { get; set; }
            public float BaselineRMS { get; set; }
            public Dictionary<FaultType, float> FaultThresholds { get; set; }
            public List<FrequencyBand> MonitoredBands { get; set; }
        }

        public class FrequencyBand
        {
            public string Name { get; set; }
            public float CenterFrequency { get; set; }
            public float Bandwidth { get; set; }
            public float AlarmLevel { get; set; }
            public float DangerLevel { get; set; }
        }

        public class FaultSignature
        {
            public FaultType Type { get; set; }
            public string Description { get; set; }
            public List<HarmonicPattern> HarmonicPatterns { get; set; }
            public float ConfidenceThreshold { get; set; }
            public SeverityCalculation SeverityCalc { get; set; }
        }

        public class HarmonicPattern
        {
            public float FrequencyMultiplier { get; set; } // Relative to running speed
            public float ExpectedMagnitudeRatio { get; set; }
            public float FrequencyTolerance { get; set; }
            public bool IsSideband { get; set; }
            public float SidebandSpacing { get; set; }
        }

        public class SeverityCalculation
        {
            public Func<float, float> Calculate { get; set; }
        }

        public class VibrationFault
        {
            public string FaultId { get; set; }
            public string SensorId { get; set; }
            public FaultType Type { get; set; }
            public float Confidence { get; set; }
            public float Severity { get; set; } // 0-100
            public DateTime DetectedTime { get; set; }
            public List<SpectralPeak> EvidencePeaks { get; set; }
            public string Recommendation { get; set; }
            public float EstimatedRUL { get; set; } // Remaining useful life in hours
        }

        public class TrendPoint
        {
            public DateTime Timestamp { get; set; }
            public float RMS { get; set; }
            public float Temperature { get; set; }
            public float RPM { get; set; }
            public float Load { get; set; }
        }

        public class TrendAlert
        {
            public string SensorId { get; set; }
            public string Parameter { get; set; }
            public float CurrentValue { get; set; }
            public float BaselineValue { get; set; }
            public float ChangePercent { get; set; }
            public float PredictedTimeToAlarm { get; set; } // hours
            public string Message { get; set; }
        }

        public struct Complex
        {
            public float Real;
            public float Imaginary;

            public Complex(float real, float imag)
            {
                Real = real;
                Imaginary = imag;
            }

            public float Magnitude => Mathf.Sqrt(Real * Real + Imaginary * Imaginary);
            public float Phase => Mathf.Atan2(Imaginary, Real);

            public static Complex operator +(Complex a, Complex b) =>
                new Complex(a.Real + b.Real, a.Imaginary + b.Imaginary);

            public static Complex operator -(Complex a, Complex b) =>
                new Complex(a.Real - b.Real, a.Imaginary - b.Imaginary);

            public static Complex operator *(Complex a, Complex b) =>
                new Complex(
                    a.Real * b.Real - a.Imaginary * b.Imaginary,
                    a.Real * b.Imaginary + a.Imaginary * b.Real
                );
        }

        public class BearingInfo
        {
            public string BearingId { get; set; }
            public string Designation { get; set; }
            public int NumberOfBalls { get; set; }
            public float BallDiameter { get; set; } // mm
            public float PitchDiameter { get; set; } // mm
            public float ContactAngle { get; set; } // degrees

            // Calculated fault frequencies (as multiples of shaft speed)
            public float BPFO { get; set; } // Ball Pass Frequency Outer Race
            public float BPFI { get; set; } // Ball Pass Frequency Inner Race
            public float BSF { get; set; }  // Ball Spin Frequency
            public float FTF { get; set; }  // Fundamental Train Frequency
        }

        public class VibrationSystemStats
        {
            public int TotalSensors { get; set; }
            public int ActiveSensors { get; set; }
            public long SamplesProcessed { get; set; }
            public int FFTsComputed { get; set; }
            public int FaultsDetected { get; set; }
            public int ActiveAlarms { get; set; }
            public float AverageProcessingTimeMs { get; set; }
        }

        #endregion

        #region Initialization

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
                DontDestroyOnLoad(gameObject);
            }
            else
            {
                Destroy(gameObject);
                return;
            }

            InitializeFFT();
            InitializeFaultSignatures();
        }

        private void Start()
        {
            StartCoroutine(AnalysisLoop());
            StartCoroutine(TrendAnalysisLoop());
            Debug.Log("[VibrationAnalysis] System initialized - FFT size: " + fftSize +
                      ", Sample rate: " + sampleRate + "Hz");
        }

        private void InitializeFFT()
        {
            // Pre-compute Hann window
            hannWindow = new float[fftSize];
            for (int i = 0; i < fftSize; i++)
            {
                hannWindow[i] = 0.5f * (1 - Mathf.Cos(2 * Mathf.PI * i / (fftSize - 1)));
            }

            // Allocate FFT buffers
            fftBuffer = new Complex[fftSize];
            magnitudeSpectrum = new float[fftSize / 2];
            frequencyResolution = (float)sampleRate / fftSize;

            Debug.Log("[VibrationAnalysis] FFT initialized - Resolution: " +
                      frequencyResolution.ToString("F2") + " Hz");
        }

        private void InitializeFaultSignatures()
        {
            // Unbalance signature - 1X running speed dominant
            knownFaultSignatures.Add(new FaultSignature
            {
                Type = FaultType.Unbalance,
                Description = "Rotor unbalance - mass distribution problem",
                HarmonicPatterns = new List<HarmonicPattern>
                {
                    new HarmonicPattern { FrequencyMultiplier = 1.0f, ExpectedMagnitudeRatio = 1.0f, FrequencyTolerance = 0.05f }
                },
                ConfidenceThreshold = 0.7f,
                SeverityCalc = new SeverityCalculation { Calculate = (mag) => Mathf.Min(mag * 10f, 100f) }
            });

            // Angular misalignment - 1X and 2X with axial vibration
            knownFaultSignatures.Add(new FaultSignature
            {
                Type = FaultType.Misalignment_Angular,
                Description = "Angular misalignment between shafts",
                HarmonicPatterns = new List<HarmonicPattern>
                {
                    new HarmonicPattern { FrequencyMultiplier = 1.0f, ExpectedMagnitudeRatio = 0.6f, FrequencyTolerance = 0.05f },
                    new HarmonicPattern { FrequencyMultiplier = 2.0f, ExpectedMagnitudeRatio = 1.0f, FrequencyTolerance = 0.05f }
                },
                ConfidenceThreshold = 0.65f,
                SeverityCalc = new SeverityCalculation { Calculate = (mag) => Mathf.Min(mag * 15f, 100f) }
            });

            // Parallel misalignment - 2X dominant
            knownFaultSignatures.Add(new FaultSignature
            {
                Type = FaultType.Misalignment_Parallel,
                Description = "Parallel/offset misalignment",
                HarmonicPatterns = new List<HarmonicPattern>
                {
                    new HarmonicPattern { FrequencyMultiplier = 2.0f, ExpectedMagnitudeRatio = 1.0f, FrequencyTolerance = 0.05f },
                    new HarmonicPattern { FrequencyMultiplier = 1.0f, ExpectedMagnitudeRatio = 0.3f, FrequencyTolerance = 0.05f }
                },
                ConfidenceThreshold = 0.65f,
                SeverityCalc = new SeverityCalculation { Calculate = (mag) => Mathf.Min(mag * 15f, 100f) }
            });

            // Mechanical looseness - many harmonics
            knownFaultSignatures.Add(new FaultSignature
            {
                Type = FaultType.Looseness_Mechanical,
                Description = "Mechanical looseness - truncated waveform",
                HarmonicPatterns = new List<HarmonicPattern>
                {
                    new HarmonicPattern { FrequencyMultiplier = 1.0f, ExpectedMagnitudeRatio = 1.0f, FrequencyTolerance = 0.05f },
                    new HarmonicPattern { FrequencyMultiplier = 2.0f, ExpectedMagnitudeRatio = 0.8f, FrequencyTolerance = 0.05f },
                    new HarmonicPattern { FrequencyMultiplier = 3.0f, ExpectedMagnitudeRatio = 0.6f, FrequencyTolerance = 0.05f },
                    new HarmonicPattern { FrequencyMultiplier = 4.0f, ExpectedMagnitudeRatio = 0.4f, FrequencyTolerance = 0.05f }
                },
                ConfidenceThreshold = 0.6f,
                SeverityCalc = new SeverityCalculation { Calculate = (mag) => Mathf.Min(mag * 20f, 100f) }
            });

            Debug.Log("[VibrationAnalysis] Loaded " + knownFaultSignatures.Count + " fault signatures");
        }

        #endregion

        #region Sensor Management

        public VibrationSensor RegisterSensor(string sensorId, string machineName, string componentName,
            SensorType type, MountingOrientation orientation, Vector3 position)
        {
            var sensor = new VibrationSensor
            {
                SensorId = sensorId,
                MachineName = machineName,
                ComponentName = componentName,
                Type = type,
                Orientation = orientation,
                Position = position,
                SensitivityMvPerG = sensitivityMvPerG,
                FrequencyRangeMin = 0.5f,
                FrequencyRangeMax = sampleRate / 2.5f,
                IsEnabled = true
            };

            sensors[sensorId] = sensor;
            sampleBuffers[sensorId] = new List<float>(sampleRate);
            spectrumHistory[sensorId] = new List<FrequencySpectrum>();
            trendData[sensorId] = new List<TrendPoint>();

            stats.TotalSensors++;
            stats.ActiveSensors++;

            Debug.Log($"[VibrationAnalysis] Registered sensor: {sensorId} on {machineName}/{componentName}");
            return sensor;
        }

        public void UnregisterSensor(string sensorId)
        {
            if (sensors.ContainsKey(sensorId))
            {
                sensors.Remove(sensorId);
                sampleBuffers.Remove(sensorId);
                spectrumHistory.Remove(sensorId);
                trendData.Remove(sensorId);
                stats.TotalSensors--;
                stats.ActiveSensors--;
            }
        }

        public void SetBearingInfo(string sensorId, BearingInfo bearing)
        {
            // Calculate bearing fault frequencies
            float d = bearing.BallDiameter;
            float D = bearing.PitchDiameter;
            int n = bearing.NumberOfBalls;
            float phi = bearing.ContactAngle * Mathf.Deg2Rad;

            // Standard formulas for rolling element bearing fault frequencies
            bearing.BPFO = (n / 2f) * (1 - (d / D) * Mathf.Cos(phi));
            bearing.BPFI = (n / 2f) * (1 + (d / D) * Mathf.Cos(phi));
            bearing.FTF = 0.5f * (1 - (d / D) * Mathf.Cos(phi));
            bearing.BSF = (D / (2 * d)) * (1 - Mathf.Pow((d / D) * Mathf.Cos(phi), 2));

            // Add bearing-specific fault signatures
            AddBearingFaultSignature(sensorId, bearing, FaultType.Bearing_OuterRace, bearing.BPFO);
            AddBearingFaultSignature(sensorId, bearing, FaultType.Bearing_InnerRace, bearing.BPFI);
            AddBearingFaultSignature(sensorId, bearing, FaultType.Bearing_BallDefect, 2 * bearing.BSF);
            AddBearingFaultSignature(sensorId, bearing, FaultType.Bearing_CageDefect, bearing.FTF);

            Debug.Log($"[VibrationAnalysis] Bearing {bearing.Designation} - BPFO: {bearing.BPFO:F2}X, " +
                      $"BPFI: {bearing.BPFI:F2}X, BSF: {bearing.BSF:F2}X, FTF: {bearing.FTF:F2}X");
        }

        private void AddBearingFaultSignature(string sensorId, BearingInfo bearing, FaultType faultType, float frequency)
        {
            var signature = new FaultSignature
            {
                Type = faultType,
                Description = $"Bearing {bearing.Designation} - {faultType}",
                HarmonicPatterns = new List<HarmonicPattern>
                {
                    new HarmonicPattern
                    {
                        FrequencyMultiplier = frequency,
                        ExpectedMagnitudeRatio = 1.0f,
                        FrequencyTolerance = 0.03f,
                        IsSideband = true,
                        SidebandSpacing = 1.0f // Running speed sidebands
                    }
                },
                ConfidenceThreshold = 0.6f,
                SeverityCalc = new SeverityCalculation { Calculate = (mag) => Mathf.Min(mag * 25f, 100f) }
            };

            knownFaultSignatures.Add(signature);
        }

        #endregion

        #region Data Acquisition

        public void ReceiveSamples(string sensorId, float[] samples)
        {
            if (!sensors.TryGetValue(sensorId, out var sensor) || !sensor.IsEnabled)
                return;

            var buffer = sampleBuffers[sensorId];
            buffer.AddRange(samples);
            stats.SamplesProcessed += samples.Length;

            // Trigger analysis when we have enough samples
            if (buffer.Count >= fftSize)
            {
                ProcessSamples(sensor, buffer.Take(fftSize).ToArray());
                buffer.RemoveRange(0, fftSize / 2); // 50% overlap
            }
        }

        private void ProcessSamples(VibrationSensor sensor, float[] samples)
        {
            var startTime = DateTime.Now;

            // Calculate time-domain statistics
            var vibData = CalculateTimedomainStats(samples);
            sensor.LastData = vibData;
            sensor.LastDataTime = DateTime.Now;

            OnVibrationDataReceived?.Invoke(sensor, vibData);

            // Compute FFT
            var spectrum = ComputeFFT(samples);
            sensor.LastSpectrum = spectrum;

            // Store in history for averaging
            var history = spectrumHistory[sensor.SensorId];
            history.Add(spectrum);
            if (history.Count > averagingCount)
                history.RemoveAt(0);

            // Compute averaged spectrum
            if (history.Count >= averagingCount)
            {
                var avgSpectrum = ComputeAveragedSpectrum(history);
                OnSpectrumComputed?.Invoke(sensor, avgSpectrum);

                // Fault detection
                DetectFaults(sensor, avgSpectrum);
            }

            stats.FFTsComputed++;
            stats.AverageProcessingTimeMs = (float)(DateTime.Now - startTime).TotalMilliseconds;
        }

        #endregion

        #region Signal Processing

        private VibrationData CalculateTimedomainStats(float[] samples)
        {
            int n = samples.Length;
            float sum = 0, sumSq = 0, sumCube = 0, sumQuad = 0;
            float min = float.MaxValue, max = float.MinValue;

            for (int i = 0; i < n; i++)
            {
                float v = samples[i];
                sum += v;
                sumSq += v * v;
                sumCube += v * v * v;
                sumQuad += v * v * v * v;
                if (v < min) min = v;
                if (v > max) max = v;
            }

            float mean = sum / n;
            float variance = (sumSq / n) - (mean * mean);
            float stdDev = Mathf.Sqrt(variance);
            float rms = Mathf.Sqrt(sumSq / n);

            // Adjust moments for mean
            float m2 = sumSq / n - mean * mean;
            float m3 = sumCube / n - 3 * mean * sumSq / n + 2 * mean * mean * mean;
            float m4 = sumQuad / n - 4 * mean * sumCube / n + 6 * mean * mean * sumSq / n - 3 * mean * mean * mean * mean;

            float skewness = m3 / Mathf.Pow(m2, 1.5f);
            float kurtosis = m4 / (m2 * m2);

            return new VibrationData
            {
                Timestamp = DateTime.Now,
                RawSamples = samples,
                RMS = rms,
                Peak = Mathf.Max(Mathf.Abs(min), Mathf.Abs(max)),
                PeakToPeak = max - min,
                CrestFactor = Mathf.Max(Mathf.Abs(min), Mathf.Abs(max)) / rms,
                Kurtosis = kurtosis,
                Skewness = skewness,
                Units = displayUnits
            };
        }

        private FrequencySpectrum ComputeFFT(float[] samples)
        {
            // Apply window function
            for (int i = 0; i < fftSize; i++)
            {
                fftBuffer[i] = new Complex(samples[i] * hannWindow[i], 0);
            }

            // Cooley-Tukey FFT
            FFT(fftBuffer);

            // Calculate magnitude spectrum
            float[] frequencies = new float[fftSize / 2];
            float[] magnitudes = new float[fftSize / 2];
            float[] phases = new float[fftSize / 2];

            float maxMag = 0;
            int maxBin = 0;
            float overallPower = 0;

            for (int i = 0; i < fftSize / 2; i++)
            {
                frequencies[i] = i * frequencyResolution;
                magnitudes[i] = fftBuffer[i].Magnitude * 2 / fftSize; // Scale factor
                phases[i] = fftBuffer[i].Phase;
                overallPower += magnitudes[i] * magnitudes[i];

                if (magnitudes[i] > maxMag)
                {
                    maxMag = magnitudes[i];
                    maxBin = i;
                }
            }

            // Convert to desired units
            ConvertUnits(magnitudes, VibrationUnits.Acceleration_g, displayUnits);

            // Find peaks
            var peaks = FindSpectralPeaks(frequencies, magnitudes, phases);

            return new FrequencySpectrum
            {
                Timestamp = DateTime.Now,
                Frequencies = frequencies,
                Magnitudes = magnitudes,
                Phases = phases,
                FrequencyResolution = frequencyResolution,
                DominantFrequency = frequencies[maxBin],
                DominantMagnitude = magnitudes[maxBin],
                Peaks = peaks,
                OverallLevel = Mathf.Sqrt(overallPower),
                Units = displayUnits
            };
        }

        private void FFT(Complex[] buffer)
        {
            int n = buffer.Length;
            if (n <= 1) return;

            // Bit-reversal permutation
            int j = 0;
            for (int i = 0; i < n - 1; i++)
            {
                if (i < j)
                {
                    var temp = buffer[i];
                    buffer[i] = buffer[j];
                    buffer[j] = temp;
                }
                int k = n >> 1;
                while (k <= j)
                {
                    j -= k;
                    k >>= 1;
                }
                j += k;
            }

            // Cooley-Tukey iterative FFT
            for (int len = 2; len <= n; len <<= 1)
            {
                float ang = -2 * Mathf.PI / len;
                Complex wlen = new Complex(Mathf.Cos(ang), Mathf.Sin(ang));

                for (int i = 0; i < n; i += len)
                {
                    Complex w = new Complex(1, 0);
                    for (int k = 0; k < len / 2; k++)
                    {
                        Complex u = buffer[i + k];
                        Complex v = buffer[i + k + len / 2] * w;
                        buffer[i + k] = u + v;
                        buffer[i + k + len / 2] = u - v;
                        w = w * wlen;
                    }
                }
            }
        }

        private void ConvertUnits(float[] magnitudes, VibrationUnits from, VibrationUnits to)
        {
            if (from == to) return;

            for (int i = 0; i < magnitudes.Length; i++)
            {
                float freq = i * frequencyResolution;
                if (freq < 0.1f) freq = 0.1f; // Avoid division by zero

                float omega = 2 * Mathf.PI * freq;

                // Convert to m/s² first
                float accelMps2 = magnitudes[i];
                if (from == VibrationUnits.Acceleration_g)
                    accelMps2 = magnitudes[i] * 9.81f;

                // Convert to target units
                switch (to)
                {
                    case VibrationUnits.Acceleration_g:
                        magnitudes[i] = accelMps2 / 9.81f;
                        break;
                    case VibrationUnits.Acceleration_mps2:
                        magnitudes[i] = accelMps2;
                        break;
                    case VibrationUnits.Velocity_mmps:
                        magnitudes[i] = (accelMps2 / omega) * 1000f;
                        break;
                    case VibrationUnits.Velocity_ips:
                        magnitudes[i] = (accelMps2 / omega) * 39.37f;
                        break;
                    case VibrationUnits.Displacement_um:
                        magnitudes[i] = (accelMps2 / (omega * omega)) * 1e6f;
                        break;
                    case VibrationUnits.Displacement_mils:
                        magnitudes[i] = (accelMps2 / (omega * omega)) * 39370f;
                        break;
                }
            }
        }

        private List<SpectralPeak> FindSpectralPeaks(float[] frequencies, float[] magnitudes, float[] phases)
        {
            var peaks = new List<SpectralPeak>();
            float threshold = magnitudes.Average() * 3; // 3x average threshold

            for (int i = 2; i < magnitudes.Length - 2; i++)
            {
                // Check if local maximum and above threshold
                if (magnitudes[i] > magnitudes[i - 1] && magnitudes[i] > magnitudes[i + 1] &&
                    magnitudes[i] > magnitudes[i - 2] && magnitudes[i] > magnitudes[i + 2] &&
                    magnitudes[i] > threshold)
                {
                    // Parabolic interpolation for precise frequency
                    float alpha = magnitudes[i - 1];
                    float beta = magnitudes[i];
                    float gamma = magnitudes[i + 1];
                    float p = 0.5f * (alpha - gamma) / (alpha - 2 * beta + gamma);
                    float preciseFreq = (i + p) * frequencyResolution;
                    float preciseMag = beta - 0.25f * (alpha - gamma) * p;

                    peaks.Add(new SpectralPeak
                    {
                        BinIndex = i,
                        Frequency = preciseFreq,
                        Magnitude = preciseMag,
                        Phase = phases[i],
                        Bandwidth = frequencyResolution // Approximate
                    });
                }
            }

            // Sort by magnitude descending
            peaks.Sort((a, b) => b.Magnitude.CompareTo(a.Magnitude));
            return peaks.Take(20).ToList(); // Return top 20 peaks
        }

        private FrequencySpectrum ComputeAveragedSpectrum(List<FrequencySpectrum> spectra)
        {
            int n = spectra[0].Magnitudes.Length;
            float[] avgMags = new float[n];

            for (int i = 0; i < n; i++)
            {
                float sum = 0;
                foreach (var s in spectra)
                    sum += s.Magnitudes[i] * s.Magnitudes[i]; // Power averaging
                avgMags[i] = Mathf.Sqrt(sum / spectra.Count);
            }

            var latest = spectra[spectra.Count - 1];
            var peaks = FindSpectralPeaks(latest.Frequencies, avgMags, latest.Phases);

            return new FrequencySpectrum
            {
                Timestamp = DateTime.Now,
                Frequencies = latest.Frequencies,
                Magnitudes = avgMags,
                Phases = latest.Phases,
                FrequencyResolution = latest.FrequencyResolution,
                DominantFrequency = peaks.Count > 0 ? peaks[0].Frequency : 0,
                DominantMagnitude = peaks.Count > 0 ? peaks[0].Magnitude : 0,
                Peaks = peaks,
                OverallLevel = Mathf.Sqrt(avgMags.Sum(m => m * m)),
                Units = latest.Units
            };
        }

        #endregion

        #region Fault Detection

        private void DetectFaults(VibrationSensor sensor, FrequencySpectrum spectrum)
        {
            float runningSpeedHz = EstimateRunningSpeed(spectrum);
            if (runningSpeedHz < 1f) return; // Machine not running

            foreach (var signature in knownFaultSignatures)
            {
                var (confidence, evidencePeaks) = EvaluateFaultSignature(spectrum, signature, runningSpeedHz);

                if (confidence >= signature.ConfidenceThreshold)
                {
                    float severity = signature.SeverityCalc?.Calculate(evidencePeaks.Sum(p => p.Magnitude)) ?? 50f;

                    var fault = new VibrationFault
                    {
                        FaultId = Guid.NewGuid().ToString(),
                        SensorId = sensor.SensorId,
                        Type = signature.Type,
                        Confidence = confidence,
                        Severity = severity,
                        DetectedTime = DateTime.Now,
                        EvidencePeaks = evidencePeaks,
                        Recommendation = GetFaultRecommendation(signature.Type, severity),
                        EstimatedRUL = EstimateRemainingLife(signature.Type, severity)
                    };

                    // Check if this fault type already exists for this sensor
                    var existingFault = activeFaults.Find(f =>
                        f.SensorId == sensor.SensorId && f.Type == signature.Type);

                    if (existingFault == null)
                    {
                        activeFaults.Add(fault);
                        stats.FaultsDetected++;
                        OnFaultDetected?.Invoke(fault);
                        Debug.LogWarning($"[VibrationAnalysis] FAULT DETECTED: {fault.Type} on {sensor.SensorId}, " +
                                        $"Confidence: {fault.Confidence:P0}, Severity: {fault.Severity:F0}%");
                    }
                    else
                    {
                        // Update existing fault
                        existingFault.Confidence = Mathf.Max(existingFault.Confidence, confidence);
                        existingFault.Severity = Mathf.Max(existingFault.Severity, severity);
                        existingFault.DetectedTime = DateTime.Now;
                    }
                }
            }
        }

        private float EstimateRunningSpeed(FrequencySpectrum spectrum)
        {
            // Find dominant frequency in expected running speed range (5-200 Hz)
            var peaksInRange = spectrum.Peaks.Where(p => p.Frequency >= 5 && p.Frequency <= 200).ToList();

            if (peaksInRange.Count > 0)
            {
                // Return the most prominent peak as running speed
                return peaksInRange[0].Frequency;
            }
            return 0;
        }

        private (float confidence, List<SpectralPeak> evidence) EvaluateFaultSignature(
            FrequencySpectrum spectrum, FaultSignature signature, float runningSpeedHz)
        {
            var evidencePeaks = new List<SpectralPeak>();
            float totalScore = 0;
            float maxScore = signature.HarmonicPatterns.Count;

            foreach (var pattern in signature.HarmonicPatterns)
            {
                float targetFreq = runningSpeedHz * pattern.FrequencyMultiplier;
                float tolerance = targetFreq * pattern.FrequencyTolerance;

                // Find peaks near target frequency
                var matchingPeak = spectrum.Peaks.FirstOrDefault(p =>
                    Mathf.Abs(p.Frequency - targetFreq) <= tolerance);

                if (matchingPeak != null)
                {
                    evidencePeaks.Add(matchingPeak);
                    totalScore += 1.0f;

                    // Check for sidebands if expected
                    if (pattern.IsSideband)
                    {
                        float sidebandFreq = pattern.SidebandSpacing * runningSpeedHz;
                        var lowerSideband = spectrum.Peaks.FirstOrDefault(p =>
                            Mathf.Abs(p.Frequency - (targetFreq - sidebandFreq)) <= tolerance);
                        var upperSideband = spectrum.Peaks.FirstOrDefault(p =>
                            Mathf.Abs(p.Frequency - (targetFreq + sidebandFreq)) <= tolerance);

                        if (lowerSideband != null || upperSideband != null)
                            totalScore += 0.5f;
                    }
                }
            }

            float confidence = totalScore / maxScore;
            return (confidence, evidencePeaks);
        }

        private string GetFaultRecommendation(FaultType type, float severity)
        {
            string urgency = severity > 80 ? "IMMEDIATE" : severity > 50 ? "SOON" : "SCHEDULED";

            return type switch
            {
                FaultType.Unbalance => $"[{urgency}] Balance rotor. Check for debris, broken blades, or uneven wear.",
                FaultType.Misalignment_Angular => $"[{urgency}] Check coupling alignment. Verify shaft centerlines.",
                FaultType.Misalignment_Parallel => $"[{urgency}] Perform laser alignment. Check soft foot.",
                FaultType.Bearing_InnerRace => $"[{urgency}] Replace bearing. Inner race defect detected.",
                FaultType.Bearing_OuterRace => $"[{urgency}] Replace bearing. Outer race defect detected.",
                FaultType.Bearing_BallDefect => $"[{urgency}] Replace bearing. Rolling element defect.",
                FaultType.Bearing_CageDefect => $"[{urgency}] Replace bearing. Cage/retainer defect.",
                FaultType.Looseness_Mechanical => $"[{urgency}] Check mounting bolts, bearing clearance, shaft fit.",
                FaultType.Looseness_Structural => $"[{urgency}] Check foundation, base plate, grouting.",
                FaultType.Gear_ToothWear => $"[{urgency}] Inspect gearbox. Consider oil analysis.",
                FaultType.Resonance => $"[{urgency}] Modify structure or speed to avoid resonance.",
                _ => $"[{urgency}] Investigate {type}. Consult vibration analyst."
            };
        }

        private float EstimateRemainingLife(FaultType type, float severity)
        {
            // Rough estimates based on severity (in hours)
            float baseLine = type switch
            {
                FaultType.Bearing_InnerRace => 500,
                FaultType.Bearing_OuterRace => 800,
                FaultType.Bearing_BallDefect => 300,
                FaultType.Unbalance => 2000,
                FaultType.Misalignment_Angular => 1500,
                FaultType.Misalignment_Parallel => 1500,
                FaultType.Looseness_Mechanical => 1000,
                _ => 1000
            };

            return baseLine * (1 - severity / 100f);
        }

        #endregion

        #region Baseline and Trending

        public void CaptureBaseline(string sensorId, float rpm, float load)
        {
            if (!sensors.TryGetValue(sensorId, out var sensor) || sensor.LastSpectrum == null)
            {
                Debug.LogError($"[VibrationAnalysis] Cannot capture baseline - no data for sensor {sensorId}");
                return;
            }

            var baseline = new BaselineProfile
            {
                SensorId = sensorId,
                CaptureDate = DateTime.Now,
                RPM = rpm,
                Load = load,
                BaselineSpectrum = (float[])sensor.LastSpectrum.Magnitudes.Clone(),
                BaselineRMS = sensor.LastData.RMS,
                FaultThresholds = new Dictionary<FaultType, float>(),
                MonitoredBands = CreateDefaultFrequencyBands(rpm)
            };

            baselines[sensorId] = baseline;
            Debug.Log($"[VibrationAnalysis] Baseline captured for {sensorId} at {rpm} RPM, {load}% load");
        }

        private List<FrequencyBand> CreateDefaultFrequencyBands(float rpm)
        {
            float runningHz = rpm / 60f;
            return new List<FrequencyBand>
            {
                new FrequencyBand { Name = "Sub-sync", CenterFrequency = runningHz * 0.5f, Bandwidth = runningHz * 0.2f, AlarmLevel = 2.5f, DangerLevel = 5.0f },
                new FrequencyBand { Name = "1X", CenterFrequency = runningHz, Bandwidth = runningHz * 0.1f, AlarmLevel = 4.0f, DangerLevel = 8.0f },
                new FrequencyBand { Name = "2X", CenterFrequency = runningHz * 2, Bandwidth = runningHz * 0.1f, AlarmLevel = 3.0f, DangerLevel = 6.0f },
                new FrequencyBand { Name = "High Freq", CenterFrequency = 5000, Bandwidth = 4000, AlarmLevel = 1.0f, DangerLevel = 2.0f }
            };
        }

        private IEnumerator TrendAnalysisLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(60f); // Check trends every minute

                foreach (var kvp in sensors)
                {
                    var sensor = kvp.Value;
                    if (sensor.LastData == null) continue;

                    // Add trend point
                    var trend = trendData[sensor.SensorId];
                    trend.Add(new TrendPoint
                    {
                        Timestamp = DateTime.Now,
                        RMS = sensor.LastData.RMS
                    });

                    // Keep last 24 hours of trend data (at 1 point/minute = 1440 points)
                    while (trend.Count > 1440)
                        trend.RemoveAt(0);

                    // Check for trending
                    if (trend.Count >= 60) // Need at least 1 hour of data
                    {
                        AnalyzeTrend(sensor, trend);
                    }
                }
            }
        }

        private void AnalyzeTrend(VibrationSensor sensor, List<TrendPoint> trend)
        {
            // Simple linear regression on RMS values
            int n = trend.Count;
            float sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;

            for (int i = 0; i < n; i++)
            {
                sumX += i;
                sumY += trend[i].RMS;
                sumXY += i * trend[i].RMS;
                sumX2 += i * i;
            }

            float slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
            float intercept = (sumY - slope * sumX) / n;

            // If slope indicates increasing vibration
            if (slope > 0)
            {
                float baseRMS = baselines.ContainsKey(sensor.SensorId) ?
                    baselines[sensor.SensorId].BaselineRMS : trend[0].RMS;
                float currentRMS = trend[n - 1].RMS;
                float changePercent = ((currentRMS - baseRMS) / baseRMS) * 100f;

                if (changePercent > 25f) // 25% increase from baseline
                {
                    // Estimate time to alarm (assuming alarm at 200% of baseline)
                    float alarmLevel = baseRMS * 2;
                    float timeToAlarm = (alarmLevel - currentRMS) / slope; // In minutes

                    var alert = new TrendAlert
                    {
                        SensorId = sensor.SensorId,
                        Parameter = "RMS",
                        CurrentValue = currentRMS,
                        BaselineValue = baseRMS,
                        ChangePercent = changePercent,
                        PredictedTimeToAlarm = timeToAlarm / 60f, // Convert to hours
                        Message = $"Vibration trending up {changePercent:F1}%. Alarm predicted in {timeToAlarm / 60f:F1} hours."
                    };

                    OnTrendAlert?.Invoke(sensor, alert);
                }
            }
        }

        #endregion

        #region Analysis Loop

        private IEnumerator AnalysisLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(analysisInterval);

                // Simulate data for testing if no real data
                foreach (var kvp in sensors)
                {
                    var sensor = kvp.Value;
                    if (sensor.IsEnabled && (DateTime.Now - sensor.LastDataTime).TotalSeconds > 1)
                    {
                        // Generate simulated vibration data
                        SimulateVibration(sensor);
                    }
                }
            }
        }

        private void SimulateVibration(VibrationSensor sensor)
        {
            float[] samples = new float[fftSize];
            float runningSpeedHz = 30f; // 1800 RPM
            float dt = 1f / sampleRate;

            for (int i = 0; i < fftSize; i++)
            {
                float t = i * dt;

                // Base running speed (1X)
                samples[i] = 0.5f * Mathf.Sin(2 * Mathf.PI * runningSpeedHz * t);

                // 2X harmonic (misalignment indicator)
                samples[i] += 0.15f * Mathf.Sin(2 * Mathf.PI * runningSpeedHz * 2 * t);

                // Some bearing frequency
                samples[i] += 0.05f * Mathf.Sin(2 * Mathf.PI * runningSpeedHz * 4.2f * t);

                // White noise
                samples[i] += UnityEngine.Random.Range(-0.1f, 0.1f);
            }

            ReceiveSamples(sensor.SensorId, samples);
        }

        #endregion

        #region Public API

        public VibrationSensor GetSensor(string sensorId)
        {
            return sensors.TryGetValue(sensorId, out var sensor) ? sensor : null;
        }

        public List<VibrationSensor> GetAllSensors()
        {
            return sensors.Values.ToList();
        }

        public List<VibrationFault> GetActiveFaults()
        {
            return activeFaults.ToList();
        }

        public List<VibrationFault> GetFaultsForSensor(string sensorId)
        {
            return activeFaults.Where(f => f.SensorId == sensorId).ToList();
        }

        public void ClearFault(string faultId)
        {
            activeFaults.RemoveAll(f => f.FaultId == faultId);
        }

        public BaselineProfile GetBaseline(string sensorId)
        {
            return baselines.TryGetValue(sensorId, out var baseline) ? baseline : null;
        }

        public List<TrendPoint> GetTrendData(string sensorId, int lastNMinutes = 60)
        {
            if (!trendData.TryGetValue(sensorId, out var trend))
                return new List<TrendPoint>();

            return trend.Skip(Math.Max(0, trend.Count - lastNMinutes)).ToList();
        }

        public VibrationSystemStats GetStats()
        {
            stats.ActiveAlarms = activeFaults.Count;
            return stats;
        }

        #endregion
    }
}
