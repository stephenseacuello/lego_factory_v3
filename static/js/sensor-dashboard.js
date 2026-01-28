/**
 * Sensor Dashboard JavaScript
 * ===========================
 * Real-time sensor visualization using Socket.IO and Plotly.js
 * for 18-modality Arduino Nano 33 BLE Sense dashboard.
 */

// =============================================================================
// Configuration
// =============================================================================

const CONFIG = {
    BUFFER_SIZE: 300,           // ~5 minutes at 1Hz display rate
    UPDATE_INTERVAL: 500,       // Chart update interval (ms)
    OFFLINE_THRESHOLD: 30000,   // 30 seconds = offline
    CHART_HISTORY: 300,         // Points to show in waveform chart
    API_BASE: '/api/sensors'
};

// Category definitions
const CATEGORIES = {
    IMU: {
        modalities: ['Ax', 'Ay', 'Az', 'Gx', 'Gy', 'Gz', 'Mx', 'My', 'Mz'],
        units: { A: 'g', G: '°/s', M: 'µT' },
        colors: ['#3b82f6', '#60a5fa', '#93c5fd', '#10b981', '#34d399', '#6ee7b7', '#f59e0b', '#fbbf24', '#fcd34d']
    },
    Environmental: {
        modalities: ['Temperature', 'Pressure'],
        units: { Temperature: '°C', Pressure: 'hPa' },
        colors: ['#10b981', '#f59e0b']
    },
    Proximity: {
        modalities: ['Proximity', 'Gesture'],
        units: { Proximity: 'cm', Gesture: '' },
        colors: ['#8b5cf6', '#a78bfa']
    },
    Color: {
        modalities: ['ColorR', 'ColorG', 'ColorB', 'ColorA'],
        units: { ColorR: '', ColorG: '', ColorB: '', ColorA: '' },
        colors: ['#ef4444', '#22c55e', '#3b82f6', '#6b7280']
    },
    Audio: {
        modalities: ['RMS'],
        units: { RMS: '' },
        colors: ['#ef4444']
    }
};

// =============================================================================
// State Management
// =============================================================================

const state = {
    socket: null,
    sensors: {},           // sensor_id -> { category, values, status, lastSeen }
    chartData: {},         // modality -> array of {x, y} points
    chartPaused: false,
    currentChartCategory: 'IMU',
    adminTab: 'pending',
    initialized: false,
    // History mode state
    historyMode: false,
    sessions: [],
    currentSession: null,
    sessionData: null,
    playbackIndex: 0,
    playbackSpeed: 1,
    playbackTimer: null,
    isPlaying: false,
    compareMode: false,
    selectedSessions: []
};

// =============================================================================
// Socket.IO Connection
// =============================================================================

function initSocketIO() {
    state.socket = io({
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionAttempts: 10
    });

    state.socket.on('connect', () => {
        console.log('[Sensor Dashboard] Connected to WebSocket');
        state.socket.emit('subscribe', { channel: 'sensors' });
    });

    state.socket.on('disconnect', () => {
        console.log('[Sensor Dashboard] Disconnected from WebSocket');
    });

    // Real-time sensor data
    state.socket.on('sensor:dashboard', (data) => {
        handleSensorDashboardUpdate(data);
    });

    // Health summary updates
    state.socket.on('sensor:health', (data) => {
        updateHealthDisplay(data);
    });

    // New sensor registered
    state.socket.on('sensor:registered', (data) => {
        console.log('[Sensor Dashboard] New sensor registered:', data);
        showNotification(`New sensor detected: ${data.sensor_id}`, 'info');
        loadSensorRegistry();
    });

    // Sensor alerts
    state.socket.on('sensor:alert', (data) => {
        showNotification(data.message, data.severity);
    });

    // Individual sensor data (high frequency)
    state.socket.on('sensor:data', (data) => {
        handleSensorData(data);
    });

    // Aggregated sensor data
    state.socket.on('sensor:all', (data) => {
        if (data.sensors) {
            data.sensors.forEach(sensor => handleSensorData(sensor));
        }
    });
}

// =============================================================================
// Data Handlers
// =============================================================================

function handleSensorDashboardUpdate(data) {
    if (!data || !data.sensors) return;

    data.sensors.forEach(sensor => {
        const sensorId = sensor.sensor_id || sensor.id;
        state.sensors[sensorId] = {
            ...state.sensors[sensorId],
            ...sensor,
            lastSeen: Date.now()
        };
    });

    updateSensorDisplay();
    updateChartData();
}

function handleSensorData(data) {
    const sensorId = data.sensor_id;
    if (!sensorId) return;

    // Infer category from modality names
    const category = inferCategory(data);

    state.sensors[sensorId] = {
        ...state.sensors[sensorId],
        sensor_id: sensorId,
        category: category,
        values: data,
        status: 'online',
        lastSeen: Date.now()
    };

    // Add to chart data buffer
    addToChartBuffer(data);

    // Throttled display update
    throttledDisplayUpdate();
}

