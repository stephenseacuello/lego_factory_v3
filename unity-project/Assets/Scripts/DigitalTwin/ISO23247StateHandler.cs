using UnityEngine;
using System;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace CNCScada.DigitalTwin
{
    /// <summary>
    /// ISO 23247 Digital Twin State Handler
    /// Deserializes and manages machine state according to ISO 23247 standard
    /// Part of Phase 2: Real-Time Visualization (60Hz)
    /// </summary>
    public class ISO23247StateHandler : MonoBehaviour
    {
        [Header("Configuration")]
        [SerializeField] private float stateUpdateRate = 60f; // Hz
        [SerializeField] private bool enableInterpolation = true;
        [SerializeField] private float interpolationSmoothing = 0.1f;

        [Header("State Prediction")]
        [SerializeField] private bool enablePrediction = true;
        [SerializeField] private float predictionTime = 0.05f; // 50ms ahead

        // Current state
        private MachineState currentState;
        private MachineState previousState;
        private MachineState predictedState;

        // Timing
        private float lastUpdateTime;
        private float timeSinceLastUpdate;
        private float updateInterval;

        // Statistics
        private int totalUpdatesReceived = 0;
        private int missedUpdates = 0;
        private float averageUpdateRate = 0f;
        private List<float> updateRateSamples = new List<float>();

        // Events
        public event Action<MachineState> OnStateUpdated;
        public event Action<string> OnAlarmTriggered;
        public event Action<float> OnUpdateRateChanged;

        [Serializable]
        public class MachineState
        {
            // ISO 23247 Core State
            public string machine_id;
            public string state; // IDLE, RUNNING, PAUSED, ALARM, ESTOP
            public long timestamp_ms;

            // Position (mm)
            public Vector3 position;
            public Vector3 work_offset;

            // Velocity (mm/min)
            public Vector3 velocity;
            public float feed_rate_actual;
            public float feed_rate_commanded;

            // Spindle
            public float spindle_speed_actual;
            public float spindle_speed_commanded;
            public float spindle_load_percent;

            // Overrides (%)
            public float feed_override;
            public float spindle_override;
            public float rapid_override;

            // Program execution
            public string current_program;
            public int current_line;
            public int total_lines;
            public float program_progress_percent;

            // Tool
            public int tool_number;
            public float tool_length_offset;
            public float tool_diameter_offset;

            // Alarms
            public List<AlarmInfo> active_alarms;

            // Modal state
            public string motion_mode; // G0, G1, G2, G3
            public string coord_system; // G54-G59
            public string plane_selection; // G17, G18, G19
            public string distance_mode; // G90, G91
            public string feed_rate_mode; // G93, G94, G95
        }

        [Serializable]
        public class AlarmInfo
        {
            public string code;
            public string severity; // INFO, WARNING, ERROR, CRITICAL
            public string message;
            public long timestamp_ms;
        }

        void Start()
        {
            updateInterval = 1f / stateUpdateRate;
            currentState = new MachineState
            {
                state = "IDLE",
                position = Vector3.zero,
                velocity = Vector3.zero,
                active_alarms = new List<AlarmInfo>()
            };
            previousState = currentState;
            lastUpdateTime = Time.time;

            Debug.Log($"[ISO23247StateHandler] Initialized - Target rate: {stateUpdateRate}Hz ({updateInterval * 1000f:F1}ms)");
        }

        void Update()
        {
            timeSinceLastUpdate = Time.time - lastUpdateTime;

            // Apply prediction if enabled
            if (enablePrediction && currentState != null)
            {
                predictedState = PredictFutureState(currentState, predictionTime);
            }

            // Check for missed updates
            if (timeSinceLastUpdate > updateInterval * 2f)
            {
                missedUpdates++;
            }
        }

        /// <summary>
        /// Process incoming state update from binary or JSON format
        /// </summary>
        public void ProcessStateUpdate(string jsonData)
        {
            try
            {
                previousState = currentState;
                currentState = JsonConvert.DeserializeObject<MachineState>(jsonData);

                float updateDelta = Time.time - lastUpdateTime;
                RecordUpdateRate(1f / updateDelta);

                lastUpdateTime = Time.time;
                timeSinceLastUpdate = 0f;
                totalUpdatesReceived++;

                // Check for new alarms
                CheckForNewAlarms();

                OnStateUpdated?.Invoke(currentState);
            }
            catch (Exception e)
            {
                Debug.LogError($"[ISO23247StateHandler] Error processing state update: {e.Message}");
            }
        }

        /// <summary>
        /// Process binary state update (FlatBuffers format)
        /// </summary>
        public void ProcessBinaryStateUpdate(byte[] binaryData)
        {
            try
            {
                // Parse binary format: [header][position][velocity][status]
                // This would use FlatBuffers deserialization in production

                previousState = currentState;
                currentState = DeserializeBinaryState(binaryData);

                float updateDelta = Time.time - lastUpdateTime;
                RecordUpdateRate(1f / updateDelta);

                lastUpdateTime = Time.time;
                timeSinceLastUpdate = 0f;
                totalUpdatesReceived++;

                CheckForNewAlarms();
                OnStateUpdated?.Invoke(currentState);
            }
            catch (Exception e)
            {
                Debug.LogError($"[ISO23247StateHandler] Error processing binary update: {e.Message}");
            }
        }

        MachineState DeserializeBinaryState(byte[] data)
        {
            // Simplified binary deserialization
            // In production, this would use FlatBuffers

            int offset = 0;

            MachineState state = new MachineState();

            // Skip header (16 bytes)
            offset += 16;

            // Position (12 bytes: 3 floats)
            state.position = new Vector3(
                BitConverter.ToSingle(data, offset),
                BitConverter.ToSingle(data, offset + 4),
                BitConverter.ToSingle(data, offset + 8)
            );
            offset += 12;

            // Velocity (12 bytes: 3 floats)
            state.velocity = new Vector3(
                BitConverter.ToSingle(data, offset),
                BitConverter.ToSingle(data, offset + 4),
                BitConverter.ToSingle(data, offset + 8)
            );
            offset += 12;

            // Feed rates, spindle, etc. (simplified)
            state.feed_rate_actual = BitConverter.ToSingle(data, offset);
            offset += 4;
            state.spindle_speed_actual = BitConverter.ToSingle(data, offset);
            offset += 4;

            return state;
        }

        MachineState PredictFutureState(MachineState current, float predictionTime)
        {
            if (current == null) return current;

            MachineState predicted = new MachineState
            {
                machine_id = current.machine_id,
                state = current.state,
                timestamp_ms = current.timestamp_ms + (long)(predictionTime * 1000),

                // Predict position based on velocity
                position = current.position + current.velocity * (predictionTime / 60f), // velocity is mm/min
                velocity = current.velocity,

                // Copy other properties
                feed_rate_actual = current.feed_rate_actual,
                spindle_speed_actual = current.spindle_speed_actual,
                tool_number = current.tool_number
            };

            return predicted;
        }

        void CheckForNewAlarms()
        {
            if (currentState.active_alarms == null) return;

            foreach (var alarm in currentState.active_alarms)
            {
                bool isNew = true;
                if (previousState?.active_alarms != null)
                {
                    foreach (var prevAlarm in previousState.active_alarms)
                    {
                        if (prevAlarm.code == alarm.code)
                        {
                            isNew = false;
                            break;
                        }
                    }
                }

                if (isNew)
                {
                    OnAlarmTriggered?.Invoke($"{alarm.severity}: {alarm.message}");
                    Debug.LogWarning($"[ISO23247StateHandler] New alarm: {alarm.code} - {alarm.message}");
                }
            }
        }

        void RecordUpdateRate(float rate)
        {
            updateRateSamples.Add(rate);
            if (updateRateSamples.Count > 60)
            {
                updateRateSamples.RemoveAt(0);
            }

            float sum = 0f;
            foreach (float sample in updateRateSamples)
            {
                sum += sample;
            }
            averageUpdateRate = sum / updateRateSamples.Count;

            OnUpdateRateChanged?.Invoke(averageUpdateRate);
        }

        /// <summary>
        /// Get interpolated state for smooth rendering
        /// </summary>
        public MachineState GetInterpolatedState()
        {
            if (!enableInterpolation || previousState == null || currentState == null)
            {
                return enablePrediction ? predictedState : currentState;
            }

            float t = Mathf.Clamp01(timeSinceLastUpdate / updateInterval);
            t = Mathf.SmoothStep(0f, 1f, t);

            MachineState interpolated = new MachineState
            {
                machine_id = currentState.machine_id,
                state = currentState.state,
                timestamp_ms = currentState.timestamp_ms,

                position = Vector3.Lerp(previousState.position, currentState.position, t),
                velocity = Vector3.Lerp(previousState.velocity, currentState.velocity, t),

                feed_rate_actual = Mathf.Lerp(previousState.feed_rate_actual, currentState.feed_rate_actual, t),
                spindle_speed_actual = Mathf.Lerp(previousState.spindle_speed_actual, currentState.spindle_speed_actual, t),

                current_program = currentState.current_program,
                current_line = currentState.current_line,
                tool_number = currentState.tool_number
            };

            return interpolated;
        }

        public MachineState GetCurrentState()
        {
            return currentState;
        }

        public Dictionary<string, object> GetStatistics()
        {
            return new Dictionary<string, object>
            {
                {"total_updates", totalUpdatesReceived},
                {"missed_updates", missedUpdates},
                {"average_update_rate_hz", averageUpdateRate},
                {"target_update_rate_hz", stateUpdateRate},
                {"time_since_last_update_ms", timeSinceLastUpdate * 1000f},
                {"interpolation_enabled", enableInterpolation},
                {"prediction_enabled", enablePrediction}
            };
        }

        void OnDrawGizmos()
        {
            if (!Application.isPlaying || currentState == null) return;

            // Draw current position
            Gizmos.color = Color.green;
            Gizmos.DrawSphere(currentState.position, 5f);

            // Draw velocity vector
            if (currentState.velocity.magnitude > 0.01f)
            {
                Gizmos.color = Color.cyan;
                Vector3 velocityVector = currentState.velocity.normalized * 20f;
                Gizmos.DrawRay(currentState.position, velocityVector);
            }

            // Draw predicted position
            if (enablePrediction && predictedState != null)
            {
                Gizmos.color = Color.yellow;
                Gizmos.DrawWireSphere(predictedState.position, 3f);
                Gizmos.DrawLine(currentState.position, predictedState.position);
            }
        }
    }
}
