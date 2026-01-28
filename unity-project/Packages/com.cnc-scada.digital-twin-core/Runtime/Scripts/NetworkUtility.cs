using UnityEngine;
using System;
using System.Collections;
using System.Net.Http;
using System.Text;
using Newtonsoft.Json;

namespace CNCScada.DigitalTwin
{
    /// <summary>
    /// Shared network utility for HTTP and WebSocket operations
    /// Provides connection pooling, retry logic, and error handling
    /// </summary>
    public static class NetworkUtility
    {
        private static HttpClient _sharedHttpClient;
        private static bool _isInitialized;

        /// <summary>
        /// Initialize shared HTTP client with default settings
        /// </summary>
        public static void Initialize()
        {
            if (_isInitialized) return;

            _sharedHttpClient = new HttpClient();
            _sharedHttpClient.Timeout = TimeSpan.FromSeconds(10);
            _sharedHttpClient.DefaultRequestHeaders.Add("User-Agent", "Unity-CNC-SCADA/1.0");
            _isInitialized = true;
        }

        /// <summary>
        /// Get shared HTTP client (creates if not initialized)
        /// </summary>
        public static HttpClient GetHttpClient()
        {
            if (!_isInitialized)
            {
                Initialize();
            }
            return _sharedHttpClient;
        }

        /// <summary>
        /// Make GET request with retry logic
        /// </summary>
        public static IEnumerator GetRequest(string url, Action<string> onSuccess, Action<string> onError, int maxRetries = 3)
        {
            var client = GetHttpClient();
            int retryCount = 0;

            while (retryCount < maxRetries)
            {
                var task = client.GetStringAsync(url);

                while (!task.IsCompleted) yield return null;

                if (task.IsFaulted)
                {
                    retryCount++;
                    if (retryCount >= maxRetries)
                    {
                        onError?.Invoke($"Request failed after {maxRetries} retries: {task.Exception?.Message}");
                        yield break;
                    }

                    Debug.LogWarning($"[NetworkUtility] Retry {retryCount}/{maxRetries}: {task.Exception?.Message}");
                    yield return new WaitForSeconds(Mathf.Pow(2, retryCount)); // Exponential backoff
                }
                else
                {
                    onSuccess?.Invoke(task.Result);
                    yield break;
                }
            }
        }

        /// <summary>
        /// Make POST request with retry logic
        /// </summary>
        public static IEnumerator PostRequest(string url, object data, Action<string> onSuccess, Action<string> onError, int maxRetries = 3)
        {
            var client = GetHttpClient();
            int retryCount = 0;

            var json = JsonConvert.SerializeObject(data);
            var content = new StringContent(json, Encoding.UTF8, "application/json");

            while (retryCount < maxRetries)
            {
                var task = client.PostAsync(url, content);

                while (!task.IsCompleted) yield return null;

                if (task.IsFaulted || !task.Result.IsSuccessStatusCode)
                {
                    retryCount++;
                    if (retryCount >= maxRetries)
                    {
                        string errorMsg = task.IsFaulted ? task.Exception?.Message : $"HTTP {task.Result?.StatusCode}";
                        onError?.Invoke($"Request failed after {maxRetries} retries: {errorMsg}");
                        yield break;
                    }

                    Debug.LogWarning($"[NetworkUtility] Retry {retryCount}/{maxRetries}");
                    yield return new WaitForSeconds(Mathf.Pow(2, retryCount)); // Exponential backoff

                    // Recreate content for retry
                    content = new StringContent(json, Encoding.UTF8, "application/json");
                }
                else
                {
                    var readTask = task.Result.Content.ReadAsStringAsync();
                    while (!readTask.IsCompleted) yield return null;

                    onSuccess?.Invoke(readTask.Result);
                    yield break;
                }
            }
        }

        /// <summary>
        /// Check if URL is reachable
        /// </summary>
        public static IEnumerator CheckConnection(string url, Action<bool> callback)
        {
            var client = GetHttpClient();
            var task = client.GetAsync(url);

            while (!task.IsCompleted) yield return null;

            bool success = !task.IsFaulted && task.Result != null && task.Result.IsSuccessStatusCode;
            callback?.Invoke(success);
        }

        /// <summary>
        /// Parse JSON response
        /// </summary>
        public static bool TryParseJson<T>(string json, out T result, out string error)
        {
            try
            {
                result = JsonConvert.DeserializeObject<T>(json);
                error = null;
                return true;
            }
            catch (Exception e)
            {
                result = default(T);
                error = e.Message;
                return false;
            }
        }

        /// <summary>
        /// Build URL with query parameters
        /// </summary>
        public static string BuildUrl(string baseUrl, params (string key, string value)[] parameters)
        {
            if (parameters == null || parameters.Length == 0)
            {
                return baseUrl;
            }

            var queryString = new StringBuilder();
            for (int i = 0; i < parameters.Length; i++)
            {
                if (i > 0) queryString.Append("&");
                queryString.Append($"{Uri.EscapeDataString(parameters[i].key)}={Uri.EscapeDataString(parameters[i].value)}");
            }

            string separator = baseUrl.Contains("?") ? "&" : "?";
            return $"{baseUrl}{separator}{queryString}";
        }

        /// <summary>
        /// Cleanup shared resources
        /// </summary>
        public static void Shutdown()
        {
            _sharedHttpClient?.Dispose();
            _sharedHttpClient = null;
            _isInitialized = false;
        }
    }

    /// <summary>
    /// Network helper MonoBehaviour for coroutine execution
    /// </summary>
    public class NetworkHelper : MonoBehaviour
    {
        private static NetworkHelper _instance;

        public static NetworkHelper Instance
        {
            get
            {
                if (_instance == null)
                {
                    var go = new GameObject("NetworkHelper");
                    _instance = go.AddComponent<NetworkHelper>();
                    DontDestroyOnLoad(go);
                }
                return _instance;
            }
        }

        void OnDestroy()
        {
            NetworkUtility.Shutdown();
        }
    }
}
