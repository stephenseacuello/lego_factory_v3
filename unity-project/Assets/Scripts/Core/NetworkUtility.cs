using UnityEngine;
using System;
using System.Collections;
using System.Net.Http;
using System.Text;
using Newtonsoft.Json;

namespace CNCScada.Core
{
    /// <summary>
    /// Network Utility for HTTP Requests
    /// Provides standardized HTTP communication with retry logic
    /// </summary>
    public static class NetworkUtility
    {
        private static HttpClient sharedClient;

        static NetworkUtility()
        {
            sharedClient = new HttpClient();
            sharedClient.Timeout = TimeSpan.FromSeconds(30);
            sharedClient.DefaultRequestHeaders.Add("User-Agent", "Unity-CNC-SCADA");
        }

        /// <summary>
        /// GET request with JSON deserialization
        /// </summary>
        public static IEnumerator GetAsync<T>(string url, Action<T> onSuccess, Action<string> onError, int maxRetries = 3)
        {
            int attempts = 0;

            while (attempts < maxRetries)
            {
                using (var request = new HttpRequestMessage(HttpMethod.Get, url))
                {
                    var task = sharedClient.SendAsync(request);
                    while (!task.IsCompleted) yield return null;

                    if (task.IsFaulted || task.Result == null)
                    {
                        attempts++;
                        if (attempts >= maxRetries)
                        {
                            onError?.Invoke($"GET failed after {maxRetries} attempts: {task.Exception?.Message}");
                            yield break;
                        }
                        yield return new WaitForSeconds(Mathf.Pow(2, attempts)); // Exponential backoff
                        continue;
                    }

                    if (!task.Result.IsSuccessStatusCode)
                    {
                        onError?.Invoke($"HTTP {task.Result.StatusCode}");
                        yield break;
                    }

                    var readTask = task.Result.Content.ReadAsStringAsync();
                    while (!readTask.IsCompleted) yield return null;

                    try
                    {
                        T result = JsonConvert.DeserializeObject<T>(readTask.Result);
                        onSuccess?.Invoke(result);
                        yield break;
                    }
                    catch (Exception e)
                    {
                        onError?.Invoke($"JSON parse error: {e.Message}");
                        yield break;
                    }
                }
            }
        }

        /// <summary>
        /// POST request with JSON serialization
        /// </summary>
        public static IEnumerator PostAsync<TRequest, TResponse>(string url, TRequest data, Action<TResponse> onSuccess, Action<string> onError)
        {
            string jsonData;
            try
            {
                jsonData = JsonConvert.SerializeObject(data);
            }
            catch (Exception e)
            {
                onError?.Invoke($"JSON serialization error: {e.Message}");
                yield break;
            }

            using (var request = new HttpRequestMessage(HttpMethod.Post, url))
            {
                request.Content = new StringContent(jsonData, Encoding.UTF8, "application/json");

                var task = sharedClient.SendAsync(request);
                while (!task.IsCompleted) yield return null;

                if (task.IsFaulted || task.Result == null)
                {
                    onError?.Invoke($"POST failed: {task.Exception?.Message}");
                    yield break;
                }

                if (!task.Result.IsSuccessStatusCode)
                {
                    onError?.Invoke($"HTTP {task.Result.StatusCode}");
                    yield break;
                }

                var readTask = task.Result.Content.ReadAsStringAsync();
                while (!readTask.IsCompleted) yield return null;

                try
                {
                    TResponse result = JsonConvert.DeserializeObject<TResponse>(readTask.Result);
                    onSuccess?.Invoke(result);
                }
                catch (Exception e)
                {
                    onError?.Invoke($"JSON parse error: {e.Message}");
                }
            }
        }

        /// <summary>
        /// Simple ping to check server availability
        /// </summary>
        public static IEnumerator PingAsync(string baseUrl, Action<bool> onComplete)
        {
            string url = baseUrl.TrimEnd('/') + "/api/v1/health";

            using (var request = new HttpRequestMessage(HttpMethod.Get, url))
            {
                var task = sharedClient.SendAsync(request);

                float timeout = 5f;
                float elapsed = 0f;

                while (!task.IsCompleted && elapsed < timeout)
                {
                    elapsed += Time.deltaTime;
                    yield return null;
                }

                bool success = task.IsCompleted && !task.IsFaulted && task.Result != null && task.Result.IsSuccessStatusCode;
                onComplete?.Invoke(success);
            }
        }

        /// <summary>
        /// Build URL with query parameters
        /// </summary>
        public static string BuildUrl(string baseUrl, string endpoint, params (string key, string value)[] queryParams)
        {
            string url = baseUrl.TrimEnd('/') + "/" + endpoint.TrimStart('/');

            if (queryParams != null && queryParams.Length > 0)
            {
                url += "?";
                for (int i = 0; i < queryParams.Length; i++)
                {
                    if (i > 0) url += "&";
                    url += Uri.EscapeDataString(queryParams[i].key) + "=" + Uri.EscapeDataString(queryParams[i].value);
                }
            }

            return url;
        }

        /// <summary>
        /// Dispose of shared client
        /// </summary>
        public static void Cleanup()
        {
            if (sharedClient != null)
            {
                sharedClient.Dispose();
                sharedClient = null;
            }
        }
    }
}
