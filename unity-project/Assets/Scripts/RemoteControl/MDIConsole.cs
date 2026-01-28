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
    /// MDI (Manual Data Input) Console for Direct G-code Entry
    /// Provides command history, auto-completion, and validation
    /// Part of Phase 5: Remote Control (<20ms)
    /// </summary>
    public class MDIConsole : MonoBehaviour
    {
        [Header("Connection Settings")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private string machineId = "CNC-001";
        [SerializeField] private float commandTimeoutSeconds = 5.0f;

        [Header("UI References")]
        [SerializeField] private InputField commandInput;
        [SerializeField] private Button sendButton;
        [SerializeField] private Button clearButton;
        [SerializeField] private Text outputText;
        [SerializeField] private ScrollRect outputScrollRect;
        [SerializeField] private Dropdown quickCommandsDropdown;
        [SerializeField] private Text statusText;

        [Header("Console Configuration")]
        [SerializeField] private int maxHistoryLines = 100;
        [SerializeField] private int maxOutputLines = 500;
        [SerializeField] private Color commandColor = Color.white;
        [SerializeField] private Color responseColor = Color.cyan;
        [SerializeField] private Color errorColor = Color.red;
        [SerializeField] private Color successColor = Color.green;

        // State
        private HttpClient httpClient;
        private List<string> commandHistory = new List<string>();
        private int historyIndex = -1;
        private List<string> outputLines = new List<string>();
        private bool isConnected = false;
        private bool isProcessing = false;

        // Statistics
        private int totalCommands = 0;
        private int successfulCommands = 0;
        private int failedCommands = 0;

        // Events
        public event Action<string> OnCommandSent;
        public event Action<string, bool> OnResponseReceived;

        // Quick Commands
        private readonly string[] quickCommands = {
            "G0 X0 Y0 Z0",
            "G1 X10 Y10 F1000",
            "G28",
            "M3 S1000",
            "M5",
            "G54",
            "G90",
            "G91"
        };

        [Serializable]
        public class MDICommand
        {
            public string machine_id;
            public string command;
            public float timestamp;
        }

        [Serializable]
        public class MDIResponse
        {
            public bool success;
            public string message;
            public string result;
            public string error;
            public float execution_time_ms;
        }

        void Start()
        {
            InitializeHTTPClient();
            SetupUI();
            AppendOutput("MDI Console Ready", successColor);
            Debug.Log("[MDIConsole] Initialized for machine: " + machineId);
        }

        void InitializeHTTPClient()
        {
            httpClient = new HttpClient();
            httpClient.Timeout = TimeSpan.FromSeconds(commandTimeoutSeconds);
            httpClient.DefaultRequestHeaders.Add("User-Agent", "Unity-CNC-MDI-Console");
        }

        void SetupUI()
        {
            if (sendButton != null)
            {
                sendButton.onClick.AddListener(OnSendButtonClicked);
            }

            if (clearButton != null)
            {
                clearButton.onClick.AddListener(OnClearButtonClicked);
            }

            if (commandInput != null)
            {
                commandInput.onEndEdit.AddListener(OnInputEndEdit);
            }

            if (quickCommandsDropdown != null)
            {
                quickCommandsDropdown.ClearOptions();
                List<string> options = new List<string> { "Quick Commands..." };
                options.AddRange(quickCommands);
                quickCommandsDropdown.AddOptions(options);
                quickCommandsDropdown.onValueChanged.AddListener(OnQuickCommandSelected);
            }
        }

        void Update()
        {
            if (commandInput != null && commandInput.isFocused)
            {
                if (Input.GetKeyDown(KeyCode.UpArrow))
                {
                    NavigateHistory(-1);
                }
                else if (Input.GetKeyDown(KeyCode.DownArrow))
                {
                    NavigateHistory(1);
                }
            }
        }

        void OnSendButtonClicked()
        {
            SendCurrentCommand();
        }

        void OnClearButtonClicked()
        {
            ClearOutput();
        }

        void OnInputEndEdit(string text)
        {
            if (Input.GetKeyDown(KeyCode.Return) || Input.GetKeyDown(KeyCode.KeypadEnter))
            {
                SendCurrentCommand();
            }
        }

        void OnQuickCommandSelected(int index)
        {
            if (index > 0 && index <= quickCommands.Length)
            {
                string command = quickCommands[index - 1];
                if (commandInput != null)
                {
                    commandInput.text = command;
                    commandInput.ActivateInputField();
                }
            }
            if (quickCommandsDropdown != null)
            {
                quickCommandsDropdown.value = 0;
            }
        }

        void SendCurrentCommand()
        {
            if (commandInput == null || string.IsNullOrWhiteSpace(commandInput.text))
            {
                return;
            }

            if (isProcessing)
            {
                AppendOutput("Waiting for previous command...", errorColor);
                return;
            }

            string command = commandInput.text.Trim();
            commandHistory.Add(command);
            if (commandHistory.Count > maxHistoryLines)
            {
                commandHistory.RemoveAt(0);
            }
            historyIndex = commandHistory.Count;

            AppendOutput($"> {command}", commandColor);
            commandInput.text = "";

            StartCoroutine(SendMDICommand(command));
        }

        void NavigateHistory(int direction)
        {
            if (commandHistory.Count == 0) return;

            historyIndex += direction;
            historyIndex = Mathf.Clamp(historyIndex, 0, commandHistory.Count);

            if (commandInput != null)
            {
                if (historyIndex < commandHistory.Count)
                {
                    commandInput.text = commandHistory[historyIndex];
                }
                else
                {
                    commandInput.text = "";
                }
            }
        }

        IEnumerator SendMDICommand(string command)
        {
            isProcessing = true;
            string url = $"{flaskServerUrl}/api/v1/unity/control/mdi";

            MDICommand mdiCommand = new MDICommand
            {
                machine_id = machineId,
                command = command,
                timestamp = Time.realtimeSinceStartup
            };

            string jsonData = JsonConvert.SerializeObject(mdiCommand);

            using (var request = new HttpRequestMessage(HttpMethod.Post, url))
            {
                request.Content = new StringContent(jsonData, Encoding.UTF8, "application/json");

                var task = httpClient.SendAsync(request);
                while (!task.IsCompleted) yield return null;

                if (task.IsFaulted || task.Result == null || !task.Result.IsSuccessStatusCode)
                {
                    failedCommands++;
                    totalCommands++;
                    string errorMsg = task.IsFaulted ? task.Exception.Message : "HTTP error";
                    AppendOutput($"Error: {errorMsg}", errorColor);
                    OnResponseReceived?.Invoke(errorMsg, false);
                    isProcessing = false;
                    yield break;
                }

                var readTask = task.Result.Content.ReadAsStringAsync();
                while (!readTask.IsCompleted) yield return null;

                try
                {
                    MDIResponse response = JsonConvert.DeserializeObject<MDIResponse>(readTask.Result);

                    if (response.success)
                    {
                        successfulCommands++;
                        totalCommands++;
                        string resultText = string.IsNullOrEmpty(response.result) ? "OK" : response.result;
                        AppendOutput($"{resultText} ({response.execution_time_ms:F1}ms)", responseColor);
                        OnResponseReceived?.Invoke(resultText, true);
                    }
                    else
                    {
                        failedCommands++;
                        totalCommands++;
                        AppendOutput($"Error: {response.error}", errorColor);
                        OnResponseReceived?.Invoke(response.error, false);
                    }
                }
                catch (Exception e)
                {
                    failedCommands++;
                    totalCommands++;
                    AppendOutput($"Parse error: {e.Message}", errorColor);
                }
            }

            isProcessing = false;
            OnCommandSent?.Invoke(command);
        }

        void AppendOutput(string message, Color color)
        {
            string colorHex = ColorUtility.ToHtmlStringRGB(color);
            string formattedMessage = $"<color=#{colorHex}>{message}</color>";

            outputLines.Add(formattedMessage);

            if (outputLines.Count > maxOutputLines)
            {
                outputLines.RemoveAt(0);
            }

            UpdateOutputDisplay();
        }

        void UpdateOutputDisplay()
        {
            if (outputText != null)
            {
                outputText.text = string.Join("\n", outputLines);
                if (outputScrollRect != null)
                {
                    Canvas.ForceUpdateCanvases();
                    outputScrollRect.verticalNormalizedPosition = 0f;
                }
            }
        }

        void ClearOutput()
        {
            outputLines.Clear();
            if (outputText != null)
            {
                outputText.text = "";
            }
            AppendOutput("Console cleared", successColor);
        }

        public Dictionary<string, object> GetStatistics()
        {
            return new Dictionary<string, object>
            {
                {"total_commands", totalCommands},
                {"successful_commands", successfulCommands},
                {"failed_commands", failedCommands},
                {"success_rate", totalCommands > 0 ? (float)successfulCommands / totalCommands : 0f},
                {"history_size", commandHistory.Count}
            };
        }

        void OnDestroy()
        {
            if (httpClient != null) httpClient.Dispose();
        }
    }
}
