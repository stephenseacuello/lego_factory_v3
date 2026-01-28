using UnityEngine;
using UnityEngine.UI;
using System;
using System.Collections;
using System.Net.Http;
using System.Text;
using Newtonsoft.Json;

namespace CNCScada.RemoteControl
{
    /// <summary>
    /// Emergency Stop Button with Confirmation
    /// Provides immediate machine stop with safety confirmation
    /// Part of Phase 5: Remote Control (<20ms)
    /// </summary>
    public class EmergencyStopButton : MonoBehaviour
    {
        [Header("Connection Settings")]
        [SerializeField] private string flaskServerUrl = "http://localhost:5000";
        [SerializeField] private string machineId = "CNC-001";

        [Header("UI References")]
        [SerializeField] private Button eStopButton;
        [SerializeField] private Button confirmButton;
        [SerializeField] private Button cancelButton;
        [SerializeField] private GameObject confirmationPanel;
        [SerializeField] private Text statusText;
        [SerializeField] private Image buttonImage;

        [Header("Configuration")]
        [SerializeField] private bool requireConfirmation = true;
        [SerializeField] private float confirmationTimeout = 10f;
        [SerializeField] private Color normalColor = Color.red;
        [SerializeField] private Color activeColor = Color.yellow;
        [SerializeField] private Color pressedColor = Color.darkred;

        // State
        private HttpClient httpClient;
        private bool isEStopped = false;
        private bool awaitingConfirmation = false;
        private float confirmationTimer = 0f;

        // Statistics
        private int totalEStops = 0;
        private int confirmedEStops = 0;
        private int cancelledEStops = 0;

        // Events
        public event Action OnEStopRequested;
        public event Action OnEStopConfirmed;
        public event Action OnEStopCancelled;
        public event Action OnEStopReset;

        void Start()
        {
            httpClient = new HttpClient();
            httpClient.Timeout = TimeSpan.FromSeconds(5);
            SetupUI();
            Debug.Log("[EmergencyStop] Initialized for machine: " + machineId);
        }

        void SetupUI()
        {
            if (eStopButton != null)
            {
                eStopButton.onClick.AddListener(OnEStopButtonClicked);
            }

            if (confirmButton != null)
            {
                confirmButton.onClick.AddListener(OnConfirmButtonClicked);
            }

            if (cancelButton != null)
            {
                cancelButton.onClick.AddListener(OnCancelButtonClicked);
            }

            if (confirmationPanel != null)
            {
                confirmationPanel.SetActive(false);
            }

            UpdateButtonAppearance();
        }

        void Update()
        {
            if (awaitingConfirmation)
            {
                confirmationTimer -= Time.deltaTime;
                if (confirmationTimer <= 0f)
                {
                    AutoCancelConfirmation();
                }

                if (statusText != null)
                {
                    statusText.text = $"Confirm E-Stop? ({confirmationTimer:F1}s)";
                }
            }
        }

        void OnEStopButtonClicked()
        {
            if (isEStopped)
            {
                ResetEStop();
            }
            else
            {
                RequestEStop();
            }
        }

        void OnConfirmButtonClicked()
        {
            ConfirmEStop();
        }

        void OnCancelButtonClicked()
        {
            CancelEStop();
        }

        public void RequestEStop()
        {
            totalEStops++;

            if (requireConfirmation && !awaitingConfirmation)
            {
                ShowConfirmation();
                OnEStopRequested?.Invoke();
            }
            else
            {
                ExecuteEStop();
            }
        }

        void ShowConfirmation()
        {
            awaitingConfirmation = true;
            confirmationTimer = confirmationTimeout;

            if (confirmationPanel != null)
            {
                confirmationPanel.SetActive(true);
            }

            if (statusText != null)
            {
                statusText.text = $"Confirm E-Stop? ({confirmationTimer:F1}s)";
            }

            UpdateButtonAppearance();
        }

        void ConfirmEStop()
        {
            if (!awaitingConfirmation) return;

            awaitingConfirmation = false;
            confirmedEStops++;

            if (confirmationPanel != null)
            {
                confirmationPanel.SetActive(false);
            }

            ExecuteEStop();
            OnEStopConfirmed?.Invoke();
        }

