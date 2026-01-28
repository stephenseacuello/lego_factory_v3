using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CNCScada.Energy
{
    /// <summary>
    /// Energy monitoring system for tracking power consumption across machines.
    /// Calculates real-time power usage, energy costs, and carbon footprint.
    /// Supports demand management and peak load detection.
    /// </summary>
    public class EnergyMonitoringSystem : MonoBehaviour
    {
        [Header("Configuration")]
        [SerializeField] private float updateInterval = 1f;
        [SerializeField] private float energyCostPerKWh = 0.12f; // dollars
        [SerializeField] private float carbonFactorKgPerKWh = 0.4f; // kg CO2 per kWh
        [SerializeField] private float peakDemandThreshold = 5000f; // Watts

        [Header("Power Sources")]
        [SerializeField] private List<PowerMeter> powerMeters = new List<PowerMeter>();

        [Header("Current Readings")]
        [SerializeField] private float totalPowerWatts;
        [SerializeField] private float totalEnergyKWh;
        [SerializeField] private float totalCostDollars;
        [SerializeField] private float carbonFootprintKg;
        [SerializeField] private float powerFactorAverage;

        [Header("Statistics")]
        [SerializeField] private float peakPowerWatts;
        [SerializeField] private float averagePowerWatts;
        [SerializeField] private DateTime peakPowerTime;
        [SerializeField] private int demandAlertCount;

        // Historical data
        private List<EnergyReading> readingHistory = new List<EnergyReading>();
        private Dictionary<string, MachineEnergyProfile> machineProfiles = new Dictionary<string, MachineEnergyProfile>();
        private const int MaxHistorySize = 3600; // 1 hour at 1 reading/sec

        // Tracking
        private DateTime monitoringStartTime;
        private float previousEnergy;
        private Coroutine monitoringCoroutine;

        // Events
        public event Action<EnergyReading> OnReadingUpdated;
        public event Action<float> OnPeakDemandAlert;
        public event Action<MachineEnergyProfile> OnMachineEnergyChanged;

        // Singleton
        public static EnergyMonitoringSystem Instance { get; private set; }

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

            monitoringStartTime = DateTime.Now;
            InitializeDefaultMeters();
        }

        private void Start()
        {
            monitoringCoroutine = StartCoroutine(MonitoringLoop());
        }

        private void OnDestroy()
        {
            if (monitoringCoroutine != null)
            {
                StopCoroutine(monitoringCoroutine);
            }
        }

        private void InitializeDefaultMeters()
        {
            // Initialize default power meters for known machines
            powerMeters.Add(new PowerMeter
            {
                meterId = "PM_CNC_001",
                meterName = "Bantam CNC Main",
                machineId = "BantamCNC",
                maxPowerWatts = 500,
                standbyPowerWatts = 25,
                voltageNominal = 120,
                currentNominal = 4.2f
            });

            powerMeters.Add(new PowerMeter
            {
                meterId = "PM_XARM_001",
                meterName = "xArm Lite 6 Main",
                machineId = "xArm",
                maxPowerWatts = 200,
                standbyPowerWatts = 15,
                voltageNominal = 24,
                currentNominal = 8.3f
            });

            powerMeters.Add(new PowerMeter
            {
                meterId = "PM_NIRYO_001",
                meterName = "Niryo Ned2 Main",
                machineId = "Niryo",
                maxPowerWatts = 100,
                standbyPowerWatts = 10,
                voltageNominal = 12,
                currentNominal = 8.3f
            });

            powerMeters.Add(new PowerMeter
            {
                meterId = "PM_AUX_001",
                meterName = "Auxiliary Systems",
                machineId = "Auxiliary",
                maxPowerWatts = 300,
                standbyPowerWatts = 50,
                voltageNominal = 120,
                currentNominal = 2.5f
            });

            // Initialize machine profiles
            foreach (var meter in powerMeters)
            {
                machineProfiles[meter.machineId] = new MachineEnergyProfile
                {
                    machineId = meter.machineId,
                    machineName = meter.meterName
                };
            }
        }

        private IEnumerator MonitoringLoop()
        {
            while (true)
            {
                UpdateReadings();
                yield return new WaitForSeconds(updateInterval);
            }
        }

        private void UpdateReadings()
        {
            float totalPower = 0;
            float totalPF = 0;
            int pfCount = 0;

            foreach (var meter in powerMeters)
            {
                // Simulate or read actual meter values
                var reading = SimulateMeterReading(meter);
                meter.currentReading = reading;

                totalPower += reading.activePowerWatts;

                if (reading.powerFactor > 0)
                {
                    totalPF += reading.powerFactor;
                    pfCount++;
                }

                // Update machine profile
                if (machineProfiles.TryGetValue(meter.machineId, out var profile))
                {
                    profile.currentPowerWatts = reading.activePowerWatts;
                    profile.totalEnergyKWh += (reading.activePowerWatts / 1000f) * (updateInterval / 3600f);

                    if (reading.activePowerWatts > profile.peakPowerWatts)
                    {
                        profile.peakPowerWatts = reading.activePowerWatts;
                        profile.peakPowerTime = DateTime.Now;
                    }

                    OnMachineEnergyChanged?.Invoke(profile);
                }
            }

            totalPowerWatts = totalPower;
            powerFactorAverage = pfCount > 0 ? totalPF / pfCount : 0;

            // Calculate energy consumption
            float energyIncrement = (totalPower / 1000f) * (updateInterval / 3600f); // kWh
            totalEnergyKWh += energyIncrement;

            // Calculate costs and carbon
            totalCostDollars = totalEnergyKWh * energyCostPerKWh;
            carbonFootprintKg = totalEnergyKWh * carbonFactorKgPerKWh;

            // Track peak demand
            if (totalPower > peakPowerWatts)
            {
                peakPowerWatts = totalPower;
                peakPowerTime = DateTime.Now;
            }

            // Calculate running average
            if (readingHistory.Count > 0)
            {
                averagePowerWatts = readingHistory.Average(r => r.totalPowerWatts);
            }

            // Check for demand alert
            if (totalPower > peakDemandThreshold)
            {
                demandAlertCount++;
                OnPeakDemandAlert?.Invoke(totalPower);

                // Raise alarm
                var alarmSystem = FindObjectOfType<CNCScada.Alarms.AlarmSystem>();
                alarmSystem?.RaiseCustomAlarm(
                    "Peak Demand Warning",
                    $"Power consumption {totalPower:F0}W exceeds threshold {peakDemandThreshold:F0}W",
                    CNCScada.Alarms.AlarmSeverity.Medium,
                    CNCScada.Alarms.AlarmCategory.System,
                    "EnergyMonitoring"
                );
            }

            // Create reading record
            var energyReading = new EnergyReading
            {
                timestamp = DateTime.Now,
                totalPowerWatts = totalPower,
                totalEnergyKWh = totalEnergyKWh,
                powerFactor = powerFactorAverage,
                costDollars = totalCostDollars,
                carbonKg = carbonFootprintKg
            };

            // Add to history
            readingHistory.Add(energyReading);
            while (readingHistory.Count > MaxHistorySize)
            {
                readingHistory.RemoveAt(0);
            }

            OnReadingUpdated?.Invoke(energyReading);
        }

        private MeterReading SimulateMeterReading(PowerMeter meter)
        {
            // Simulate realistic power consumption based on machine state
            float basePower = meter.standbyPowerWatts;
            float loadFactor = 0.3f; // Default 30% load

            // Check if machine is actively running
            var cncController = FindObjectOfType<CNCScada.Machines.BantamCNCController>();
            var xarmController = FindObjectOfType<CNCScada.Machines.XArmLite6Controller>();
            var niryoController = FindObjectOfType<CNCScada.Machines.NiryoNed2Controller>();

            switch (meter.machineId)
            {
                case "BantamCNC":
                    if (cncController != null)
                    {
                        // Power based on spindle speed and axis movement
                        float spindleLoad = cncController.SpindleSpeed / 10000f;
                        loadFactor = 0.2f + spindleLoad * 0.6f;
                        loadFactor += UnityEngine.Random.Range(-0.05f, 0.05f); // Add noise
                    }
                    break;

                case "xArm":
                    if (xarmController != null)
                    {
                        // Power based on joint movement
                        loadFactor = 0.15f + UnityEngine.Random.Range(0f, 0.3f);
                    }
                    break;

                case "Niryo":
                    if (niryoController != null)
                    {
                        loadFactor = 0.1f + UnityEngine.Random.Range(0f, 0.25f);
                    }
                    break;

                case "Auxiliary":
                    // Auxiliary systems have relatively constant load
                    loadFactor = 0.4f + UnityEngine.Random.Range(-0.1f, 0.1f);
                    break;
            }

            loadFactor = Mathf.Clamp01(loadFactor);
            float activePower = basePower + (meter.maxPowerWatts - basePower) * loadFactor;

            // Calculate apparent power and power factor
            float powerFactor = 0.85f + UnityEngine.Random.Range(-0.05f, 0.1f);
            powerFactor = Mathf.Clamp(powerFactor, 0.7f, 0.99f);

            float apparentPower = activePower / powerFactor;
            float reactivePower = Mathf.Sqrt(apparentPower * apparentPower - activePower * activePower);

            // Calculate voltage and current
            float voltage = meter.voltageNominal * (0.98f + UnityEngine.Random.Range(0f, 0.04f));
            float current = apparentPower / voltage;

            return new MeterReading
            {
                timestamp = DateTime.Now,
                voltage = voltage,
                current = current,
                activePowerWatts = activePower,
                reactivePowerVAR = reactivePower,
                apparentPowerVA = apparentPower,
                powerFactor = powerFactor,
                frequency = 60f + UnityEngine.Random.Range(-0.1f, 0.1f)
            };
        }

        // =========================================================================
        // Public API
        // =========================================================================

        /// <summary>
        /// Get current energy reading
        /// </summary>
        public EnergyReading GetCurrentReading()
        {
            return new EnergyReading
            {
                timestamp = DateTime.Now,
                totalPowerWatts = totalPowerWatts,
                totalEnergyKWh = totalEnergyKWh,
                powerFactor = powerFactorAverage,
                costDollars = totalCostDollars,
                carbonKg = carbonFootprintKg
            };
        }

        /// <summary>
        /// Get energy profile for a specific machine
        /// </summary>
        public MachineEnergyProfile GetMachineProfile(string machineId)
        {
            return machineProfiles.TryGetValue(machineId, out var profile) ? profile : null;
        }

        /// <summary>
        /// Get all machine energy profiles
        /// </summary>
        public List<MachineEnergyProfile> GetAllMachineProfiles()
        {
            return new List<MachineEnergyProfile>(machineProfiles.Values);
        }

        /// <summary>
        /// Get energy consumption for a time period
        /// </summary>
        public EnergyPeriodSummary GetPeriodSummary(DateTime start, DateTime end)
        {
            var periodReadings = readingHistory
                .Where(r => r.timestamp >= start && r.timestamp <= end)
                .ToList();

            if (periodReadings.Count == 0)
            {
                return new EnergyPeriodSummary { periodStart = start, periodEnd = end };
            }

            return new EnergyPeriodSummary
            {
                periodStart = start,
                periodEnd = end,
                totalEnergyKWh = periodReadings.Last().totalEnergyKWh - periodReadings.First().totalEnergyKWh,
                averagePowerWatts = periodReadings.Average(r => r.totalPowerWatts),
                peakPowerWatts = periodReadings.Max(r => r.totalPowerWatts),
                minPowerWatts = periodReadings.Min(r => r.totalPowerWatts),
                averagePowerFactor = periodReadings.Average(r => r.powerFactor),
                totalCostDollars = (periodReadings.Last().totalEnergyKWh - periodReadings.First().totalEnergyKWh) * energyCostPerKWh,
                totalCarbonKg = (periodReadings.Last().totalEnergyKWh - periodReadings.First().totalEnergyKWh) * carbonFactorKgPerKWh
            };
        }

        /// <summary>
        /// Get reading history
        /// </summary>
        public List<EnergyReading> GetReadingHistory(int maxRecords = 100)
        {
            int skip = Math.Max(0, readingHistory.Count - maxRecords);
            return readingHistory.Skip(skip).ToList();
        }

        /// <summary>
        /// Set energy cost rate
        /// </summary>
        public void SetEnergyCost(float costPerKWh)
        {
            energyCostPerKWh = costPerKWh;
            Debug.Log($"[EnergyMonitoring] Energy cost set to ${costPerKWh}/kWh");
        }

        /// <summary>
        /// Set peak demand threshold
        /// </summary>
        public void SetPeakDemandThreshold(float thresholdWatts)
        {
            peakDemandThreshold = thresholdWatts;
            Debug.Log($"[EnergyMonitoring] Peak demand threshold set to {thresholdWatts}W");
        }

        /// <summary>
        /// Reset energy counters
        /// </summary>
        public void ResetCounters()
        {
            totalEnergyKWh = 0;
            totalCostDollars = 0;
            carbonFootprintKg = 0;
            peakPowerWatts = 0;
            demandAlertCount = 0;
            monitoringStartTime = DateTime.Now;
            readingHistory.Clear();

            foreach (var profile in machineProfiles.Values)
            {
                profile.totalEnergyKWh = 0;
                profile.peakPowerWatts = 0;
            }

            Debug.Log("[EnergyMonitoring] Counters reset");
        }

        /// <summary>
        /// Add a power meter
        /// </summary>
        public void AddPowerMeter(PowerMeter meter)
        {
            powerMeters.Add(meter);
            machineProfiles[meter.machineId] = new MachineEnergyProfile
            {
                machineId = meter.machineId,
                machineName = meter.meterName
            };
        }

        // Properties
        public float TotalPowerWatts => totalPowerWatts;
        public float TotalEnergyKWh => totalEnergyKWh;
        public float TotalCostDollars => totalCostDollars;
        public float CarbonFootprintKg => carbonFootprintKg;
        public float PeakPowerWatts => peakPowerWatts;
        public float AveragePowerWatts => averagePowerWatts;
        public float PowerFactor => powerFactorAverage;
        public TimeSpan MonitoringDuration => DateTime.Now - monitoringStartTime;
    }

    // =========================================================================
    // Data Types
    // =========================================================================

    [Serializable]
    public class PowerMeter
    {
        public string meterId;
        public string meterName;
        public string machineId;
        public float maxPowerWatts;
        public float standbyPowerWatts;
        public float voltageNominal;
        public float currentNominal;
        public MeterReading currentReading;
    }

    [Serializable]
    public class MeterReading
    {
        public DateTime timestamp;
        public float voltage;
        public float current;
        public float activePowerWatts;
        public float reactivePowerVAR;
        public float apparentPowerVA;
        public float powerFactor;
        public float frequency;
    }

    [Serializable]
    public class EnergyReading
    {
        public DateTime timestamp;
        public float totalPowerWatts;
        public float totalEnergyKWh;
        public float powerFactor;
        public float costDollars;
        public float carbonKg;
    }

    [Serializable]
    public class MachineEnergyProfile
    {
        public string machineId;
        public string machineName;
        public float currentPowerWatts;
        public float totalEnergyKWh;
        public float peakPowerWatts;
        public DateTime peakPowerTime;
        public float averageEfficiency;
    }

    [Serializable]
    public class EnergyPeriodSummary
    {
        public DateTime periodStart;
        public DateTime periodEnd;
        public float totalEnergyKWh;
        public float averagePowerWatts;
        public float peakPowerWatts;
        public float minPowerWatts;
        public float averagePowerFactor;
        public float totalCostDollars;
        public float totalCarbonKg;

        public TimeSpan Duration => periodEnd - periodStart;
    }
}
