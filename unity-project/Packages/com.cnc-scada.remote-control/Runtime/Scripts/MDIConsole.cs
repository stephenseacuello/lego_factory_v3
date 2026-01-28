using UnityEngine;
using UnityEngine.UI;
using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Linq;
using Newtonsoft.Json;

namespace CNCScada.RemoteControl
{
    /// <summary>
    /// Manual Data Input (MDI) console for G-code execution
    /// Supports command history, auto-completion, and syntax validation
    /// </summary>
    public class MDIConsole : MonoBehaviour
    {
        #region Serialized Fields

        [Header("Connection")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private string machineId = "CNC-001";

        [Header("UI References")]
        [SerializeField] private InputField commandInput;
        [SerializeField] private Text outputText;
        [SerializeField] private ScrollRect outputScrollRect;
        [SerializeField] private Button sendButton;
        [SerializeField] private Button clearButton;

        [Header("Console Settings")]
        [SerializeField] private int maxHistorySize = 100;
        [SerializeField] private int maxOutputLines = 500;
        [SerializeField] private bool enableAutoComplete = true;
        [SerializeField] private bool validateSyntax = true;

        [Header("Colors")]
        [SerializeField] private Color commandColor = Color.white;
        [SerializeField] private Color responseColor = Color.cyan;
        [SerializeField] private Color errorColor = Color.red;
        [SerializeField] private Color warningColor = Color.yellow;

        #endregion

        #region Private Fields

        private HttpClient _httpClient;
        private List<string> _commandHistory;
        private int _historyIndex;
        private List<string> _outputLines;
        private string[] _gcodeSuggestions;

        #endregion

        #region Events

        public event Action<string> OnCommandSent;
        public event Action<string> OnResponse;
        public event Action<string> OnError;

        #endregion

        #region Unity Lifecycle

        void Start()
        {
            _httpClient = new HttpClient();
            _httpClient.Timeout = TimeSpan.FromSeconds(10);
            _commandHistory = new List<string>();
            _outputLines = new List<string>();
            _historyIndex = 0;

            InitializeGCodeSuggestions();
            InitializeUI();
            AddOutputLine("MDI Console Ready", responseColor);
        }

        void Update()
        {
            HandleKeyboardInput();
        }

        void OnDestroy()
        {
            _httpClient?.Dispose();
        }

        #endregion

        #region Public Methods

        /// <summary>
        /// Send G-code command
        /// </summary>
        public void SendCommand(string command)
        {
            if (string.IsNullOrWhiteSpace(command)) return;

            command = command.Trim().ToUpper();

            // Validate syntax if enabled
            if (validateSyntax && !ValidateGCode(command))
            {
                AddOutputLine($"Syntax Error: {command}", errorColor);
                OnError?.Invoke($"Invalid G-code: {command}");
                return;
            }

            // Add to history
            AddToHistory(command);

            // Display command
            AddOutputLine($"> {command}", commandColor);

            // Send to backend
            StartCoroutine(ExecuteCommand(command));
            OnCommandSent?.Invoke(command);
        }

        /// <summary>
        /// Clear console output
        /// </summary>
        public void ClearOutput()
        {
            _outputLines.Clear();
            if (outputText != null)
            {
                outputText.text = "";
            }
        }

        /// <summary>
        /// Get command history
        /// </summary>
        public List<string> GetCommandHistory()
        {
            return new List<string>(_commandHistory);
        }

        /// <summary>
        /// Get auto-complete suggestions for partial command
        /// </summary>
        public List<string> GetSuggestions(string partial)
        {
            if (!enableAutoComplete || string.IsNullOrEmpty(partial)) return new List<string>();

            return _gcodeSuggestions
                .Where(s => s.StartsWith(partial.ToUpper()))
                .ToList();
        }

        #endregion

        #region Private Methods

        private void InitializeGCodeSuggestions()
        {
            _gcodeSuggestions = new string[]
            {
                "G0", "G1", "G2", "G3", "G4", "G17", "G18", "G19",
                "G20", "G21", "G28", "G90", "G91", "G92", "G94",
                "M0", "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9",
                "M30", "M98", "M99",
                "F", "S", "T",
                "X", "Y", "Z", "A", "B", "C",
                "I", "J", "K", "R", "P", "Q"
            };
        }

        private void InitializeUI()
        {
            if (commandInput != null)
            {
                commandInput.onEndEdit.AddListener((value) =>
                {
                    if (Input.GetKeyDown(KeyCode.Return) || Input.GetKeyDown(KeyCode.KeypadEnter))
                    {
                        SendCommand(value);
                        commandInput.text = "";
                        commandInput.ActivateInputField();
                    }
                });
            }

            if (sendButton != null)
            {
                sendButton.onClick.AddListener(() =>
                {
                    SendCommand(commandInput.text);
                    commandInput.text = "";
                    commandInput.ActivateInputField();
                });
            }

            if (clearButton != null)
            {
                clearButton.onClick.AddListener(ClearOutput);
            }
        }

        private void HandleKeyboardInput()
        {
            if (commandInput == null || !commandInput.isFocused) return;

            // History navigation
            if (Input.GetKeyDown(KeyCode.UpArrow))
            {
                NavigateHistory(-1);
            }
            else if (Input.GetKeyDown(KeyCode.DownArrow))
            {
                NavigateHistory(1);
            }

            // Auto-complete
            if (Input.GetKeyDown(KeyCode.Tab) && enableAutoComplete)
            {
                AutoComplete();
            }
        }

        private void NavigateHistory(int direction)
        {
            if (_commandHistory.Count == 0) return;

            _historyIndex = Mathf.Clamp(_historyIndex + direction, 0, _commandHistory.Count);

            if (_historyIndex == _commandHistory.Count)
            {
                commandInput.text = "";
            }
            else
            {
                commandInput.text = _commandHistory[_commandHistory.Count - 1 - _historyIndex];
                commandInput.caretPosition = commandInput.text.Length;
            }
        }

        private void AutoComplete()
        {
            if (string.IsNullOrEmpty(commandInput.text)) return;

            var suggestions = GetSuggestions(commandInput.text);
            if (suggestions.Count == 1)
            {
                commandInput.text = suggestions[0];
                commandInput.caretPosition = commandInput.text.Length;
            }
            else if (suggestions.Count > 1)
            {
                AddOutputLine($"Suggestions: {string.Join(", ", suggestions)}", warningColor);
            }
        }

        private void AddToHistory(string command)
        {
            _commandHistory.Add(command);
            while (_commandHistory.Count > maxHistorySize)
            {
                _commandHistory.RemoveAt(0);
            }
            _historyIndex = 0;
        }

        private void AddOutputLine(string line, Color color)
        {
            _outputLines.Add(line);
            while (_outputLines.Count > maxOutputLines)
            {
                _outputLines.RemoveAt(0);
            }

            UpdateOutputDisplay();
        }

        private void UpdateOutputDisplay()
        {
            if (outputText == null) return;

            // Combine all output lines
            outputText.text = string.Join("\n", _outputLines);

            // Scroll to bottom
            if (outputScrollRect != null)
            {
                Canvas.ForceUpdateCanvases();
                outputScrollRect.verticalNormalizedPosition = 0f;
            }
        }

        private bool ValidateGCode(string command)
        {
            // Basic G-code validation
            if (string.IsNullOrWhiteSpace(command)) return false;

            // Must start with G, M, or valid axis letter
            char firstChar = command[0];
            if (!char.IsLetter(firstChar)) return false;

            // Check for valid command codes
            if (firstChar == 'G' || firstChar == 'M')
            {
                // Must have number after G or M
                if (command.Length < 2) return false;
                if (!char.IsDigit(command[1])) return false;
            }
            else if (!"XYZABCFSTPIJKRQ".Contains(firstChar))
            {
                return false;
            }

            return true;
        }

        private System.Collections.IEnumerator ExecuteCommand(string command)
        {
            var url = $"{flaskServerUrl}/api/control/mdi";
            var data = new
            {
                machineId,
                command
            };

            var json = JsonConvert.SerializeObject(data);
            var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");
            var task = _httpClient.PostAsync(url, content);

            while (!task.IsCompleted) yield return null;

            if (task.IsFaulted || !task.Result.IsSuccessStatusCode)
            {
                string errorMsg = task.Exception?.Message ?? $"HTTP {task.Result?.StatusCode}";
                AddOutputLine($"Error: {errorMsg}", errorColor);
                OnError?.Invoke(errorMsg);
                yield break;
            }

            var readTask = task.Result.Content.ReadAsStringAsync();
            while (!readTask.IsCompleted) yield return null;

            try
            {
                var response = JsonConvert.DeserializeObject<CommandResponse>(readTask.Result);
                if (response.success)
                {
                    AddOutputLine($"OK: {response.message}", responseColor);
                    OnResponse?.Invoke(response.message);
                }
                else
                {
                    AddOutputLine($"Error: {response.message}", errorColor);
                    OnError?.Invoke(response.message);
                }
            }
            catch (Exception e)
            {
                AddOutputLine($"Parse Error: {e.Message}", errorColor);
                OnError?.Invoke($"Parse error: {e.Message}");
            }
        }

        #endregion
    }

    #region Data Classes

    [Serializable]
    public class CommandResponse
    {
        public bool success;
        public string message;
        public int executionTimeMs;
    }

    #endregion
}
