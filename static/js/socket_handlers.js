/**
 * LEGO Factory WebSocket Handlers
 * ================================
 * WebSocket connection to Flask-SocketIO with event handlers
 * for real-time updates and reconnection logic.
 */

class SocketManager {
    constructor(options = {}) {
        this.socket = null;
        this.connected = false;
        this.reconnecting = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = options.maxReconnectAttempts || 10;
        this.reconnectDelay = options.reconnectDelay || 1000;
        this.maxReconnectDelay = options.maxReconnectDelay || 30000;

        // Event handlers by category
        this.handlers = {
            alarm: [],
            machine: [],
            workOrder: [],
            oee: [],
            downtime: [],
            production: [],
            system: [],
            custom: {},
        };

        // Connection status callbacks
        this.statusCallbacks = [];

        // Subscribed rooms/channels
        this.subscriptions = new Set();

        // Auto-connect unless disabled
        if (options.autoConnect !== false) {
            this.connect();
        }
    }

    // =========================================================================
    // Connection Management
    // =========================================================================

    /**
     * Connect to Socket.IO server
     * @param {string} url - Optional server URL
     */
    connect(url = null) {
        if (this.socket && this.socket.connected) {
            console.log('Socket already connected');
            return;
        }

        try {
            const socketOptions = {
                transports: ['websocket', 'polling'],
                reconnection: true,
                reconnectionAttempts: this.maxReconnectAttempts,
                reconnectionDelay: this.reconnectDelay,
                reconnectionDelayMax: this.maxReconnectDelay,
                timeout: 20000,
            };

            this.socket = url ? io(url, socketOptions) : io(socketOptions);
            this._setupConnectionHandlers();
            this._setupEventHandlers();

        } catch (error) {
            console.error('Failed to initialize Socket.IO:', error);
            this._notifyStatus('error', error.message);
        }
    }

