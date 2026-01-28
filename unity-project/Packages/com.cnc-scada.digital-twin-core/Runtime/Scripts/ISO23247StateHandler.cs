using UnityEngine;
using System;
using System.Collections;
using System.Collections.Generic;
using System.Net.Http;
using System.Text;
using Newtonsoft.Json;

namespace CNCScada.DigitalTwin
{
    /// <summary>
    /// ISO 23247 compliant digital twin state handler
    /// Receives machine state updates via WebSocket and binary protocol
    /// Supports 60Hz update rate with velocity-based prediction
    /// </summary>
    public class ISO23247StateHandler : MonoBehaviour
    {
        #region Serialized Fields

        [Header("Connection Settings")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private string machineId = "CNC-001";
        [SerializeField] private bool useBinaryProtocol = true;

        [Header("Update Settings")]
        [SerializeField] private float updateInterval = 0.016f; // 60Hz
        [SerializeField] private bool enablePrediction = true;
        [SerializeField] private float predictionLookahead = 0.033f; // 2 frames

        [Header("State Interpolation")]
        [SerializeField] private bool smoothInterpolation = true;
        [SerializeField] private float interpolationSpeed = 10f;

        #endregion

        #region Private Fields

        private HttpClient _httpClient;
        private MachineState _currentState;
        private MachineState _targetState;
        private MachineState _predictedState;
        private Vector3 _velocity;
        private float _lastUpdateTime;
        private bool _isConnected;

        #endregion

        #region Events

        public event Action<MachineState> OnStateUpdated;
        public event Action OnConnected;
        public event Action OnDisconnected;
        public event Action<string> OnError;

        #endregion

        #region Unity Lifecycle

        void Start()
        {
            _httpClient = new HttpClient();
            _httpClient.Timeout = TimeSpan.FromSeconds(5);
            _currentState = new MachineState();
            _targetState = new MachineState();
            _predictedState = new MachineState();

            StartCoroutine(ConnectAndStream());
        }

        void Update()
        {
            if (_isConnected && smoothInterpolation && _targetState != null)
            {
                InterpolateState();
            }
        }

        void OnDestroy()
        {
            _httpClient?.Dispose();
        }

        #endregion

        #region Public Methods

        /// <summary>
        /// Get current machine state
        /// </summary>
        public MachineState GetCurrentState()
        {
            return enablePrediction ? _predictedState : _currentState;
        }

        /// <summary>
        /// Get machine position
        /// </summary>
        public Vector3 GetPosition()
        {
            var state = GetCurrentState();
            return new Vector3(state.x, state.y, state.z);
        }

        /// <summary>
        /// Get machine velocity
        /// </summary>
        public Vector3 GetVelocity()
        {
            return _velocity;
        }

        /// <summary>
        /// Check if machine is connected
        /// </summary>
        public bool IsConnected()
        {
            return _isConnected;
        }

        #endregion

        #region Private Methods

        private IEnumerator ConnectAndStream()
        {
            while (true)
            {
                var requestUrl = $"{flaskServerUrl}/api/unity/state/stream?machine_id={machineId}&binary={useBinaryProtocol}";

                var request = new HttpRequestMessage(HttpMethod.Get, requestUrl);
                var task = _httpClient.SendAsync(request, HttpCompletionOption.ResponseHeadersRead);

                while (!task.IsCompleted) yield return null;

                if (task.IsFaulted || task.Result == null)
                {
                    Debug.LogError($"[ISO23247] Connection failed: {task.Exception?.Message}");
                    OnError?.Invoke($"Connection failed: {task.Exception?.Message}");
                    _isConnected = false;
                    OnDisconnected?.Invoke();
                    yield return new WaitForSeconds(5f);
                    continue;
                }

                var response = task.Result;
                if (!response.IsSuccessStatusCode)
                {
                    Debug.LogError($"[ISO23247] HTTP {response.StatusCode}");
                    OnError?.Invoke($"HTTP error: {response.StatusCode}");
                    yield return new WaitForSeconds(5f);
                    continue;
                }

                _isConnected = true;
                OnConnected?.Invoke();
                Debug.Log($"[ISO23247] Connected to {requestUrl}");

                yield return ProcessStream(response);

                _isConnected = false;
                OnDisconnected?.Invoke();
                yield return new WaitForSeconds(2f);
            }
        }

        private IEnumerator ProcessStream(HttpResponseMessage response)
        {
            var streamTask = response.Content.ReadAsStreamAsync();
            while (!streamTask.IsCompleted) yield return null;

            if (streamTask.IsFaulted)
            {
                Debug.LogError($"[ISO23247] Stream read failed: {streamTask.Exception?.Message}");
                yield break;
            }

            var stream = streamTask.Result;
            var buffer = new byte[1024];

            while (true)
            {
                var readTask = stream.ReadAsync(buffer, 0, buffer.Length);
                while (!readTask.IsCompleted) yield return null;

                if (readTask.IsFaulted || readTask.Result == 0)
                {
                    Debug.LogWarning("[ISO23247] Stream ended");
                    yield break;
                }

                var bytesRead = readTask.Result;
                ProcessStateUpdate(buffer, bytesRead);
                yield return null;
            }
        }

        private void ProcessStateUpdate(byte[] data, int length)
        {
            try
            {
                if (useBinaryProtocol)
                {
                    DecodeBinaryState(data, length);
                }
                else
                {
                    var json = Encoding.UTF8.GetString(data, 0, length);
                    var lines = json.Split('\n');
                    foreach (var line in lines)
                    {
                        if (!string.IsNullOrWhiteSpace(line))
                        {
                            _targetState = JsonConvert.DeserializeObject<MachineState>(line);
                            UpdateState();
                        }
                    }
                }
            }
            catch (Exception e)
            {
                Debug.LogError($"[ISO23247] State decode error: {e.Message}");
                OnError?.Invoke($"Decode error: {e.Message}");
            }
        }

        private void DecodeBinaryState(byte[] data, int length)
        {
            if (length < 29) return; // Minimum binary message size

            // Binary format (29 bytes total):
            // 1 byte: message type (0x01 = position update)
            // 4 bytes: payload length
            // 2 bytes: machine_id
            // 4 bytes: x (float)
            // 4 bytes: y (float)
            // 4 bytes: z (float)
            // 8 bytes: timestamp (long)
            // 1 byte: state (0=idle, 1=running, 2=paused, 3=alarm)
            // 1 byte: flags

            int offset = 0;
            byte msgType = data[offset++];

            if (msgType != 0x01) return; // Not a position update

            offset += 4; // Skip payload length
            offset += 2; // Skip machine_id

            _targetState.x = BitConverter.ToSingle(data, offset);
            offset += 4;
            _targetState.y = BitConverter.ToSingle(data, offset);
            offset += 4;
            _targetState.z = BitConverter.ToSingle(data, offset);
            offset += 4;

            _targetState.timestamp = BitConverter.ToInt64(data, offset);
            offset += 8;

            _targetState.state = (MachineStateEnum)data[offset++];
            _targetState.flags = data[offset++];

            UpdateState();
        }

        private void UpdateState()
        {
            // Calculate velocity
            float dt = Time.time - _lastUpdateTime;
            if (dt > 0)
            {
                var currentPos = new Vector3(_currentState.x, _currentState.y, _currentState.z);
                var targetPos = new Vector3(_targetState.x, _targetState.y, _targetState.z);
                _velocity = (targetPos - currentPos) / dt;
            }

            if (!smoothInterpolation)
            {
                _currentState = _targetState.Clone();
            }

            // Predict future position
            if (enablePrediction)
            {
                _predictedState = _targetState.Clone();
                _predictedState.x += _velocity.x * predictionLookahead;
                _predictedState.y += _velocity.y * predictionLookahead;
                _predictedState.z += _velocity.z * predictionLookahead;
            }

            _lastUpdateTime = Time.time;
            OnStateUpdated?.Invoke(GetCurrentState());
        }

        private void InterpolateState()
        {
            float t = interpolationSpeed * Time.deltaTime;
            _currentState.x = Mathf.Lerp(_currentState.x, _targetState.x, t);
            _currentState.y = Mathf.Lerp(_currentState.y, _targetState.y, t);
            _currentState.z = Mathf.Lerp(_currentState.z, _targetState.z, t);
            _currentState.a = Mathf.Lerp(_currentState.a, _targetState.a, t);
            _currentState.b = Mathf.Lerp(_currentState.b, _targetState.b, t);
            _currentState.c = Mathf.Lerp(_currentState.c, _targetState.c, t);
            _currentState.spindleSpeed = Mathf.Lerp(_currentState.spindleSpeed, _targetState.spindleSpeed, t);
            _currentState.feedRate = Mathf.Lerp(_currentState.feedRate, _targetState.feedRate, t);
        }

        #endregion
    }

    #region Data Classes

    [Serializable]
    public class MachineState
    {
        public float x;
        public float y;
        public float z;
        public float a;
        public float b;
        public float c;
        public float spindleSpeed;
        public float feedRate;
        public long timestamp;
        public MachineStateEnum state;
        public byte flags;

        public MachineState Clone()
        {
            return new MachineState
            {
                x = this.x,
                y = this.y,
                z = this.z,
                a = this.a,
                b = this.b,
                c = this.c,
                spindleSpeed = this.spindleSpeed,
                feedRate = this.feedRate,
                timestamp = this.timestamp,
                state = this.state,
                flags = this.flags
            };
        }
    }

    public enum MachineStateEnum : byte
    {
        Idle = 0,
        Running = 1,
        Paused = 2,
        Alarm = 3
    }

    #endregion
}
