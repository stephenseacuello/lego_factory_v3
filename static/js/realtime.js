/**
 * Flask CNC SCADA Real-time WebSocket Helper
 * =============================================
 * Provides easy-to-use Socket.IO connection and event handling
 * for all dashboard pages.
 *
 * Usage:
 *   const rt = new CNCRealtime();
 *   rt.on('tinyg:status', (data) => { ... });
 *   rt.on('oee:update', (data) => { ... });
 */

class CNCRealtime {
    constructor(options = {}) {
        this.socket = null;
        this.connected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = options.maxReconnectAttempts || 10;
        this.reconnectDelay = options.reconnectDelay || 1000;
        this.handlers = {};
        this.statusCallbacks = [];

        // Auto-connect unless disabled
        if (options.autoConnect !== false) {
            this.connect();
        }
    }

    /**
     * Connect to Socket.IO server
     */
    connect() {
        if (this.socket && this.socket.connected) {
            return;
        }

        try {
            this.socket = io({
                transports: ['websocket', 'polling'],
                reconnection: true,
                reconnectionAttempts: this.maxReconnectAttempts,
                reconnectionDelay: this.reconnectDelay
            });

            this._setupCoreHandlers();
            this._registerStoredHandlers();
        } catch (error) {
            console.error('Failed to initialize Socket.IO:', error);
        }
    }

    /**
     * Set up core connection handlers
     */
    _setupCoreHandlers() {
        this.socket.on('connect', () => {
            this.connected = true;
            this.reconnectAttempts = 0;
            console.log('🔌 Connected to CNC SCADA real-time server');
            this._notifyStatus('connected');
        });

        this.socket.on('disconnect', (reason) => {
            this.connected = false;
            console.log('🔌 Disconnected:', reason);
            this._notifyStatus('disconnected', reason);
        });

        this.socket.on('connect_error', (error) => {
            this.reconnectAttempts++;
            console.warn('Connection error:', error.message);
            this._notifyStatus('error', error.message);
        });

        this.socket.on('system:event', (data) => {
            console.log('System event:', data);
        });

        this.socket.on('system:alert', (data) => {
            this._showAlert(data);
        });
    }

    /**
     * Register event handlers that were added before connection
     */
    _registerStoredHandlers() {
        Object.entries(this.handlers).forEach(([event, callbacks]) => {
            callbacks.forEach(callback => {
                this.socket.on(event, callback);
            });
        });
    }

    /**
     * Subscribe to a Socket.IO event
     * @param {string} event - Event name (e.g., 'tinyg:status', 'oee:update')
     * @param {function} callback - Handler function
     */
    on(event, callback) {
        if (!this.handlers[event]) {
            this.handlers[event] = [];
        }
        this.handlers[event].push(callback);

        if (this.socket) {
            this.socket.on(event, callback);
        }

        return this; // Allow chaining
    }

    /**
     * Unsubscribe from a Socket.IO event
     * @param {string} event - Event name
     * @param {function} callback - Handler to remove (optional, removes all if not provided)
     */
    off(event, callback) {
        if (this.socket) {
            this.socket.off(event, callback);
        }

        if (callback && this.handlers[event]) {
            this.handlers[event] = this.handlers[event].filter(h => h !== callback);
        } else {
            delete this.handlers[event];
        }

        return this;
    }

    /**
     * Emit an event to the server
     * @param {string} event - Event name
     * @param {object} data - Event data
     */
    emit(event, data) {
        if (this.socket && this.connected) {
            this.socket.emit(event, data);
        } else {
            console.warn('Cannot emit - not connected');
        }
    }

    /**
     * Subscribe to a channel for filtered updates
     * @param {string} channel - Channel name
     */
    subscribe(channel) {
        this.emit('subscribe', { channel });
    }

    /**
     * Request current status from server
     */
    requestStatus() {
        this.emit('request:status');
    }

    /**
     * Join a Unity/factory room for targeted updates
     * @param {string} roomType - Room type ('unity', 'factory', 'robot', 'bantam')
     * @param {string} id - Machine/cell/robot ID
     */
    joinRoom(roomType, id) {
        this.emit(`${roomType}:join`, { [`${roomType === 'factory' ? 'cell_id' : 'machine_id'}`]: id });
    }

    /**
     * Leave a room
     * @param {string} roomType - Room type
     * @param {string} id - ID
     */
    leaveRoom(roomType, id) {
        this.emit(`${roomType}:leave`, { [`${roomType === 'factory' ? 'cell_id' : 'machine_id'}`]: id });
    }