function inferCategory(data) {
    const keys = Object.keys(data);
    for (const key of keys) {
        if (['Ax', 'Ay', 'Az', 'Gx', 'Gy', 'Gz', 'Mx', 'My', 'Mz'].includes(key)) return 'IMU';
        if (['Temperature', 'Pressure'].includes(key)) return 'Environmental';
        if (['Proximity', 'Gesture'].includes(key)) return 'Proximity';
        if (key.startsWith('Color')) return 'Color';
        if (key === 'RMS') return 'Audio';
    }
    return 'Unknown';
}

function addToChartBuffer(data) {
    const timestamp = Date.now();

    Object.entries(data).forEach(([key, value]) => {
        if (typeof value === 'number' && !['sensor_id', 'timestamp'].includes(key)) {
            if (!state.chartData[key]) {
                state.chartData[key] = [];
            }
            state.chartData[key].push({ x: timestamp, y: value });

            // Trim to buffer size
            if (state.chartData[key].length > CONFIG.BUFFER_SIZE) {
                state.chartData[key].shift();
            }
        }
    });
}

// =============================================================================
// Display Updates
// =============================================================================

let displayUpdateTimer = null;

function throttledDisplayUpdate() {
    if (displayUpdateTimer) return;
    displayUpdateTimer = setTimeout(() => {
        updateSensorDisplay();
        displayUpdateTimer = null;
    }, 100);
}

function updateSensorDisplay() {
    const categories = ['IMU', 'Environmental', 'Proximity', 'Color', 'Audio'];

    categories.forEach(category => {
        const container = document.getElementById(`sensors-${category.toLowerCase()}`);
        if (!container) return;

        const sensors = Object.values(state.sensors).filter(s => s.category === category);
        const badge = document.querySelector(`[data-category="${category}"] .category-badge`);

        if (badge) {
            badge.textContent = `${sensors.length} sensor${sensors.length !== 1 ? 's' : ''}`;
        }

        if (sensors.length === 0) {
            container.innerHTML = '<div class="sensor-placeholder">No sensors detected</div>';
            return;
        }

        container.innerHTML = sensors.map(sensor => renderSensorItem(sensor)).join('');
    });

    updateHealthCounts();
}

function renderSensorItem(sensor) {
    const status = getSensorStatus(sensor);
    const values = sensor.values || {};

    // Get modality values for display
    const displayValues = Object.entries(values)
        .filter(([key]) => !['sensor_id', 'timestamp', 'category'].includes(key))
        .map(([key, value]) => {
            const unit = getUnit(sensor.category, key);
            const formattedValue = typeof value === 'number' ? value.toFixed(2) : value;
            return { key, value: formattedValue, unit };
        });

    if (sensor.category === 'Color') {
        return renderColorSensor(sensor, displayValues, status);
    }

    return `
        <div class="sensor-item ${status}" data-sensor-id="${sensor.sensor_id}">
            <div class="sensor-name">
                <span class="status-dot ${status}"></span>
                ${sensor.display_name || sensor.sensor_id}
            </div>
            ${displayValues.map(v => `
                <div class="sensor-value">
                    ${v.value}<span class="sensor-unit">${v.unit}</span>
                </div>
            `).join('')}
        </div>
    `;
}

function renderColorSensor(sensor, values, status) {
    const r = values.find(v => v.key === 'ColorR')?.value || 0;
    const g = values.find(v => v.key === 'ColorG')?.value || 0;
    const b = values.find(v => v.key === 'ColorB')?.value || 0;

    return `
        <div class="sensor-item color-sensor ${status}" data-sensor-id="${sensor.sensor_id}">
            <div class="sensor-name">
                <span class="status-dot ${status}"></span>
                ${sensor.display_name || sensor.sensor_id}
            </div>
            <div class="sensor-value">
                <div class="color-preview" style="background: rgb(${r}, ${g}, ${b})"></div>
                <span>R:${r} G:${g} B:${b}</span>
            </div>
        </div>
    `;
}

function getSensorStatus(sensor) {
    if (sensor.status === 'pending_approval') return 'pending';
    if (sensor.status === 'disabled') return 'offline';

    const timeSinceLastSeen = Date.now() - (sensor.lastSeen || 0);
    if (timeSinceLastSeen > CONFIG.OFFLINE_THRESHOLD) return 'offline';

    return 'online';
}

function getUnit(category, modality) {
    if (category === 'IMU') {
        if (modality.startsWith('A')) return 'g';
        if (modality.startsWith('G')) return '°/s';
        if (modality.startsWith('M')) return 'µT';
    }
    if (category === 'Environmental') {
        if (modality === 'Temperature') return '°C';
        if (modality === 'Pressure') return 'hPa';
    }
    if (category === 'Proximity') {
        if (modality === 'Proximity') return 'cm';
    }
    return '';
}

