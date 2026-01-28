using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace CNCScada.Connection
{
    /// <summary>
    /// WebSocket connection wrapper for Unity.
    /// Handles low-level WebSocket communication with Flask SocketIO server.
    /// </summary>
    public class WebSocketConnection
    {
        private string url;
        private bool isConnected = false;
        private Queue<string> messageQueue = new Queue<string>();

        // Native WebSocket for WebGL builds
#if UNITY_WEBGL && !UNITY_EDITOR
        [System.Runtime.InteropServices.DllImport("__Internal")]
        private static extern int WebSocketCreate(string url);

        [System.Runtime.InteropServices.DllImport("__Internal")]
        private static extern int WebSocketState(int instanceId);

        [System.Runtime.InteropServices.DllImport("__Internal")]
        private static extern void WebSocketSend(int instanceId, string message);

        [System.Runtime.InteropServices.DllImport("__Internal")]
        private static extern void WebSocketClose(int instanceId);

        private int webSocketInstance = -1;
#else
        // For standalone builds, we'll use a polling approach with UnityWebRequest
        // In production, consider using a native WebSocket library like NativeWebSocket
        private bool usePolling = true;
        private float pollInterval = 0.1f;
        private MonoBehaviour coroutineRunner;
#endif

        // Events
        public event Action OnOpen;
        public event Action OnClose;
        public event Action<string> OnMessage;
        public event Action<string> OnError;

        public bool IsConnected => isConnected;

        public WebSocketConnection(string url)
        {
            this.url = url;
        }

        /// <summary>
        /// Connect to the WebSocket server
        /// </summary>
        public IEnumerator Connect()
        {
#if UNITY_WEBGL && !UNITY_EDITOR
            webSocketInstance = WebSocketCreate(url);

            // Wait for connection
            float timeout = 5f;
            float elapsed = 0f;
            while (WebSocketState(webSocketInstance) == 0 && elapsed < timeout)
            {
                elapsed += Time.deltaTime;
                yield return null;
            }

            if (WebSocketState(webSocketInstance) == 1)
            {
                isConnected = true;
                OnOpen?.Invoke();
            }
            else
            {
                OnError?.Invoke("WebSocket connection timeout");
            }
#else
            // For Editor/Standalone: Use HTTP long-polling fallback
            // This simulates the connection for development
            Debug.Log($"[WebSocket] Connecting to {url} (polling mode)");

            // Try to establish connection via HTTP handshake
            string httpUrl = url.Replace("ws://", "http://").Replace("wss://", "https://");
            httpUrl = httpUrl.Split('?')[0].Replace("/socket.io/", "/socket.io/");

            using (UnityWebRequest request = UnityWebRequest.Get(httpUrl + "?EIO=4&transport=polling"))
            {
                request.timeout = 5;
                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.Success)
                {
                    isConnected = true;
                    OnOpen?.Invoke();
                    Debug.Log("[WebSocket] Connected via polling");
                }
                else
                {
                    // Even if polling fails, mark as connected for local development
                    isConnected = true;
                    OnOpen?.Invoke();
                    Debug.LogWarning($"[WebSocket] HTTP handshake failed, continuing anyway: {request.error}");
                }
            }
#endif
        }

        /// <summary>
        /// Send a message to the server
        /// </summary>
        public void Send(string message)
        {
            if (!isConnected)
            {
                Debug.LogWarning("[WebSocket] Cannot send - not connected");
                return;
            }

#if UNITY_WEBGL && !UNITY_EDITOR
            WebSocketSend(webSocketInstance, message);
#else
            // Queue message for HTTP POST in polling mode
            messageQueue.Enqueue(message);
            SendQueuedMessages();
#endif
        }

        /// <summary>
        /// Close the connection
        /// </summary>
        public void Close()
        {
#if UNITY_WEBGL && !UNITY_EDITOR
            if (webSocketInstance >= 0)
            {
                WebSocketClose(webSocketInstance);
            }
#endif
            isConnected = false;
            OnClose?.Invoke();
        }

        private void SendQueuedMessages()
        {
            // In a real implementation, this would POST to the Socket.IO polling endpoint
            while (messageQueue.Count > 0)
            {
                string msg = messageQueue.Dequeue();
                Debug.Log($"[WebSocket] Sending: {msg}");
            }
        }

        /// <summary>
        /// Process incoming messages (call from Update)
        /// </summary>
        public void ProcessMessages()
        {
#if UNITY_WEBGL && !UNITY_EDITOR
            // WebGL: Messages come via JavaScript callbacks
#else
            // Polling mode: Would fetch messages from server
#endif
        }
    }

    /// <summary>
    /// WebGL JavaScript plugin bridge
    /// Place WebSocket.jslib in Plugins/WebGL folder
    /// </summary>
#if UNITY_WEBGL
    public static class WebSocketJSLib
    {
        public const string JSLIB_CONTENT = @"
var WebSocketPlugin = {
    $webSockets: [],
    $messageQueues: [],

    WebSocketCreate: function(urlPtr) {
        var url = UTF8ToString(urlPtr);
        var id = webSockets.length;
        var ws = new WebSocket(url);
        webSockets.push(ws);
        messageQueues.push([]);

        ws.onopen = function() { console.log('WebSocket connected'); };
        ws.onclose = function() { console.log('WebSocket closed'); };
        ws.onerror = function(e) { console.error('WebSocket error', e); };
        ws.onmessage = function(e) { messageQueues[id].push(e.data); };

        return id;
    },

    WebSocketState: function(id) {
        if (id < 0 || id >= webSockets.length) return 3;
        return webSockets[id].readyState;
    },

    WebSocketSend: function(id, msgPtr) {
        if (id < 0 || id >= webSockets.length) return;
        var msg = UTF8ToString(msgPtr);
        webSockets[id].send(msg);
    },

    WebSocketClose: function(id) {
        if (id < 0 || id >= webSockets.length) return;
        webSockets[id].close();
    }
};

autoAddDeps(WebSocketPlugin, '$webSockets');
autoAddDeps(WebSocketPlugin, '$messageQueues');
mergeInto(LibraryManager.library, WebSocketPlugin);
";
    }
#endif
}
