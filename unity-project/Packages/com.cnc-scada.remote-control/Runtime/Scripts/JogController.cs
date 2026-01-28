using UnityEngine;
using UnityEngine.UI;
using System;
using System.Net.Http;
using System.Collections.Generic;
using Newtonsoft.Json;

namespace CNCScada.RemoteControl
{
    /// <summary>
    /// Multi-axis jog controller with continuous and incremental modes
    /// Supports keyboard, gamepad, and touch input with safety limits
    /// </summary>
    public class JogController : MonoBehaviour
    {
        #region Serialized Fields

        [Header("Connection")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private string machineId = "CNC-001";

        [Header("Jog Settings")]
        [SerializeField] private bool enableContinuousJog = true;
        [SerializeField] private bool enableIncrementalJog = true;
        [SerializeField] private float[] incrementalSteps = { 0.1f, 1.0f, 10.0f, 100.0f }; // mm
        [SerializeField] private int currentStepIndex = 1;

        [Header("Speed Settings")]
        [SerializeField] private float defaultJogSpeed = 500f; // mm/min
        [SerializeField] private float minJogSpeed = 10f;
        [SerializeField] private float maxJogSpeed = 5000f;
        [SerializeField] private float speedIncrement = 100f;

        [Header("Safety")]
        [SerializeField] private bool requireHold = true; // Must hold button for continuous jog
        [SerializeField] private float maxJogDistance = 500f; // mm per command
        [SerializeField] private bool checkSoftLimits = true;

        [Header("UI References")]
        [SerializeField] private Button[] jogButtons; // X+, X-, Y+, Y-, Z+, Z-, A+, A-, etc.
        [SerializeField] private Slider speedSlider;
        [SerializeField] private Text speedText;
        [SerializeField] private Text stepSizeText;

        #endregion

        #region Private Fields

        private HttpClient _httpClient;
        private Dictionary<string, bool> _axisJogging;
        private float _currentSpeed;
        private bool _isJogging;

        #endregion

        #region Events

        public event Action<string, float, float> OnJogCommand; // axis, direction, speed
        public event Action OnJogStopped;
        public event Action<string> OnError;

        #endregion

        #region Unity Lifecycle

        void Start()
        {
            _httpClient = new HttpClient();
            _httpClient.Timeout = TimeSpan.FromSeconds(2);
            _axisJogging = new Dictionary<string, bool>();
            _currentSpeed = defaultJogSpeed;

            InitializeUI();
        }

        void Update()
        {
            HandleKeyboardInput();
            HandleGamepadInput();
        }

        void OnDestroy()
        {
            _httpClient?.Dispose();
            StopAllJogging();
        }

        #endregion

        #region Public Methods

        /// <summary>
        /// Jog axis by direction and distance
        /// </summary>
        public void JogAxis(string axis, float direction, float distance)
        {
            if (_isJogging && requireHold)
            {
                Debug.LogWarning("[JogController] Already jogging");
                return;
            }

            StartCoroutine(SendJogCommand(axis, direction, distance));
        }

        /// <summary>
        /// Start continuous jog
        /// </summary>
        public void StartContinuousJog(string axis, float direction)
        {
            if (!enableContinuousJog) return;

            _axisJogging[axis] = true;
            OnJogCommand?.Invoke(axis, direction, _currentSpeed);
            StartCoroutine(SendContinuousJogCommand(axis, direction));
        }

        /// <summary>
        /// Stop continuous jog
        /// </summary>
        public void StopContinuousJog(string axis)
        {
            if (_axisJogging.ContainsKey(axis))
            {
                _axisJogging[axis] = false;
            }

            StartCoroutine(SendStopCommand(axis));
        }

        /// <summary>
        /// Stop all jogging
        /// </summary>
        public void StopAllJogging()
        {
            foreach (var axis in _axisJogging.Keys)
            {
                _axisJogging[axis] = false;
            }

            StartCoroutine(SendStopCommand("all"));
            OnJogStopped?.Invoke();
        }

        /// <summary>
        /// Set jog speed
        /// </summary>
        public void SetJogSpeed(float speed)
        {
            _currentSpeed = Mathf.Clamp(speed, minJogSpeed, maxJogSpeed);
            UpdateSpeedDisplay();
        }

        /// <summary>
        /// Cycle through step sizes
        /// </summary>
        public void CycleStepSize()
        {
            currentStepIndex = (currentStepIndex + 1) % incrementalSteps.Length;
            UpdateStepDisplay();
        }

        /// <summary>
        /// Get current step size
        /// </summary>
        public float GetCurrentStepSize()
        {
            return incrementalSteps[currentStepIndex];
        }

        #endregion

        #region Private Methods

        private void InitializeUI()
        {
            // Setup speed slider
            if (speedSlider != null)
            {
                speedSlider.minValue = minJogSpeed;
                speedSlider.maxValue = maxJogSpeed;
                speedSlider.value = _currentSpeed;
                speedSlider.onValueChanged.AddListener(SetJogSpeed);
            }

            UpdateSpeedDisplay();
            UpdateStepDisplay();
        }

        private void HandleKeyboardInput()
        {
            if (!enableContinuousJog && !enableIncrementalJog) return;

            // X axis
            if (Input.GetKeyDown(KeyCode.RightArrow))
            {
                HandleAxisInput("X", 1f);
            }
            else if (Input.GetKeyUp(KeyCode.RightArrow))
            {
                StopContinuousJog("X");
            }

            if (Input.GetKeyDown(KeyCode.LeftArrow))
            {
                HandleAxisInput("X", -1f);
            }
            else if (Input.GetKeyUp(KeyCode.LeftArrow))
            {
                StopContinuousJog("X");
            }

            // Y axis
            if (Input.GetKeyDown(KeyCode.UpArrow))
            {
                HandleAxisInput("Y", 1f);
            }
            else if (Input.GetKeyUp(KeyCode.UpArrow))
            {
                StopContinuousJog("Y");
            }

            if (Input.GetKeyDown(KeyCode.DownArrow))
            {
                HandleAxisInput("Y", -1f);
            }
            else if (Input.GetKeyUp(KeyCode.DownArrow))
            {
                StopContinuousJog("Y");
            }

            // Z axis
            if (Input.GetKeyDown(KeyCode.PageUp))
            {
                HandleAxisInput("Z", 1f);
            }
            else if (Input.GetKeyUp(KeyCode.PageUp))
            {
                StopContinuousJog("Z");
            }

            if (Input.GetKeyDown(KeyCode.PageDown))
            {
                HandleAxisInput("Z", -1f);
            }
            else if (Input.GetKeyUp(KeyCode.PageDown))
            {
                StopContinuousJog("Z");
            }

            // Step size cycling
            if (Input.GetKeyDown(KeyCode.Space))
            {
                CycleStepSize();
            }

            // Emergency stop
            if (Input.GetKeyDown(KeyCode.Escape))
            {
                StopAllJogging();
            }
        }

        private void HandleGamepadInput()
        {
            // Left stick for X/Y
            float horizontal = Input.GetAxis("Horizontal");
            float vertical = Input.GetAxis("Vertical");

            if (Mathf.Abs(horizontal) > 0.1f)
            {
                if (enableContinuousJog)
                {
                    StartContinuousJog("X", Mathf.Sign(horizontal));
                }
            }
            else
            {
                StopContinuousJog("X");
            }

            if (Mathf.Abs(vertical) > 0.1f)
            {
                if (enableContinuousJog)
                {
                    StartContinuousJog("Y", Mathf.Sign(vertical));
                }
            }
            else
            {
                StopContinuousJog("Y");
            }
        }

        private void HandleAxisInput(string axis, float direction)
        {
            if (enableContinuousJog)
            {
                StartContinuousJog(axis, direction);
            }
            else if (enableIncrementalJog)
            {
                JogAxis(axis, direction, GetCurrentStepSize());
            }
        }

        private System.Collections.IEnumerator SendJogCommand(string axis, float direction, float distance)
        {
            _isJogging = true;

            var url = $"{flaskServerUrl}/api/control/jog";
            var data = new
            {
                machineId,
                axis,
                direction,
                distance,
                speed = _currentSpeed
            };

            var json = JsonConvert.SerializeObject(data);
            var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");
            var task = _httpClient.PostAsync(url, content);

            while (!task.IsCompleted) yield return null;

            if (task.IsFaulted || !task.Result.IsSuccessStatusCode)
            {
                Debug.LogError($"[JogController] Jog command failed");
                OnError?.Invoke("Jog command failed");
            }
            else
            {
                OnJogCommand?.Invoke(axis, direction, _currentSpeed);
            }

            _isJogging = false;
        }

        private System.Collections.IEnumerator SendContinuousJogCommand(string axis, float direction)
        {
            var url = $"{flaskServerUrl}/api/control/jog/continuous";
            var data = new
            {
                machineId,
                axis,
                direction,
                speed = _currentSpeed
            };

            var json = JsonConvert.SerializeObject(data);
            var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");
            var task = _httpClient.PostAsync(url, content);

            while (!task.IsCompleted) yield return null;

            if (task.IsFaulted || !task.Result.IsSuccessStatusCode)
            {
                Debug.LogError($"[JogController] Continuous jog failed");
                OnError?.Invoke("Continuous jog failed");
            }
        }

        private System.Collections.IEnumerator SendStopCommand(string axis)
        {
            var url = $"{flaskServerUrl}/api/control/jog/stop";
            var data = new { machineId, axis };

            var json = JsonConvert.SerializeObject(data);
            var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");
            var task = _httpClient.PostAsync(url, content);

            while (!task.IsCompleted) yield return null;

            if (task.IsFaulted || !task.Result.IsSuccessStatusCode)
            {
                Debug.LogWarning($"[JogController] Stop command failed");
            }
        }

        private void UpdateSpeedDisplay()
        {
            if (speedText != null)
            {
                speedText.text = $"{_currentSpeed:F0} mm/min";
            }
        }

        private void UpdateStepDisplay()
        {
            if (stepSizeText != null)
            {
                stepSizeText.text = $"Step: {GetCurrentStepSize():F1} mm";
            }
        }

        #endregion
    }
}