    /**
     * Disconnect from server
     */
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
            this.connected = false;
            this.subscriptions.clear();
        }
    }

    /**
     * Check if connected
     * @returns {boolean}
     */
    isConnected() {
        return this.connected && this.socket?.connected;
    }

    /**
     * Set up connection event handlers
     */
    _setupConnectionHandlers() {
        this.socket.on('connect', () => {
            this.connected = true;
            this.reconnecting = false;
            this.reconnectAttempts = 0;
            console.log('[Socket] Connected to server');
            this._notifyStatus('connected');

            // Resubscribe to rooms
            this._resubscribe();
        });

        this.socket.on('disconnect', (reason) => {
            this.connected = false;
            console.log('[Socket] Disconnected:', reason);
            this._notifyStatus('disconnected', reason);

            // Handle specific disconnect reasons
            if (reason === 'io server disconnect') {
                // Server initiated disconnect, try to reconnect
                setTimeout(() => this.socket.connect(), this.reconnectDelay);
            }
        });

        this.socket.on('connect_error', (error) => {
            this.reconnectAttempts++;
            this.reconnecting = true;
            console.warn('[Socket] Connection error:', error.message);
            this._notifyStatus('reconnecting', {
                attempt: this.reconnectAttempts,
                maxAttempts: this.maxReconnectAttempts,
            });
        });

        this.socket.on('reconnect', (attemptNumber) => {
            console.log('[Socket] Reconnected after', attemptNumber, 'attempts');
            this.reconnecting = false;
            this._notifyStatus('connected');
        });

        this.socket.on('reconnect_failed', () => {
            console.error('[Socket] Reconnection failed');
            this.reconnecting = false;
            this._notifyStatus('failed');
        });
    }

    /**
     * Set up domain event handlers
     */
    _setupEventHandlers() {
        // -----------------------------------------------------------------
        // Alarm Events
        // -----------------------------------------------------------------
        this.socket.on('alarm_triggered', (data) => {
            console.log('[Socket] Alarm triggered:', data);
            this._dispatch('alarm', 'triggered', data);
        });

        this.socket.on('alarm_acknowledged', (data) => {
            console.log('[Socket] Alarm acknowledged:', data);
            this._dispatch('alarm', 'acknowledged', data);
        });

        this.socket.on('alarm_cleared', (data) => {
            console.log('[Socket] Alarm cleared:', data);
            this._dispatch('alarm', 'cleared', data);
        });

        this.socket.on('alarm_update', (data) => {
            this._dispatch('alarm', 'update', data);
        });

        // -----------------------------------------------------------------
        // Machine Events
        // -----------------------------------------------------------------
        this.socket.on('machine_status', (data) => {
            this._dispatch('machine', 'status', data);
        });

        this.socket.on('machine_connected', (data) => {
            console.log('[Socket] Machine connected:', data);
            this._dispatch('machine', 'connected', data);
        });

        this.socket.on('machine_disconnected', (data) => {
            console.log('[Socket] Machine disconnected:', data);
            this._dispatch('machine', 'disconnected', data);
        });

        this.socket.on('machine_position', (data) => {
            this._dispatch('machine', 'position', data);
        });

        this.socket.on('machine_state_change', (data) => {
            this._dispatch('machine', 'stateChange', data);
        });

        // -----------------------------------------------------------------
        // Work Order Events
        // -----------------------------------------------------------------
        this.socket.on('workorder_created', (data) => {
            console.log('[Socket] Work order created:', data);
            this._dispatch('workOrder', 'created', data);
        });

        this.socket.on('workorder_updated', (data) => {
            this._dispatch('workOrder', 'updated', data);
        });

        this.socket.on('workorder_status_changed', (data) => {
            console.log('[Socket] Work order status changed:', data);
            this._dispatch('workOrder', 'statusChanged', data);
        });

        this.socket.on('workorder_completed', (data) => {
            console.log('[Socket] Work order completed:', data);
            this._dispatch('workOrder', 'completed', data);
        });

        this.socket.on('mes:workorder_update', (data) => {
            this._dispatch('workOrder', 'update', data);
        });

        // -----------------------------------------------------------------
        // OEE Events
        // -----------------------------------------------------------------
        this.socket.on('oee_update', (data) => {
            this._dispatch('oee', 'update', data);
        });

        this.socket.on('oee:update', (data) => {
            this._dispatch('oee', 'update', data);
        });

        // -----------------------------------------------------------------
        // Downtime Events
        // -----------------------------------------------------------------
        this.socket.on('downtime_started', (data) => {
            console.log('[Socket] Downtime started:', data);
            this._dispatch('downtime', 'started', data);
        });

        this.socket.on('downtime_ended', (data) => {
            console.log('[Socket] Downtime ended:', data);
            this._dispatch('downtime', 'ended', data);
        });

        this.socket.on('downtime:event', (data) => {
            this._dispatch('downtime', 'event', data);
        });

        // -----------------------------------------------------------------
        // Production Events
        // -----------------------------------------------------------------
        this.socket.on('production_recorded', (data) => {
            this._dispatch('production', 'recorded', data);
        });

        this.socket.on('production_update', (data) => {
            this._dispatch('production', 'update', data);
        });

        // -----------------------------------------------------------------
        // System Events
        // -----------------------------------------------------------------
        this.socket.on('system_alert', (data) => {
            console.log('[Socket] System alert:', data);
            this._dispatch('system', 'alert', data);

            // Show toast for system alerts
            if (window.Toast) {
                const type = data.severity === 'error' ? 'error'
                    : data.severity === 'warning' ? 'warning'
                    : 'info';
                Toast.show(data.message, type);
            }
        });

        this.socket.on('system_notification', (data) => {
            this._dispatch('system', 'notification', data);
        });

        this.socket.on('system:event', (data) => {
            this._dispatch('system', 'event', data);
        });
    }

    /**
     * Dispatch event to registered handlers
     */
    _dispatch(category, eventType, data) {
        const eventData = { type: eventType, data, timestamp: new Date() };

        // Call category handlers
        this.handlers[category]?.forEach(handler => {
            try {
                handler(eventData);
            } catch (error) {
                console.error(`[Socket] Error in ${category} handler:`, error);
            }
        });

        // Call specific event handlers
        const customKey = `${category}:${eventType}`;
        this.handlers.custom[customKey]?.forEach(handler => {
            try {
                handler(data);
            } catch (error) {
                console.error(`[Socket] Error in ${customKey} handler:`, error);
            }
        });
    }

    /**
     * Notify connection status callbacks
     */
    _notifyStatus(status, details = null) {
        this.statusCallbacks.forEach(callback => {
            try {
                callback(status, details);
            } catch (error) {
                console.error('[Socket] Error in status callback:', error);
            }
        });
    }

    /**
     * Resubscribe to rooms after reconnection
     */
    _resubscribe() {
        this.subscriptions.forEach(room => {
            this.socket.emit('join', { room });
        });
    }

    // =========================================================================
    // Event Registration
    // =========================================================================

    /**
     * Register handler for alarm events
     * @param {Function} handler - Receives { type, data, timestamp }
     */
    onAlarm(handler) {
        this.handlers.alarm.push(handler);
        return () => this._removeHandler('alarm', handler);
    }

    /**
     * Register handler for machine events
     * @param {Function} handler
     */
    onMachine(handler) {
        this.handlers.machine.push(handler);
        return () => this._removeHandler('machine', handler);
    }

    /**
     * Register handler for work order events
     * @param {Function} handler
     */
    onWorkOrder(handler) {
        this.handlers.workOrder.push(handler);
        return () => this._removeHandler('workOrder', handler);
    }

    /**
     * Register handler for OEE events
     * @param {Function} handler
     */
    onOEE(handler) {
        this.handlers.oee.push(handler);
        return () => this._removeHandler('oee', handler);
    }

    /**
     * Register handler for downtime events
     * @param {Function} handler
     */
    onDowntime(handler) {
        this.handlers.downtime.push(handler);
        return () => this._removeHandler('downtime', handler);
    }

    /**
     * Register handler for production events
     * @param {Function} handler
     */
    onProduction(handler) {
        this.handlers.production.push(handler);
        return () => this._removeHandler('production', handler);
    }

    /**
     * Register handler for system events
     * @param {Function} handler
     */
    onSystem(handler) {
        this.handlers.system.push(handler);
        return () => this._removeHandler('system', handler);
    }

    /**
     * Register handler for specific event
     * @param {string} event - Event name (e.g., 'alarm:triggered', 'machine:status')
     * @param {Function} handler
     */
    on(event, handler) {
        if (!this.handlers.custom[event]) {
            this.handlers.custom[event] = [];
        }
        this.handlers.custom[event].push(handler);
        return () => this._removeCustomHandler(event, handler);
    }

    /**
     * Remove a handler
     */
    _removeHandler(category, handler) {
        const index = this.handlers[category].indexOf(handler);
        if (index > -1) {
            this.handlers[category].splice(index, 1);
        }
    }

    /**
     * Remove a custom handler
     */
    _removeCustomHandler(event, handler) {
        if (this.handlers.custom[event]) {
            const index = this.handlers.custom[event].indexOf(handler);
            if (index > -1) {
                this.handlers.custom[event].splice(index, 1);
            }
        }
    }

    /**
     * Register connection status handler
     * @param {Function} handler - Receives (status, details)
     */
    onStatusChange(handler) {
        this.statusCallbacks.push(handler);
        return () => {
            const index = this.statusCallbacks.indexOf(handler);
            if (index > -1) {
                this.statusCallbacks.splice(index, 1);
            }
        };
    }

    // =========================================================================
    // Room/Channel Management
    // =========================================================================

    /**
     * Subscribe to a room/channel
     * @param {string} room - Room name
     */
    subscribe(room) {
        this.subscriptions.add(room);
        if (this.isConnected()) {
            this.socket.emit('join', { room });
        }
    }

    /**
     * Unsubscribe from a room/channel
     * @param {string} room - Room name
     */
    unsubscribe(room) {
        this.subscriptions.delete(room);
        if (this.isConnected()) {
            this.socket.emit('leave', { room });
        }
    }

    /**
     * Subscribe to machine updates
     * @param {string} machineId
     */
    subscribeMachine(machineId) {
        this.subscribe(`machine:${machineId}`);
    }

    /**
     * Unsubscribe from machine updates
     * @param {string} machineId
     */
    unsubscribeMachine(machineId) {
        this.unsubscribe(`machine:${machineId}`);
    }

    /**
     * Subscribe to alarm updates
     */
    subscribeAlarms() {
        this.subscribe('alarms');
    }

    /**
     * Subscribe to OEE updates
     * @param {string} machineId - Optional specific machine
     */
    subscribeOEE(machineId = null) {
        this.subscribe(machineId ? `oee:${machineId}` : 'oee');
    }

    // =========================================================================
    // Emit Events
    // =========================================================================

    /**
     * Emit event to server
     * @param {string} event - Event name
     * @param {Object} data - Event data
     */
    emit(event, data = {}) {
        if (this.isConnected()) {
            this.socket.emit(event, data);
        } else {
            console.warn('[Socket] Cannot emit - not connected');
        }
    }

    /**
     * Request data refresh
     * @param {string} dataType - Type of data to refresh
     */
    requestRefresh(dataType) {
        this.emit('request_refresh', { type: dataType });
    }
}

