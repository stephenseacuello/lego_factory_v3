using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace CNCDigitalTwin.Energy
{
    /// <summary>
    /// Energy Management System for CNC Digital Twin
    /// Monitors power consumption, calculates energy costs, optimizes usage,
    /// and supports ISO 50001 energy management compliance
    /// </summary>
    public class EnergyManagementSystem : MonoBehaviour
    {
        public static EnergyManagementSystem Instance { get; private set; }

        [Header("Energy Configuration")]
        [SerializeField] private float updateInterval = 1f; // seconds
        [SerializeField] private float baselinePower = 5000f; // Watts (idle)
        [SerializeField] private float maxPower = 50000f; // Watts
        [SerializeField] private float powerFactor = 0.92f;

        [Header("Cost Configuration")]
        [SerializeField] private float energyCostPerKwh = 0.12f; // $/kWh
        [SerializeField] private float demandChargePerKw = 15f; // $/kW peak
        [SerializeField] private bool useTieredPricing = true;
        [SerializeField] private float peakRateMultiplier = 1.5f;
        [SerializeField] private int peakStartHour = 14;
        [SerializeField] private int peakEndHour = 19;

        [Header("Efficiency Targets")]
        [SerializeField] private float targetEfficiency = 85f; // %
        [SerializeField] private float targetPUE = 1.2f; // Power Usage Effectiveness
        [SerializeField] private float targetSEC = 0.5f; // Specific Energy Consumption kWh/part

        // Events
        public event Action<EnergyState> OnEnergyStateUpdated;
        public event Action<PowerMeter, PowerReading> OnPowerReadingReceived;
        public event Action<EnergyAlert> OnEnergyAlert;
        public event Action<LoadEvent> OnLoadEvent;
        public event Action<EnergySavingOpportunity> OnSavingOpportunityDetected;

        // Meters and monitoring
        private Dictionary<string, PowerMeter> powerMeters = new Dictionary<string, PowerMeter>();
        private Dictionary<string, EnergyConsumer> energyConsumers = new Dictionary<string, EnergyConsumer>();
        private Dictionary<string, LoadProfile> loadProfiles = new Dictionary<string, LoadProfile>();

        // Energy data
        private List<PowerReading> powerHistory = new List<PowerReading>();
        private Dictionary<string, DailyEnergyData> dailyData = new Dictionary<string, DailyEnergyData>();
        private Dictionary<string, MonthlyEnergyData> monthlyData = new Dictionary<string, MonthlyEnergyData>();

        // Current state
        private EnergyState currentState = new EnergyState();
        private float peakDemandThisMonth = 0;
        private float totalEnergyThisMonth = 0;

        // Statistics
        private EnergyStats stats = new EnergyStats();

        #region Data Structures

        public enum MeterType
        {
            Main,
            Submeter,
            Circuit,
            Equipment,
            Virtual
        }

        public enum ConsumerType
        {
            Spindle,
            AxisDrive,
            Coolant,
            Hydraulic,
            Pneumatic,
            Lighting,
            HVAC,
            Auxiliary,
            Control
        }

        public enum LoadState
        {
            Off,
            Idle,
            Running,
            PeakLoad,
            Overload
        }

        public enum AlertType
        {
            HighPower,
            PeakDemand,
            LowPowerFactor,
            Anomaly,
            CostThreshold,
            EfficiencyLow,
            Harmonic
        }

        public class PowerMeter
        {
            public string MeterId { get; set; }
            public string Name { get; set; }
            public MeterType Type { get; set; }
            public string ParentMeterId { get; set; }
            public List<string> ChildMeterIds { get; set; } = new List<string>();
            public List<string> ConsumerIds { get; set; } = new List<string>();

            // Electrical parameters
            public float Voltage { get; set; }
            public float Current { get; set; }
            public float ActivePower { get; set; } // Watts
            public float ReactivePower { get; set; } // VAR
            public float ApparentPower { get; set; } // VA
            public float PowerFactor { get; set; }
            public float Frequency { get; set; }
            public float TotalEnergy { get; set; } // kWh (cumulative)

            // Harmonics
            public float THD_Voltage { get; set; } // %
            public float THD_Current { get; set; } // %

            // Demand
            public float DemandWindow { get; set; } // minutes
            public float CurrentDemand { get; set; }
            public float PeakDemand { get; set; }
            public DateTime PeakDemandTime { get; set; }

            public DateTime LastUpdate { get; set; }
            public bool IsOnline { get; set; }
        }

        public class PowerReading
        {
            public string MeterId { get; set; }
            public DateTime Timestamp { get; set; }
            public float Voltage { get; set; }
            public float Current { get; set; }
            public float ActivePower { get; set; }
            public float ReactivePower { get; set; }
            public float PowerFactor { get; set; }
            public float Energy { get; set; } // kWh since last reading
        }

        public class EnergyConsumer
        {
            public string ConsumerId { get; set; }
            public string Name { get; set; }
            public ConsumerType Type { get; set; }
            public string MeterId { get; set; }
            public float RatedPower { get; set; } // Watts
            public float EfficiencyRating { get; set; } // %
            public LoadState CurrentState { get; set; }
            public float CurrentPower { get; set; }
            public float TotalEnergy { get; set; } // kWh
            public float RunHours { get; set; }
            public DateTime LastStateChange { get; set; }

            // Cost allocation
            public float EnergyCost { get; set; }
            public float CostPerPart { get; set; }
        }

        public class LoadProfile
        {
            public string ProfileId { get; set; }
            public string Name { get; set; }
            public float[] HourlyLoad { get; set; } = new float[24]; // Average kW by hour
            public float BaseLoad { get; set; }
            public float PeakLoad { get; set; }
            public float LoadFactor { get; set; }
            public DateTime ProfileDate { get; set; }
        }

        public class DailyEnergyData
        {
            public DateTime Date { get; set; }
            public float TotalEnergy { get; set; } // kWh
            public float PeakDemand { get; set; } // kW
            public float AveragePower { get; set; } // kW
            public float AveragePowerFactor { get; set; }
            public float EnergyCost { get; set; }
            public float DemandCost { get; set; }
            public int PartsProduced { get; set; }
            public float EnergyPerPart { get; set; } // kWh/part
            public float[] HourlyEnergy { get; set; } = new float[24];
        }

        public class MonthlyEnergyData
        {
            public int Year { get; set; }
            public int Month { get; set; }
            public float TotalEnergy { get; set; } // kWh
            public float PeakDemand { get; set; } // kW
            public float EnergyCost { get; set; }
            public float DemandCost { get; set; }
            public float TotalCost { get; set; }
            public int ProductionDays { get; set; }
            public int TotalParts { get; set; }
            public float SEC { get; set; } // Specific energy consumption
        }

        public class EnergyState
        {
            public DateTime Timestamp { get; set; }
            public float TotalPower { get; set; } // kW
            public float TotalCurrent { get; set; } // A
            public float AveragePowerFactor { get; set; }
            public float CurrentDemand { get; set; } // kW (15-min average)
            public float TodayEnergy { get; set; } // kWh
            public float TodayCost { get; set; }
            public float CurrentEfficiency { get; set; } // %
            public float PUE { get; set; } // Power Usage Effectiveness
            public bool IsPeakPeriod { get; set; }
            public float CurrentRate { get; set; } // $/kWh
            public LoadState OverallLoadState { get; set; }
        }

        public class EnergyAlert
        {
            public string AlertId { get; set; }
            public DateTime Timestamp { get; set; }
            public AlertType Type { get; set; }
            public string Source { get; set; }
            public string Message { get; set; }
            public float CurrentValue { get; set; }
            public float Threshold { get; set; }
            public AlertSeverity Severity { get; set; }
            public string RecommendedAction { get; set; }
        }

        public enum AlertSeverity
        {
            Info,
            Warning,
            Critical
        }

        public class LoadEvent
        {
            public string EventId { get; set; }
            public DateTime Timestamp { get; set; }
            public string ConsumerId { get; set; }
            public LoadState FromState { get; set; }
            public LoadState ToState { get; set; }
            public float PowerChange { get; set; } // kW
        }

        public class EnergySavingOpportunity
        {
            public string OpportunityId { get; set; }
            public string Category { get; set; }
            public string Description { get; set; }
            public float PotentialSavingsKwh { get; set; }
            public float PotentialCostSavings { get; set; }
            public float ImplementationCost { get; set; }
            public float PaybackMonths { get; set; }
            public string RecommendedAction { get; set; }
            public float Confidence { get; set; }
        }

        public class EnergyStats
        {
            public DateTime StartTime { get; set; }
            public int TotalMeters { get; set; }
            public int OnlineMeters { get; set; }
            public int TotalConsumers { get; set; }
            public float TotalEnergyConsumed { get; set; }
            public float TotalEnergyCost { get; set; }
            public float BestEfficiency { get; set; }
            public float WorstEfficiency { get; set; }
            public int AlertsGenerated { get; set; }
            public int SavingsIdentified { get; set; }
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

            stats.StartTime = DateTime.Now;
        }

        private void Start()
        {
            InitializeDefaultConfiguration();
            StartCoroutine(EnergyMonitorLoop());
            StartCoroutine(DemandCalculationLoop());
            StartCoroutine(AnalysisLoop());

            Debug.Log("[Energy] Management system initialized");
        }

        private void InitializeDefaultConfiguration()
        {
            // Register main meter
            RegisterMeter("main", "Main Incomer", MeterType.Main);

            // Register submeters
            RegisterMeter("sub_machine", "Machine Panel", MeterType.Submeter, "main");
            RegisterMeter("sub_auxiliary", "Auxiliary Panel", MeterType.Submeter, "main");
            RegisterMeter("sub_hvac", "HVAC Panel", MeterType.Submeter, "main");

            // Register equipment meters
            RegisterMeter("meter_spindle", "Spindle Drive", MeterType.Equipment, "sub_machine");
            RegisterMeter("meter_x_axis", "X Axis Drive", MeterType.Equipment, "sub_machine");
            RegisterMeter("meter_y_axis", "Y Axis Drive", MeterType.Equipment, "sub_machine");
            RegisterMeter("meter_z_axis", "Z Axis Drive", MeterType.Equipment, "sub_machine");
            RegisterMeter("meter_coolant", "Coolant System", MeterType.Equipment, "sub_auxiliary");
            RegisterMeter("meter_hydraulic", "Hydraulic Unit", MeterType.Equipment, "sub_auxiliary");

            // Register consumers
            RegisterConsumer("spindle", "Main Spindle", ConsumerType.Spindle, "meter_spindle", 15000f, 95f);
            RegisterConsumer("x_drive", "X Axis Servo", ConsumerType.AxisDrive, "meter_x_axis", 3000f, 92f);
            RegisterConsumer("y_drive", "Y Axis Servo", ConsumerType.AxisDrive, "meter_y_axis", 3000f, 92f);
            RegisterConsumer("z_drive", "Z Axis Servo", ConsumerType.AxisDrive, "meter_z_axis", 4000f, 92f);
            RegisterConsumer("coolant_pump", "Coolant Pump", ConsumerType.Coolant, "meter_coolant", 2200f, 85f);
            RegisterConsumer("hydraulic_pump", "Hydraulic Pump", ConsumerType.Hydraulic, "meter_hydraulic", 5500f, 88f);
        }

        #endregion

        #region Meter Management

        public PowerMeter RegisterMeter(string meterId, string name, MeterType type, string parentId = null)
        {
            var meter = new PowerMeter
            {
                MeterId = meterId,
                Name = name,
                Type = type,
                ParentMeterId = parentId,
                Voltage = 480f,
                Frequency = 60f,
                DemandWindow = 15f,
                IsOnline = true,
                LastUpdate = DateTime.Now
            };

            powerMeters[meterId] = meter;
            stats.TotalMeters++;
            stats.OnlineMeters++;

            // Add to parent's child list
            if (!string.IsNullOrEmpty(parentId) && powerMeters.ContainsKey(parentId))
            {
                powerMeters[parentId].ChildMeterIds.Add(meterId);
            }

            Debug.Log($"[Energy] Registered meter: {meterId} ({type})");
            return meter;
        }

        public void RegisterConsumer(string consumerId, string name, ConsumerType type,
            string meterId, float ratedPower, float efficiency)
        {
            var consumer = new EnergyConsumer
            {
                ConsumerId = consumerId,
                Name = name,
                Type = type,
                MeterId = meterId,
                RatedPower = ratedPower,
                EfficiencyRating = efficiency,
                CurrentState = LoadState.Off,
                LastStateChange = DateTime.Now
            };

            energyConsumers[consumerId] = consumer;
            stats.TotalConsumers++;

            // Add to meter's consumer list
            if (powerMeters.ContainsKey(meterId))
            {
                powerMeters[meterId].ConsumerIds.Add(consumerId);
            }

            Debug.Log($"[Energy] Registered consumer: {consumerId} ({ratedPower}W)");
        }

        public void UpdateMeterReading(string meterId, float voltage, float current,
            float activePower, float reactivePower, float powerFactor)
        {
            if (!powerMeters.TryGetValue(meterId, out var meter))
                return;

            meter.Voltage = voltage;
            meter.Current = current;
            meter.ActivePower = activePower;
            meter.ReactivePower = reactivePower;
            meter.ApparentPower = Mathf.Sqrt(activePower * activePower + reactivePower * reactivePower);
            meter.PowerFactor = powerFactor;
            meter.LastUpdate = DateTime.Now;

            // Calculate energy increment
            float hoursElapsed = updateInterval / 3600f;
            float energyIncrement = activePower * hoursElapsed / 1000f; // kWh
            meter.TotalEnergy += energyIncrement;

            var reading = new PowerReading
            {
                MeterId = meterId,
                Timestamp = DateTime.Now,
                Voltage = voltage,
                Current = current,
                ActivePower = activePower,
                ReactivePower = reactivePower,
                PowerFactor = powerFactor,
                Energy = energyIncrement
            };

            powerHistory.Add(reading);

            // Trim history (keep last 24 hours at 1-second intervals)
            while (powerHistory.Count > 86400)
                powerHistory.RemoveAt(0);

            OnPowerReadingReceived?.Invoke(meter, reading);

            // Check for alerts
            CheckPowerAlerts(meter, reading);
        }

        public void UpdateConsumerState(string consumerId, LoadState state, float power)
        {
            if (!energyConsumers.TryGetValue(consumerId, out var consumer))
                return;

            var oldState = consumer.CurrentState;
            consumer.CurrentState = state;
            consumer.CurrentPower = power;

            if (oldState != state)
            {
                consumer.LastStateChange = DateTime.Now;

                OnLoadEvent?.Invoke(new LoadEvent
                {
                    EventId = Guid.NewGuid().ToString(),
                    Timestamp = DateTime.Now,
                    ConsumerId = consumerId,
                    FromState = oldState,
                    ToState = state,
                    PowerChange = (power - consumer.CurrentPower) / 1000f
                });
            }

            // Update run hours
            if (state == LoadState.Running || state == LoadState.PeakLoad)
            {
                consumer.RunHours += updateInterval / 3600f;
            }

            // Calculate energy and cost
            float energyIncrement = power * updateInterval / 3600000f; // kWh
            consumer.TotalEnergy += energyIncrement;
            consumer.EnergyCost = consumer.TotalEnergy * GetCurrentRate();
        }

        #endregion

        #region Energy Monitoring

        private IEnumerator EnergyMonitorLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(updateInterval);

                // Simulate readings for all meters
                SimulateMeterReadings();

                // Update overall state
                UpdateEnergyState();

                // Update daily data
                UpdateDailyData();
            }
        }

        private void SimulateMeterReadings()
        {
            float time = Time.time;

            foreach (var meter in powerMeters.Values)
            {
                if (!meter.IsOnline) continue;

                float basePower = 0;
                float loadVariation = 0;

                // Calculate power based on consumers
                foreach (var consumerId in meter.ConsumerIds)
                {
                    if (energyConsumers.TryGetValue(consumerId, out var consumer))
                    {
                        // Simulate consumer power based on state
                        float consumerPower = consumer.CurrentState switch
                        {
                            LoadState.Off => 0,
                            LoadState.Idle => consumer.RatedPower * 0.1f,
                            LoadState.Running => consumer.RatedPower * (0.5f + 0.3f * Mathf.Sin(time * 0.5f)),
                            LoadState.PeakLoad => consumer.RatedPower * 0.95f,
                            _ => 0
                        };

                        basePower += consumerPower;
                        UpdateConsumerState(consumer.ConsumerId, consumer.CurrentState, consumerPower);
                    }
                }

                // Add child meter power
                foreach (var childId in meter.ChildMeterIds)
                {
                    if (powerMeters.TryGetValue(childId, out var child))
                    {
                        basePower += child.ActivePower;
                    }
                }

                // For main meter, add baseline
                if (meter.Type == MeterType.Main)
                {
                    basePower += baselinePower;
                }

                // Add some variation
                loadVariation = basePower * 0.05f * Mathf.PerlinNoise(time * 0.1f, meter.MeterId.GetHashCode());
                float activePower = basePower + loadVariation;

                // Calculate other electrical parameters
                float voltage = 480f + UnityEngine.Random.Range(-5f, 5f);
                float pf = powerFactor + UnityEngine.Random.Range(-0.02f, 0.02f);
                float apparentPower = activePower / pf;
                float current = apparentPower / (voltage * Mathf.Sqrt(3f));
                float reactivePower = Mathf.Sqrt(apparentPower * apparentPower - activePower * activePower);

                UpdateMeterReading(meter.MeterId, voltage, current, activePower, reactivePower, pf);
            }
        }

        private void UpdateEnergyState()
        {
            var main = powerMeters.Values.FirstOrDefault(m => m.Type == MeterType.Main);
            if (main == null) return;

            currentState.Timestamp = DateTime.Now;
            currentState.TotalPower = main.ActivePower / 1000f; // kW
            currentState.TotalCurrent = main.Current;
            currentState.AveragePowerFactor = main.PowerFactor;
            currentState.CurrentDemand = main.CurrentDemand;

            // Check if peak period
            int hour = DateTime.Now.Hour;
            currentState.IsPeakPeriod = hour >= peakStartHour && hour < peakEndHour;
            currentState.CurrentRate = GetCurrentRate();

            // Calculate today's energy (from daily data)
            string todayKey = DateTime.Today.ToString("yyyy-MM-dd");
            if (dailyData.TryGetValue(todayKey, out var today))
            {
                currentState.TodayEnergy = today.TotalEnergy;
                currentState.TodayCost = today.EnergyCost + today.DemandCost;
            }

            // Calculate efficiency
            float productivePower = energyConsumers.Values
                .Where(c => c.CurrentState == LoadState.Running || c.CurrentState == LoadState.PeakLoad)
                .Sum(c => c.CurrentPower);
            currentState.CurrentEfficiency = main.ActivePower > 0 ?
                (productivePower / main.ActivePower) * 100f : 0;

            // Calculate PUE (IT load / Total load) - simplified for manufacturing
            float productionPower = powerMeters.Values
                .Where(m => m.Type == MeterType.Equipment)
                .Sum(m => m.ActivePower);
            currentState.PUE = productionPower > 0 ?
                main.ActivePower / productionPower : 1f;

            // Determine load state
            float loadPercent = main.ActivePower / maxPower * 100f;
            currentState.OverallLoadState = loadPercent switch
            {
                < 10 => LoadState.Off,
                < 30 => LoadState.Idle,
                < 80 => LoadState.Running,
                < 100 => LoadState.PeakLoad,
                _ => LoadState.Overload
            };

            OnEnergyStateUpdated?.Invoke(currentState);
        }

        private IEnumerator DemandCalculationLoop()
        {
            var demandWindow = new Queue<PowerReading>();
            float windowMinutes = 15f;

            while (true)
            {
                yield return new WaitForSeconds(60f); // Calculate every minute

                // Get readings from last 15 minutes
                var cutoff = DateTime.Now.AddMinutes(-windowMinutes);
                var recentReadings = powerHistory.Where(r =>
                    r.Timestamp > cutoff && r.MeterId == "main").ToList();

                if (recentReadings.Count > 0)
                {
                    float avgPower = recentReadings.Average(r => r.ActivePower) / 1000f; // kW

                    if (powerMeters.TryGetValue("main", out var main))
                    {
                        main.CurrentDemand = avgPower;

                        // Update peak demand
                        if (avgPower > main.PeakDemand)
                        {
                            main.PeakDemand = avgPower;
                            main.PeakDemandTime = DateTime.Now;

                            // Update monthly peak
                            if (avgPower > peakDemandThisMonth)
                            {
                                peakDemandThisMonth = avgPower;

                                GenerateAlert(AlertType.PeakDemand, "main",
                                    $"New peak demand: {avgPower:F1} kW",
                                    avgPower, peakDemandThisMonth * 0.9f, AlertSeverity.Warning);
                            }
                        }
                    }
                }
            }
        }

        #endregion

        #region Daily/Monthly Tracking

        private void UpdateDailyData()
        {
            string todayKey = DateTime.Today.ToString("yyyy-MM-dd");

            if (!dailyData.ContainsKey(todayKey))
            {
                dailyData[todayKey] = new DailyEnergyData
                {
                    Date = DateTime.Today,
                    HourlyEnergy = new float[24]
                };
            }

            var today = dailyData[todayKey];
            var main = powerMeters.Values.FirstOrDefault(m => m.Type == MeterType.Main);

            if (main != null)
            {
                // Add energy increment
                float energyIncrement = main.ActivePower * updateInterval / 3600000f; // kWh
                today.TotalEnergy += energyIncrement;
                today.HourlyEnergy[DateTime.Now.Hour] += energyIncrement;

                // Update peak
                float currentDemandKw = main.ActivePower / 1000f;
                if (currentDemandKw > today.PeakDemand)
                {
                    today.PeakDemand = currentDemandKw;
                }

                // Update average
                today.AveragePower = (float)(today.TotalEnergy / ((DateTime.Now - DateTime.Today).TotalHours + 0.001));
                today.AveragePowerFactor = main.PowerFactor; // Simplified

                // Calculate costs
                bool isPeak = DateTime.Now.Hour >= peakStartHour && DateTime.Now.Hour < peakEndHour;
                float rate = isPeak ? energyCostPerKwh * peakRateMultiplier : energyCostPerKwh;
                today.EnergyCost += energyIncrement * rate;
            }

            // Update monthly totals
            UpdateMonthlyData(today);
        }

        private void UpdateMonthlyData(DailyEnergyData dailyData)
        {
            string monthKey = $"{DateTime.Now.Year}-{DateTime.Now.Month:D2}";

            if (!this.monthlyData.ContainsKey(monthKey))
            {
                this.monthlyData[monthKey] = new MonthlyEnergyData
                {
                    Year = DateTime.Now.Year,
                    Month = DateTime.Now.Month
                };
            }

            var monthly = this.monthlyData[monthKey];
            monthly.TotalEnergy = this.dailyData.Values
                .Where(d => d.Date.Year == DateTime.Now.Year && d.Date.Month == DateTime.Now.Month)
                .Sum(d => d.TotalEnergy);

            monthly.PeakDemand = peakDemandThisMonth;
            monthly.EnergyCost = monthly.TotalEnergy * energyCostPerKwh; // Simplified
            monthly.DemandCost = monthly.PeakDemand * demandChargePerKw;
            monthly.TotalCost = monthly.EnergyCost + monthly.DemandCost;
        }

        #endregion

        #region Cost Calculation

        public float GetCurrentRate()
        {
            if (!useTieredPricing)
                return energyCostPerKwh;

            int hour = DateTime.Now.Hour;
            bool isPeak = hour >= peakStartHour && hour < peakEndHour;

            return isPeak ? energyCostPerKwh * peakRateMultiplier : energyCostPerKwh;
        }

        public float CalculateEnergyCost(float kWh, DateTime startTime, DateTime endTime)
        {
            float cost = 0;
            float remainingEnergy = kWh;
            DateTime current = startTime;

            while (current < endTime && remainingEnergy > 0)
            {
                float hourlyEnergy = kWh / (float)(endTime - startTime).TotalHours;
                bool isPeak = current.Hour >= peakStartHour && current.Hour < peakEndHour;
                float rate = isPeak ? energyCostPerKwh * peakRateMultiplier : energyCostPerKwh;

                cost += hourlyEnergy * rate;
                remainingEnergy -= hourlyEnergy;
                current = current.AddHours(1);
            }

            return cost;
        }

        public float CalculateDemandCost(float peakDemandKw)
        {
            return peakDemandKw * demandChargePerKw;
        }

        #endregion

        #region Analysis

        private IEnumerator AnalysisLoop()
        {
            while (true)
            {
                yield return new WaitForSeconds(300f); // Every 5 minutes

                AnalyzeEfficiency();
                IdentifySavingOpportunities();
                GenerateLoadProfile();
            }
        }

        private void AnalyzeEfficiency()
        {
            foreach (var consumer in energyConsumers.Values)
            {
                if (consumer.RunHours > 0 && consumer.TotalEnergy > 0)
                {
                    float actualEfficiency = (consumer.RatedPower * consumer.RunHours / 1000f) /
                                            (consumer.TotalEnergy + 0.001f) * 100f;

                    // Check if efficiency is significantly below rated
                    if (actualEfficiency < consumer.EfficiencyRating * 0.85f)
                    {
                        GenerateAlert(AlertType.EfficiencyLow, consumer.ConsumerId,
                            $"Efficiency degraded: {actualEfficiency:F1}% vs {consumer.EfficiencyRating:F1}% rated",
                            actualEfficiency, consumer.EfficiencyRating * 0.85f, AlertSeverity.Warning);
                    }
                }
            }

            // Overall efficiency tracking
            if (currentState.CurrentEfficiency > stats.BestEfficiency)
                stats.BestEfficiency = currentState.CurrentEfficiency;
            if (currentState.CurrentEfficiency < stats.WorstEfficiency || stats.WorstEfficiency == 0)
                stats.WorstEfficiency = currentState.CurrentEfficiency;
        }

        private void IdentifySavingOpportunities()
        {
            // Check for idle power waste
            var idleConsumers = energyConsumers.Values.Where(c =>
                c.CurrentState == LoadState.Idle && c.CurrentPower > c.RatedPower * 0.2f);

            foreach (var consumer in idleConsumers)
            {
                float excessPower = consumer.CurrentPower - (consumer.RatedPower * 0.1f);
                float annualSavings = excessPower * 8760f / 1000f * energyCostPerKwh;

                if (annualSavings > 100) // Only report if savings > $100/year
                {
                    var opportunity = new EnergySavingOpportunity
                    {
                        OpportunityId = Guid.NewGuid().ToString(),
                        Category = "Idle Power Reduction",
                        Description = $"High idle power on {consumer.Name}",
                        PotentialSavingsKwh = excessPower * 8760f / 1000f,
                        PotentialCostSavings = annualSavings,
                        ImplementationCost = 0,
                        PaybackMonths = 0,
                        RecommendedAction = "Implement auto-shutdown or power management",
                        Confidence = 85f
                    };

                    OnSavingOpportunityDetected?.Invoke(opportunity);
                    stats.SavingsIdentified++;
                }
            }

            // Check power factor opportunities
            var main = powerMeters.Values.FirstOrDefault(m => m.Type == MeterType.Main);
            if (main != null && main.PowerFactor < 0.9f)
            {
                float reactiveKvar = main.ReactivePower / 1000f;
                float capacitorCost = reactiveKvar * 50f; // Rough estimate
                float demandSavings = reactiveKvar * 0.2f * demandChargePerKw * 12f; // Annual savings

                var opportunity = new EnergySavingOpportunity
                {
                    OpportunityId = Guid.NewGuid().ToString(),
                    Category = "Power Factor Correction",
                    Description = $"Power factor at {main.PowerFactor:P0}, below optimal 0.95",
                    PotentialSavingsKwh = 0,
                    PotentialCostSavings = demandSavings,
                    ImplementationCost = capacitorCost,
                    PaybackMonths = capacitorCost / (demandSavings / 12f),
                    RecommendedAction = $"Install {reactiveKvar:F0} kVAR capacitor bank",
                    Confidence = 90f
                };

                OnSavingOpportunityDetected?.Invoke(opportunity);
            }
        }

        private void GenerateLoadProfile()
        {
            var profile = new LoadProfile
            {
                ProfileId = DateTime.Today.ToString("yyyy-MM-dd"),
                Name = "Daily Load Profile",
                ProfileDate = DateTime.Today,
                HourlyLoad = new float[24]
            };

            string todayKey = DateTime.Today.ToString("yyyy-MM-dd");
            if (dailyData.TryGetValue(todayKey, out var today))
            {
                for (int h = 0; h < 24; h++)
                {
                    profile.HourlyLoad[h] = today.HourlyEnergy[h]; // kWh as proxy for average kW
                }

                profile.PeakLoad = today.PeakDemand;
                profile.BaseLoad = profile.HourlyLoad.Where(l => l > 0).DefaultIfEmpty(0).Min();
                profile.LoadFactor = today.AveragePower / (today.PeakDemand + 0.001f);
            }

            loadProfiles[profile.ProfileId] = profile;
        }

        #endregion

        #region Alerts

        private void CheckPowerAlerts(PowerMeter meter, PowerReading reading)
        {
            // High power alert
            if (meter.Type == MeterType.Main && reading.ActivePower > maxPower * 0.9f)
            {
                GenerateAlert(AlertType.HighPower, meter.MeterId,
                    $"Power at {reading.ActivePower / 1000f:F1} kW ({reading.ActivePower / maxPower * 100:F0}% of max)",
                    reading.ActivePower / 1000f, maxPower * 0.9f / 1000f, AlertSeverity.Warning);
            }

            // Low power factor alert
            if (reading.PowerFactor < 0.85f)
            {
                GenerateAlert(AlertType.LowPowerFactor, meter.MeterId,
                    $"Low power factor: {reading.PowerFactor:P0}",
                    reading.PowerFactor * 100f, 85f, AlertSeverity.Warning);
            }

            // High THD alert
            if (meter.THD_Current > 15f)
            {
                GenerateAlert(AlertType.Harmonic, meter.MeterId,
                    $"High current THD: {meter.THD_Current:F1}%",
                    meter.THD_Current, 15f, AlertSeverity.Warning);
            }
        }

        private void GenerateAlert(AlertType type, string source, string message,
            float currentValue, float threshold, AlertSeverity severity)
        {
            var alert = new EnergyAlert
            {
                AlertId = Guid.NewGuid().ToString(),
                Timestamp = DateTime.Now,
                Type = type,
                Source = source,
                Message = message,
                CurrentValue = currentValue,
                Threshold = threshold,
                Severity = severity,
                RecommendedAction = GetRecommendedAction(type)
            };

            stats.AlertsGenerated++;
            OnEnergyAlert?.Invoke(alert);

            Debug.LogWarning($"[Energy] ALERT: {type} - {message}");
        }

        private string GetRecommendedAction(AlertType type)
        {
            return type switch
            {
                AlertType.HighPower => "Review active loads, consider load shedding",
                AlertType.PeakDemand => "Implement demand limiting, reschedule loads",
                AlertType.LowPowerFactor => "Check capacitor banks, add PF correction",
                AlertType.Harmonic => "Check VFD filters, install harmonic filters",
                AlertType.EfficiencyLow => "Schedule maintenance inspection",
                AlertType.CostThreshold => "Review energy usage patterns",
                _ => "Investigate and monitor"
            };
        }

        #endregion

        #region Public API

        public PowerMeter GetMeter(string meterId)
        {
            return powerMeters.TryGetValue(meterId, out var meter) ? meter : null;
        }

        public List<PowerMeter> GetAllMeters()
        {
            return powerMeters.Values.ToList();
        }

        public EnergyConsumer GetConsumer(string consumerId)
        {
            return energyConsumers.TryGetValue(consumerId, out var consumer) ? consumer : null;
        }

        public List<EnergyConsumer> GetAllConsumers()
        {
            return energyConsumers.Values.ToList();
        }

        public EnergyState GetCurrentState()
        {
            return currentState;
        }

        public DailyEnergyData GetDailyData(DateTime date)
        {
            string key = date.ToString("yyyy-MM-dd");
            return dailyData.TryGetValue(key, out var data) ? data : null;
        }

        public MonthlyEnergyData GetMonthlyData(int year, int month)
        {
            string key = $"{year}-{month:D2}";
            return monthlyData.TryGetValue(key, out var data) ? data : null;
        }

        public LoadProfile GetLoadProfile(string date)
        {
            return loadProfiles.TryGetValue(date, out var profile) ? profile : null;
        }

        public List<PowerReading> GetPowerHistory(string meterId, int lastNMinutes)
        {
            var cutoff = DateTime.Now.AddMinutes(-lastNMinutes);
            return powerHistory.Where(r => r.MeterId == meterId && r.Timestamp > cutoff).ToList();
        }

        public EnergyStats GetStats()
        {
            stats.TotalEnergyConsumed = powerMeters.Values
                .Where(m => m.Type == MeterType.Main)
                .Sum(m => m.TotalEnergy);
            stats.TotalEnergyCost = stats.TotalEnergyConsumed * energyCostPerKwh;
            stats.OnlineMeters = powerMeters.Values.Count(m => m.IsOnline);

            return stats;
        }

        public float GetTotalPowerKw()
        {
            return currentState.TotalPower;
        }

        public float GetTodayEnergyKwh()
        {
            return currentState.TodayEnergy;
        }

        public float GetTodayCost()
        {
            return currentState.TodayCost;
        }

        public void SetConsumerState(string consumerId, LoadState state)
        {
            if (energyConsumers.TryGetValue(consumerId, out var consumer))
            {
                float power = state switch
                {
                    LoadState.Off => 0,
                    LoadState.Idle => consumer.RatedPower * 0.1f,
                    LoadState.Running => consumer.RatedPower * 0.7f,
                    LoadState.PeakLoad => consumer.RatedPower * 0.95f,
                    _ => 0
                };

                UpdateConsumerState(consumerId, state, power);
            }
        }

        #endregion
    }
}
