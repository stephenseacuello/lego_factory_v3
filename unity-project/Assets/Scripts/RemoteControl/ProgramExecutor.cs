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
    /// Program Executor for CNC Program Management
    /// Run, pause, resume, and stop G-code programs
    /// Part of Phase 5: Remote Control (<20ms)
    /// </summary>
    public class ProgramExecutor : MonoBehaviour
    {
        [Header("Connection Settings")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private string machineId = "CNC-001";
        [SerializeField] private float statusPollInterval = 0.5f;

        [Header("UI References")]
        [SerializeField] private Button runButton;
        [SerializeField] private Button pauseButton;
        [SerializeField] private Button resumeButton;
        [SerializeField] private Button stopButton;
        [SerializeField] private Dropdown programDropdown;
        [SerializeField] private Slider feedOverrideSlider;
        [SerializeField] private Slider speedOverrideSlider;
        [SerializeField] private Text progressText;
        [SerializeField] private Slider progressBar;
        [SerializeField] private Text statusText;
        [SerializeField] private Text timeRemainingText;
        [SerializeField] private Text feedOverrideText;
        [SerializeField] private Text speedOverrideText;

        [Header("Configuration")]
        [SerializeField] private float minOverride = 10f;
        [SerializeField] private float maxOverride = 200f;

        // State
        private HttpClient httpClient;
        private string currentProgram = "";
        private ProgramState programState = ProgramState.IDLE;
        private int totalLines = 0;
        private int currentLine = 0;
        private float feedOverride = 100f;
        private float speedOverride = 100f;
        private float estimatedTimeRemaining = 0f;

        // Statistics
        private int totalProgramsRun = 0;
        private int successfulCompletions = 0;
        private int failedExecutions = 0;

        // Events
        public event Action<string> OnProgramStarted;
        public event Action<string> OnProgramPaused;
        public event Action<string> OnProgramResumed;
        public event Action<string> OnProgramStopped;
        public event Action<string> OnProgramCompleted;
        public event Action<int, int> OnProgressUpdated;

        public enum ProgramState
        {
            IDLE,
            RUNNING,
            PAUSED,
            STOPPED,
            COMPLETED,
            ERROR
        }

        [Serializable]
        public class ProgramCommand
        {
            public string machine_id;
            public string action;
            public string program_name;
            public float feed_override;
            public float speed_override;
        }

        [Serializable]
        public class ProgramStatusResponse
        {
            public bool success;
            public string state;
            public string program_name;
            public int total_lines;
            public int current_line;
            public float progress_percent;
            public float estimated_time_remaining;
            public string error;
        }

        void Start()
        {
            httpClient = new HttpClient();
            httpClient.Timeout = TimeSpan.FromSeconds(30);
            SetupUI();
            StartCoroutine(PollProgramStatus());
            Debug.Log("[ProgramExecutor] Initialized for machine: " + machineId);
        }

        void SetupUI()
        {
            if (runButton != null) runButton.onClick.AddListener(OnRunButtonClicked);
            if (pauseButton != null) pauseButton.onClick.AddListener(OnPauseButtonClicked);
            if (resumeButton != null) resumeButton.onClick.AddListener(OnResumeButtonClicked);
            if (stopButton != null) stopButton.onClick.AddListener(OnStopButtonClicked);

            if (feedOverrideSlider != null)
            {
                feedOverrideSlider.minValue = minOverride;
                feedOverrideSlider.maxValue = maxOverride;
                feedOverrideSlider.value = feedOverride;
                feedOverrideSlider.onValueChanged.AddListener(OnFeedOverrideChanged);
            }

            if (speedOverrideSlider != null)
            {
                speedOverrideSlider.minValue = minOverride;
                speedOverrideSlider.maxValue = maxOverride;
                speedOverrideSlider.value = speedOverride;
                speedOverrideSlider.onValueChanged.AddListener(OnSpeedOverrideChanged);
            }

            UpdateButtonStates();
        }

        void OnRunButtonClicked()
        {
            if (programDropdown != null && programDropdown.value > 0)
            {
                string programName = programDropdown.options[programDropdown.value].text;
                RunProgram(programName);
            }
        }

        void OnPauseButtonClicked()
        {
            PauseProgram();
        }

        void OnResumeButtonClicked()
        {
            ResumeProgram();
        }

        void OnStopButtonClicked()
        {
            StopProgram();
        }

        void OnFeedOverrideChanged(float value)
        {
            feedOverride = value;
            if (feedOverrideText != null) feedOverrideText.text = $"{value:F0}%";
            if (programState == ProgramState.RUNNING) StartCoroutine(SendOverrideUpdate());
        }

        void OnSpeedOverrideChanged(float value)
        {
            speedOverride = value;
            if (speedOverrideText != null) speedOverrideText.text = $"{value:F0}%";
            if (programState == ProgramState.RUNNING) StartCoroutine(SendOverrideUpdate());
        }

        public void RunProgram(string programName)
        {
            if (programState == ProgramState.RUNNING)
            {
                UpdateStatus("Program already running", true);
                return;
            }

            currentProgram = programName;
            StartCoroutine(SendProgramCommand("run", programName));
        }

        public void PauseProgram()
        {
            if (programState != ProgramState.RUNNING)
            {
                return;
            }
            StartCoroutine(SendProgramCommand("pause", currentProgram));
        }

        public void ResumeProgram()
        {
            if (programState != ProgramState.PAUSED)
            {
                return;
            }
            StartCoroutine(SendProgramCommand("resume", currentProgram));
        }

        public void StopProgram()
        {
            if (programState == ProgramState.IDLE || programState == ProgramState.STOPPED)
            {
                return;
            }
            StartCoroutine(SendProgramCommand("stop", currentProgram));
        }

        IEnumerator SendProgramCommand(string action, string programName)
        {
            string url = $"{flaskServerUrl}/api/v1/unity/control/program";

            ProgramCommand command = new ProgramCommand
            {
                machine_id = machineId,
                action = action,
                program_name = programName,
                feed_override = feedOverride,
                speed_override = speedOverride
            };

            string jsonData = JsonConvert.SerializeObject(command);

            using (var request = new HttpRequestMessage(HttpMethod.Post, url))
            {
                request.Content = new StringContent(jsonData, Encoding.UTF8, "application/json");
                var task = httpClient.SendAsync(request);
                while (!task.IsCompleted) yield return null;

                if (task.IsFaulted || task.Result == null || !task.Result.IsSuccessStatusCode)
                {
                    UpdateStatus($"{action} failed", true);
                    yield break;
                }

                var readTask = task.Result.Content.ReadAsStringAsync();
                while (!readTask.IsCompleted) yield return null;

                try
                {
                    var response = JsonConvert.DeserializeObject<Dictionary<string, object>>(readTask.Result);
                    bool success = response.ContainsKey("success") && (bool)response["success"];

                    if (success)
                    {
                        switch (action)
                        {
                            case "run":
                                totalProgramsRun++;
                                programState = ProgramState.RUNNING;
                                OnProgramStarted?.Invoke(programName);
                                UpdateStatus($"Running: {programName}", false);
                                break;
                            case "pause":
                                programState = ProgramState.PAUSED;
                                OnProgramPaused?.Invoke(programName);
                                UpdateStatus("Program paused", false);
                                break;
                            case "resume":
                                programState = ProgramState.RUNNING;
                                OnProgramResumed?.Invoke(programName);
                                UpdateStatus("Program resumed", false);
                                break;
                            case "stop":
                                programState = ProgramState.STOPPED;
                                OnProgramStopped?.Invoke(programName);
                                UpdateStatus("Program stopped", false);
                                break;
                        }
                        UpdateButtonStates();
                    }
                    else
                    {
                        UpdateStatus($"{action} failed", true);
                    }
                }
                catch { UpdateStatus($"{action} error", true); }
            }
        }

        IEnumerator SendOverrideUpdate()
        {
            string url = $"{flaskServerUrl}/api/v1/unity/control/override";
            var overrideData = new
            {
                machine_id = machineId,
                feed_override = feedOverride,
                speed_override = speedOverride
            };

            string jsonData = JsonConvert.SerializeObject(overrideData);

            using (var request = new HttpRequestMessage(HttpMethod.Post, url))
            {
                request.Content = new StringContent(jsonData, Encoding.UTF8, "application/json");
                var task = httpClient.SendAsync(request);
                while (!task.IsCompleted) yield return null;
            }
        }

        IEnumerator PollProgramStatus()
        {
            while (true)
            {
                yield return new WaitForSeconds(statusPollInterval);

                string url = $"{flaskServerUrl}/api/v1/unity/program/status/{machineId}";

                using (var request = new HttpRequestMessage(HttpMethod.Get, url))
                {
                    var task = httpClient.SendAsync(request);
                    while (!task.IsCompleted) yield return null;

                    if (task.IsFaulted || task.Result == null || !task.Result.IsSuccessStatusCode)
                    {
                        continue;
                    }

                    var readTask = task.Result.Content.ReadAsStringAsync();
                    while (!readTask.IsCompleted) yield return null;

                    try
                    {
                        ProgramStatusResponse status = JsonConvert.DeserializeObject<ProgramStatusResponse>(readTask.Result);

                        if (status.success)
                        {
                            UpdateProgramState(status);
                        }
                    }
                    catch { }
                }
            }
        }

        void UpdateProgramState(ProgramStatusResponse status)
        {
            currentProgram = status.program_name;
            totalLines = status.total_lines;
            currentLine = status.current_line;
            estimatedTimeRemaining = status.estimated_time_remaining;

            if (progressBar != null)
            {
                progressBar.value = status.progress_percent / 100f;
            }

            if (progressText != null)
            {
                progressText.text = $"{status.progress_percent:F1}% ({currentLine}/{totalLines})";
            }

            if (timeRemainingText != null)
            {
                TimeSpan timeSpan = TimeSpan.FromSeconds(estimatedTimeRemaining);
                timeRemainingText.text = $"Est: {timeSpan:hh\\:mm\\:ss}";
            }

            OnProgressUpdated?.Invoke(currentLine, totalLines);

            if (status.state == "COMPLETED" && programState == ProgramState.RUNNING)
            {
                successfulCompletions++;
                programState = ProgramState.COMPLETED;
                OnProgramCompleted?.Invoke(currentProgram);
                UpdateStatus("Program completed", false);
                UpdateButtonStates();
            }
        }

        void UpdateButtonStates()
        {
            if (runButton != null) runButton.interactable = (programState == ProgramState.IDLE || programState == ProgramState.STOPPED || programState == ProgramState.COMPLETED);
            if (pauseButton != null) pauseButton.interactable = (programState == ProgramState.RUNNING);
            if (resumeButton != null) resumeButton.interactable = (programState == ProgramState.PAUSED);
            if (stopButton != null) stopButton.interactable = (programState == ProgramState.RUNNING || programState == ProgramState.PAUSED);
        }

        void UpdateStatus(string message, bool isError)
        {
            if (statusText != null)
            {
                statusText.text = message;
                statusText.color = isError ? Color.red : Color.white;
            }
        }

        public Dictionary<string, object> GetStatistics()
        {
            return new Dictionary<string, object>
            {
                {"total_programs_run", totalProgramsRun},
                {"successful_completions", successfulCompletions},
                {"failed_executions", failedExecutions},
                {"current_program", currentProgram},
                {"current_state", programState.ToString()},
                {"progress_percent", totalLines > 0 ? ((float)currentLine / totalLines) * 100f : 0f}
            };
        }

        void OnDestroy()
        {
            if (httpClient != null) httpClient.Dispose();
        }
    }
}