// =============================================================================
// Connection Status Indicator
// =============================================================================

class ConnectionIndicator {
    constructor(socketManager, options = {}) {
        this.socketManager = socketManager;
        this.element = null;
        this.options = {
            position: options.position || 'bottom-right',
            showText: options.showText !== false,
            ...options,
        };

        this._create();
        this._bindEvents();
    }

    /**
     * Create the indicator element
     */
    _create() {
        this.element = document.createElement('div');
        this.element.className = 'socket-connection-indicator';

        const positions = {
            'bottom-right': 'bottom: 20px; right: 20px;',
            'bottom-left': 'bottom: 20px; left: 20px;',
            'top-right': 'top: 80px; right: 20px;',
            'top-left': 'top: 80px; left: 20px;',
        };

        this.element.style.cssText = `
            position: fixed;
            ${positions[this.options.position] || positions['bottom-right']}
            background: rgba(30, 41, 59, 0.95);
            padding: 8px 16px;
            border-radius: 20px;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
            color: #94a3b8;
            z-index: 9999;
            transition: all 0.3s ease;
            cursor: pointer;
            user-select: none;
        `;

        this.element.innerHTML = `
            <span class="indicator-dot"></span>
            ${this.options.showText ? '<span class="indicator-text">Connecting...</span>' : ''}
        `;

        const dot = this.element.querySelector('.indicator-dot');
        dot.style.cssText = `
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #f59e0b;
            transition: all 0.3s ease;
        `;

        document.body.appendChild(this.element);

        // Click to show connection details
        this.element.addEventListener('click', () => this._showDetails());
    }

