using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.Networking;

namespace CNCScada.Notifications
{
    /// <summary>
    /// Notification service for operator alerts and system messages.
    /// Supports multiple notification channels: UI, audio, email, SMS, push.
    /// Integrates with external notification providers via webhooks.
    /// </summary>
    public class NotificationService : MonoBehaviour
    {
        [Header("Configuration")]
        [SerializeField] private bool enableNotifications = true;
        [SerializeField] private int maxNotifications = 100;
        [SerializeField] private float defaultDuration = 5f;

        [Header("Channels")]
        [SerializeField] private bool enableUINotifications = true;
        [SerializeField] private bool enableAudioAlerts = true;
        [SerializeField] private bool enableWebhooks = false;

        [Header("Webhook Settings")]
        [SerializeField] private string slackWebhookUrl = "";
        [SerializeField] private string teamsWebhookUrl = "";
        [SerializeField] private string emailApiUrl = "";

        [Header("Audio")]
        [SerializeField] private AudioSource audioSource;
        [SerializeField] private AudioClip infoSound;
        [SerializeField] private AudioClip warningSound;
        [SerializeField] private AudioClip errorSound;
        [SerializeField] private AudioClip successSound;

        [Header("Active Notifications")]
        [SerializeField] private List<Notification> activeNotifications = new List<Notification>();

        [Header("Statistics")]
        [SerializeField] private int totalNotificationsSent;
        [SerializeField] private int unreadCount;

        // History
        private Queue<Notification> notificationHistory = new Queue<Notification>();

        // Notification rules
        private List<NotificationRule> rules = new List<NotificationRule>();

        // Events
        public event Action<Notification> OnNotificationCreated;
        public event Action<Notification> OnNotificationDismissed;
        public event Action<Notification> OnNotificationRead;
        public event Action<int> OnUnreadCountChanged;

        // Singleton
        public static NotificationService Instance { get; private set; }

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
            }
            else
            {
                Destroy(gameObject);
                return;
            }

