using System;
using System.Collections.Generic;
using UnityEngine;

namespace CNCScada.Energy
{
    /// <summary>
    /// Monitors energy consumption for machining operations.
    /// Tracks power usage, calculates costs, and identifies optimization opportunities.
    /// Part of Feature 3.3: Energy Dashboard (MEDIUM PRIORITY - Phase 3)
    /// </summary>
    public class EnergyMonitor : MonoBehaviour
    {
        [Header("Monitoring Configuration")]
        [SerializeField] private string machineId = "CNC-001";
        [SerializeField] private float sampleRate = 1f; // Hz
        [SerializeField] private bool enableRealTimeMonitoring = true;

        [Header("Power Parameters")]
        [SerializeField] private float idlePower = 500f; // Watts
        [SerializeField] private float maxPower = 5000f; // Watts
        [SerializeField] private float spindlePowerCoefficient = 0.8f;
        [SerializeField] private float axisPowerCoefficient = 0.3f;

        [Header("Cost Configuration")]
        [SerializeField] private float energyCostPerKwh = 0.12f; // $/kWh
        [SerializeField] private bool enableCostTracking = true;

        [Header("Thresholds")]
        [SerializeField] private float highPowerThreshold = 4000f; // Watts
        [SerializeField] private float efficiencyAlertThreshold = 0.6f; // 60%

        // Monitoring data
        private float currentPower = 0f; // Watts
        private float totalEnergy = 0f; // Wh (Watt-hours)
        private float totalCost = 0f; // $
        private float peakPower = 0f; // Watts
        private float averagePower = 0f; // Watts

        // Timing
        private float sampleTimer = 0f;
        private float sampleInterval = 1f;
        private DateTime sessionStartTime;
        private float sessionDuration = 0f; // seconds

        // Machine state
        private MachineOperationState operationState = MachineOperationState.Idle;
        private float spindleSpeed = 0f; // RPM
        private float feedRate = 0f; // mm/min
        private bool spindleActive = false;
        private bool axesMoving = false;

        // Historical data
        private List<PowerSample> powerHistory = new List<PowerSample>();
        private int maxHistorySize = 1000;

        // Events
        public event Action<PowerSample> OnPowerSampleRecorded;
        public event Action<EnergyAlert> OnEnergyAlert;
        public event Action<EnergyStatistics> OnStatisticsUpdated;

        // Statistics
        private int totalSamples = 0;
        private int highPowerEvents = 0;
        private float powerIntegral = 0f; // For average calculation

        void Start()
        {
            sessionStartTime = DateTime.UtcNow;
            sampleInterval = 1f / sampleRate;

            Debug.Log($"[EnergyMonitor] Monitoring started for {machineId}");
        }

        void Update()
        {
            sessionDuration += Time.deltaTime;

            if (enableRealTimeMonitoring)
            {
                sampleTimer += Time.deltaTime;
                if (sampleTimer >= sampleInterval)
                {
                    SamplePower();
                    sampleTimer = 0f;
                }
            }
        }

        /// <summary>
        /// Sample current power consumption
        /// </summary>
        private void SamplePower()
        {
            // Calculate current power based on machine state
            currentPower = CalculatePower();

            // Update statistics
            totalSamples++;
            powerIntegral += currentPower;
            averagePower = powerIntegral / totalSamples;

            if (currentPower > peakPower)
            {
                peakPower = currentPower;
            }

            // Calculate energy (Wh)
            float energyDelta = (currentPower / 1000f) * (sampleInterval / 3600f); // Convert to kWh then to Wh
            totalEnergy += energyDelta * 1000f; // Store in Wh

            // Calculate cost
            if (enableCostTracking)
            {
                float costDelta = (energyDelta * energyCostPerKwh);
                totalCost += costDelta;
            }

            // Create power sample record
            var sample = new PowerSample
            {
                Timestamp = DateTime.UtcNow,
                Power = currentPower,
                Energy = energyDelta * 1000f, // Wh
                Cost = enableCostTracking ? (energyDelta * energyCostPerKwh) : 0,
                OperationState = operationState,
                SpindleSpeed = spindleSpeed,
                FeedRate = feedRate
            };

            powerHistory.Add(sample);

            // Enforce history limit
            if (powerHistory.Count > maxHistorySize)
            {
                powerHistory.RemoveAt(0);
            }

            OnPowerSampleRecorded?.Invoke(sample);

            // Check for alerts
            CheckForAlerts(sample);
        }