    /**
     * Register a connection status callback
     * @param {function} callback - Called with (status, details)
     */
    onStatus(callback) {
        this.statusCallbacks.push(callback);
        return this;
    }

    /**
     * Notify status callbacks
     */
    _notifyStatus(status, details = null) {
        this.statusCallbacks.forEach(cb => cb(status, details));
    }

    /**
     * Show system alert (can be overridden)
     */
    _showAlert(data) {
        const { type, message, severity } = data;
        console.log(`[${severity.toUpperCase()}] ${type}: ${message}`);

        // Try to show toast notification if available
        if (window.showToast) {
            window.showToast(message, severity);
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
        }
    }

    /**
     * Check if connected
     * @returns {boolean}
     */
    isConnected() {
        return this.connected && this.socket && this.socket.connected;
    }
}

// =============================================================================
// MES Dashboard Helper
// =============================================================================

class MESRealtime extends CNCRealtime {
    constructor(options = {}) {
        super(options);
        this._setupMESHandlers();
    }

    _setupMESHandlers() {
        // Work order updates
        this.on('mes:workorder_update', (data) => {
            if (this.onWorkOrderUpdate) {
                this.onWorkOrderUpdate(data);
            }
        });

        // Labor updates
        this.on('mes:labor_update', (data) => {
            if (this.onLaborUpdate) {
                this.onLaborUpdate(data);
            }
        });

        // Dispatch updates
        this.on('dispatch:update', (data) => {
            if (this.onDispatchUpdate) {
                this.onDispatchUpdate(data);
            }
        });
    }

    /**
     * Set work order update handler
     */
    setWorkOrderHandler(handler) {
        this.onWorkOrderUpdate = handler;
        return this;
    }

    /**
     * Set labor update handler
     */
    setLaborHandler(handler) {
        this.onLaborUpdate = handler;
        return this;
    }

    /**
     * Set dispatch update handler
     */
    setDispatchHandler(handler) {
        this.onDispatchUpdate = handler;
        return this;
    }
}

// =============================================================================
// OEE Dashboard Helper
// =============================================================================

class OEERealtime extends CNCRealtime {
    constructor(options = {}) {
        super(options);
        this._setupOEEHandlers();
    }

    _setupOEEHandlers() {
        this.on('oee:update', (data) => {
            if (this.onOEEUpdate) {
                this.onOEEUpdate(data);
            }
        });

        this.on('downtime:event', (data) => {
            if (this.onDowntimeEvent) {
                this.onDowntimeEvent(data);
            }
        });
    }

    setOEEHandler(handler) {
        this.onOEEUpdate = handler;
        return this;
    }

    setDowntimeHandler(handler) {
        this.onDowntimeEvent = handler;
        return this;
    }
}

// =============================================================================
// Quality Dashboard Helper
// =============================================================================

class QualityRealtime extends CNCRealtime {
    constructor(options = {}) {
        super(options);
        this._setupQualityHandlers();
    }

    _setupQualityHandlers() {
        this.on('quality:alert', (data) => {
            if (this.onQualityAlert) {
                this.onQualityAlert(data);
            }
        });

        this.on('inspection:result', (data) => {
            if (this.onInspectionResult) {
                this.onInspectionResult(data);
            }
        });
    }

    setQualityAlertHandler(handler) {
        this.onQualityAlert = handler;
        return this;
    }

    setInspectionHandler(handler) {
        this.onInspectionResult = handler;
        return this;
    }
}

// =============================================================================
// Portal Dashboard Helper
// =============================================================================

class PortalRealtime extends CNCRealtime {
    constructor(options = {}) {
        super(options);
        this._setupPortalHandlers();
    }

    _setupPortalHandlers() {
        this.on('portal:stats', (data) => {
            if (this.onStatsUpdate) {
                this.onStatsUpdate(data);
            }
        });

        // Listen to all relevant events for dashboard stats
        this.on('mes:workorder_update', () => this._requestStatsRefresh());
        this.on('mes:labor_update', () => this._requestStatsRefresh());
        this.on('downtime:event', () => this._requestStatsRefresh());
        this.on('oee:update', () => this._requestStatsRefresh());
    }

    _requestStatsRefresh() {
        // Debounce stats refresh
        if (this._refreshTimeout) {
            clearTimeout(this._refreshTimeout);
        }
        this._refreshTimeout = setTimeout(() => {
            if (this.onStatsRefreshNeeded) {
                this.onStatsRefreshNeeded();
            }
        }, 500);
    }

