/*
 * WebSocket.jslib - Native WebSocket plugin for Unity WebGL
 *
 * Provides low-level WebSocket access for Unity WebGL builds.
 * Used by FlaskSocketIOClient for real-time communication.
 *
 * Usage:
 *   // From C#:
 *   [DllImport("__Internal")]
 *   private static extern int WebSocketCreate(string url);
 *   [DllImport("__Internal")]
 *   private static extern int WebSocketState(int instanceId);
 *   [DllImport("__Internal")]
 *   private static extern void WebSocketSend(int instanceId, string message);
 *   [DllImport("__Internal")]
 *   private static extern void WebSocketClose(int instanceId);
 */

var WebSocketPlugin = {

    $webSockets: [],
    $webSocketCallbacks: {},
    $webSocketNextId: 0,

    /**
     * Create a new WebSocket connection
     * @param {string} urlPtr - Pointer to URL string
     * @returns {number} Instance ID
     */
    WebSocketCreate: function(urlPtr) {
        var url = UTF8ToString(urlPtr);
        var id = webSocketNextId++;

        var socket = new WebSocket(url);
        socket.binaryType = 'arraybuffer';

        webSockets[id] = socket;
        webSocketCallbacks[id] = {
            onOpen: null,
            onClose: null,
            onMessage: null,
            onError: null,
            messages: []
        };

        socket.onopen = function(event) {
            console.log('[WebSocketPlugin] Connected to ' + url);
            var callbacks = webSocketCallbacks[id];
            if (callbacks && callbacks.onOpen) {
                dynCall_vi(callbacks.onOpen, id);
            }
        };

        socket.onclose = function(event) {
            console.log('[WebSocketPlugin] Disconnected: ' + event.code);
            var callbacks = webSocketCallbacks[id];
            if (callbacks && callbacks.onClose) {
                dynCall_vii(callbacks.onClose, id, event.code);
            }
        };

        socket.onmessage = function(event) {
            var callbacks = webSocketCallbacks[id];
            if (callbacks) {
                if (typeof event.data === 'string') {
                    callbacks.messages.push(event.data);
                } else if (event.data instanceof ArrayBuffer) {
                    // Handle binary data
                    var bytes = new Uint8Array(event.data);
                    var str = '';
                    for (var i = 0; i < bytes.length; i++) {
                        str += String.fromCharCode(bytes[i]);
                    }
                    callbacks.messages.push(str);
                }

                if (callbacks.onMessage) {
                    dynCall_vi(callbacks.onMessage, id);
                }
            }
        };

        socket.onerror = function(event) {
            console.error('[WebSocketPlugin] Error');
            var callbacks = webSocketCallbacks[id];
            if (callbacks && callbacks.onError) {
                dynCall_vi(callbacks.onError, id);
            }
        };

        return id;
    },

    /**
     * Get WebSocket connection state
     * @param {number} instanceId - WebSocket instance ID
     * @returns {number} State: 0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED
     */
    WebSocketState: function(instanceId) {
        var socket = webSockets[instanceId];
        if (socket) {
            return socket.readyState;
        }
        return 3; // CLOSED
    },

    /**
     * Send message through WebSocket
     * @param {number} instanceId - WebSocket instance ID
     * @param {string} msgPtr - Pointer to message string
     */
    WebSocketSend: function(instanceId, msgPtr) {
        var socket = webSockets[instanceId];
        if (socket && socket.readyState === WebSocket.OPEN) {
            var msg = UTF8ToString(msgPtr);
            socket.send(msg);
        }
    },

    /**
     * Send binary data through WebSocket
     * @param {number} instanceId - WebSocket instance ID
     * @param {number} dataPtr - Pointer to data buffer
     * @param {number} length - Data length
     */
    WebSocketSendBinary: function(instanceId, dataPtr, length) {
        var socket = webSockets[instanceId];
        if (socket && socket.readyState === WebSocket.OPEN) {
            var data = new Uint8Array(HEAPU8.buffer, dataPtr, length);
            socket.send(data);
        }
    },

    /**
     * Get queued message count
     * @param {number} instanceId - WebSocket instance ID
     * @returns {number} Number of queued messages
     */
    WebSocketGetMessageCount: function(instanceId) {
        var callbacks = webSocketCallbacks[instanceId];
        if (callbacks) {
            return callbacks.messages.length;
        }
        return 0;
    },

    /**
     * Get next queued message
     * @param {number} instanceId - WebSocket instance ID
     * @param {number} bufferPtr - Pointer to output buffer
     * @param {number} bufferSize - Buffer size
     * @returns {number} Actual message length, or 0 if no message
     */
    WebSocketGetMessage: function(instanceId, bufferPtr, bufferSize) {
        var callbacks = webSocketCallbacks[instanceId];
        if (callbacks && callbacks.messages.length > 0) {
            var msg = callbacks.messages.shift();
            var msgLength = lengthBytesUTF8(msg) + 1;

            if (msgLength <= bufferSize) {
                stringToUTF8(msg, bufferPtr, bufferSize);
                return msgLength - 1;
            } else {
                // Message too long, truncate
                stringToUTF8(msg.substring(0, bufferSize - 1), bufferPtr, bufferSize);
                return bufferSize - 1;
            }
        }
        return 0;
    },

    /**
     * Set callback function pointers
     * @param {number} instanceId - WebSocket instance ID
     * @param {number} onOpen - Open callback function pointer
     * @param {number} onClose - Close callback function pointer
     * @param {number} onMessage - Message callback function pointer
     * @param {number} onError - Error callback function pointer
     */
    WebSocketSetCallbacks: function(instanceId, onOpen, onClose, onMessage, onError) {
        var callbacks = webSocketCallbacks[instanceId];
        if (callbacks) {
            callbacks.onOpen = onOpen;
            callbacks.onClose = onClose;
            callbacks.onMessage = onMessage;
            callbacks.onError = onError;
        }
    },

    /**
     * Close WebSocket connection
     * @param {number} instanceId - WebSocket instance ID
     */
    WebSocketClose: function(instanceId) {
        var socket = webSockets[instanceId];
        if (socket) {
            socket.close();
        }
    },

    /**
     * Destroy WebSocket instance
     * @param {number} instanceId - WebSocket instance ID
     */
    WebSocketDestroy: function(instanceId) {
        var socket = webSockets[instanceId];
        if (socket) {
            socket.close();
            delete webSockets[instanceId];
            delete webSocketCallbacks[instanceId];
        }
    }
};

autoAddDeps(WebSocketPlugin, '$webSockets');
autoAddDeps(WebSocketPlugin, '$webSocketCallbacks');
autoAddDeps(WebSocketPlugin, '$webSocketNextId');
mergeInto(LibraryManager.library, WebSocketPlugin);
