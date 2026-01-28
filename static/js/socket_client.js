/**
 * LEGO Factory v3 - WebSocket Client
 * ===================================
 * JavaScript client helper for Flask-SocketIO communication.
 *
 * Namespaces:
 * - /unity: Unity Digital Twin
 * - /dashboard: Web dashboard
 * - /alarms: Real-time alarms
 * - /tags: Tag value subscriptions
 *
 * Usage:
 *   const client = new LegoFactorySocket('/dashboard');
 *   await client.connect();
 *   client.subscribeTags(['tag1', 'tag2']);
 *   client.on('tag_value', (data) => console.log(data));
 */

class LegoFactorySocket {
    /**
     * Create a new WebSocket client.
     * @param {string} namespace - Socket.IO namespace (/unity, /dashboard, /alarms, /tags)
     * @param {object} options - Configuration options
     */
    constructor(namespace = '/', options = {}) {
        this.namespace = namespace;
        this.options = {
            url: options.url || window.location.origin,
            autoConnect: options.autoConnect !== false,
            reconnection: options.reconnection !== false,
            reconnectionAttempts: options.reconnectionAttempts || 5,
            reconnectionDelay: options.reconnectionDelay || 1000,
            reconnectionDelayMax: options.reconnectionDelayMax || 5000,
            timeout: options.timeout || 20000,
            auth: options.auth || {},
            ...options
        };

        this.socket = null;
        this.connected = false;
        this.reconnectAttempts = 0;
        this.eventHandlers = new Map();
        this.subscriptions = {
            tags: new Set(),
            entities: new Set(),
            priorities: new Set(),
            areas: new Set(),
            machines: new Set()
        };

        // Bind methods
        this._onConnect = this._onConnect.bind(this);
        this._onDisconnect = this._onDisconnect.bind(this);
        this._onError = this._onError.bind(this);
        this._onReconnect = this._onReconnect.bind(this);
        this._onReconnectError = this._onReconnectError.bind(this);
    }

    /**
     * Connect to the WebSocket server.
     * @returns {Promise} Resolves when connected
     */
    connect() {
        return new Promise((resolve, reject) => {
            if (this.connected) {
                resolve(this.socket);
                return;
            }

            try {
                // Check if Socket.IO is available
                if (typeof io === 'undefined') {
                    throw new Error('Socket.IO client library not loaded');
                }

                // Create socket connection
                this.socket = io(this.options.url + this.namespace, {
                    autoConnect: this.options.autoConnect,
                    reconnection: this.options.reconnection,
                    reconnectionAttempts: this.options.reconnectionAttempts,
                    reconnectionDelay: this.options.reconnectionDelay,
                    reconnectionDelayMax: this.options.reconnectionDelayMax,
                    timeout: this.options.timeout,
                    auth: this.options.auth,
                    transports: ['websocket', 'polling']
                });

                // Setup core event handlers
                this.socket.on('connect', () => {
                    this._onConnect();
                    resolve(this.socket);
                });

                this.socket.on('disconnect', this._onDisconnect);
                this.socket.on('connect_error', (error) => {
                    this._onError(error);
                    if (!this.connected) {
                        reject(error);
                    }
                });
                this.socket.on('reconnect', this._onReconnect);
                this.socket.on('reconnect_error', this._onReconnectError);

                // Setup connection acknowledgment handler
                this.socket.on('connection_ack', (data) => {
                    console.log(`[${this.namespace}] Connection acknowledged:`, data);
                    this._trigger('connection_ack', data);
                });

                // Setup error handler
                this.socket.on('error', (error) => {
                    console.error(`[${this.namespace}] Server error:`, error);
                    this._trigger('error', error);
                });

                // Connect if not auto-connecting
                if (!this.options.autoConnect) {
                    this.socket.connect();
                }

            } catch (error) {
                reject(error);
            }
        });
    }