    setStatsHandler(handler) {
        this.onStatsUpdate = handler;
        return this;
    }

    setRefreshHandler(handler) {
        this.onStatsRefreshNeeded = handler;
        return this;
    }
}

// =============================================================================
// Digital Twin Helper
// =============================================================================

class DigitalTwinRealtime extends CNCRealtime {
    constructor(machineId, options = {}) {
        super(options);
        this.machineId = machineId;
        this._setupDigitalTwinHandlers();
    }

    _setupDigitalTwinHandlers() {
        // Join Unity room for this machine
        this.onStatus((status) => {
            if (status === 'connected') {
                this.joinRoom('unity', this.machineId);
            }
        });

        this.on('iso23247:state', (data) => {
            if (data.machine_id === this.machineId && this.onStateUpdate) {
                this.onStateUpdate(data);
            }
        });

        this.on('unity:position', (data) => {
            if (data.machine_id === this.machineId && this.onPositionUpdate) {
                this.onPositionUpdate(data);
            }
        });

        this.on('unity:kinematics', (data) => {
            if (data.machine_id === this.machineId && this.onKinematicsUpdate) {
                this.onKinematicsUpdate(data);
            }
        });

        this.on('machine:state_change', (data) => {
            if (data.machine_id === this.machineId && this.onMachineStateChange) {
                this.onMachineStateChange(data);
            }
        });
    }

    setStateHandler(handler) {
        this.onStateUpdate = handler;
        return this;
    }

    setPositionHandler(handler) {
        this.onPositionUpdate = handler;
        return this;
    }

    setKinematicsHandler(handler) {
        this.onKinematicsUpdate = handler;
        return this;
    }

    setMachineStateHandler(handler) {
        this.onMachineStateChange = handler;
        return this;
    }

    requestCurrentState() {
        this.emit('unity:request_state', { machine_id: this.machineId });
    }
}

// =============================================================================
// Sensor Dashboard Helper
// =============================================================================

class SensorRealtime extends CNCRealtime {
    constructor(options = {}) {
        super(options);
        this._setupSensorHandlers();
    }

    _setupSensorHandlers() {
        this.on('sensor:dashboard', (data) => {
            if (this.onDashboardUpdate) {
                this.onDashboardUpdate(data);
            }
        });

        this.on('sensor:data', (data) => {
            if (this.onSensorData) {
                this.onSensorData(data);
            }
        });

        this.on('sensor:health', (data) => {
            if (this.onHealthUpdate) {
                this.onHealthUpdate(data);
            }
        });

        this.on('sensor:alert', (data) => {
            if (this.onSensorAlert) {
                this.onSensorAlert(data);
            }
        });
    }

    setDashboardHandler(handler) {
        this.onDashboardUpdate = handler;
        return this;
    }

    setSensorDataHandler(handler) {
        this.onSensorData = handler;
        return this;
    }

    setHealthHandler(handler) {
        this.onHealthUpdate = handler;
        return this;
    }

    setAlertHandler(handler) {
        this.onSensorAlert = handler;
        return this;
    }
}

// =============================================================================
// Connection Status UI Helper
// =============================================================================

function createConnectionIndicator(rt) {
    const indicator = document.createElement('div');
    indicator.className = 'connection-indicator';
    indicator.innerHTML = `
        <span class="connection-dot"></span>
        <span class="connection-text">Connecting...</span>
    `;
    indicator.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
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
    `;

    const dot = indicator.querySelector('.connection-dot');
    dot.style.cssText = `
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #f59e0b;
        transition: all 0.3s ease;
    `;

    const text = indicator.querySelector('.connection-text');

    rt.onStatus((status) => {
        switch (status) {
            case 'connected':
                dot.style.background = '#10b981';
                dot.style.boxShadow = '0 0 8px #10b981';
                text.textContent = 'Live';
                break;
            case 'disconnected':
                dot.style.background = '#ef4444';
                dot.style.boxShadow = 'none';
                text.textContent = 'Disconnected';
                break;
            case 'error':
                dot.style.background = '#f59e0b';
                dot.style.boxShadow = 'none';
                text.textContent = 'Reconnecting...';
                break;
        }
    });

    document.body.appendChild(indicator);
    return indicator;
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        CNCRealtime,
        MESRealtime,
        OEERealtime,
        QualityRealtime,
        PortalRealtime,
        DigitalTwinRealtime,
        SensorRealtime,
        createConnectionIndicator
    };
}