    /**
     * Bind socket manager events
     */
    _bindEvents() {
        this.socketManager.onStatusChange((status, details) => {
            this._updateStatus(status, details);
        });
    }

    /**
     * Update status display
     */
    _updateStatus(status, details) {
        const dot = this.element.querySelector('.indicator-dot');
        const text = this.element.querySelector('.indicator-text');

        const states = {
            connected: { color: '#10b981', shadow: '0 0 8px #10b981', text: 'Live' },
            disconnected: { color: '#ef4444', shadow: 'none', text: 'Disconnected' },
            reconnecting: { color: '#f59e0b', shadow: 'none', text: `Reconnecting (${details?.attempt || 0}/${details?.maxAttempts || 10})` },
            failed: { color: '#ef4444', shadow: 'none', text: 'Connection Failed' },
            error: { color: '#ef4444', shadow: 'none', text: 'Error' },
        };

        const state = states[status] || states.disconnected;
        dot.style.background = state.color;
        dot.style.boxShadow = state.shadow;

        if (text) {
            text.textContent = state.text;
        }
    }

    /**
     * Show connection details popup
     */
    _showDetails() {
        const connected = this.socketManager.isConnected();
        const subscriptions = Array.from(this.socketManager.subscriptions);

        let detailsHtml = `
            <div style="padding: 15px; min-width: 200px;">
                <h6 style="margin-bottom: 10px; color: ${connected ? '#10b981' : '#ef4444'}">
                    ${connected ? 'Connected' : 'Disconnected'}
                </h6>
                <p style="margin-bottom: 5px; font-size: 12px; color: #94a3b8;">
                    Reconnect attempts: ${this.socketManager.reconnectAttempts}
                </p>
        `;

        if (subscriptions.length > 0) {
            detailsHtml += `
                <p style="margin-bottom: 5px; font-size: 12px; color: #94a3b8;">
                    Subscriptions:
                </p>
                <ul style="margin: 0; padding-left: 20px; font-size: 11px; color: #64748b;">
                    ${subscriptions.map(s => `<li>${s}</li>`).join('')}
                </ul>
            `;
        }

        detailsHtml += '</div>';

        // Show as tooltip or modal
        if (window.Toast) {
            Toast.info(connected ? 'WebSocket connected' : 'WebSocket disconnected');
        }
    }