function updateHealthCounts() {
    const sensors = Object.values(state.sensors);
    let online = 0, pending = 0, offline = 0;

    sensors.forEach(sensor => {
        const status = getSensorStatus(sensor);
        if (status === 'online') online++;
        else if (status === 'pending') pending++;
        else offline++;
    });

    updateHealthDisplay({ online, pending, offline });
}

function updateHealthDisplay(data) {
    const onlineEl = document.getElementById('health-online');
    const pendingEl = document.getElementById('health-pending');
    const offlineEl = document.getElementById('health-offline');
    const pendingCountEl = document.getElementById('pending-count');

    if (onlineEl) onlineEl.textContent = data.online || 0;
    if (pendingEl) pendingEl.textContent = data.pending || 0;
    if (offlineEl) offlineEl.textContent = data.offline || 0;
    if (pendingCountEl) pendingCountEl.textContent = data.pending || 0;
}

// =============================================================================
// Plotly.js Charts
// =============================================================================

let chartInstance = null;

function initChart() {
    const container = document.getElementById('waveform-chart');
    if (!container) return;

    const layout = {
        paper_bgcolor: '#0d1117',
        plot_bgcolor: '#0d1117',
        font: { color: '#e6edf3', family: 'Source Sans Pro' },
        margin: { t: 30, r: 30, b: 40, l: 50 },
        xaxis: {
            title: 'Time',
            type: 'date',
            gridcolor: '#30363d',
            linecolor: '#30363d'
        },
        yaxis: {
            title: getYAxisTitle(state.currentChartCategory),
            gridcolor: '#30363d',
            linecolor: '#30363d'
        },
        showlegend: true,
        legend: {
            orientation: 'h',
            y: 1.1,
            x: 0.5,
            xanchor: 'center'
        }
    };

    const config = {
        responsive: true,
        displayModeBar: false
    };

    Plotly.newPlot(container, [], layout, config);
    chartInstance = container;
}

function getYAxisTitle(category) {
    switch (category) {
        case 'IMU': return 'Acceleration (g)';
        case 'Gyroscope': return 'Angular Velocity (°/s)';
        case 'Magnetometer': return 'Magnetic Field (µT)';
        case 'Environmental': return 'Value';
        case 'Audio': return 'RMS Level';
        default: return 'Value';
    }
}

function getChartModalities(category) {
    switch (category) {
        case 'IMU': return ['Ax', 'Ay', 'Az'];
        case 'Gyroscope': return ['Gx', 'Gy', 'Gz'];
        case 'Magnetometer': return ['Mx', 'My', 'Mz'];
        case 'Environmental': return ['Temperature', 'Pressure'];
        case 'Audio': return ['RMS'];
        default: return [];
    }
}

function updateChart() {
    if (!chartInstance || state.chartPaused) return;

    const modalities = getChartModalities(state.currentChartCategory);
    const colors = CATEGORIES[state.currentChartCategory === 'Gyroscope' || state.currentChartCategory === 'Magnetometer'
        ? 'IMU' : state.currentChartCategory]?.colors || ['#3b82f6'];

    const traces = modalities.map((modality, index) => {
        const data = state.chartData[modality] || [];
        return {
            x: data.map(d => new Date(d.x)),
            y: data.map(d => d.y),
            type: 'scatter',
            mode: 'lines',
            name: modality,
            line: { color: colors[index % colors.length], width: 2 }
        };
    });

    const layout = {
        yaxis: { title: getYAxisTitle(state.currentChartCategory) }
    };

    Plotly.react(chartInstance, traces, layout);
}

function updateChartCategory() {
    const select = document.getElementById('chart-category');
    if (select) {
        state.currentChartCategory = select.value;
        updateChart();
    }
}

function clearCharts() {
    state.chartData = {};
    updateChart();
}

function pauseCharts() {
    state.chartPaused = !state.chartPaused;
    const btn = document.getElementById('pause-btn');
    if (btn) {
        btn.innerHTML = state.chartPaused
            ? '<i class="fas fa-play"></i> Resume'
            : '<i class="fas fa-pause"></i> Pause';
    }
}

// =============================================================================
// Admin Panel
// =============================================================================

function openAdminPanel() {
    const modal = document.getElementById('admin-modal');
    if (modal) {
        modal.classList.add('active');
        loadSensorRegistry();
    }
}

function closeAdminPanel() {
    const modal = document.getElementById('admin-modal');
    if (modal) {
        modal.classList.remove('active');
    }
}

function showAdminTab(tab) {
    state.adminTab = tab;

    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');

    // Reload list
    loadSensorRegistry();
}

