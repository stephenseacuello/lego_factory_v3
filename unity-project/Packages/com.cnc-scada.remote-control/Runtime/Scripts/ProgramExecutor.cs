using UnityEngine;
using UnityEngine.UI;
using System;
using System.Collections.Generic;
using System.Net.Http;
using Newtonsoft.Json;

namespace CNCScada.RemoteControl
{
    /// <summary>
    /// Program execution controller with state machine
    /// Supports run, pause, resume, stop, and feed rate override
    /// </summary>
    public class ProgramExecutor : MonoBehaviour
    {
        #region Serialized Fields

        [Header("Connection")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private string machineId = "CNC-001";

        [Header("UI References")]
        [SerializeField] private Button runButton;
        [SerializeField] private Button pauseButton;
        [SerializeField] private Button resumeButton;
        [SerializeField] private Button stopButton;
        [SerializeField] private Slider feedOverrideSlider;
        [SerializeField] private Text statusText;
        [SerializeField] private Text progressText;
        [SerializeField] private Image progressBar;

        [Header("Settings")]
        [SerializeField] private float statusPollInterval = 0.5f;
        [SerializeField] private bool autoRefreshStatus = true;

        #endregion

        #region Private Fields

        private HttpClient _httpClient;
        private ProgramState _currentState;
        private float _lastStatusPoll;
        private string _currentProgram;
        private float _feedOverride = 100f;

        #endregion

        #region Events

        public event Action OnProgramStarted;
        public event Action OnProgramPaused;
        public event Action OnProgramResumed;
        public event Action OnProgramCompleted;
        public event Action OnProgramStopped;
        public event Action<ProgramState> OnStateChanged;
        public event Action<float> OnProgressUpdate;
        public event Action<string> OnError;

        #endregion

        #region Unity Lifecycle

        void Start()
        {
            _httpClient = new HttpClient();
            _httpClient.Timeout = TimeSpan.FromSeconds(5);
            _currentState = ProgramState.Idle;

            InitializeUI();
        }

        void Update()
        {
            if (autoRefreshStatus && Time.time - _lastStatusPoll >= statusPollInterval)
            {
                PollStatus();
                _lastStatusPoll = Time.time;
            }

            UpdateUI();
        }

        void OnDestroy()
        {
            _httpClient?.Dispose();
        }

        #endregion

        #region Public Methods

        /// <summary>
        /// Start program execution
        /// </summary>
        public void RunProgram(string programId)
        {
            if (_currentState != ProgramState.Idle && _currentState != ProgramState.Completed)
            {
                Debug.LogWarning("[ProgramExecutor] Program already running");
                return;
            }

            _currentProgram = programId;
            StartCoroutine(SendRunCommand(programId));
        }

        /// <summary>
        /// Pause program execution
        /// </summary>
        public void PauseProgram()
        {
            if (_currentState != ProgramState.Running)
            {
                Debug.LogWarning("[ProgramExecutor] No program running");
                return;
            }

            StartCoroutine(SendPauseCommand());
        }

        /// <summary>
        /// Resume program execution
        /// </summary>
        public void ResumeProgram()
        {
            if (_currentState != ProgramState.Paused)
            {
                Debug.LogWarning("[ProgramExecutor] Program not paused");
                return;
            }

            StartCoroutine(SendResumeCommand());
        }

        /// <summary>
        /// Stop program execution
        /// </summary>
        public void StopProgram()
        {
            if (_currentState == ProgramState.Idle || _currentState == ProgramState.Completed)
            {
                return;
            }

            StartCoroutine(SendStopCommand());
        }

        /// <summary>
        /// Set feed rate override (50-200%)
        /// </summary>
        public void SetFeedOverride(float percent)
        {
            _feedOverride = Mathf.Clamp(percent, 50f, 200f);
            StartCoroutine(SendFeedOverrideCommand(_feedOverride));
        }

        /// <summary>
        /// Get current program state
        /// </summary>
        public ProgramState GetState()
        {
            return _currentState;
        }

        #endregion

        #region Private Methods

        private void InitializeUI()
        {
            if (runButton != null)
            {
                runButton.onClick.AddListener(() => RunProgram(_currentProgram ?? "default"));
            }

            if (pauseButton != null)
            {
                pauseButton.onClick.AddListener(PauseProgram);
            }

            if (resumeButton != null)
            {
                resumeButton.onClick.AddListener(ResumeProgram);
            }

            if (stopButton != null)
            {
                stopButton.onClick.AddListener(StopProgram);
            }

            if (feedOverrideSlider != null)
            {
                feedOverrideSlider.minValue = 50f;
                feedOverrideSlider.maxValue = 200f;
                feedOverrideSlider.value = 100f;
                feedOverrideSlider.onValueChanged.AddListener(SetFeedOverride);
            }

            UpdateUI();
        }

        private void UpdateUI()
        {
            // Update button interactability
            if (runButton != null)
            {
                runButton.interactable = _currentState == ProgramState.Idle || _currentState == ProgramState.Completed;
            }

            if (pauseButton != null)
            {
                pauseButton.interactable = _currentState == ProgramState.Running;
            }

            if (resumeButton != null)
            {
                resumeButton.interactable = _currentState == ProgramState.Paused;
            }

            if (stopButton != null)
            {
                stopButton.interactable = _currentState != ProgramState.Idle && _currentState != ProgramState.Completed;
            }

            // Update status text
            if (statusText != null)
            {
                statusText.text = $"Status: {_currentState}";
                statusText.color = GetStateColor(_currentState);
            }
        }

        private Color GetStateColor(ProgramState state)
        {
            switch (state)
            {
                case ProgramState.Running: return Color.green;
                case ProgramState.Paused: return Color.yellow;
                case ProgramState.Error: return Color.red;
                case ProgramState.Completed: return Color.cyan;
                default: return Color.white;
            }
        }

        private void PollStatus()
        {
            StartCoroutine(FetchProgramStatus());
        }

        private System.Collections.IEnumerator FetchProgramStatus()
        {
            var url = $"{flaskServerUrl}/api/control/program/status?machine_id={machineId}";
            var task = _httpClient.GetStringAsync(url);

            while (!task.IsCompleted) yield return null;

            if (task.IsFaulted)
            {
                // Silent failure for status polling
                yield break;
            }

            try
            {
                var response = JsonConvert.DeserializeObject<ProgramStatusResponse>(task.Result);
                UpdateState(response.state);
                UpdateProgress(response.progress, response.totalLines);
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[ProgramExecutor] Status parse error: {e.Message}");
            }
        }

        private void UpdateState(ProgramState newState)
        {
            if (newState != _currentState)
            {
                var oldState = _currentState;
                _currentState = newState;
                OnStateChanged?.Invoke(newState);

                // Trigger specific events
                if (newState == ProgramState.Running && oldState == ProgramState.Idle)
                {
                    OnProgramStarted?.Invoke();
                }
                else if (newState == ProgramState.Paused)
                {
                    OnProgramPaused?.Invoke();
                }
                else if (newState == ProgramState.Running && oldState == ProgramState.Paused)
                {
                    OnProgramResumed?.Invoke();
                }
                else if (newState == ProgramState.Completed)
                {
                    OnProgramCompleted?.Invoke();
                }
                else if (newState == ProgramState.Idle && oldState != ProgramState.Completed)
                {
                    OnProgramStopped?.Invoke();
                }
            }
        }

        private void UpdateProgress(int currentLine, int totalLines)
        {
            if (totalLines == 0) return;

            float progress = (float)currentLine / totalLines;
            OnProgressUpdate?.Invoke(progress);

            if (progressText != null)
            {
                progressText.text = $"Line {currentLine}/{totalLines} ({progress * 100:F1}%)";
            }

            if (progressBar != null)
            {
                progressBar.fillAmount = progress;
            }
        }

        private System.Collections.IEnumerator SendRunCommand(string programId)
        {
            var url = $"{flaskServerUrl}/api/control/program/run";
            var data = new { machineId, programId };

            var json = JsonConvert.SerializeObject(data);
            var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");
            var task = _httpClient.PostAsync(url, content);

            while (!task.IsCompleted) yield return null;

            if (task.IsFaulted || !task.Result.IsSuccessStatusCode)
            {
                Debug.LogError("[ProgramExecutor] Run command failed");
                OnError?.Invoke("Failed to start program");
                UpdateState(ProgramState.Error);
            }
            else
            {
                Debug.Log($"[ProgramExecutor] Program {programId} started");
                UpdateState(ProgramState.Running);
            }
        }

        private System.Collections.IEnumerator SendPauseCommand()
        {
            var url = $"{flaskServerUrl}/api/control/program/pause";
            var data = new { machineId };

            var json = JsonConvert.SerializeObject(data);
            var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");
            var task = _httpClient.PostAsync(url, content);

            while (!task.IsCompleted) yield return null;

            if (task.IsFaulted || !task.Result.IsSuccessStatusCode)
            {
                Debug.LogError("[ProgramExecutor] Pause command failed");
                OnError?.Invoke("Failed to pause program");
            }
            else
            {
                UpdateState(ProgramState.Paused);
            }
        }

        private System.Collections.IEnumerator SendResumeCommand()
        {
            var url = $"{flaskServerUrl}/api/control/program/resume";
            var data = new { machineId };

            var json = JsonConvert.SerializeObject(data);
            var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");
            var task = _httpClient.PostAsync(url, content);

            while (!task.IsCompleted) yield return null;

            if (task.IsFaulted || !task.Result.IsSuccessStatusCode)
            {
                Debug.LogError("[ProgramExecutor] Resume command failed");
                OnError?.Invoke("Failed to resume program");
            }
            else
            {
                UpdateState(ProgramState.Running);
            }
        }

        private System.Collections.IEnumerator SendStopCommand()
        {
            var url = $"{flaskServerUrl}/api/control/program/stop";
            var data = new { machineId };

            var json = JsonConvert.SerializeObject(data);
            var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");
            var task = _httpClient.PostAsync(url, content);

            while (!task.IsCompleted) yield return null;

            if (task.IsFaulted || !task.Result.IsSuccessStatusCode)
            {
                Debug.LogError("[ProgramExecutor] Stop command failed");
                OnError?.Invoke("Failed to stop program");
            }
            else
            {
                UpdateState(ProgramState.Idle);
            }
        }

        private System.Collections.IEnumerator SendFeedOverrideCommand(float percent)
        {
            var url = $"{flaskServerUrl}/api/control/feed-override";
            var data = new { machineId, percent };

            var json = JsonConvert.SerializeObject(data);
            var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");
            var task = _httpClient.PostAsync(url, content);

            while (!task.IsCompleted) yield return null;

            if (task.IsFaulted || !task.Result.IsSuccessStatusCode)
            {
                Debug.LogWarning("[ProgramExecutor] Feed override failed");
            }
        }

        #endregion
    }

    #region Data Classes

    [Serializable]
    public class ProgramStatusResponse
    {
        public string machineId;
        public ProgramState state;
        public int progress;
        public int totalLines;
        public string currentProgram;
    }

    public enum ProgramState
    {
        Idle,
        Running,
        Paused,
        Completed,
        Error
    }

    #endregion
}