    /**
     * Remove indicator
     */
    destroy() {
        if (this.element) {
            this.element.remove();
        }
    }

    /**
     * Show indicator
     */
    show() {
        if (this.element) {
            this.element.style.display = 'flex';
        }
    }

    /**
     * Hide indicator
     */
    hide() {
        if (this.element) {
            this.element.style.display = 'none';
        }
    }
}

// =============================================================================
// Dashboard-Specific Socket Handlers
// =============================================================================

/**
 * Alarm Dashboard Socket Handler
 */
class AlarmSocketHandler {
    constructor(socketManager, options = {}) {
        this.socketManager = socketManager;
        this.options = options;

        // Callbacks
        this.onNewAlarm = options.onNewAlarm || (() => {});
        this.onAlarmAcknowledged = options.onAlarmAcknowledged || (() => {});
        this.onAlarmCleared = options.onAlarmCleared || (() => {});
        this.onSummaryUpdate = options.onSummaryUpdate || (() => {});

        this._init();
    }

    _init() {
        this.socketManager.subscribeAlarms();

        this.socketManager.onAlarm((event) => {
            switch (event.type) {
                case 'triggered':
                    this.onNewAlarm(event.data);
                    if (window.Toast) {
                        Toast.warning(`New Alarm: ${event.data.message}`);
                    }
                    break;
                case 'acknowledged':
                    this.onAlarmAcknowledged(event.data);
                    break;
                case 'cleared':
                    this.onAlarmCleared(event.data);
                    break;
                case 'update':
                    this.onSummaryUpdate(event.data);
                    break;
            }
        });
    }
}

/**
 * Machine Dashboard Socket Handler
 */
class MachineSocketHandler {
    constructor(socketManager, options = {}) {
        this.socketManager = socketManager;
        this.options = options;
        this.subscribedMachines = new Set();

        // Callbacks
        this.onStatusUpdate = options.onStatusUpdate || (() => {});
        this.onPositionUpdate = options.onPositionUpdate || (() => {});
        this.onConnectionChange = options.onConnectionChange || (() => {});
        this.onStateChange = options.onStateChange || (() => {});

        this._init();
    }

    _init() {
        this.socketManager.onMachine((event) => {
            switch (event.type) {
                case 'status':
                    this.onStatusUpdate(event.data);
                    break;
                case 'position':
                    this.onPositionUpdate(event.data);
                    break;
                case 'connected':
                    this.onConnectionChange(event.data.machine_id, true);
                    break;
                case 'disconnected':
                    this.onConnectionChange(event.data.machine_id, false);
                    break;
                case 'stateChange':
                    this.onStateChange(event.data);
                    break;
            }
        });
    }

