using UnityEngine;
using UnityEngine.UI;
using System;
using System.Net.Http;
using Newtonsoft.Json;

namespace CNCScada.RemoteControl
{
    /// <summary>
    /// Emergency stop button with confirmation dialog
    /// High-priority command with visual/audio feedback
    /// </summary>
    public class EmergencyStopButton : MonoBehaviour
    {
        #region Serialized Fields

        [Header("Connection")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private string machineId = "CNC-001";

        [Header("UI References")]
        [SerializeField] private Button eStopButton;
        [SerializeField] private Button resetButton;
        [SerializeField] private GameObject confirmationDialog;
        [SerializeField] private Text statusText;

        [Header("Safety Settings")]
        [SerializeField] private bool requireConfirmation = true;
        [SerializeField] private float confirmationTimeout = 5f;
        [SerializeField] private bool enableAudioFeedback = true;
        [SerializeField] private AudioClip eStopSound;

        [Header("Visual Feedback")]
        [SerializeField] private Color normalColor = Color.red;
        [SerializeField] private Color activeColor = new Color(0.5f, 0f, 0f); // dark red
        [SerializeField] private Color pulseColor = new Color(1f, 0f, 0f); // bright red
        [SerializeField] private bool animateButton = true;
        [SerializeField] private float pulseSpeed = 3f;

        #endregion

        #region Private Fields

        private HttpClient _httpClient;
        private bool _isEStopActive;
        private bool _confirmationPending;
        private float _confirmationTimer;
        private AudioSource _audioSource;

        #endregion

        #region Events

        public event Action OnEStopTriggered;
        public event Action OnEStopReset;
        public event Action<string> OnError;

        #endregion

        #region Unity Lifecycle

        void Start()
        {
            _httpClient = new HttpClient();
            _httpClient.Timeout = TimeSpan.FromSeconds(5);

            if (enableAudioFeedback)
            {
                _audioSource = gameObject.AddComponent<AudioSource>();
            }

            InitializeUI();
        }

        void Update()
        {
            // Handle confirmation timeout
            if (_confirmationPending)
            {
                _confirmationTimer -= Time.deltaTime;
                if (_confirmationTimer <= 0)
                {
                    CancelConfirmation();
                }
            }

            // Animate button when E-stop is active
            if (animateButton && _isEStopActive)
            {
                AnimateButton();
            }

            // Keyboard shortcut
            if (Input.GetKeyDown(KeyCode.F1))
            {
                TriggerEStop();
            }
        }

        void OnDestroy()
        {
            _httpClient?.Dispose();
        }

        #endregion

        #region Public Methods

        /// <summary>
        /// Trigger emergency stop
        /// </summary>
        public void TriggerEStop()
        {
            if (_isEStopActive)
            {
                Debug.LogWarning("[EStop] Already active");
                return;
            }

            if (requireConfirmation && !_confirmationPending)
            {
                ShowConfirmation();
                return;
            }

            ExecuteEStop();
        }

        /// <summary>
        /// Reset emergency stop
        /// </summary>
        public void ResetEStop()
        {
            if (!_isEStopActive)
            {
                Debug.LogWarning("[EStop] Not active");
                return;
            }

            StartCoroutine(SendResetCommand());
        }

        /// <summary>
        /// Check if E-stop is active
        /// </summary>
        public bool IsActive()
        {
            return _isEStopActive;
        }

        #endregion

        #region Private Methods

        private void InitializeUI()
        {
            if (eStopButton != null)
            {
                eStopButton.onClick.AddListener(TriggerEStop);

                var image = eStopButton.GetComponent<Image>();
                if (image != null)
                {
                    image.color = normalColor;
                }
            }

            if (resetButton != null)
            {
                resetButton.onClick.AddListener(ResetEStop);
                resetButton.interactable = false;
            }

            if (confirmationDialog != null)
            {
                confirmationDialog.SetActive(false);

                // Setup confirmation buttons
                var confirmButton = confirmationDialog.GetComponentInChildren<Button>();
                if (confirmButton != null)
                {
                    confirmButton.onClick.AddListener(() =>
                    {
                        _confirmationPending = false;
                        ExecuteEStop();
                        confirmationDialog.SetActive(false);
                    });
                }
            }

            UpdateStatusDisplay();
        }

        private void ShowConfirmation()
        {
            if (confirmationDialog != null)
            {
                confirmationDialog.SetActive(true);
                _confirmationPending = true;
                _confirmationTimer = confirmationTimeout;
            }
            else
            {
                // No dialog, execute immediately
                ExecuteEStop();
            }
        }

        private void CancelConfirmation()
        {
            _confirmationPending = false;
            if (confirmationDialog != null)
            {
                confirmationDialog.SetActive(false);
            }
        }

        private void ExecuteEStop()
        {
            Debug.Log("[EStop] EMERGENCY STOP TRIGGERED");

            // Play audio feedback
            if (enableAudioFeedback && _audioSource != null && eStopSound != null)
            {
                _audioSource.PlayOneShot(eStopSound);
            }

            // Visual feedback
            SetButtonColor(activeColor);

            // Send command
            StartCoroutine(SendEStopCommand());
        }

        private System.Collections.IEnumerator SendEStopCommand()
        {
            var url = $"{flaskServerUrl}/api/control/estop";
            var data = new { machineId, priority = 1 }; // Highest priority

            var json = JsonConvert.SerializeObject(data);
            var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");

            // Use shorter timeout for E-stop
            var oldTimeout = _httpClient.Timeout;
            _httpClient.Timeout = TimeSpan.FromSeconds(2);

            var task = _httpClient.PostAsync(url, content);

            while (!task.IsCompleted) yield return null;

            _httpClient.Timeout = oldTimeout;

            if (task.IsFaulted || !task.Result.IsSuccessStatusCode)
            {
                Debug.LogError("[EStop] Command failed!");
                OnError?.Invoke("E-Stop command failed");

                // Still mark as active locally for safety
                _isEStopActive = true;
                OnEStopTriggered?.Invoke();
                UpdateStatusDisplay();
            }
            else
            {
                Debug.Log("[EStop] Command sent successfully");
                _isEStopActive = true;
                OnEStopTriggered?.Invoke();
                UpdateStatusDisplay();
            }
        }

        private System.Collections.IEnumerator SendResetCommand()
        {
            var url = $"{flaskServerUrl}/api/control/estop/reset";
            var data = new { machineId };

            var json = JsonConvert.SerializeObject(data);
            var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");
            var task = _httpClient.PostAsync(url, content);

            while (!task.IsCompleted) yield return null;

            if (task.IsFaulted || !task.Result.IsSuccessStatusCode)
            {
                Debug.LogError("[EStop] Reset failed");
                OnError?.Invoke("E-Stop reset failed");
            }
            else
            {
                Debug.Log("[EStop] Reset successful");
                _isEStopActive = false;
                OnEStopReset?.Invoke();
                SetButtonColor(normalColor);
                UpdateStatusDisplay();
            }
        }

        private void AnimateButton()
        {
            if (eStopButton == null) return;

            float pulse = (Mathf.Sin(Time.time * pulseSpeed) + 1f) / 2f;
            var image = eStopButton.GetComponent<Image>();
            if (image != null)
            {
                image.color = Color.Lerp(activeColor, pulseColor, pulse);
            }

            // Scale pulsing
            eStopButton.transform.localScale = Vector3.one * (1f + pulse * 0.1f);
        }

        private void SetButtonColor(Color color)
        {
            if (eStopButton != null)
            {
                var image = eStopButton.GetComponent<Image>();
                if (image != null)
                {
                    image.color = color;
                }
            }
        }

        private void UpdateStatusDisplay()
        {
            if (statusText != null)
            {
                statusText.text = _isEStopActive ? "E-STOP ACTIVE" : "NORMAL";
                statusText.color = _isEStopActive ? Color.red : Color.green;
            }

            if (eStopButton != null)
            {
                var text = eStopButton.GetComponentInChildren<Text>();
                if (text != null)
                {
                    text.text = _isEStopActive ? "ACTIVE" : "E-STOP";
                }
            }

            if (resetButton != null)
            {
                resetButton.interactable = _isEStopActive;
            }
        }

        #endregion
    }
}