    /**
     * Disconnect from the WebSocket server.
     */
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
            this.connected = false;
        }
    }

    /**
     * Register an event handler.
     * @param {string} event - Event name
     * @param {function} handler - Event handler function
     */
    on(event, handler) {
        if (!this.eventHandlers.has(event)) {
            this.eventHandlers.set(event, new Set());

            // Register with Socket.IO if connected
            if (this.socket) {
                this.socket.on(event, (data) => {
                    this._trigger(event, data);
                });
            }
        }

        this.eventHandlers.get(event).add(handler);
    }

    /**
     * Remove an event handler.
     * @param {string} event - Event name
     * @param {function} handler - Event handler function
     */
    off(event, handler) {
        if (this.eventHandlers.has(event)) {
            if (handler) {
                this.eventHandlers.get(event).delete(handler);
            } else {
                this.eventHandlers.delete(event);
            }
        }
    }

    /**
     * Emit an event to the server.
     * @param {string} event - Event name
     * @param {*} data - Event data
     * @param {function} callback - Optional acknowledgment callback
     */
    emit(event, data, callback) {
        if (!this.socket || !this.connected) {
            console.warn(`[${this.namespace}] Cannot emit: not connected`);
            return false;
        }

        if (callback) {
            this.socket.emit(event, data, callback);
        } else {
            this.socket.emit(event, data);
        }

        return true;
    }

    // ==================== Tag Subscriptions ====================

    /**
     * Subscribe to tag value updates.
     * @param {string|array} tagIds - Tag ID(s) to subscribe to
     * @param {object} options - Subscription options
     */
    subscribeTags(tagIds, options = {}) {
        if (!Array.isArray(tagIds)) {
            tagIds = [tagIds];
        }

        tagIds.forEach(id => this.subscriptions.tags.add(id));

        this.emit('subscribe_tags', {
            tag_ids: tagIds,
            tag_group: options.tagGroup,
            area: options.area,
            update_interval: options.updateInterval
        });
    }

    /**
     * Unsubscribe from tag value updates.
     * @param {string|array} tagIds - Tag ID(s) to unsubscribe from
     */
    unsubscribeTags(tagIds) {
        if (!Array.isArray(tagIds)) {
            tagIds = [tagIds];
        }

        tagIds.forEach(id => this.subscriptions.tags.delete(id));

        this.emit('unsubscribe_tags', {
            tag_ids: tagIds
        });
    }

    /**
     * Unsubscribe from all tags.
     */
    unsubscribeAllTags() {
        this.subscriptions.tags.clear();
        this.emit('unsubscribe_tags', { all: true });
    }

    /**
     * Write a value to a tag.
     * @param {string} tagId - Tag ID
     * @param {*} value - Value to write
     * @returns {Promise} Resolves with acknowledgment
     */
    writeTagValue(tagId, value) {
        return new Promise((resolve, reject) => {
            this.emit('write_value', { tag_id: tagId, value }, (response) => {
                if (response.success) {
                    resolve(response);
                } else {
                    reject(response);
                }
            });
        });
    }

    // ==================== Entity Subscriptions (Unity) ====================

    /**
     * Subscribe to entity updates.
     * @param {string|array} entityIds - Entity ID(s) to subscribe to
     * @param {object} options - Subscription options
     */
    subscribeEntities(entityIds, options = {}) {
        if (!Array.isArray(entityIds)) {
            entityIds = [entityIds];
        }

        entityIds.forEach(id => this.subscriptions.entities.add(id));

        this.emit('subscribe_entity', {
            entity_id: entityIds,
            include_children: options.includeChildren
        });
    }

    /**
     * Unsubscribe from entity updates.
     * @param {string|array} entityIds - Entity ID(s) to unsubscribe from
     */
    unsubscribeEntities(entityIds) {
        if (!Array.isArray(entityIds)) {
            entityIds = [entityIds];
        }

        entityIds.forEach(id => this.subscriptions.entities.delete(id));

        this.emit('unsubscribe_entity', {
            entity_id: entityIds
        });
    }

    /**
     * Request full state synchronization.
     * @param {object} options - Sync options
     */
    requestStateSync(options = {}) {
        this.emit('request_sync', {
            scene_id: options.sceneId,
            entity_types: options.entityTypes
        });
    }

    /**
     * Update an entity from the client side.
     * @param {string} entityId - Entity ID
     * @param {object} state - State updates
     * @param {object} transform - Transform updates
     */
    updateEntity(entityId, state = null, transform = null) {
        this.emit('update_entity', {
            entity_id: entityId,
            state,
            transform
        });
    }

    // ==================== Alarm Subscriptions ====================

    /**
     * Subscribe to alarms by priority level.
     * @param {array} priorities - Priority levels (1-5)
     */
    subscribePriorities(priorities) {
        if (!Array.isArray(priorities)) {
            priorities = [priorities];
        }

        priorities.forEach(p => this.subscriptions.priorities.add(p));

        this.emit('subscribe_priority', {
            priorities
        });
    }

    /**
     * Subscribe to alarms at or above a priority level.
     * @param {number} minPriority - Minimum priority (1 = emergency)
     */
    subscribeMinPriority(minPriority) {
        this.emit('subscribe_priority', {
            min_priority: minPriority
        });
    }

    /**
     * Subscribe to alarms in an area.
     * @param {string|array} areas - Area(s) to subscribe to
     */
    subscribeAlarmAreas(areas) {
        if (!Array.isArray(areas)) {
            areas = [areas];
        }

        areas.forEach(a => this.subscriptions.areas.add(a));

        this.emit('subscribe_area', {
            area: areas
        });
    }

    /**
     * Acknowledge an alarm.
     * @param {string} alarmId - Alarm ID to acknowledge
     * @param {string} notes - Optional notes
     * @returns {Promise} Resolves with acknowledgment
     */
    acknowledgeAlarm(alarmId, notes = null) {
        return new Promise((resolve, reject) => {
            const handler = (response) => {
                if (response.acknowledged) {
                    resolve(response);
                } else {
                    reject(response);
                }
                this.off('acknowledge_ack', handler);
            };

            this.on('acknowledge_ack', handler);
            this.emit('acknowledge_alarm', { alarm_id: alarmId, notes });
        });
    }

    /**
     * Acknowledge all active alarms.
     * @param {number} priority - Optional priority filter
     */
    acknowledgeAllAlarms(priority = null) {
        this.emit('acknowledge_all', { priority });
    }

    /**
     * Shelve an alarm.
     * @param {string} alarmId - Alarm ID
     * @param {number} durationMinutes - Shelve duration in minutes
     * @param {string} reason - Shelve reason
     */
    shelveAlarm(alarmId, durationMinutes, reason) {
        this.emit('shelve_alarm', {
            alarm_id: alarmId,
            duration_minutes: durationMinutes,
            reason
        });
    }

    /**
     * Request all active alarms.
     * @param {object} options - Query options
     */
    requestActiveAlarms(options = {}) {
        this.emit('request_active_alarms', {
            priority: options.priority,
            include_shelved: options.includeShelved
        });
    }

    // ==================== Machine Subscriptions ====================

    /**
     * Subscribe to machine status updates.
     * @param {string|array} machineIds - Machine ID(s)
     */
    subscribeMachines(machineIds) {
        if (!Array.isArray(machineIds)) {
            machineIds = [machineIds];
        }

        machineIds.forEach(id => this.subscriptions.machines.add(id));

        this.emit('subscribe_machine', {
            machine_id: machineIds
        });
    }

    // ==================== Dashboard Methods ====================

    /**
     * Request initial dashboard data.
     * @param {string} dashboardType - Dashboard type (scada, mes, oee, etc.)
     * @param {object} options - Query options
     */
    requestDashboardData(dashboardType, options = {}) {
        this.emit('request_dashboard_data', {
            dashboard_type: dashboardType,
            area: options.area
        });
    }

    /**
     * Join a room for targeted updates.
     * @param {string} room - Room name
     */
    joinRoom(room) {
        this.emit('join', { room });
    }

    /**
     * Leave a room.
     * @param {string} room - Room name
     */
    leaveRoom(room) {
        this.emit('leave', { room });
    }

    // ==================== Utility Methods ====================

    /**
     * Send a ping to the server.
     * @returns {Promise} Resolves with pong response
     */
    ping() {
        return new Promise((resolve) => {
            const start = Date.now();
            this.on('pong', (data) => {
                resolve({
                    ...data,
                    latency: Date.now() - start
                });
            });
            this.emit('ping');
        });
    }

    /**
     * Get connection statistics.
     */
    getStats() {
        this.emit('get_stats');
    }

    /**
     * Check if connected.
     * @returns {boolean}
     */
    isConnected() {
        return this.connected;
    }

    /**
     * Get current subscriptions.
     * @returns {object}
     */
    getSubscriptions() {
        return {
            tags: Array.from(this.subscriptions.tags),
            entities: Array.from(this.subscriptions.entities),
            priorities: Array.from(this.subscriptions.priorities),
            areas: Array.from(this.subscriptions.areas),
            machines: Array.from(this.subscriptions.machines)
        };
    }

    // ==================== Private Methods ====================

    _onConnect() {
        this.connected = true;
        this.reconnectAttempts = 0;
        console.log(`[${this.namespace}] Connected`);
        this._trigger('connected');

        // Re-register event handlers with socket
        this.eventHandlers.forEach((handlers, event) => {
            if (!['connected', 'disconnected', 'error', 'reconnected', 'connection_ack'].includes(event)) {
                this.socket.on(event, (data) => {
                    this._trigger(event, data);
                });
            }
        });

        // Resubscribe after reconnection
        this._resubscribe();
    }

    _onDisconnect(reason) {
        this.connected = false;
        console.log(`[${this.namespace}] Disconnected:`, reason);
        this._trigger('disconnected', { reason });
    }

    _onError(error) {
        console.error(`[${this.namespace}] Connection error:`, error);
        this._trigger('error', { error: error.message || error });
    }

    _onReconnect(attemptNumber) {
        console.log(`[${this.namespace}] Reconnected after ${attemptNumber} attempts`);
        this._trigger('reconnected', { attempts: attemptNumber });
    }

    _onReconnectError(error) {
        this.reconnectAttempts++;
        console.warn(`[${this.namespace}] Reconnection attempt ${this.reconnectAttempts} failed`);
        this._trigger('reconnect_error', {
            attempt: this.reconnectAttempts,
            error: error.message || error
        });
    }

    _trigger(event, data) {
        if (this.eventHandlers.has(event)) {
            this.eventHandlers.get(event).forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error(`[${this.namespace}] Error in event handler for ${event}:`, error);
                }
            });
        }
    }

    _resubscribe() {
        // Resubscribe to tags
        if (this.subscriptions.tags.size > 0) {
            this.emit('subscribe_tags', {
                tag_ids: Array.from(this.subscriptions.tags)
            });
        }

        // Resubscribe to entities
        if (this.subscriptions.entities.size > 0) {
            this.emit('subscribe_entity', {
                entity_id: Array.from(this.subscriptions.entities)
            });
        }

        // Resubscribe to priorities
        if (this.subscriptions.priorities.size > 0) {
            this.emit('subscribe_priority', {
                priorities: Array.from(this.subscriptions.priorities)
            });
        }

        // Resubscribe to areas
        if (this.subscriptions.areas.size > 0) {
            this.emit('subscribe_area', {
                area: Array.from(this.subscriptions.areas)
            });
        }

        // Resubscribe to machines
        if (this.subscriptions.machines.size > 0) {
            this.emit('subscribe_machine', {
                machine_id: Array.from(this.subscriptions.machines)
            });
        }
    }
}


/**
 * Factory function to create namespace-specific clients.
 */
const LegoFactory = {
    /**
     * Create a dashboard socket client.
     * @param {object} options - Configuration options
     * @returns {LegoFactorySocket}
     */
    dashboard(options = {}) {
        return new LegoFactorySocket('/dashboard', options);
    },

    /**
     * Create a Unity socket client.
     * @param {object} options - Configuration options
     * @returns {LegoFactorySocket}
     */
    unity(options = {}) {
        return new LegoFactorySocket('/unity', options);
    },

    /**
     * Create an alarms socket client.
     * @param {object} options - Configuration options
     * @returns {LegoFactorySocket}
     */
    alarms(options = {}) {
        return new LegoFactorySocket('/alarms', options);
    },

    /**
     * Create a tags socket client.
     * @param {object} options - Configuration options
     * @returns {LegoFactorySocket}
     */
    tags(options = {}) {
        return new LegoFactorySocket('/tags', options);
    }
};


// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { LegoFactorySocket, LegoFactory };
}

// Global export for browser
if (typeof window !== 'undefined') {
    window.LegoFactorySocket = LegoFactorySocket;
    window.LegoFactory = LegoFactory;
}