            InitializeDefaultRules();
            SetupEventListeners();
        }

        private void Start()
        {
            if (audioSource == null && enableAudioAlerts)
            {
                audioSource = gameObject.AddComponent<AudioSource>();
                audioSource.playOnAwake = false;
            }
        }

        private void InitializeDefaultRules()
        {
            // Production alerts
            rules.Add(new NotificationRule
            {
                ruleId = "PRODUCTION_COMPLETE",
                ruleName = "Production Order Complete",
                eventType = "WorkOrderCompleted",
                channels = new List<NotificationChannel> { NotificationChannel.UI, NotificationChannel.Audio },
                notificationType = NotificationType.Success,
                priority = NotificationPriority.Normal
            });

            // Quality alerts
            rules.Add(new NotificationRule
            {
                ruleId = "QUALITY_FAIL",
                ruleName = "Quality Inspection Failed",
                eventType = "InspectionFailed",
                channels = new List<NotificationChannel> { NotificationChannel.UI, NotificationChannel.Audio, NotificationChannel.Webhook },
                notificationType = NotificationType.Warning,
                priority = NotificationPriority.High
            });

            // Safety alerts
            rules.Add(new NotificationRule
            {
                ruleId = "SAFETY_VIOLATION",
                ruleName = "Safety Zone Violation",
                eventType = "SafetyViolation",
                channels = new List<NotificationChannel> { NotificationChannel.UI, NotificationChannel.Audio, NotificationChannel.Webhook },
                notificationType = NotificationType.Error,
                priority = NotificationPriority.Critical
            });

            // Maintenance alerts
            rules.Add(new NotificationRule
            {
                ruleId = "MAINTENANCE_DUE",
                ruleName = "Maintenance Due",
                eventType = "MaintenanceDue",
                channels = new List<NotificationChannel> { NotificationChannel.UI, NotificationChannel.Email },
                notificationType = NotificationType.Warning,
                priority = NotificationPriority.Normal
            });

            // Energy alerts
            rules.Add(new NotificationRule
            {
                ruleId = "PEAK_DEMAND",
                ruleName = "Peak Demand Warning",
                eventType = "PeakDemand",
                channels = new List<NotificationChannel> { NotificationChannel.UI, NotificationChannel.Audio },
                notificationType = NotificationType.Warning,
                priority = NotificationPriority.Normal
            });
        }

        private void SetupEventListeners()
        {
            // Subscribe to alarm system
            var alarmSystem = FindObjectOfType<CNCScada.Alarms.AlarmSystem>();
            if (alarmSystem != null)
            {
                alarmSystem.OnAlarmRaised += (alarm) =>
                {
                    var type = alarm.severity >= CNCScada.Alarms.AlarmSeverity.High ?
                        NotificationType.Error : NotificationType.Warning;

                    Notify(
                        $"Alarm: {alarm.name}",
                        alarm.description,
                        type,
                        alarm.severity == CNCScada.Alarms.AlarmSeverity.Critical ?
                            NotificationPriority.Critical : NotificationPriority.High
                    );
                };
            }

            // Subscribe to work order manager
            var workOrderManager = FindObjectOfType<CNCScada.WorkOrder.WorkOrderManager>();
            if (workOrderManager != null)
            {
                workOrderManager.OnOrderCompleted += (order) =>
                {
                    Notify(
                        "Order Complete",
                        $"Work order {order.orderId} completed: {order.partName} x{order.quantity}",
                        NotificationType.Success,
                        NotificationPriority.Normal
                    );
                };
            }

            // Subscribe to vision inspection
            var visionSystem = FindObjectOfType<CNCScada.Vision.VisionInspectionSystem>();
            if (visionSystem != null)
            {
                visionSystem.OnDefectDetected += (defect) =>
                {
                    var type = defect.severity == CNCScada.Vision.DefectSeverity.Critical ?
                        NotificationType.Error : NotificationType.Warning;

                    Notify(
                        "Defect Detected",
                        $"Quality issue: {defect.defectType} ({defect.severity})",
                        type,
                        NotificationPriority.High
                    );
                };
            }

            // Subscribe to safety zone monitor
            var safetyMonitor = FindObjectOfType<CNCScada.Safety.SafetyZoneMonitor>();
            if (safetyMonitor != null)
            {
                safetyMonitor.OnZoneViolation += (zone, violation) =>
                {
                    Notify(
                        "Safety Violation",
                        $"Intrusion detected in {zone.zoneName}",
                        NotificationType.Error,
                        NotificationPriority.Critical
                    );
                };

                safetyMonitor.OnEmergencyStop += () =>
                {
                    Notify(
                        "EMERGENCY STOP",
                        "Emergency stop has been activated. All machines stopped.",
                        NotificationType.Error,
                        NotificationPriority.Critical
                    );
                };
            }

            // Subscribe to predictive maintenance
            var predictive = FindObjectOfType<CNCScada.Predictive.PredictiveMaintenanceSystem>();
            if (predictive != null)
            {
                predictive.OnPredictionUpdated += (prediction) =>
                {
                    if (prediction.severity == CNCScada.Predictive.AlertSeverity.Warning ||
                        prediction.severity == CNCScada.Predictive.AlertSeverity.Critical)
                    {
                        Notify(
                            "Maintenance Required",
                            $"Predicted maintenance needed: {prediction.recommendation}",
                            NotificationType.Warning,
                            NotificationPriority.Normal
                        );
                    }
                };
            }
        }

        // =========================================================================
        // Notification Creation
        // =========================================================================

        /// <summary>
        /// Send a notification
        /// </summary>
        public Notification Notify(string title, string message,
            NotificationType type = NotificationType.Info,
            NotificationPriority priority = NotificationPriority.Normal,
            float duration = -1)
        {
            if (!enableNotifications)
            {
                return null;
            }

            var notification = new Notification
            {
                id = $"NOTIF_{DateTime.Now.Ticks}",
                title = title,
                message = message,
                type = type,
                priority = priority,
                timestamp = DateTime.Now,
                duration = duration > 0 ? duration : defaultDuration,
                isRead = false,
                isDismissed = false
            };

            ProcessNotification(notification);

            return notification;
        }

        /// <summary>
        /// Send a notification with action buttons
        /// </summary>
        public Notification NotifyWithActions(string title, string message,
            NotificationType type, List<NotificationAction> actions)
        {
            var notification = Notify(title, message, type, NotificationPriority.High, 0);

            if (notification != null)
            {
                notification.actions = actions;
                notification.duration = 0; // Don't auto-dismiss
            }

            return notification;
        }

        private void ProcessNotification(Notification notification)
        {
            // Add to active notifications
            activeNotifications.Add(notification);
            totalNotificationsSent++;
            unreadCount++;

            // Add to history
            notificationHistory.Enqueue(notification);
            while (notificationHistory.Count > maxNotifications)
            {
                notificationHistory.Dequeue();
            }

            // Trigger channels
            if (enableUINotifications)
            {
                // UI notification is handled via events
            }

            if (enableAudioAlerts)
            {
                PlayNotificationSound(notification.type);
            }

            if (enableWebhooks && notification.priority >= NotificationPriority.High)
            {
                StartCoroutine(SendWebhookNotification(notification));
            }

            OnNotificationCreated?.Invoke(notification);
            OnUnreadCountChanged?.Invoke(unreadCount);

            // Schedule auto-dismiss
            if (notification.duration > 0)
            {
                StartCoroutine(AutoDismiss(notification));
            }

            Debug.Log($"[Notification] {notification.type}: {notification.title}");
        }

        private void PlayNotificationSound(NotificationType type)
        {
            if (audioSource == null)
            {
                return;
            }

            AudioClip clip = type switch
            {
                NotificationType.Success => successSound,
                NotificationType.Warning => warningSound,
                NotificationType.Error => errorSound,
                _ => infoSound
            };

            if (clip != null)
            {
                audioSource.PlayOneShot(clip);
            }
        }

        private IEnumerator AutoDismiss(Notification notification)
        {
            yield return new WaitForSeconds(notification.duration);

            if (!notification.isDismissed)
            {
                DismissNotification(notification.id);
            }
        }

        // =========================================================================
        // Webhook Integration
        // =========================================================================

        private IEnumerator SendWebhookNotification(Notification notification)
        {
            // Send to Slack
            if (!string.IsNullOrEmpty(slackWebhookUrl))
            {
                yield return StartCoroutine(SendSlackNotification(notification));
            }

            // Send to Microsoft Teams
            if (!string.IsNullOrEmpty(teamsWebhookUrl))
            {
                yield return StartCoroutine(SendTeamsNotification(notification));
            }
        }

        private IEnumerator SendSlackNotification(Notification notification)
        {
            string color = notification.type switch
            {
                NotificationType.Success => "good",
                NotificationType.Warning => "warning",
                NotificationType.Error => "danger",
                _ => "#439FE0"
            };

            var payload = new SlackPayload
            {
                attachments = new SlackAttachment[]
                {
                    new SlackAttachment
                    {
                        fallback = $"{notification.title}: {notification.message}",
                        color = color,
                        title = notification.title,
                        text = notification.message,
                        footer = "CNC SCADA Digital Twin",
                        ts = DateTimeOffset.Now.ToUnixTimeSeconds()
                    }
                }
            };

            string json = JsonUtility.ToJson(payload);

            using (UnityWebRequest request = new UnityWebRequest(slackWebhookUrl, "POST"))
            {
                byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(json);
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json");
                request.timeout = 10;

                yield return request.SendWebRequest();

                if (request.result != UnityWebRequest.Result.Success)
                {
                    Debug.LogWarning($"[Notification] Slack webhook failed: {request.error}");
                }
            }
        }

        private IEnumerator SendTeamsNotification(Notification notification)
        {
            string themeColor = notification.type switch
            {
                NotificationType.Success => "00FF00",
                NotificationType.Warning => "FFFF00",
                NotificationType.Error => "FF0000",
                _ => "0078D7"
            };

            var payload = new TeamsPayload
            {
                themeColor = themeColor,
                title = notification.title,
                text = notification.message
            };

            string json = JsonUtility.ToJson(payload);

            using (UnityWebRequest request = new UnityWebRequest(teamsWebhookUrl, "POST"))
            {
                byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(json);
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json");
                request.timeout = 10;

                yield return request.SendWebRequest();

                if (request.result != UnityWebRequest.Result.Success)
                {
                    Debug.LogWarning($"[Notification] Teams webhook failed: {request.error}");
                }
            }
        }

        // =========================================================================
        // Notification Management
        // =========================================================================

        /// <summary>
        /// Dismiss a notification
        /// </summary>
        public void DismissNotification(string notificationId)
        {
            var notification = activeNotifications.Find(n => n.id == notificationId);

            if (notification != null)
            {
                notification.isDismissed = true;
                activeNotifications.Remove(notification);
                OnNotificationDismissed?.Invoke(notification);
            }
        }

        /// <summary>
        /// Mark notification as read
        /// </summary>
        public void MarkAsRead(string notificationId)
        {
            var notification = activeNotifications.Find(n => n.id == notificationId);

            if (notification != null && !notification.isRead)
            {
                notification.isRead = true;
                unreadCount = Mathf.Max(0, unreadCount - 1);
                OnNotificationRead?.Invoke(notification);
                OnUnreadCountChanged?.Invoke(unreadCount);
            }
        }

        /// <summary>
        /// Mark all notifications as read
        /// </summary>
        public void MarkAllAsRead()
        {
            foreach (var notification in activeNotifications)
            {
                if (!notification.isRead)
                {
                    notification.isRead = true;
                    OnNotificationRead?.Invoke(notification);
                }
            }

            unreadCount = 0;
            OnUnreadCountChanged?.Invoke(unreadCount);
        }

        /// <summary>
        /// Dismiss all notifications
        /// </summary>
        public void DismissAll()
        {
            foreach (var notification in activeNotifications.ToArray())
            {
                notification.isDismissed = true;
                OnNotificationDismissed?.Invoke(notification);
            }

            activeNotifications.Clear();
        }

        /// <summary>
        /// Execute notification action
        /// </summary>
        public void ExecuteAction(string notificationId, string actionId)
        {
            var notification = activeNotifications.Find(n => n.id == notificationId);

            if (notification?.actions != null)
            {
                var action = notification.actions.Find(a => a.actionId == actionId);
                action?.callback?.Invoke();

                // Dismiss after action
                DismissNotification(notificationId);
            }
        }

        // =========================================================================
        // Query Methods
        // =========================================================================

        public List<Notification> GetActiveNotifications() => new List<Notification>(activeNotifications);

        public List<Notification> GetNotificationHistory(int count = 50)
        {
            var list = notificationHistory.ToList();
            list.Reverse();
            return list.Take(count).ToList();
        }

        public List<Notification> GetUnreadNotifications()
        {
            return activeNotifications.FindAll(n => !n.isRead);
        }

        public List<Notification> GetNotificationsByType(NotificationType type)
        {
            return activeNotifications.FindAll(n => n.type == type);
        }

        public List<Notification> GetNotificationsByPriority(NotificationPriority minPriority)
        {
            return activeNotifications.FindAll(n => n.priority >= minPriority);
        }

        // =========================================================================
        // Rule Management
        // =========================================================================

        public void AddRule(NotificationRule rule) => rules.Add(rule);
        public void RemoveRule(string ruleId) => rules.RemoveAll(r => r.ruleId == ruleId);
        public List<NotificationRule> GetRules() => new List<NotificationRule>(rules);

        // Properties
        public int UnreadCount => unreadCount;
        public int ActiveCount => activeNotifications.Count;
        public int TotalSent => totalNotificationsSent;
    }

    // =========================================================================
    // Data Types
    // =========================================================================

    public enum NotificationType
    {
        Info,
        Success,
        Warning,
        Error
    }

    public enum NotificationPriority
    {
        Low = 0,
        Normal = 1,
        High = 2,
        Critical = 3
    }

    public enum NotificationChannel
    {
        UI,
        Audio,
        Email,
        SMS,
        Webhook,
        Push
    }

    [Serializable]
    public class Notification
    {
        public string id;
        public string title;
        public string message;
        public NotificationType type;
        public NotificationPriority priority;
        public DateTime timestamp;
        public float duration;
        public bool isRead;
        public bool isDismissed;
        public string category;
        public string source;
        public List<NotificationAction> actions;
    }

    [Serializable]
    public class NotificationAction
    {
        public string actionId;
        public string label;
        public Action callback;
    }

    [Serializable]
    public class NotificationRule
    {
        public string ruleId;
        public string ruleName;
        public string eventType;
        public List<NotificationChannel> channels;
        public NotificationType notificationType;
        public NotificationPriority priority;
        public bool isEnabled = true;
    }

    // Webhook payloads
    [Serializable]
    public class SlackPayload
    {
        public SlackAttachment[] attachments;
    }

    [Serializable]
    public class SlackAttachment
    {
        public string fallback;
        public string color;
        public string title;
        public string text;
        public string footer;
        public long ts;
    }

    [Serializable]
    public class TeamsPayload
    {
        [SerializeField] private string type = "MessageCard";
        [SerializeField] private string context = "https://schema.org/extensions";
        public string themeColor;
        public string title;
        public string text;
    }
}