        /// <summary>
        /// Calculate power consumption based on machine state
        /// </summary>
        private float CalculatePower()
        {
            float power = idlePower;

            // Add spindle power
            if (spindleActive && spindleSpeed > 0)
            {
                float spindleLoad = spindleSpeed / 24000f; // Normalize to max spindle speed
                power += spindleLoad * maxPower * spindlePowerCoefficient;
            }

            // Add axes power
            if (axesMoving && feedRate > 0)
            {
                float axesLoad = feedRate / 2000f; // Normalize to max feed rate
                power += axesLoad * maxPower * axisPowerCoefficient;
            }

            return Mathf.Clamp(power, idlePower, maxPower);
        }

        /// <summary>
        /// Check for energy-related alerts
        /// </summary>
        private void CheckForAlerts(PowerSample sample)
        {
            // High power consumption alert
            if (sample.Power >= highPowerThreshold)
            {
                highPowerEvents++;

                OnEnergyAlert?.Invoke(new EnergyAlert
                {
                    AlertType = EnergyAlertType.HighPowerConsumption,
                    Severity = AlertSeverity.Warning,
                    Message = $"High power consumption: {sample.Power:F0}W",
                    Power = sample.Power,
                    Timestamp = DateTime.UtcNow
                });
            }

            // Efficiency alert (idle power too high relative to operation)
            if (operationState == MachineOperationState.Idle && sample.Power > idlePower * 1.5f)
            {
                OnEnergyAlert?.Invoke(new EnergyAlert
                {
                    AlertType = EnergyAlertType.InefficiencyDetected,
                    Severity = AlertSeverity.Info,
                    Message = "Elevated idle power consumption detected",
                    Power = sample.Power,
                    Timestamp = DateTime.UtcNow
                });
            }
        }

        /// <summary>
        /// Update machine operation state
        /// </summary>
        public void SetOperationState(MachineOperationState state)
        {
            operationState = state;
        }

        /// <summary>
        /// Update spindle parameters
        /// </summary>
        public void UpdateSpindleState(float speed, bool active)
        {
            spindleSpeed = speed;
            spindleActive = active;
        }

        /// <summary>
        /// Update axes movement state
        /// </summary>
        public void UpdateAxesState(float feed, bool moving)
        {
            feedRate = feed;
            axesMoving = moving;
        }

        /// <summary>
        /// Get current energy statistics
        /// </summary>
        public EnergyStatistics GetStatistics()
        {
            float efficiency = 0f;
            if (totalEnergy > 0)
            {
                // Efficiency = (productive energy / total energy)
                // Simplified: assume cutting state is productive
                float productiveEnergy = powerHistory.FindAll(s => s.OperationState == MachineOperationState.Cutting)
                    .Sum(s => s.Energy);
                efficiency = productiveEnergy / totalEnergy;
            }

            return new EnergyStatistics
            {
                MachineId = machineId,
                CurrentPower = currentPower,
                AveragePower = averagePower,
                PeakPower = peakPower,
                TotalEnergy = totalEnergy / 1000f, // Convert to kWh
                TotalCost = totalCost,
                SessionDuration = sessionDuration,
                Efficiency = efficiency,
                HighPowerEvents = highPowerEvents,
                TotalSamples = totalSamples,
                SessionStartTime = sessionStartTime
            };
        }

        /// <summary>
        /// Get power consumption by operation state
        /// </summary>
        public Dictionary<MachineOperationState, float> GetPowerByState()
        {
            var powerByState = new Dictionary<MachineOperationState, float>();

            foreach (MachineOperationState state in Enum.GetValues(typeof(MachineOperationState)))
            {
                var samplesInState = powerHistory.FindAll(s => s.OperationState == state);
                if (samplesInState.Count > 0)
                {
                    powerByState[state] = samplesInState.Average(s => s.Power);
                }
            }

            return powerByState;
        }

        /// <summary>
        /// Get power history for a time range
        /// </summary>
        public List<PowerSample> GetPowerHistory(int lastNSamples = 100)
        {
            int startIndex = Math.Max(0, powerHistory.Count - lastNSamples);
            return powerHistory.GetRange(startIndex, powerHistory.Count - startIndex);
        }

