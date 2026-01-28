using UnityEngine;
using UnityEngine.UI;
using System;
using System.Collections;
using System.Collections.Generic;
using System.Net.Http;
using System.Text;
using Newtonsoft.Json;

namespace CNCScada.RemoteControl
{
    /// <summary>
    /// Jog Controller for Remote Machine Control
    /// Provides continuous and incremental jogging with <20ms latency
    /// Part of Phase 5: Remote Control (<20ms)
    /// </summary>
    public class JogController : MonoBehaviour
    {
        [Header("Connection Settings")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private string machineId = "CNC-001";
        [SerializeField] private float commandTimeoutSeconds = 2.0f;

        [Header("Jog Configuration")]
        [SerializeField] private JogMode jogMode = JogMode.Continuous;
        [SerializeField] private float continuousJogSpeed = 100.0f;
        [SerializeField] private float[] incrementalDistances = { 0.01f, 0.1f, 1.0f, 10.0f };
        [SerializeField] private int currentIncrementIndex = 2;

        [Header("Feed Rate Settings")]
        [SerializeField] private float minFeedRate = 10.0f;
        [SerializeField] private float maxFeedRate = 3000.0f;
        [SerializeField] private float feedRateStep = 10.0f;

        [Header("Safety Limits")]
        [SerializeField] private bool enforceSoftLimits = true;
        [SerializeField] private Vector3 minPosition = new Vector3(-300f, -300f, -100f);
        [SerializeField] private Vector3 maxPosition = new Vector3(300f, 300f, 100f);
        [SerializeField] private float emergencyStopRadius = 5.0f;

        [Header("UI References")]
        [SerializeField] private Button jogXPlusButton;
        [SerializeField] private Button jogXMinusButton;
        [SerializeField] private Button jogYPlusButton;
        [SerializeField] private Button jogYMinusButton;
        [SerializeField] private Button jogZPlusButton;
        [SerializeField] private Button jogZMinusButton;
        [SerializeField] private Slider feedRateSlider;
        [SerializeField] private Text feedRateText;
        [SerializeField] private Dropdown incrementDropdown;
        [SerializeField] private Toggle continuousModeToggle;
        [SerializeField] private Text statusText;
        [SerializeField] private Text positionText;

        [Header("Visual Feedback")]
        [SerializeField] private Color normalColor = Color.white;
        [SerializeField] private Color activeColor = Color.green;
        [SerializeField] private Color errorColor = Color.red;

        // State
        private HttpClient httpClient;
        private Dictionary<string, bool> activeJogs = new Dictionary<string, bool>();
        private Vector3 currentPosition = Vector3.zero;
        private bool isConnected = false;
        private bool isMachineReady = false;
        private float currentFeedRate = 100.0f;
        private Queue<JogCommand> commandQueue = new Queue<JogCommand>();
        private bool isProcessingCommands = false;

        // Statistics
        private int totalJogCommands = 0;
        private int successfulJogs = 0;
        private int failedJogs = 0;
        private float averageLatencyMs = 0f;
        private List<float> latencySamples = new List<float>();

        // Events
        public event Action<Vector3> OnPositionUpdated;
        public event Action<string> OnJogStarted;
        public event Action<string> OnJogStopped;
        public event Action<string> OnJogError;

        public enum JogMode
        {
            Continuous,
            Incremental
        }

        [Serializable]
        public class JogCommand
        {
            public string machine_id;
            public string axis;
            public string direction;
            public float feed_rate;
            public float? distance;
            public string mode;
            public bool absolute;
            public float timestamp;
        }

        [Serializable]
        public class JogResponse
        {
            public bool success;
            public string message;
            public string command_id;
            public float latency_ms;
            public Vector3 new_position;
            public string error;
        }

        void Start()
        {
            InitializeHTTPClient();
            SetupUI();
            InitializeActiveJogs();
            StartCoroutine(PollMachineStatus());
            StartCoroutine(ProcessCommandQueue());
            Debug.Log("[JogController] Initialized for machine: " + machineId);
        }

        void InitializeHTTPClient()
        {
            httpClient = new HttpClient();
            httpClient.Timeout = TimeSpan.FromSeconds(commandTimeoutSeconds);
            httpClient.DefaultRequestHeaders.Add("User-Agent", "Unity-CNC-Jog-Controller");
        }

        void InitializeActiveJogs()
        {
            activeJogs["X"] = false;
            activeJogs["Y"] = false;
            activeJogs["Z"] = false;
            activeJogs["A"] = false;
            activeJogs["B"] = false;
            activeJogs["C"] = false;
        }

        void SetupUI()
        {
            if (jogXPlusButton != null) SetupJogButton(jogXPlusButton, "X", "+");
            if (jogXMinusButton != null) SetupJogButton(jogXMinusButton, "X", "-");
            if (jogYPlusButton != null) SetupJogButton(jogYPlusButton, "Y", "+");
            if (jogYMinusButton != null) SetupJogButton(jogYMinusButton, "Y", "-");
            if (jogZPlusButton != null) SetupJogButton(jogZPlusButton, "Z", "+");
            if (jogZMinusButton != null) SetupJogButton(jogZMinusButton, "Z", "-");

            if (feedRateSlider != null)
            {
                feedRateSlider.minValue = minFeedRate;
                feedRateSlider.maxValue = maxFeedRate;
                feedRateSlider.value = currentFeedRate;
                feedRateSlider.onValueChanged.AddListener(OnFeedRateSliderChanged);
            }

            if (incrementDropdown != null)
            {
                incrementDropdown.ClearOptions();
                List<string> options = new List<string>();
                foreach (float dist in incrementalDistances)
                {
                    options.Add(dist.ToString("F3") + " mm");
                }
                incrementDropdown.AddOptions(options);
                incrementDropdown.value = currentIncrementIndex;
                incrementDropdown.onValueChanged.AddListener(OnIncrementChanged);
            }

            if (continuousModeToggle != null)
            {
                continuousModeToggle.isOn = (jogMode == JogMode.Continuous);
                continuousModeToggle.onValueChanged.AddListener(OnModeToggleChanged);
            }

            UpdateUI();
        }

        void SetupJogButton(Button button, string axis, string direction)
        {
            var trigger = button.gameObject.AddComponent<UnityEngine.EventSystems.EventTrigger>();
            var pointerDown = new UnityEngine.EventSystems.EventTrigger.Entry();
            pointerDown.eventID = UnityEngine.EventSystems.EventTriggerType.PointerDown;
            pointerDown.callback.AddListener((data) => { StartJog(axis, direction); });
            trigger.triggers.Add(pointerDown);
            var pointerUp = new UnityEngine.EventSystems.EventTrigger.Entry();
            pointerUp.eventID = UnityEngine.EventSystems.EventTriggerType.PointerUp;
            pointerUp.callback.AddListener((data) => { StopJog(axis); });
            trigger.triggers.Add(pointerUp);
        }

        void Update()
        {
            if (Input.GetKey(KeyCode.RightArrow)) StartJog("X", "+");
            if (Input.GetKeyUp(KeyCode.RightArrow)) StopJog("X");
            if (Input.GetKey(KeyCode.LeftArrow)) StartJog("X", "-");
            if (Input.GetKeyUp(KeyCode.LeftArrow)) StopJog("X");
            if (Input.GetKey(KeyCode.UpArrow)) StartJog("Y", "+");
            if (Input.GetKeyUp(KeyCode.UpArrow)) StopJog("Y");
            if (Input.GetKey(KeyCode.DownArrow)) StartJog("Y", "-");
            if (Input.GetKeyUp(KeyCode.DownArrow)) StopJog("Y");
            if (Input.GetKey(KeyCode.PageUp)) StartJog("Z", "+");
            if (Input.GetKeyUp(KeyCode.PageUp)) StopJog("Z");
            if (Input.GetKey(KeyCode.PageDown)) StartJog("Z", "-");
            if (Input.GetKeyUp(KeyCode.PageDown)) StopJog("Z");
        }

        public void StartJog(string axis, string direction)
        {
            if (!isConnected || !isMachineReady)
            {
                UpdateStatus("Machine not ready", true);
                return;
            }
            if (activeJogs[axis]) return;
            if (enforceSoftLimits && !CheckSafetyLimits(axis, direction))
            {
                UpdateStatus($"Safety limit: {axis}{direction}", true);
                OnJogError?.Invoke($"Safety limit: {axis}{direction}");
                return;
            }

            JogCommand command = new JogCommand
            {
                machine_id = machineId,
                axis = axis,
                direction = direction,
                feed_rate = currentFeedRate,
                mode = jogMode.ToString().ToLower(),
                absolute = false,
                timestamp = Time.realtimeSinceStartup
            };

            if (jogMode == JogMode.Incremental)
            {
                command.distance = incrementalDistances[currentIncrementIndex];
            }

            commandQueue.Enqueue(command);
            activeJogs[axis] = true;
            UpdateStatus($"Jogging {axis}{direction}...", false);
            OnJogStarted?.Invoke($"{axis}{direction}");
        }

        public void StopJog(string axis)
        {
            if (!activeJogs[axis]) return;
            activeJogs[axis] = false;
            StartCoroutine(SendJogStopCommand(axis));
            UpdateStatus($"Stopped {axis}", false);
            OnJogStopped?.Invoke(axis);
        }

        bool CheckSafetyLimits(string axis, string direction)
        {
            float axisValue = 0f;
            float minLimit = 0f;
            float maxLimit = 0f;

            switch (axis)
            {
                case "X":
                    axisValue = currentPosition.x;
                    minLimit = minPosition.x;
                    maxLimit = maxPosition.x;
                    break;
                case "Y":
                    axisValue = currentPosition.y;
                    minLimit = minPosition.y;
                    maxLimit = maxPosition.y;
                    break;
                case "Z":
                    axisValue = currentPosition.z;
                    minLimit = minPosition.z;
                    maxLimit = maxPosition.z;
                    break;
                default:
                    return true;
            }

            if (direction == "+" && axisValue >= (maxLimit - emergencyStopRadius)) return false;
            if (direction == "-" && axisValue <= (minLimit + emergencyStopRadius)) return false;
            return true;
        }

        IEnumerator ProcessCommandQueue()
        {
            isProcessingCommands = true;
            while (true)
            {
                if (commandQueue.Count > 0)
                {
                    JogCommand command = commandQueue.Dequeue();
                    yield return StartCoroutine(SendJogCommand(command));
                }
                else
                {
                    yield return new WaitForSeconds(0.01f);
                }
            }
        }

        IEnumerator SendJogCommand(JogCommand command)
        {
            string url = $"{flaskServerUrl}/api/v1/unity/control/jog";
            string jsonData = JsonConvert.SerializeObject(command);
            float sendTime = Time.realtimeSinceStartup;

            using (var request = new HttpRequestMessage(HttpMethod.Post, url))
            {
                request.Content = new StringContent(jsonData, Encoding.UTF8, "application/json");
                var task = httpClient.SendAsync(request);
                while (!task.IsCompleted) yield return null;

                if (task.IsFaulted || task.Result == null || !task.Result.IsSuccessStatusCode)
                {
                    failedJogs++;
                    totalJogCommands++;
                    UpdateStatus("Jog command failed", true);
                    yield break;
                }

                var readTask = task.Result.Content.ReadAsStringAsync();
                while (!readTask.IsCompleted) yield return null;

                JogResponse jogResponse = JsonConvert.DeserializeObject<JogResponse>(readTask.Result);
                float latency = (Time.realtimeSinceStartup - sendTime) * 1000f;
                RecordLatency(latency);

                if (jogResponse.success)
                {
                    successfulJogs++;
                    totalJogCommands++;
                    currentPosition = jogResponse.new_position;
                    OnPositionUpdated?.Invoke(currentPosition);
                    UpdatePosition();
                }
                else
                {
                    failedJogs++;
                    totalJogCommands++;
                    UpdateStatus($"Jog failed: {jogResponse.error}", true);
                    OnJogError?.Invoke(jogResponse.error);
                }
            }
        }

        IEnumerator SendJogStopCommand(string axis)
        {
            string url = $"{flaskServerUrl}/api/v1/unity/control/jog/stop";
            var stopCommand = new { machine_id = machineId, axis = axis };
            string jsonData = JsonConvert.SerializeObject(stopCommand);

            using (var request = new HttpRequestMessage(HttpMethod.Post, url))
            {
                request.Content = new StringContent(jsonData, Encoding.UTF8, "application/json");
                var task = httpClient.SendAsync(request);
                while (!task.IsCompleted) yield return null;
            }
        }

        IEnumerator PollMachineStatus()
        {
            while (true)
            {
                yield return new WaitForSeconds(0.5f);
                string url = $"{flaskServerUrl}/api/v1/unity/status/{machineId}";

                using (var request = new HttpRequestMessage(HttpMethod.Get, url))
                {
                    var task = httpClient.SendAsync(request);
                    while (!task.IsCompleted) yield return null;

                    if (task.IsFaulted || task.Result == null || !task.Result.IsSuccessStatusCode)
                    {
                        isConnected = false;
                        isMachineReady = false;
                        continue;
                    }

                    var readTask = task.Result.Content.ReadAsStringAsync();
                    while (!readTask.IsCompleted) yield return null;

                    try
                    {
                        var statusData = JsonConvert.DeserializeObject<Dictionary<string, object>>(readTask.Result);
                        isConnected = true;
                        isMachineReady = statusData.ContainsKey("state") && statusData["state"].ToString() == "IDLE";
                    }
                    catch { }
                }
            }
        }

        void RecordLatency(float latencyMs)
        {
            latencySamples.Add(latencyMs);
            if (latencySamples.Count > 100) latencySamples.RemoveAt(0);
            float sum = 0f;
            foreach (float sample in latencySamples) sum += sample;
            averageLatencyMs = sum / latencySamples.Count;
        }

        void OnFeedRateSliderChanged(float value)
        {
            currentFeedRate = value;
            UpdateFeedRateDisplay();
        }

        void OnIncrementChanged(int index)
        {
            currentIncrementIndex = index;
        }

        void OnModeToggleChanged(bool isContinuous)
        {
            jogMode = isContinuous ? JogMode.Continuous : JogMode.Incremental;
        }

        void UpdateUI()
        {
            UpdateStatus(isConnected ? "Connected" : "Disconnected", !isConnected);
            UpdatePosition();
            UpdateFeedRateDisplay();
        }

        void UpdateStatus(string message, bool isError)
        {
            if (statusText != null)
            {
                statusText.text = message;
                statusText.color = isError ? errorColor : normalColor;
            }
        }

        void UpdatePosition()
        {
            if (positionText != null)
            {
                positionText.text = $"X: {currentPosition.x:F3}  Y: {currentPosition.y:F3}  Z: {currentPosition.z:F3}";
            }
        }

        void UpdateFeedRateDisplay()
        {
            if (feedRateText != null)
            {
                feedRateText.text = $"{currentFeedRate:F0} mm/min";
            }
        }

        public Dictionary<string, object> GetStatistics()
        {
            return new Dictionary<string, object>
            {
                {"total_commands", totalJogCommands},
                {"successful_jogs", successfulJogs},
                {"failed_jogs", failedJogs},
                {"success_rate", totalJogCommands > 0 ? (float)successfulJogs / totalJogCommands : 0f},
                {"average_latency_ms", averageLatencyMs},
                {"is_connected", isConnected},
                {"is_ready", isMachineReady}
            };
        }

        void OnDestroy()
        {
            if (httpClient != null) httpClient.Dispose();
        }

        void OnDrawGizmos()
        {
            if (!Application.isPlaying) return;
            if (enforceSoftLimits)
            {
                Gizmos.color = Color.yellow;
                Vector3 center = (minPosition + maxPosition) / 2f;
                Vector3 size = maxPosition - minPosition;
                Gizmos.DrawWireCube(center, size);
            }
            Gizmos.color = Color.green;
            Gizmos.DrawSphere(currentPosition, 5f);
        }
    }
}