    /**
     * Subscribe to specific machine
     * @param {string} machineId
     */
    subscribeMachine(machineId) {
        this.subscribedMachines.add(machineId);
        this.socketManager.subscribeMachine(machineId);
    }

    /**
     * Unsubscribe from machine
     * @param {string} machineId
     */
    unsubscribeMachine(machineId) {
        this.subscribedMachines.delete(machineId);
        this.socketManager.unsubscribeMachine(machineId);
    }

    /**
     * Subscribe to all machines
     * @param {Array<string>} machineIds
     */
    subscribeAll(machineIds) {
        machineIds.forEach(id => this.subscribeMachine(id));
    }
}

/**
 * OEE Dashboard Socket Handler
 */
class OEESocketHandler {
    constructor(socketManager, options = {}) {
        this.socketManager = socketManager;
        this.options = options;

        // Callbacks
        this.onOEEUpdate = options.onOEEUpdate || (() => {});
        this.onDowntimeStart = options.onDowntimeStart || (() => {});
        this.onDowntimeEnd = options.onDowntimeEnd || (() => {});

        this._init();
    }

    _init() {
        this.socketManager.subscribeOEE();

        this.socketManager.onOEE((event) => {
            if (event.type === 'update') {
                this.onOEEUpdate(event.data);
            }
        });

        this.socketManager.onDowntime((event) => {
            switch (event.type) {
                case 'started':
                    this.onDowntimeStart(event.data);
                    if (window.Toast) {
                        Toast.warning(`Machine Down: ${event.data.machine_id}`);
                    }
                    break;
                case 'ended':
                    this.onDowntimeEnd(event.data);
                    if (window.Toast) {
                        Toast.success(`Machine Up: ${event.data.machine_id}`);
                    }
                    break;
                case 'event':
                    if (event.data.event_type === 'started') {
                        this.onDowntimeStart(event.data);
                    } else {
                        this.onDowntimeEnd(event.data);
                    }
                    break;
            }
        });
    }
}

/**
 * Work Order Dashboard Socket Handler
 */
class WorkOrderSocketHandler {
    constructor(socketManager, options = {}) {
        this.socketManager = socketManager;
        this.options = options;

        // Callbacks
        this.onCreated = options.onCreated || (() => {});
        this.onUpdated = options.onUpdated || (() => {});
        this.onStatusChanged = options.onStatusChanged || (() => {});
        this.onCompleted = options.onCompleted || (() => {});

        this._init();
    }

    _init() {
        this.socketManager.subscribe('workorders');

        this.socketManager.onWorkOrder((event) => {
            switch (event.type) {
                case 'created':
                    this.onCreated(event.data);
                    if (window.Toast) {
                        Toast.info(`New Work Order: ${event.data.wo_number}`);
                    }
                    break;
                case 'updated':
                case 'update':
                    this.onUpdated(event.data);
                    break;
                case 'statusChanged':
                    this.onStatusChanged(event.data);
                    break;
                case 'completed':
                    this.onCompleted(event.data);
                    if (window.Toast) {
                        Toast.success(`Work Order Completed: ${event.data.wo_number}`);
                    }
                    break;
            }
        });
    }
}

// =============================================================================
// Global Socket Instance
// =============================================================================

// Create global socket manager instance
const socketManager = new SocketManager({ autoConnect: true });

// Create connection indicator (can be enabled per page)
let connectionIndicator = null;

function showConnectionIndicator(options = {}) {
    if (!connectionIndicator) {
        connectionIndicator = new ConnectionIndicator(socketManager, options);
    }
    connectionIndicator.show();
    return connectionIndicator;
}

function hideConnectionIndicator() {
    if (connectionIndicator) {
        connectionIndicator.hide();
    }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        SocketManager,
        ConnectionIndicator,
        AlarmSocketHandler,
        MachineSocketHandler,
        OEESocketHandler,
        WorkOrderSocketHandler,
        socketManager,
        showConnectionIndicator,
        hideConnectionIndicator,
    };
}