        /// <summary>
        /// Calculate projected cost for remaining time
        /// </summary>
        public float CalculateProjectedCost(float remainingHours)
        {
            if (sessionDuration == 0) return 0;

            float currentHourlyRate = (totalCost / (sessionDuration / 3600f));
            return currentHourlyRate * remainingHours;
        }

        /// <summary>
        /// Get energy optimization recommendations
        /// </summary>
        public List<string> GetOptimizationRecommendations()
        {
            var recommendations = new List<string>();

            var stats = GetStatistics();

            // Check idle power
            var idleSamples = powerHistory.FindAll(s => s.OperationState == MachineOperationState.Idle);
            if (idleSamples.Count > 0)
            {
                float avgIdlePower = idleSamples.Average(s => s.Power);
                if (avgIdlePower > idlePower * 1.3f)
                {
                    recommendations.Add($"Reduce idle power consumption (current: {avgIdlePower:F0}W, baseline: {idlePower:F0}W)");
                }
            }

            // Check efficiency
            if (stats.Efficiency < efficiencyAlertThreshold)
            {
                recommendations.Add($"Improve energy efficiency (current: {stats.Efficiency:P0})");
            }

            // Check for high power events
            if (highPowerEvents > totalSamples * 0.1f) // More than 10% of samples
            {
                recommendations.Add("Frequent high power events detected - review cutting parameters");
            }

            // Check peak power
            if (peakPower > maxPower * 0.9f)
            {
                recommendations.Add($"Peak power approaching limit ({peakPower:F0}W / {maxPower:F0}W)");
            }

            if (recommendations.Count == 0)
            {
                recommendations.Add("Energy consumption is optimal");
            }

            return recommendations;
        }

        /// <summary>
        /// Reset monitoring session
        /// </summary>
        public void ResetSession()
        {
            currentPower = 0f;
            totalEnergy = 0f;
            totalCost = 0f;
            peakPower = 0f;
            averagePower = 0f;
            sessionDuration = 0f;
            totalSamples = 0;
            highPowerEvents = 0;
            powerIntegral = 0f;
            powerHistory.Clear();
            sessionStartTime = DateTime.UtcNow;

            Debug.Log("[EnergyMonitor] Session reset");
        }

        #region Public Properties

        public float CurrentPower => currentPower;
        public float TotalEnergy => totalEnergy / 1000f; // kWh
        public float TotalCost => totalCost;
        public float AveragePower => averagePower;
        public float PeakPower => peakPower;
        public MachineOperationState OperationState => operationState;

        #endregion
    }

    #region Data Structures

    /// <summary>
    /// Power sample record
    /// </summary>
    [Serializable]
    public struct PowerSample
    {
        public DateTime Timestamp;
        public float Power; // Watts
        public float Energy; // Wh
        public float Cost; // $
        public MachineOperationState OperationState;
        public float SpindleSpeed; // RPM
        public float FeedRate; // mm/min
    }

    /// <summary>
    /// Energy statistics
    /// </summary>
    [Serializable]
    public struct EnergyStatistics
    {
        public string MachineId;
        public float CurrentPower;
        public float AveragePower;
        public float PeakPower;
        public float TotalEnergy; // kWh
        public float TotalCost; // $
        public float SessionDuration; // seconds
        public float Efficiency; // 0-1
        public int HighPowerEvents;
        public int TotalSamples;
        public DateTime SessionStartTime;
    }

    /// <summary>
    /// Energy alert
    /// </summary>
    [Serializable]
    public struct EnergyAlert
    {
        public EnergyAlertType AlertType;
        public AlertSeverity Severity;
        public string Message;
        public float Power;
        public DateTime Timestamp;
    }

    /// <summary>
    /// Machine operation state
    /// </summary>
    public enum MachineOperationState
    {
        Idle,
        Warming,
        Positioning,
        Cutting,
        Cooldown,
        Maintenance
    }

    /// <summary>
    /// Energy alert types
    /// </summary>
    public enum EnergyAlertType
    {
        HighPowerConsumption,
        InefficiencyDetected,
        CostThresholdExceeded,
        PeakDemandAlert
    }

    /// <summary>
    /// Alert severity levels
    /// </summary>
    public enum AlertSeverity
    {
        Info,
        Warning,
        Critical
    }

    #endregion
}