async function loadSensorRegistry() {
    const container = document.getElementById('admin-sensor-list');
    if (!container) return;

    container.innerHTML = '<div class="loading">Loading sensors...</div>';

    try {
        const statusMap = {
            'pending': 'pending_approval',
            'approved': 'approved',
            'disabled': 'disabled'
        };

        const response = await fetch(`${CONFIG.API_BASE}/registry?status=${statusMap[state.adminTab] || ''}`);
        const data = await response.json();

        if (!data.success || !data.sensors || data.sensors.length === 0) {
            container.innerHTML = `<div class="sensor-placeholder">No ${state.adminTab} sensors</div>`;
            return;
        }

        container.innerHTML = data.sensors.map(sensor => renderAdminSensorItem(sensor)).join('');

        // Update pending count
        if (state.adminTab === 'pending') {
            const pendingCountEl = document.getElementById('pending-count');
            if (pendingCountEl) pendingCountEl.textContent = data.sensors.length;
        }
    } catch (error) {
        console.error('Failed to load sensor registry:', error);
        container.innerHTML = '<div class="sensor-placeholder">Failed to load sensors</div>';
    }
}

function renderAdminSensorItem(sensor) {
    const status = sensor.status || 'pending_approval';
    const lastSeen = sensor.last_seen ? new Date(sensor.last_seen).toLocaleString() : 'Never';

    let actions = '';
    if (status === 'pending_approval') {
        actions = `
            <button class="btn btn-approve" onclick="approveSensor('${sensor.sensor_id}')">
                <i class="fas fa-check"></i> Approve
            </button>
        `;
    } else if (status === 'approved') {
        actions = `
            <button class="btn btn-disable" onclick="disableSensor('${sensor.sensor_id}')">
                <i class="fas fa-ban"></i> Disable
            </button>
        `;
    } else {
        actions = `
            <button class="btn btn-approve" onclick="approveSensor('${sensor.sensor_id}')">
                <i class="fas fa-check"></i> Re-enable
            </button>
        `;
    }

    return `
        <div class="sensor-list-item">
            <div class="sensor-list-info">
                <div class="sensor-list-id">${sensor.sensor_id}</div>
                <div class="sensor-list-meta">
                    Category: ${sensor.category || 'Unknown'} | Last seen: ${lastSeen}
                </div>
            </div>
            <div class="sensor-list-actions">
                ${actions}
            </div>
        </div>
    `;
}