        void CancelEStop()
        {
            if (!awaitingConfirmation) return;

            awaitingConfirmation = false;
            cancelledEStops++;

            if (confirmationPanel != null)
            {
                confirmationPanel.SetActive(false);
            }

            if (statusText != null)
            {
                statusText.text = "E-Stop cancelled";
            }

            UpdateButtonAppearance();
            OnEStopCancelled?.Invoke();
        }

        void AutoCancelConfirmation()
        {
            CancelEStop();
            Debug.Log("[EmergencyStop] Confirmation timed out");
        }

        void ExecuteEStop()
        {
            isEStopped = true;
            StartCoroutine(SendEStopCommand());

            if (statusText != null)
            {
                statusText.text = "EMERGENCY STOP ACTIVE";
            }

            UpdateButtonAppearance();
            Debug.LogWarning("[EmergencyStop] E-STOP ACTIVATED!");
        }

        void ResetEStop()
        {
            isEStopped = false;
            StartCoroutine(SendResetCommand());

            if (statusText != null)
            {
                statusText.text = "E-Stop reset - Machine ready";
            }

            UpdateButtonAppearance();
            OnEStopReset?.Invoke();
            Debug.Log("[EmergencyStop] E-Stop reset");
        }

        IEnumerator SendEStopCommand()
        {
            string url = $"{flaskServerUrl}/api/v1/unity/control/estop";

            var eStopData = new
            {
                machine_id = machineId,
                action = "activate"
            };

            string jsonData = JsonConvert.SerializeObject(eStopData);

            using (var request = new HttpRequestMessage(HttpMethod.Post, url))
            {
                request.Content = new StringContent(jsonData, Encoding.UTF8, "application/json");

                var task = httpClient.SendAsync(request);
                while (!task.IsCompleted) yield return null;

                if (task.IsFaulted || task.Result == null || !task.Result.IsSuccessStatusCode)
                {
                    Debug.LogError("[EmergencyStop] Failed to send E-Stop command");
                }
                else
                {
                    Debug.Log("[EmergencyStop] E-Stop command sent successfully");
                }
            }
        }

        IEnumerator SendResetCommand()
        {
            string url = $"{flaskServerUrl}/api/v1/unity/control/estop";

            var resetData = new
            {
                machine_id = machineId,
                action = "reset"
            };

            string jsonData = JsonConvert.SerializeObject(resetData);

            using (var request = new HttpRequestMessage(HttpMethod.Post, url))
            {
                request.Content = new StringContent(jsonData, Encoding.UTF8, "application/json");

                var task = httpClient.SendAsync(request);
                while (!task.IsCompleted) yield return null;

                if (task.IsFaulted || task.Result == null || !task.Result.IsSuccessStatusCode)
                {
                    Debug.LogError("[EmergencyStop] Failed to send reset command");
                }
                else
                {
                    Debug.Log("[EmergencyStop] Reset command sent successfully");
                }
            }
        }

        void UpdateButtonAppearance()
        {
            if (buttonImage != null)
            {
                if (isEStopped)
                {
                    buttonImage.color = pressedColor;
                }
                else if (awaitingConfirmation)
                {
                    buttonImage.color = activeColor;
                }
                else
                {
                    buttonImage.color = normalColor;
                }
            }

            if (eStopButton != null)
            {
                var buttonText = eStopButton.GetComponentInChildren<Text>();
                if (buttonText != null)
                {
                    buttonText.text = isEStopped ? "RESET" : "E-STOP";
                }
            }
        }

        public Dictionary<string, object> GetStatistics()
        {
            return new Dictionary<string, object>
            {
                {"total_estops", totalEStops},
                {"confirmed_estops", confirmedEStops},
                {"cancelled_estops", cancelledEStops},
                {"is_estopped", isEStopped},
                {"awaiting_confirmation", awaitingConfirmation}
            };
        }

        void OnDestroy()
        {
            if (httpClient != null) httpClient.Dispose();
        }

        void OnDrawGizmos()
        {
            if (!Application.isPlaying) return;

            if (isEStopped)
            {
                Gizmos.color = Color.red;
                Gizmos.DrawWireSphere(transform.position, 50f);
            }
        }
    }
}