async function approveSensor(sensorId) {
    try {
        const response = await fetch(`${CONFIG.API_BASE}/registry/${sensorId}/approve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();

        if (data.success) {
            showNotification(`Sensor ${sensorId} approved`, 'success');
            loadSensorRegistry();
            loadInitialData(); // Refresh main display
        } else {
            showNotification(data.error || 'Failed to approve sensor', 'error');
        }
    } catch (error) {
        console.error('Failed to approve sensor:', error);
        showNotification('Failed to approve sensor', 'error');
    }
}

async function disableSensor(sensorId) {
    try {
        const response = await fetch(`${CONFIG.API_BASE}/registry/${sensorId}/disable`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();

        if (data.success) {
            showNotification(`Sensor ${sensorId} disabled`, 'warning');
            loadSensorRegistry();
            loadInitialData();
        } else {
            showNotification(data.error || 'Failed to disable sensor', 'error');
        }
    } catch (error) {
        console.error('Failed to disable sensor:', error);
        showNotification('Failed to disable sensor', 'error');
    }
}

// =============================================================================
// Notifications
// =============================================================================

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <i class="fas fa-${getNotificationIcon(type)}"></i>
        <span>${message}</span>
    `;

    // Style it
    Object.assign(notification.style, {
        position: 'fixed',
        top: '1rem',
        right: '1rem',
        padding: '0.75rem 1rem',
        borderRadius: '6px',
        background: getNotificationColor(type),
        color: 'white',
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        zIndex: '10000',
        animation: 'slideIn 0.3s ease',
        boxShadow: '0 4px 6px rgba(0,0,0,0.3)'
    });

    document.body.appendChild(notification);

    // Auto remove
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

function getNotificationIcon(type) {
    switch (type) {
        case 'success': return 'check-circle';
        case 'error': return 'exclamation-circle';
        case 'warning': return 'exclamation-triangle';
        default: return 'info-circle';
    }
}

function getNotificationColor(type) {
    switch (type) {
        case 'success': return '#10b981';
        case 'error': return '#ef4444';
        case 'warning': return '#f59e0b';
        default: return '#3b82f6';
    }
}

// Add notification animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);

// =============================================================================
// Initial Data Load
// =============================================================================

async function loadInitialData() {
    try {
        // Load current readings
        const readingsResponse = await fetch(`${CONFIG.API_BASE}/current?all=true`);
        const readingsData = await readingsResponse.json();

        if (readingsData.success && readingsData.readings) {
            Object.entries(readingsData.readings).forEach(([sensorId, values]) => {
                state.sensors[sensorId] = {
                    sensor_id: sensorId,
                    category: inferCategory(values),
                    values: values,
                    status: 'online',
                    lastSeen: Date.now()
                };
            });
        }

        // Load health summary
        const healthResponse = await fetch(`${CONFIG.API_BASE}/health`);
        const healthData = await healthResponse.json();

        if (healthData.success) {
            updateHealthDisplay(healthData);
        }

        updateSensorDisplay();
    } catch (error) {
        console.error('Failed to load initial data:', error);
    }
}

// =============================================================================
// Initialization
// =============================================================================

function init() {
    if (state.initialized) return;
    state.initialized = true;

    console.log('[Sensor Dashboard] Initializing...');

    // Initialize Socket.IO
    initSocketIO();

    // Initialize chart
    initChart();

    // Load initial data
    loadInitialData();

    // Start chart update interval
    setInterval(() => {
        if (!state.chartPaused) {
            updateChart();
        }
    }, CONFIG.UPDATE_INTERVAL);

    // Periodic health check
    setInterval(() => {
        updateHealthCounts();
    }, 5000);

    console.log('[Sensor Dashboard] Initialized');
}

// Run on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// =============================================================================
// History Mode - Session Management
// =============================================================================

async function toggleHistoryMode() {
    state.historyMode = !state.historyMode;

    const historyBtn = document.getElementById('history-mode-btn');
    const liveIndicator = document.getElementById('live-indicator');
    const historyPanel = document.getElementById('history-panel');

    if (state.historyMode) {
        // Enter history mode
        if (historyBtn) historyBtn.classList.add('active');
        if (liveIndicator) liveIndicator.style.display = 'none';
        if (historyPanel) historyPanel.style.display = 'block';

        // Stop real-time updates
        if (state.socket) state.socket.disconnect();

        // Load available sessions
        await loadSessions();

        showNotification('History mode enabled', 'info');
    } else {
        // Return to live mode
        if (historyBtn) historyBtn.classList.remove('active');
        if (liveIndicator) liveIndicator.style.display = 'inline-flex';
        if (historyPanel) historyPanel.style.display = 'none';

        // Stop playback
        stopPlayback();

        // Clear history data
        state.currentSession = null;
        state.sessionData = null;
        state.chartData = {};

        // Reconnect to real-time
        if (state.socket) state.socket.connect();

        showNotification('Live mode enabled', 'success');
    }
}

async function loadSessions() {
    const container = document.getElementById('session-list');
    if (!container) return;

    container.innerHTML = '<div class="loading">Loading sessions...</div>';

    try {
        const response = await fetch(`${CONFIG.API_BASE}/history/sessions?limit=50`);
        const data = await response.json();

        if (!data.success) {
            container.innerHTML = '<div class="sensor-placeholder">Failed to load sessions</div>';
            return;
        }

        state.sessions = data.sessions || [];

        if (state.sessions.length === 0) {
            container.innerHTML = '<div class="sensor-placeholder">No recorded sessions found</div>';
            return;
        }

        container.innerHTML = state.sessions.map(session => renderSessionItem(session)).join('');
    } catch (error) {
        console.error('Failed to load sessions:', error);
        container.innerHTML = '<div class="sensor-placeholder">Error loading sessions</div>';
    }
}

function renderSessionItem(session) {
    const date = new Date(session.modified);
    const dateStr = date.toLocaleDateString();
    const timeStr = date.toLocaleTimeString();
    const isAligned = session.aligned ? '<span class="badge aligned">Multi-Sensor</span>' : '';
    const isSelected = state.selectedSessions.includes(session.id);

    return `
        <div class="session-item ${state.currentSession?.id === session.id ? 'active' : ''}"
             data-session-id="${session.id}">
            <div class="session-info" onclick="selectSession('${session.id}')">
                <div class="session-name">${session.experiment || session.id}</div>
                <div class="session-meta">
                    ${dateStr} ${timeStr} | ${session.size_mb} MB ${isAligned}
                </div>
            </div>
            <div class="session-actions">
                <input type="checkbox"
                       class="compare-checkbox"
                       ${isSelected ? 'checked' : ''}
                       onclick="toggleSessionCompare('${session.id}', this.checked)"
                       title="Add to comparison">
            </div>
        </div>
    `;
}

async function selectSession(sessionId) {
    const session = state.sessions.find(s => s.id === sessionId);
    if (!session) return;

    state.currentSession = session;

    // Update UI
    document.querySelectorAll('.session-item').forEach(el => {
        el.classList.remove('active');
    });
    document.querySelector(`[data-session-id="${sessionId}"]`)?.classList.add('active');

    // Show loading
    showNotification(`Loading session: ${session.experiment || sessionId}...`, 'info');

    // Load playback data
    await loadPlaybackData(sessionId);

    // Load analytics
    await loadSessionAnalytics(sessionId);
}

async function loadPlaybackData(sessionId) {
    try {
        const response = await fetch(`${CONFIG.API_BASE}/history/playback/${sessionId}?points=500`);
        const data = await response.json();

        if (!data.success) {
            showNotification('Failed to load session data', 'error');
            return;
        }

        state.sessionData = data;
        state.playbackIndex = 0;

        // Extract sensors from column names
        const sensors = new Set();
        data.columns.forEach(col => {
            if (col.includes('.')) {
                sensors.add(col.split('.')[0]);
            }
        });

        // Update sensor list in UI
        updateHistorySensorList(Array.from(sensors));

        // Populate chart data
        populateChartFromSession(data.data);

        // Update playback slider
        const slider = document.getElementById('playback-slider');
        if (slider) {
            slider.max = data.data.length - 1;
            slider.value = 0;
        }

        // Update time display
        updatePlaybackTimeDisplay(0);

        showNotification(`Loaded ${data.displayed_rows} samples (${data.downsample_factor}x downsampled)`, 'success');
    } catch (error) {
        console.error('Failed to load playback data:', error);
        showNotification('Error loading playback data', 'error');
    }
}

function populateChartFromSession(data) {
    state.chartData = {};

    data.forEach((row, index) => {
        const timestamp = row.ts_ms || index * 50; // Fallback to index-based time

        Object.entries(row).forEach(([key, value]) => {
            if (key === 'ts_ms' || value === null || typeof value !== 'number') return;

            // Extract modality from "sensor.modality" format
            let modality = key;
            if (key.includes('.')) {
                modality = key.split('.')[1];
            }

            if (!state.chartData[modality]) {
                state.chartData[modality] = [];
            }

            state.chartData[modality].push({
                x: timestamp,
                y: value,
                fullKey: key
            });
        });
    });

    updateChart();
}

function updateHistorySensorList(sensors) {
    const container = document.getElementById('history-sensors');
    if (!container) return;

    container.innerHTML = sensors.map(sensor => `
        <div class="history-sensor-item">
            <input type="checkbox"
                   id="sensor-${sensor}"
                   checked
                   onchange="toggleHistorySensor('${sensor}', this.checked)">
            <label for="sensor-${sensor}">${sensor}</label>
        </div>
    `).join('');
}

function toggleHistorySensor(sensorId, checked) {
    // Re-filter chart data based on selected sensors
    if (state.sessionData) {
        const selectedSensors = [];
        document.querySelectorAll('.history-sensor-item input:checked').forEach(el => {
            selectedSensors.push(el.id.replace('sensor-', ''));
        });

        // Reload chart with filtered sensors
        const filteredData = state.sessionData.data.map(row => {
            const filtered = { ts_ms: row.ts_ms };
            Object.entries(row).forEach(([key, value]) => {
                if (key === 'ts_ms') return;
                const sensor = key.split('.')[0];
                if (selectedSensors.includes(sensor)) {
                    filtered[key] = value;
                }
            });
            return filtered;
        });

        populateChartFromSession(filteredData);
    }
}

// =============================================================================
// History Mode - Playback Controls
// =============================================================================

function playSession() {
    if (!state.sessionData || !state.sessionData.data.length) {
        showNotification('No session loaded', 'warning');
        return;
    }

    state.isPlaying = true;
    updatePlaybackButtons();

    const interval = 100 / state.playbackSpeed; // Base 100ms per frame

    state.playbackTimer = setInterval(() => {
        if (state.playbackIndex >= state.sessionData.data.length - 1) {
            stopPlayback();
            return;
        }

        state.playbackIndex++;
        onPlaybackFrame(state.playbackIndex);
    }, interval);
}

function pausePlayback() {
    state.isPlaying = false;
    if (state.playbackTimer) {
        clearInterval(state.playbackTimer);
        state.playbackTimer = null;
    }
    updatePlaybackButtons();
}

function stopPlayback() {
    pausePlayback();
    state.playbackIndex = 0;
    onPlaybackFrame(0);
}

function onPlaybackFrame(index) {
    // Update slider
    const slider = document.getElementById('playback-slider');
    if (slider) slider.value = index;

    // Update time display
    updatePlaybackTimeDisplay(index);

    // Highlight current point on chart
    highlightChartPosition(index);

    // Update sensor values display
    updatePlaybackSensorValues(index);
}

function onSliderChange(value) {
    state.playbackIndex = parseInt(value);
    onPlaybackFrame(state.playbackIndex);
}

function updatePlaybackTimeDisplay(index) {
    const display = document.getElementById('playback-time');
    if (!display || !state.sessionData) return;

    const row = state.sessionData.data[index];
    if (row && row.ts_ms) {
        const ms = row.ts_ms;
        const seconds = Math.floor((ms / 1000) % 60);
        const minutes = Math.floor((ms / 60000) % 60);
        display.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    } else {
        display.textContent = `${index} / ${state.sessionData.data.length}`;
    }
}

function highlightChartPosition(index) {
    if (!chartInstance || !state.sessionData) return;

    const row = state.sessionData.data[index];
    if (!row) return;

    // Add vertical line annotation at current position
    const timestamp = row.ts_ms || index * 50;

    Plotly.relayout(chartInstance, {
        shapes: [{
            type: 'line',
            x0: timestamp,
            x1: timestamp,
            y0: 0,
            y1: 1,
            yref: 'paper',
            line: { color: '#ef4444', width: 2, dash: 'dash' }
        }]
    });
}

function updatePlaybackSensorValues(index) {
    if (!state.sessionData) return;

    const row = state.sessionData.data[index];
    if (!row) return;

    // Update display with current values
    // This would update sensor cards with historical values at this timestamp
    Object.entries(row).forEach(([key, value]) => {
        if (key === 'ts_ms' || value === null) return;

        const el = document.querySelector(`[data-modality="${key}"] .sensor-value`);
        if (el && typeof value === 'number') {
            el.textContent = value.toFixed(2);
        }
    });
}

function updatePlaybackButtons() {
    const playBtn = document.getElementById('play-btn');
    const pauseBtn = document.getElementById('pause-btn-history');

    if (playBtn) {
        playBtn.disabled = state.isPlaying;
        playBtn.style.opacity = state.isPlaying ? '0.5' : '1';
    }
    if (pauseBtn) {
        pauseBtn.disabled = !state.isPlaying;
        pauseBtn.style.opacity = !state.isPlaying ? '0.5' : '1';
    }
}

function setPlaybackSpeed(speed) {
    state.playbackSpeed = parseFloat(speed);

    // Update speed buttons
    document.querySelectorAll('.speed-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');

    // Restart if playing
    if (state.isPlaying) {
        pausePlayback();
        playSession();
    }
}

// =============================================================================
// History Mode - Analytics & Comparison
// =============================================================================

async function loadSessionAnalytics(sessionId) {
    const container = document.getElementById('analytics-panel');
    if (!container) return;

    container.innerHTML = '<div class="loading">Computing analytics...</div>';

    try {
        const response = await fetch(`${CONFIG.API_BASE}/history/session/${sessionId}/analytics`);
        const data = await response.json();

        if (!data.success) {
            container.innerHTML = '<div class="sensor-placeholder">Failed to load analytics</div>';
            return;
        }

        container.innerHTML = renderAnalytics(data);
    } catch (error) {
        console.error('Failed to load analytics:', error);
        container.innerHTML = '<div class="sensor-placeholder">Error loading analytics</div>';
    }
}

function renderAnalytics(data) {
    const summary = data.summary || {};
    const anomalies = data.anomalies || [];
    const trends = data.trends || {};

    let html = `
        <div class="analytics-section">
            <h4>Session Summary</h4>
            <div class="analytics-grid">
                <div class="analytics-stat">
                    <span class="stat-value">${summary.total_samples?.toLocaleString() || 'N/A'}</span>
                    <span class="stat-label">Total Samples</span>
                </div>
                <div class="analytics-stat">
                    <span class="stat-value">${summary.sample_rate_hz || 'N/A'} Hz</span>
                    <span class="stat-label">Sample Rate</span>
                </div>
                <div class="analytics-stat">
                    <span class="stat-value">${summary.duration_ms ? (summary.duration_ms / 1000).toFixed(1) + 's' : 'N/A'}</span>
                    <span class="stat-label">Duration</span>
                </div>
            </div>
        </div>
    `;

    // Anomalies section
    if (anomalies.length > 0) {
        html += `
            <div class="analytics-section anomalies">
                <h4>⚠️ Anomalies Detected (${anomalies.length})</h4>
                <div class="anomaly-list">
                    ${anomalies.slice(0, 5).map(a => `
                        <div class="anomaly-item">
                            <span class="anomaly-sensor">${a.sensor}.${a.modality}</span>
                            <span class="anomaly-count">${a.count} outliers (${a.percent}%)</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    // Trends section
    const trendEntries = Object.entries(trends);
    if (trendEntries.length > 0) {
        html += `
            <div class="analytics-section trends">
                <h4>📈 Trends</h4>
                <div class="trend-list">
                    ${trendEntries.slice(0, 5).map(([sensor, modalities]) => {
                        const items = Object.entries(modalities).map(([mod, t]) => {
                            const icon = t.direction === 'increasing' ? '↗️' : t.direction === 'decreasing' ? '↘️' : '➡️';
                            return `<span class="trend-item">${mod}: ${icon}</span>`;
                        });
                        return `<div class="trend-sensor"><strong>${sensor}</strong>: ${items.join(' ')}</div>`;
                    }).join('')}
                </div>
            </div>
        `;
    }

    return html;
}

function toggleSessionCompare(sessionId, checked) {
    if (checked) {
        if (!state.selectedSessions.includes(sessionId)) {
            state.selectedSessions.push(sessionId);
        }
    } else {
        state.selectedSessions = state.selectedSessions.filter(id => id !== sessionId);
    }

    // Update compare button visibility
    const compareBtn = document.getElementById('compare-btn');
    if (compareBtn) {
        compareBtn.style.display = state.selectedSessions.length >= 2 ? 'inline-flex' : 'none';
        compareBtn.textContent = `Compare (${state.selectedSessions.length})`;
    }
}

async function runComparison() {
    if (state.selectedSessions.length < 2) {
        showNotification('Select at least 2 sessions to compare', 'warning');
        return;
    }

    const modal = document.getElementById('compare-modal');
    const container = document.getElementById('compare-results');

    if (modal) modal.classList.add('active');
    if (container) container.innerHTML = '<div class="loading">Comparing sessions...</div>';

    try {
        const sessionIds = state.selectedSessions.join(',');
        const response = await fetch(`${CONFIG.API_BASE}/history/compare?sessions=${sessionIds}`);
        const data = await response.json();

        if (!data.success) {
            container.innerHTML = '<div class="sensor-placeholder">Comparison failed</div>';
            return;
        }

        container.innerHTML = renderComparison(data);
    } catch (error) {
        console.error('Failed to compare sessions:', error);
        container.innerHTML = '<div class="sensor-placeholder">Error comparing sessions</div>';
    }
}

function renderComparison(data) {
    const sessions = data.sessions || {};
    const modalities = data.summary?.modalities || {};

    let html = `
        <div class="comparison-header">
            <h4>Session Comparison</h4>
            <p>${Object.keys(sessions).length} sessions compared</p>
        </div>
    `;

    // Comparison table per modality
    Object.entries(modalities).forEach(([key, values]) => {
        if (values.length < 2) return;

        html += `
            <div class="comparison-modality">
                <h5>${key}</h5>
                <table class="comparison-table">
                    <thead>
                        <tr>
                            <th>Session</th>
                            <th>Min</th>
                            <th>Max</th>
                            <th>Mean</th>
                            <th>Std Dev</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${values.map(v => `
                            <tr>
                                <td>${v.session}</td>
                                <td>${v.min?.toFixed(2) || '-'}</td>
                                <td>${v.max?.toFixed(2) || '-'}</td>
                                <td>${v.mean?.toFixed(2) || '-'}</td>
                                <td>${v.std?.toFixed(2) || '-'}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    });

    return html;
}

function closeCompareModal() {
    const modal = document.getElementById('compare-modal');
    if (modal) modal.classList.remove('active');
}

function openCompareModal() {
    const modal = document.getElementById('compare-modal');
    if (modal) {
        modal.classList.add('active');
        populateCompareSessionList();
    }
}

async function populateCompareSessionList() {
    const container = document.getElementById('compare-session-list');
    if (!container) return;

    // Load sessions if not already loaded
    if (state.sessions.length === 0) {
        await loadSessions();
    }

    container.innerHTML = state.sessions.map(session => `
        <label class="compare-session-item ${state.selectedSessions.includes(session.id) ? 'selected' : ''}">
            <input type="checkbox"
                   ${state.selectedSessions.includes(session.id) ? 'checked' : ''}
                   onchange="toggleSessionCompare('${session.id}')">
            <span>${session.experiment || session.filename}</span>
        </label>
    `).join('');
}

function toggleAnalyticsPanel() {
    const panel = document.getElementById('analytics-panel');
    if (panel) {
        panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
    }
}

function exportSession() {
    if (!state.currentSession) {
        showNotification('No session selected', 'warning');
        return;
    }

    // Find the session to get the file path
    const session = state.sessions.find(s => s.id === state.currentSession);
    if (session && session.filename) {
        // Create download link for the CSV file
        const link = document.createElement('a');
        link.href = `/api/sensors/history/session/${state.currentSession}/download`;
        link.download = session.filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        showNotification(`Downloading ${session.filename}`, 'success');
    } else {
        showNotification('Session file not found', 'error');
    }
}

// Expose functions for HTML onclick handlers
window.updateChartCategory = updateChartCategory;
window.clearCharts = clearCharts;
window.pauseCharts = pauseCharts;
window.openAdminPanel = openAdminPanel;
window.closeAdminPanel = closeAdminPanel;
window.showAdminTab = showAdminTab;
window.approveSensor = approveSensor;
window.disableSensor = disableSensor;
// History mode functions
window.toggleHistoryMode = toggleHistoryMode;
window.selectSession = selectSession;
window.toggleSessionCompare = toggleSessionCompare;
window.runComparison = runComparison;
window.closeCompareModal = closeCompareModal;
window.playSession = playSession;
window.pausePlayback = pausePlayback;
window.stopPlayback = stopPlayback;
window.onSliderChange = onSliderChange;
window.setPlaybackSpeed = setPlaybackSpeed;
window.toggleHistorySensor = toggleHistorySensor;
window.openCompareModal = openCompareModal;
window.toggleAnalyticsPanel = toggleAnalyticsPanel;
window.exportSession = exportSession;
window.loadSessions = loadSessions;
window.loadSessionAnalytics = loadSessionAnalytics;
