/**
 * Flask CNC SCADA System - Main JavaScript
 * ==========================================
 * Handles UI interactions and API calls
 */

// API Base URL
const API_BASE = '';

// Current machine selection (for multi-machine filtering)
let currentMachine = localStorage.getItem('selectedMachine') || 'all';

// Machine selector - stores selection and updates UI
function selectMachine() {
    const selector = document.getElementById('machine-selector');
    if (selector) {
        currentMachine = selector.value;
        localStorage.setItem('selectedMachine', currentMachine);
        log(`Switched to: ${currentMachine === 'all' ? 'All Machines' : currentMachine}`, 'info');

        // Refresh status with new machine filter
        refreshStatus();

        // Update Grafana links with machine filter
        updateGrafanaLinks();
    }
}

// Update Grafana dashboard links with machine_id variable
function updateGrafanaLinks() {
    const grafanaLink = document.querySelector('a[href*="localhost:3000"]');
    if (grafanaLink) {
        const baseUrl = 'http://localhost:3000';
        if (currentMachine !== 'all') {
            grafanaLink.href = `${baseUrl}/d/cnc-overview?var-machine_id=${currentMachine}`;
        } else {
            grafanaLink.href = baseUrl;
        }
    }
}

// Initialize machine selector from localStorage
function initMachineSelector() {
    const selector = document.getElementById('machine-selector');
    if (selector && currentMachine) {
        selector.value = currentMachine;
        updateGrafanaLinks();
    }
}

// Log function
function log(message, type = 'info') {
    const logBox = document.getElementById('activity-log');
    const timestamp = new Date().toLocaleTimeString();
    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;
    entry.textContent = `[${timestamp}] ${message}`;
    logBox.appendChild(entry);
    logBox.scrollTop = logBox.scrollHeight;
}

// Clear log
function clearLog() {
    document.getElementById('activity-log').innerHTML = '';
    log('Log cleared', 'info');
}

// API call helper
async function apiCall(endpoint, method = 'GET', body = null) {
    try {
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            }
        };

        if (body && method !== 'GET') {
            options.body = JSON.stringify(body);
        }

        const response = await fetch(API_BASE + endpoint, options);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Request failed');
        }

        return data;
    } catch (error) {
        log(`Error: ${error.message}`, 'error');
        throw error;
    }
}

// Refresh system status
async function refreshStatus() {
    try {
        const machineFilter = currentMachine !== 'all' ? ` (${currentMachine})` : '';
        log(`Refreshing system status${machineFilter}...`, 'info');

        // Get system status (includes machine_id filtering info)
        const endpoint = currentMachine !== 'all'
            ? `/status?machine_id=${currentMachine}`
            : '/status';
        const status = await apiCall(endpoint);

        // Update InfluxDB status
        const influxStatus = document.getElementById('influxdb-status');
        if (status.infrastructure?.influxdb?.enabled) {
            const influxHealth = status.infrastructure.influxdb.status;
            influxStatus.innerHTML = `<span class="status-badge status-${influxHealth === 'healthy' ? 'connected' : 'warning'}">${influxHealth || 'Connected'}</span>`;
        } else {
            influxStatus.innerHTML = '<span class="status-badge status-disconnected">Disabled</span>';
        }

        // Update controller-specific status if available
        if (status.controllers) {
            updateControllerStatusFromAPI(status.controllers);
        }

        // Refresh all component statuses
        await Promise.all([
            updateTinyGStatus(),
            updateSensorStatus(),
            updateMCCStatus()
        ]);

        log('Status refreshed successfully', 'success');
    } catch (error) {
        log(`Failed to refresh status: ${error.message}`, 'error');
    }
}

// Update controller displays from comprehensive status API response
function updateControllerStatusFromAPI(controllers) {
    // Update TinyG controller status
    if (controllers.tinyg) {
        const tinygStatus = document.getElementById('tinyg-status');
        if (tinygStatus) {
            const status = controllers.tinyg.status || 'unknown';
            const connected = controllers.tinyg.connected;
            if (connected) {
                tinygStatus.innerHTML = '<span class="status-badge status-connected">Connected</span>';
            } else if (status === 'disconnected') {
                tinygStatus.innerHTML = '<span class="status-badge status-disconnected">Disconnected</span>';
            } else {
                tinygStatus.innerHTML = `<span class="status-badge status-warning">${status}</span>`;
            }
        }
    }

    // Update Sensor controller status
    if (controllers.sensor) {
        const sensorStatus = document.getElementById('sensor-status');
        if (sensorStatus) {
            const status = controllers.sensor.status || 'unknown';
            if (status === 'recording') {
                sensorStatus.innerHTML = '<span class="status-badge status-running">Recording</span>';
            } else if (status === 'idle') {
                sensorStatus.innerHTML = '<span class="status-badge status-connected">Idle</span>';
            } else {
                sensorStatus.innerHTML = '<span class="status-badge status-disconnected">Stopped</span>';
            }
        }
    }

    // Update MCC controller status
    if (controllers.mcc) {
        const mccStatus = document.getElementById('mcc-status');
        if (mccStatus) {
            const status = controllers.mcc.status || 'unknown';
            if (status === 'recording') {
                mccStatus.innerHTML = '<span class="status-badge status-running">Recording</span>';
            } else if (status === 'idle') {
                mccStatus.innerHTML = '<span class="status-badge status-connected">Idle</span>';
            } else {
                mccStatus.innerHTML = '<span class="status-badge status-disconnected">Stopped</span>';
            }
        }
    }
}

// Discover serial ports
async function discoverPorts() {
    try {
        log('Discovering serial ports...', 'info');
        const data = await apiCall('/ports');

        // Update port count
        document.getElementById('port-count').textContent = data.count;

        // Update TinyG port selector
        const tinygSelect = document.getElementById('tinyg-port');
        tinygSelect.innerHTML = '<option value="">Select port...</option>';

        // Update sensor port selector
        const sensorSelect = document.getElementById('sensor-ports');
        sensorSelect.innerHTML = '';

        data.ports.forEach(port => {
            // Add to TinyG if it looks like TinyG
            if (port.is_tinyg) {
                const option = document.createElement('option');
                option.value = port.device;
                option.textContent = `${port.device} (${port.description})`;
                tinygSelect.appendChild(option);
            }

            // Add to sensor if it looks like Arduino
            if (port.is_arduino) {
                const option = document.createElement('option');
                option.value = port.device;
                option.textContent = `${port.device} (${port.description})`;
                sensorSelect.appendChild(option);
            }
        });

        log(`Found ${data.count} serial ports`, 'success');
    } catch (error) {
        log(`Failed to discover ports: ${error.message}`, 'error');
    }
}

// TinyG Functions
async function updateTinyGStatus() {
    try {
        const data = await apiCall('/tinyg/status');
        const status = data.status;

        const statusDiv = document.getElementById('tinyg-status');
        if (status.connected) {
            statusDiv.innerHTML = '<span class="status-badge status-connected">Connected</span>';
            if (status.polling) {
                statusDiv.innerHTML += ' <span class="status-badge status-running">Polling</span>';
            }
        } else {
            statusDiv.innerHTML = '<span class="status-badge status-disconnected">Disconnected</span>';
        }

        // Update position info in TinyG card
        if (status.last_status && status.last_status.wx !== undefined) {
            const infoDiv = document.getElementById('tinyg-info');
            infoDiv.innerHTML = `
                <span class="info-label">Position:</span>
                <span class="info-value">X:${status.last_status.wx?.toFixed(2) || 'N/A'}
                    Y:${status.last_status.wy?.toFixed(2) || 'N/A'}
                    Z:${status.last_status.wz?.toFixed(2) || 'N/A'}</span>
                <span class="info-label">Poll Count:</span>
                <span class="info-value">${status.poll_count}</span>
            `;
        }

        // Also update the main position display
        updatePositionDisplay(status);
    } catch (error) {
        // Silently fail for status updates
    }
}

async function connectTinyG() {
    const port = document.getElementById('tinyg-port').value;
    if (!port) {
        log('Please select a port', 'error');
        return;
    }

    try {
        log(`Connecting to TinyG on ${port}...`, 'info');
        const data = await apiCall('/tinyg/connect', 'POST', { port: port });
        log(data.message, 'success');
        await updateTinyGStatus();
    } catch (error) {
        log(`Connection failed: ${error.message}`, 'error');
    }
}

async function disconnectTinyG() {
    try {
        log('Disconnecting TinyG...', 'info');
        const data = await apiCall('/tinyg/disconnect', 'POST');
        log(data.message, 'success');
        await updateTinyGStatus();
    } catch (error) {
        log(`Disconnect failed: ${error.message}`, 'error');
    }
}

async function startTinyGPolling() {
    try {
        log('Starting TinyG polling...', 'info');
        const data = await apiCall('/tinyg/start_polling', 'POST', {
            experiment_name: 'demo',
            interval: 0.05
        });
        log(data.message, 'success');
        await updateTinyGStatus();
    } catch (error) {
        log(`Failed to start polling: ${error.message}`, 'error');
    }
}

async function stopTinyGPolling() {
    try {
        log('Stopping TinyG polling...', 'info');
        const data = await apiCall('/tinyg/stop_polling', 'POST');
        log(data.message, 'success');
        await updateTinyGStatus();
    } catch (error) {
        log(`Failed to stop polling: ${error.message}`, 'error');
    }
}

// Sensor Functions
async function updateSensorStatus() {
    try {
        const data = await apiCall('/sensor/status');
        const status = data.status;

        const statusDiv = document.getElementById('sensor-status');
        if (status.running) {
            statusDiv.innerHTML = '<span class="status-badge status-running">Recording</span>';
            if (status.paused) {
                statusDiv.innerHTML += ' <span class="status-badge" style="background: #f59e0b;">Paused</span>';
            }
        } else {
            statusDiv.innerHTML = '<span class="status-badge status-disconnected">Stopped</span>';
        }
    } catch (error) {
        // Silently fail
    }
}

async function startSensors() {
    const select = document.getElementById('sensor-ports');
    const ports = Array.from(select.selectedOptions).map(opt => opt.value);

    if (ports.length === 0) {
        log('Please select at least one sensor port', 'error');
        return;
    }

    try {
        log(`Starting sensor recording on ${ports.length} port(s)...`, 'info');
        const data = await apiCall('/sensor/start', 'POST', {
            ports: ports,
            experiment_name: 'demo'
        });
        log(data.message, 'success');
        await updateSensorStatus();
    } catch (error) {
        log(`Failed to start sensors: ${error.message}`, 'error');
    }
}

async function stopSensors() {
    try {
        log('Stopping sensor recording...', 'info');
        const data = await apiCall('/sensor/stop', 'POST');
        log(data.message, 'success');
        await updateSensorStatus();
    } catch (error) {
        log(`Failed to stop sensors: ${error.message}`, 'error');
    }
}

async function pauseSensors() {
    try {
        log('Pausing sensor recording...', 'info');
        const data = await apiCall('/sensor/pause', 'POST');
        log(data.message, 'success');
        await updateSensorStatus();
    } catch (error) {
        log(`Failed to pause sensors: ${error.message}`, 'error');
    }
}

async function resumeSensors() {
    try {
        log('Resuming sensor recording...', 'info');
        const data = await apiCall('/sensor/resume', 'POST');
        log(data.message, 'success');
        await updateSensorStatus();
    } catch (error) {
        log(`Failed to resume sensors: ${error.message}`, 'error');
    }
}

// MCC Functions
async function updateMCCStatus() {
    try {
        const data = await apiCall('/mcc/status');
        const status = data.status;

        const statusDiv = document.getElementById('mcc-status');
        if (status.recording) {
            statusDiv.innerHTML = '<span class="status-badge status-running">Recording</span>';
        } else if (status.connected) {
            statusDiv.innerHTML = '<span class="status-badge status-connected">Connected</span>';
        } else {
            statusDiv.innerHTML = '<span class="status-badge status-disconnected">Stopped</span>';
        }

        // Update stats if available
        if (status.stats) {
            const statsDiv = document.getElementById('mcc-stats');
            statsDiv.innerHTML = `
                <span class="info-label">Spindle:</span>
                <span class="info-value">${status.stats.spindle.voltage.toFixed(3)} V</span>
                <span class="info-label">X Motor:</span>
                <span class="info-value">${status.stats.x_motor.voltage.toFixed(3)} V</span>
                <span class="info-label">Y Motor:</span>
                <span class="info-value">${status.stats.y_motor.voltage.toFixed(3)} V</span>
                <span class="info-label">Z Motor:</span>
                <span class="info-value">${status.stats.z_motor.voltage.toFixed(3)} V</span>
            `;
        }
    } catch (error) {
        // Silently fail
    }
}

async function testMCCConnection() {
    try {
        log('Testing MCC connection...', 'info');
        const data = await apiCall('/mcc/test_connection', 'POST');
        log(data.message, data.success ? 'success' : 'error');
        await updateMCCStatus();
    } catch (error) {
        log(`Connection test failed: ${error.message}`, 'error');
    }
}

async function startMCC() {
    try {
        log('Starting MCC recording...', 'info');
        const data = await apiCall('/mcc/start', 'POST', {
            experiment_name: 'demo'
        });
        log(data.message, 'success');
        await updateMCCStatus();
    } catch (error) {
        log(`Failed to start MCC: ${error.message}`, 'error');
    }
}

async function stopMCC() {
    try {
        log('Stopping MCC recording...', 'info');
        const data = await apiCall('/mcc/stop', 'POST');
        log(data.message, 'success');
        await updateMCCStatus();
    } catch (error) {
        log(`Failed to stop MCC: ${error.message}`, 'error');
    }
}

// Auto-refresh status every 2 seconds
setInterval(() => {
    updateTinyGStatus();
    updateSensorStatus();
    updateMCCStatus();
}, 2000);

// Dark mode toggle
function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');
    localStorage.setItem('darkMode', isDark ? 'enabled' : 'disabled');
    log(`Dark mode ${isDark ? 'enabled' : 'disabled'}`, 'info');
}

// =================== Manual Jog Functions ===================

async function jog(axis, direction) {
    const distance = parseFloat(document.getElementById('jog-distance').value) * direction;
    const speed = parseInt(document.getElementById('jog-speed').value);

    try {
        log(`Jogging ${axis} by ${distance}mm at ${speed}mm/min`, 'info');
        const data = await apiCall('/tinyg/jog', 'POST', {
            axis: axis,
            distance: distance,
            speed: speed
        });
        if (data.success) {
            log(`Jog ${axis} ${direction > 0 ? '+' : ''}${distance}mm complete`, 'success');
        }
    } catch (error) {
        log(`Jog failed: ${error.message}`, 'error');
    }
}

async function zeroAxis(axis) {
    try {
        log(`Zeroing ${axis} axis...`, 'info');
        const command = axis === 'ALL' ? 'G28.3 X0 Y0 Z0' : `G28.3 ${axis}0`;
        const data = await apiCall('/tinyg/send', 'POST', { command: command });
        if (data.success) {
            log(`${axis} axis zeroed`, 'success');
        }
    } catch (error) {
        log(`Zero failed: ${error.message}`, 'error');
    }
}

async function homeAll() {
    try {
        log('Homing all axes...', 'info');
        const data = await apiCall('/tinyg/send', 'POST', { command: 'G28.2 X0 Y0 Z0' });
        if (data.success) {
            log('Homing complete', 'success');
        }
    } catch (error) {
        log(`Homing failed: ${error.message}`, 'error');
    }
}

async function feedHold() {
    try {
        log('Feed hold...', 'info');
        const data = await apiCall('/tinyg/send', 'POST', { command: '!' });
        log('Feed hold activated', 'success');
    } catch (error) {
        log(`Feed hold failed: ${error.message}`, 'error');
    }
}

async function cycleStart() {
    try {
        log('Cycle start...', 'info');
        const data = await apiCall('/tinyg/send', 'POST', { command: '~' });
        log('Cycle started', 'success');
    } catch (error) {
        log(`Cycle start failed: ${error.message}`, 'error');
    }
}

async function emergencyStop() {
    try {
        log('EMERGENCY STOP!', 'error');
        const data = await apiCall('/tinyg/send', 'POST', { command: '%' });
        log('Emergency stop executed', 'error');
    } catch (error) {
        log(`E-STOP failed: ${error.message}`, 'error');
    }
}

// =================== Job Control Functions ===================

let loadedGcodeFile = null;

async function refreshJobGcodeFiles() {
    const select = document.getElementById('job-gcode-file');
    select.innerHTML = '<option value="">-- Loading... --</option>';

    try {
        const data = await apiCall('/list_gcode', 'GET');

        select.innerHTML = '<option value="">-- Select a file --</option>';

        if (data.files && data.files.length > 0) {
            data.files.forEach(file => {
                const option = document.createElement('option');
                option.value = file.name;
                option.textContent = `${file.name} (${formatBytes(file.size)})`;
                select.appendChild(option);
            });
        }
    } catch (error) {
        select.innerHTML = '<option value="">-- Error loading files --</option>';
        log(`Failed to load G-code files: ${error.message}`, 'error');
    }
}

async function uploadGcodeFile() {
    const fileInput = document.getElementById('gcode-upload-input');
    const file = fileInput.files[0];

    if (!file) {
        log('No file selected for upload', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        log(`Uploading ${file.name}...`, 'info');

        const response = await fetch('/api/gcode/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            log(`Uploaded: ${file.name}`, 'success');
            fileInput.value = '';  // Clear the input
            refreshJobGcodeFiles();  // Refresh the file list
        } else {
            log(`Upload failed: ${data.error || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        log(`Upload error: ${error.message}`, 'error');
    }
}

async function loadGcodeJob() {
    const select = document.getElementById('job-gcode-file');
    const filename = select.value;

    if (!filename) {
        log('No file selected to load', 'error');
        return;
    }

    try {
        log(`Loading ${filename}...`, 'info');

        const data = await apiCall('/tinyg/load_gcode', 'POST', { filepath: filename });

        if (data.success) {
            loadedGcodeFile = filename;
            document.getElementById('job-loaded-file').textContent = filename;
            document.getElementById('job-status').textContent = 'Ready to run';
            log(`Loaded: ${filename}`, 'success');
        } else {
            log(`Load failed: ${data.error || data.message}`, 'error');
        }
    } catch (error) {
        log(`Load error: ${error.message}`, 'error');
    }
}

async function runGcodeJob() {
    if (!loadedGcodeFile) {
        log('No job loaded. Load a G-code file first.', 'error');
        return;
    }

    try {
        log(`Running ${loadedGcodeFile}...`, 'info');
        document.getElementById('job-status').textContent = 'Running...';

        const data = await apiCall('/tinyg/run_gcode', 'POST', {});

        if (data.success) {
            log(`Job started: ${loadedGcodeFile}`, 'success');
        } else {
            document.getElementById('job-status').textContent = 'Error';
            log(`Run failed: ${data.error || data.message}`, 'error');
        }
    } catch (error) {
        document.getElementById('job-status').textContent = 'Error';
        log(`Run error: ${error.message}`, 'error');
    }
}

// Initialize job file list on page load
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(refreshJobGcodeFiles, 500);
});

// =================== G-code Console Functions ===================

function addToGcodeConsole(text, type = 'info') {
    const console = document.getElementById('gcode-console');
    const line = document.createElement('div');
    line.className = `console-line console-${type}`;
    line.textContent = text;
    console.appendChild(line);
    console.scrollTop = console.scrollHeight;

    // Keep only last 100 lines
    while (console.children.length > 100) {
        console.removeChild(console.firstChild);
    }
}

function clearGcodeConsole() {
    const console = document.getElementById('gcode-console');
    console.innerHTML = '<div class="console-line console-info">// Console cleared</div>';
}

// =================== MDI Terminal Enhancements ===================

// Command history
const mdiHistory = [];
const MAX_HISTORY = 50;
let historyIndex = -1;
let currentInput = '';

// G-code commands for autocomplete
const GCODE_COMMANDS = [
    { cmd: 'G0', desc: 'Rapid move' },
    { cmd: 'G1', desc: 'Linear interpolation' },
    { cmd: 'G2', desc: 'Clockwise arc' },
    { cmd: 'G3', desc: 'Counter-clockwise arc' },
    { cmd: 'G4', desc: 'Dwell (pause)' },
    { cmd: 'G10', desc: 'Set coordinate offset' },
    { cmd: 'G17', desc: 'XY plane selection' },
    { cmd: 'G18', desc: 'XZ plane selection' },
    { cmd: 'G19', desc: 'YZ plane selection' },
    { cmd: 'G20', desc: 'Inch units' },
    { cmd: 'G21', desc: 'Millimeter units' },
    { cmd: 'G28', desc: 'Return to home' },
    { cmd: 'G28.1', desc: 'Set home position' },
    { cmd: 'G30', desc: 'Return to secondary home' },
    { cmd: 'G38.2', desc: 'Probe toward workpiece' },
    { cmd: 'G40', desc: 'Cutter compensation off' },
    { cmd: 'G41', desc: 'Cutter compensation left' },
    { cmd: 'G42', desc: 'Cutter compensation right' },
    { cmd: 'G43', desc: 'Tool length offset' },
    { cmd: 'G49', desc: 'Tool length offset cancel' },
    { cmd: 'G53', desc: 'Machine coordinates' },
    { cmd: 'G54', desc: 'Work coordinate system 1' },
    { cmd: 'G55', desc: 'Work coordinate system 2' },
    { cmd: 'G56', desc: 'Work coordinate system 3' },
    { cmd: 'G57', desc: 'Work coordinate system 4' },
    { cmd: 'G58', desc: 'Work coordinate system 5' },
    { cmd: 'G59', desc: 'Work coordinate system 6' },
    { cmd: 'G80', desc: 'Cancel canned cycle' },
    { cmd: 'G90', desc: 'Absolute positioning' },
    { cmd: 'G91', desc: 'Incremental positioning' },
    { cmd: 'G92', desc: 'Set position' },
    { cmd: 'G92.1', desc: 'Reset G92 offsets' },
    { cmd: 'G93', desc: 'Inverse time feed mode' },
    { cmd: 'G94', desc: 'Units per minute feed mode' },
    { cmd: 'M0', desc: 'Program stop' },
    { cmd: 'M1', desc: 'Optional program stop' },
    { cmd: 'M2', desc: 'Program end' },
    { cmd: 'M3', desc: 'Spindle on clockwise' },
    { cmd: 'M4', desc: 'Spindle on counter-clockwise' },
    { cmd: 'M5', desc: 'Spindle stop' },
    { cmd: 'M6', desc: 'Tool change' },
    { cmd: 'M7', desc: 'Mist coolant on' },
    { cmd: 'M8', desc: 'Flood coolant on' },
    { cmd: 'M9', desc: 'Coolant off' },
    { cmd: 'M30', desc: 'Program end and rewind' },
    { cmd: 'M48', desc: 'Enable speed/feed override' },
    { cmd: 'M49', desc: 'Disable speed/feed override' },
    { cmd: 'F', desc: 'Feed rate' },
    { cmd: 'S', desc: 'Spindle speed' },
    { cmd: 'X', desc: 'X axis coordinate' },
    { cmd: 'Y', desc: 'Y axis coordinate' },
    { cmd: 'Z', desc: 'Z axis coordinate' },
    { cmd: 'I', desc: 'Arc X center offset' },
    { cmd: 'J', desc: 'Arc Y center offset' },
    { cmd: 'K', desc: 'Arc Z center offset' },
    { cmd: 'R', desc: 'Arc radius' },
    { cmd: 'P', desc: 'Dwell time / parameter' },
    { cmd: 'T', desc: 'Tool number' }
];

let autocompleteIndex = -1;
let autocompleteMatches = [];

function handleMDIKeydown(event) {
    const input = document.getElementById('gcode-input');
    const dropdown = document.getElementById('gcode-autocomplete');

    switch (event.key) {
        case 'ArrowUp':
            event.preventDefault();
            if (dropdown.style.display !== 'none' && autocompleteMatches.length > 0) {
                // Navigate autocomplete
                autocompleteIndex = Math.max(0, autocompleteIndex - 1);
                updateAutocompleteSelection();
            } else {
                // Navigate history
                navigateHistory(-1);
            }
            break;

        case 'ArrowDown':
            event.preventDefault();
            if (dropdown.style.display !== 'none' && autocompleteMatches.length > 0) {
                // Navigate autocomplete
                autocompleteIndex = Math.min(autocompleteMatches.length - 1, autocompleteIndex + 1);
                updateAutocompleteSelection();
            } else {
                // Navigate history
                navigateHistory(1);
            }
            break;

        case 'Tab':
            event.preventDefault();
            if (dropdown.style.display !== 'none' && autocompleteIndex >= 0) {
                // Select autocomplete item
                selectAutocomplete();
            } else {
                // Show/update autocomplete
                updateAutocomplete(input.value);
            }
            break;

        case 'Enter':
            if (dropdown.style.display !== 'none' && autocompleteIndex >= 0) {
                event.preventDefault();
                selectAutocomplete();
            } else {
                hideAutocomplete();
                sendGcode();
            }
            break;

        case 'Escape':
            hideAutocomplete();
            break;

        default:
            // Update autocomplete on text input
            setTimeout(() => updateAutocomplete(input.value), 10);
    }
}

function navigateHistory(direction) {
    const input = document.getElementById('gcode-input');

    if (mdiHistory.length === 0) return;

    // Save current input if starting history navigation
    if (historyIndex === -1 && direction === -1) {
        currentInput = input.value;
    }

    // Navigate
    historyIndex += direction;

    // Clamp
    if (historyIndex < -1) historyIndex = -1;
    if (historyIndex >= mdiHistory.length) historyIndex = mdiHistory.length - 1;

    // Update input
    if (historyIndex === -1) {
        input.value = currentInput;
    } else {
        input.value = mdiHistory[mdiHistory.length - 1 - historyIndex];
    }

    // Move cursor to end
    input.setSelectionRange(input.value.length, input.value.length);
}

function addToHistory(command) {
    // Don't add duplicates consecutively
    if (mdiHistory.length > 0 && mdiHistory[mdiHistory.length - 1] === command) {
        return;
    }

    mdiHistory.push(command);

    // Trim to max size
    while (mdiHistory.length > MAX_HISTORY) {
        mdiHistory.shift();
    }

    // Reset navigation
    historyIndex = -1;
    currentInput = '';

    // Update counter
    const countEl = document.getElementById('mdi-history-count');
    if (countEl) {
        countEl.textContent = mdiHistory.length;
    }
}

function updateAutocomplete(text) {
    const dropdown = document.getElementById('gcode-autocomplete');
    text = text.toUpperCase().trim();

    if (!text) {
        hideAutocomplete();
        return;
    }

    // Get the last token (word) for autocomplete
    const tokens = text.split(/\s+/);
    const lastToken = tokens[tokens.length - 1];

    if (!lastToken) {
        hideAutocomplete();
        return;
    }

    // Find matches
    autocompleteMatches = GCODE_COMMANDS.filter(c =>
        c.cmd.toUpperCase().startsWith(lastToken) && c.cmd.toUpperCase() !== lastToken
    );

    if (autocompleteMatches.length === 0) {
        hideAutocomplete();
        return;
    }

    // Build dropdown
    dropdown.innerHTML = autocompleteMatches.map((c, i) =>
        `<div class="autocomplete-item${i === autocompleteIndex ? ' selected' : ''}"
              onclick="selectAutocompleteItem(${i})">
            <span class="cmd">${c.cmd}</span>
            <span class="desc">${c.desc}</span>
        </div>`
    ).join('');

    dropdown.style.display = 'block';
    autocompleteIndex = 0;
    updateAutocompleteSelection();
}

function updateAutocompleteSelection() {
    const dropdown = document.getElementById('gcode-autocomplete');
    const items = dropdown.querySelectorAll('.autocomplete-item');

    items.forEach((item, i) => {
        item.classList.toggle('selected', i === autocompleteIndex);
    });

    // Scroll into view
    if (items[autocompleteIndex]) {
        items[autocompleteIndex].scrollIntoView({ block: 'nearest' });
    }
}

function selectAutocomplete() {
    if (autocompleteIndex < 0 || autocompleteIndex >= autocompleteMatches.length) return;

    selectAutocompleteItem(autocompleteIndex);
}

function selectAutocompleteItem(index) {
    const input = document.getElementById('gcode-input');
    const match = autocompleteMatches[index];

    if (!match) return;

    // Replace last token with selected command
    const text = input.value;
    const tokens = text.split(/\s+/);
    tokens[tokens.length - 1] = match.cmd;
    input.value = tokens.join(' ') + ' ';

    hideAutocomplete();
    input.focus();
}

function hideAutocomplete() {
    const dropdown = document.getElementById('gcode-autocomplete');
    if (dropdown) {
        dropdown.style.display = 'none';
    }
    autocompleteIndex = -1;
    autocompleteMatches = [];
}

async function sendGcode() {
    const input = document.getElementById('gcode-input');
    const command = input.value.trim();

    if (!command) return;

    // Add to history
    addToHistory(command);

    addToGcodeConsole(`>> ${command}`, 'sent');
    input.value = '';
    hideAutocomplete();

    try {
        const data = await apiCall('/tinyg/send', 'POST', { command: command });
        if (data.success) {
            addToGcodeConsole(`<< ${data.message}`, 'received');
        } else {
            addToGcodeConsole(`!! ${data.error || 'Command failed'}`, 'error');
        }
    } catch (error) {
        addToGcodeConsole(`!! Error: ${error.message}`, 'error');
    }
}

async function sendQuickGcode(command) {
    addToGcodeConsole(`>> ${command}`, 'sent');

    try {
        const data = await apiCall('/tinyg/send', 'POST', { command: command });
        if (data.success) {
            addToGcodeConsole(`<< ${data.message}`, 'received');
            log(`Sent: ${command}`, 'success');
        } else {
            addToGcodeConsole(`!! ${data.error || 'Command failed'}`, 'error');
        }
    } catch (error) {
        addToGcodeConsole(`!! Error: ${error.message}`, 'error');
    }
}

// =================== Position Display Updates ===================

function updatePositionDisplay(status) {
    if (!status.last_status) return;

    const sr = status.last_status;

    // Update modal status badges
    updateModalStatus(sr);

    // Update position values
    const posX = document.getElementById('pos-x');
    const posY = document.getElementById('pos-y');
    const posZ = document.getElementById('pos-z');

    if (posX) posX.textContent = formatNumber(sr.wx);
    if (posY) posY.textContent = formatNumber(sr.wy);
    if (posZ) posZ.textContent = formatNumber(sr.wz);

    // Update machine state
    const stateNames = {
        0: 'Init', 1: 'Ready', 2: 'Alarm', 3: 'Stop', 4: 'End',
        5: 'Run', 6: 'Hold', 7: 'Probe', 8: 'Cycle', 9: 'Homing'
    };
    const stateColors = {
        0: '#999', 1: '#10b981', 2: '#ef4444', 3: '#f59e0b', 4: '#666',
        5: '#3b82f6', 6: '#f59e0b', 7: '#8b5cf6', 8: '#3b82f6', 9: '#8b5cf6'
    };

    const machineState = document.getElementById('machine-state');
    if (machineState && sr.stat !== undefined) {
        machineState.textContent = stateNames[sr.stat] || 'Unknown';
        machineState.style.color = stateColors[sr.stat] || '#666';
    }

    // Update feed rate and velocity
    const feedRate = document.getElementById('feed-rate');
    const velocity = document.getElementById('velocity');
    const spindleSpeed = document.getElementById('spindle-speed');

    if (feedRate && sr.feed !== undefined) feedRate.textContent = sr.feed.toFixed(0);
    if (velocity && sr.vel !== undefined) velocity.textContent = sr.vel.toFixed(0);
    if (spindleSpeed && sr.sps !== undefined) spindleSpeed.textContent = sr.sps.toFixed(0);
}

function formatNumber(n) {
    if (n === null || n === undefined) return '---';
    return parseFloat(n).toFixed(4);
}

// =================== WebSocket Real-time Updates ===================

let socket = null;

function initWebSocket() {
    if (typeof io === 'undefined') {
        log('Socket.IO not loaded, using polling', 'info');
        return;
    }

    try {
        socket = io();

        socket.on('connect', () => {
            log('WebSocket connected', 'success');
        });

        socket.on('disconnect', () => {
            log('WebSocket disconnected', 'error');
        });

        socket.on('tinyg:status', (status) => {
            updatePositionDisplay({ last_status: status });
        });

        socket.on('tinyg:position', (pos) => {
            const posX = document.getElementById('pos-x');
            const posY = document.getElementById('pos-y');
            const posZ = document.getElementById('pos-z');

            if (posX) posX.textContent = formatNumber(pos.x);
            if (posY) posY.textContent = formatNumber(pos.y);
            if (posZ) posZ.textContent = formatNumber(pos.z);
        });

        socket.on('system:alert', (alert) => {
            log(`[${alert.severity.toUpperCase()}] ${alert.message}`, alert.severity === 'error' ? 'error' : 'info');
        });

    } catch (error) {
        log(`WebSocket init failed: ${error.message}`, 'error');
    }
}

// =================== WCS Functions ===================

async function selectWCS() {
    const wcs = document.getElementById('active-wcs').value;
    try {
        const data = await apiCall('/tinyg/send', 'POST', { command: wcs });
        if (data.success) {
            log(`Switched to ${wcs}`, 'success');
        }
    } catch (error) {
        log(`WCS switch failed: ${error.message}`, 'error');
    }
}

async function zeroWCS(axes) {
    const wcs = document.getElementById('active-wcs').value;
    const wcsNum = parseInt(wcs.replace('G', '')) - 53; // G54=1, G55=2, etc.

    if (!confirm(`Zero ${axes} axis/axes for ${wcs}?`)) return;

    let cmd = `G10 L2 P${wcsNum}`;
    if (axes.includes('X')) cmd += ' X0';
    if (axes.includes('Y')) cmd += ' Y0';
    if (axes.includes('Z')) cmd += ' Z0';

    try {
        const data = await apiCall('/tinyg/send', 'POST', { command: cmd });
        if (data.success) {
            log(`Zeroed ${axes} for ${wcs}`, 'success');
        }
    } catch (error) {
        log(`Zero WCS failed: ${error.message}`, 'error');
    }
}

async function setG92Offset() {
    if (!confirm('Set G92 temporary offset at current position?')) return;
    try {
        await apiCall('/tinyg/send', 'POST', { command: 'G92 X0 Y0 Z0' });
        log('G92 offset set', 'success');
    } catch (error) {
        log(`G92 set failed: ${error.message}`, 'error');
    }
}

async function clearG92Offset() {
    try {
        await apiCall('/tinyg/send', 'POST', { command: 'G92.1' });
        log('G92 offset cleared', 'success');
    } catch (error) {
        log(`G92 clear failed: ${error.message}`, 'error');
    }
}

// =================== Homing Functions ===================

async function homeAxis(axes) {
    if (!confirm(`Home ${axes} axis/axes?`)) return;

    let cmd = 'G28.2';
    if (axes.includes('X')) cmd += ' X0';
    if (axes.includes('Y')) cmd += ' Y0';
    if (axes.includes('Z')) cmd += ' Z0';

    try {
        log(`Homing ${axes}...`, 'info');
        await apiCall('/tinyg/send', 'POST', { command: cmd });
        log(`Homing ${axes} started`, 'success');
    } catch (error) {
        log(`Homing failed: ${error.message}`, 'error');
    }
}

let savedG28 = false;
let savedG30 = false;

async function setG28() {
    try {
        await apiCall('/tinyg/send', 'POST', { command: 'G28.1' });
        savedG28 = true;
        log('G28 position saved', 'success');
    } catch (error) {
        log(`G28 save failed: ${error.message}`, 'error');
    }
}

async function goToG28() {
    if (!savedG28) {
        log('G28 not set! Use Set button first.', 'error');
        return;
    }
    try {
        await apiCall('/tinyg/send', 'POST', { command: 'G28' });
        log('Moving to G28...', 'info');
    } catch (error) {
        log(`Go to G28 failed: ${error.message}`, 'error');
    }
}

async function setG30() {
    try {
        await apiCall('/tinyg/send', 'POST', { command: 'G30.1' });
        savedG30 = true;
        log('G30 position saved', 'success');
    } catch (error) {
        log(`G30 save failed: ${error.message}`, 'error');
    }
}

async function goToG30() {
    if (!savedG30) {
        log('G30 not set! Use Set button first.', 'error');
        return;
    }
    try {
        await apiCall('/tinyg/send', 'POST', { command: 'G30' });
        log('Moving to G30...', 'info');
    } catch (error) {
        log(`Go to G30 failed: ${error.message}`, 'error');
    }
}

async function safeZ() {
    const height = parseFloat(document.getElementById('safe-z-height').value);
    try {
        await apiCall('/tinyg/send', 'POST', { command: `G90 G0 Z${height}` });
        log(`Moving to safe Z (${height})...`, 'info');
    } catch (error) {
        log(`Safe Z failed: ${error.message}`, 'error');
    }
}

async function goToZero() {
    if (!confirm('Move to work zero (X0 Y0 Z0)?')) return;
    try {
        await apiCall('/tinyg/send', 'POST', { command: 'G90 G0 X0 Y0 Z0' });
        log('Moving to zero...', 'info');
    } catch (error) {
        log(`Go to zero failed: ${error.message}`, 'error');
    }
}

// =================== Probing Functions ===================

let lastProbePosition = null;

async function probeZ() {
    const travel = parseFloat(document.getElementById('probe-travel').value);
    const feed = parseFloat(document.getElementById('probe-feed').value);

    if (!confirm(`Probe Z down ${travel} mm at ${feed} mm/min?`)) return;

    try {
        const cmd = `G38.2 Z-${travel} F${feed}`;
        await apiCall('/tinyg/send', 'POST', { command: cmd });
        log('Probing Z...', 'info');
        lastProbePosition = 'Z';
    } catch (error) {
        log(`Probe Z failed: ${error.message}`, 'error');
    }
}

async function probeEdge(axis, direction) {
    const travel = parseFloat(document.getElementById('probe-travel').value);
    const feed = parseFloat(document.getElementById('probe-feed').value);
    const sign = direction > 0 ? '+' : '-';

    if (!confirm(`Probe ${axis}${sign} for ${travel} mm at ${feed} mm/min?`)) return;

    try {
        const dist = direction * travel;
        const cmd = `G38.2 ${axis}${dist} F${feed}`;
        await apiCall('/tinyg/send', 'POST', { command: cmd });
        log(`Probing ${axis}${sign}...`, 'info');
        lastProbePosition = axis;
    } catch (error) {
        log(`Probe ${axis} failed: ${error.message}`, 'error');
    }
}

async function setZeroAfterProbe(axis) {
    if (!lastProbePosition) {
        log('No recent probe! Probe first.', 'error');
        return;
    }

    const wcs = document.getElementById('active-wcs').value;
    const wcsNum = parseInt(wcs.replace('G', '')) - 53;

    try {
        const cmd = `G10 L2 P${wcsNum} ${axis}0`;
        await apiCall('/tinyg/send', 'POST', { command: cmd });
        log(`${axis} zero set after probe`, 'success');
    } catch (error) {
        log(`Set zero failed: ${error.message}`, 'error');
    }
}

// =================== Override Functions ===================

// Debounce timer for override commands
let overrideDebounceTimer = null;

async function updateOverride(type, value) {
    // Update display immediately
    document.getElementById(`${type}-override-value`).textContent = `${value}%`;

    // Debounce the actual command (wait 100ms after last change)
    clearTimeout(overrideDebounceTimer);
    overrideDebounceTimer = setTimeout(() => sendOverrideCommand(type, value), 100);
}

async function sendOverrideCommand(type, value) {
    // TinyG uses JSON commands for overrides:
    // - mfo: Motion Feed Override (0.05 to 2.0, where 1.0 = 100%)
    // - mto: Motion Traverse (Rapid) Override (0.05 to 1.0, where 1.0 = 100%)
    // Note: Spindle override isn't directly supported - would need to change S value

    let command = '';
    const overrideValue = value / 100;  // Convert percentage to decimal

    if (type === 'feed') {
        // Feed override: 0-200% maps to 0.05-2.0
        const mfo = Math.max(0.05, Math.min(2.0, overrideValue));
        command = `{"mfo":${mfo.toFixed(2)}}`;
    } else if (type === 'rapid') {
        // Rapid override: 0-100% maps to 0.05-1.0
        const mto = Math.max(0.05, Math.min(1.0, overrideValue));
        command = `{"mto":${mto.toFixed(2)}}`;
    } else if (type === 'spindle') {
        // Spindle override: TinyG doesn't have direct override
        // Log but don't send - would need to change S value during operation
        log(`Spindle override: ${value}% (note: takes effect on next S command)`, 'info');
        return;
    }

    if (command) {
        try {
            const response = await apiCall('/tinyg/send', {
                method: 'POST',
                body: JSON.stringify({ command })
            });
            if (response.success) {
                log(`${type.charAt(0).toUpperCase() + type.slice(1)} override set to ${value}%`, 'info');
            } else {
                log(`Override failed: ${response.error || response.message}`, 'error');
            }
        } catch (error) {
            log(`Override error: ${error.message}`, 'error');
        }
    }
}

function resetOverrides() {
    document.getElementById('feed-override').value = 100;
    document.getElementById('spindle-override').value = 100;
    document.getElementById('rapid-override').value = 100;
    document.getElementById('feed-override-value').textContent = '100%';
    document.getElementById('spindle-override-value').textContent = '100%';
    document.getElementById('rapid-override-value').textContent = '100%';

    // Send reset commands to TinyG
    sendOverrideCommand('feed', 100);
    sendOverrideCommand('rapid', 100);
    log('All overrides reset to 100%', 'info');
}

// =================== Status Console Functions ===================

function addToStatusConsole(text) {
    const console = document.getElementById('status-console');
    const timestamp = new Date().toLocaleTimeString();
    console.textContent += `\n[${timestamp}] ${text}`;
    console.scrollTop = console.scrollHeight;

    // Keep only last 50 lines
    const lines = console.textContent.split('\n');
    if (lines.length > 50) {
        console.textContent = lines.slice(-50).join('\n');
    }
}

function clearStatusConsole() {
    document.getElementById('status-console').textContent = 'Console cleared...';
}

// =================== Unified Recording Functions ===================

async function startAll() {
    const expName = document.getElementById('exp-name').value.trim();
    const trialNum = document.getElementById('trial-num').value;

    try {
        log('Starting all recording systems...', 'info');

        // Start TinyG polling
        const tinygData = await apiCall('/tinyg/start_polling', 'POST', {
            experiment_name: expName,
            trial_number: trialNum ? parseInt(trialNum) : null
        });

        // Start sensor recording (if ports selected)
        const sensorPorts = Array.from(document.getElementById('sensor-ports').selectedOptions)
            .map(opt => opt.value)
            .filter(v => v);
        if (sensorPorts.length > 0) {
            await apiCall('/sensor/start', 'POST', {
                ports: sensorPorts,
                experiment_name: expName,
                trial_number: trialNum ? parseInt(trialNum) : null
            });
        }

        // Start MCC recording
        await apiCall('/mcc/start', 'POST', {
            experiment_name: expName,
            trial_number: trialNum ? parseInt(trialNum) : null
        });

        // Show recording status
        const statusDiv = document.getElementById('recording-status');
        statusDiv.style.display = 'block';
        document.getElementById('recording-session').textContent = tinygData.session_ts || new Date().toISOString();

        log('All recording systems started!', 'success');
    } catch (error) {
        log(`Start all failed: ${error.message}`, 'error');
    }
}

async function stopAll() {
    try {
        log('Stopping all recording systems...', 'info');

        // Stop TinyG polling
        await apiCall('/tinyg/stop_polling', 'POST', {});

        // Stop sensor recording
        await apiCall('/sensor/stop', 'POST', {});

        // Stop MCC recording
        await apiCall('/mcc/stop', 'POST', {});

        // Hide recording status
        document.getElementById('recording-status').style.display = 'none';

        log('All recording systems stopped!', 'success');
    } catch (error) {
        log(`Stop all failed: ${error.message}`, 'error');
    }
}

// =================== Modal Status Update ===================

function updateModalStatus(status) {
    if (!status) return;

    const planeNames = { 0: 'G17', 1: 'G18', 2: 'G19' };
    const unitNames = { 0: 'G20', 1: 'G21' };
    const distNames = { 0: 'G90', 1: 'G91' };

    const plane = document.getElementById('modal-plane');
    const units = document.getElementById('modal-units');
    const dist = document.getElementById('modal-distance');

    if (plane && status.plane !== undefined) plane.textContent = planeNames[status.plane] || 'G17';
    if (units && status.unit !== undefined) units.textContent = unitNames[status.unit] || 'G21';
    if (dist && status.distance_mode !== undefined) dist.textContent = distNames[status.distance_mode] || 'G90';

    // Add to status console
    if (status.wx !== undefined) {
        addToStatusConsole(`X:${status.wx?.toFixed(3)} Y:${status.wy?.toFixed(3)} Z:${status.wz?.toFixed(3)} F:${status.feed || 0}`);
    }
}

// =================== Session Management Functions ===================

// Store current session state
let currentSessionId = null;
let selectedGcodeFile = null;

async function createSession() {
    const name = document.getElementById('session-name').value.trim();
    if (!name) {
        log('Session name is required', 'error');
        return;
    }

    const sources = [];
    if (document.getElementById('src-tinyg').checked) sources.push('tinyg');
    if (document.getElementById('src-sensors').checked) sources.push('sensors');
    if (document.getElementById('src-mcc').checked) sources.push('mcc');

    const gcodeFile = document.getElementById('session-gcode-file').value;

    try {
        const data = await apiCall('/api/session', 'POST', {
            name: name,
            gcode_file: gcodeFile || null,
            sources: sources
        });

        if (data.success) {
            currentSessionId = data.session.id;
            log(`Session created: ${data.session.id}`, 'success');
            document.getElementById('session-name').value = '';
            loadSessions();
        } else {
            log(`Failed to create session: ${data.error}`, 'error');
        }
    } catch (error) {
        log(`Create session failed: ${error.message}`, 'error');
    }
}

async function startCurrentSession() {
    if (!currentSessionId) {
        // Try to get from align select
        currentSessionId = document.getElementById('align-session-select').value;
    }
    if (!currentSessionId) {
        log('No session selected. Create a session first.', 'error');
        return;
    }

    try {
        const data = await apiCall(`/api/session/${currentSessionId}/start`, 'POST', {});

        if (data.success) {
            log(`Session started: ${currentSessionId}`, 'success');
            // Show active session alert
            document.getElementById('active-session-alert').style.display = 'block';
            document.getElementById('active-session-name').textContent = data.session.name;
            loadSessions();
        } else {
            log(`Failed to start session: ${data.error}`, 'error');
        }
    } catch (error) {
        log(`Start session failed: ${error.message}`, 'error');
    }
}

async function stopCurrentSession() {
    if (!currentSessionId) {
        // Check for active session
        try {
            const active = await apiCall('/api/session/active', 'GET');
            if (active.session) {
                currentSessionId = active.session.id;
            }
        } catch (e) { /* ignore */ }
    }

    if (!currentSessionId) {
        log('No active session to stop', 'error');
        return;
    }

    try {
        const data = await apiCall(`/api/session/${currentSessionId}/stop`, 'POST', {});

        if (data.success) {
            log(`Session stopped: ${currentSessionId} (${data.line_events_count} G-code events)`, 'success');
            // Hide active session alert
            document.getElementById('active-session-alert').style.display = 'none';
            loadSessions();
        } else {
            log(`Failed to stop session: ${data.error}`, 'error');
        }
    } catch (error) {
        log(`Stop session failed: ${error.message}`, 'error');
    }
}

async function loadSessions() {
    try {
        const data = await apiCall('/api/session', 'GET');

        if (data.success) {
            updateSessionList(data.sessions);
            updateAlignmentSelect(data.sessions);
            log(`Loaded ${data.count} sessions`, 'info');
        }
    } catch (error) {
        log(`Failed to load sessions: ${error.message}`, 'error');
    }
}

function updateSessionList(sessions) {
    const container = document.getElementById('session-history-list');

    if (!sessions || sessions.length === 0) {
        container.innerHTML = '<div style="color: #666; text-align: center; padding: 20px;">No sessions yet</div>';
        return;
    }

    const stateColors = {
        'created': '#3b82f6',
        'recording': '#10b981',
        'stopped': '#f59e0b',
        'completed': '#8b5cf6',
        'error': '#ef4444'
    };

    container.innerHTML = sessions.map(s => `
        <div style="padding: 10px; border-bottom: 1px solid #eee; cursor: pointer;"
             onclick="selectSession('${s.id}')">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <strong>${s.name}</strong>
                <span class="status-badge" style="background: ${stateColors[s.state] || '#666'}; color: white;">
                    ${s.state}
                </span>
            </div>
            <div style="font-size: 0.85rem; color: #666; margin-top: 5px;">
                ID: ${s.id.substring(0, 20)}...
            </div>
            <div style="font-size: 0.8rem; color: #888; margin-top: 3px;">
                Sources: ${s.sources.join(', ') || 'none'}
                ${s.gcode_file ? ' | G-code: ' + s.gcode_file.split('/').pop() : ''}
            </div>
        </div>
    `).join('');
}

function updateAlignmentSelect(sessions) {
    const select = document.getElementById('align-session-select');
    const stoppedSessions = sessions.filter(s => s.state === 'stopped' || s.state === 'completed');

    select.innerHTML = '<option value="">Select a stopped session...</option>';
    stoppedSessions.forEach(s => {
        select.innerHTML += `<option value="${s.id}">${s.name} (${s.state})</option>`;
    });
}

function selectSession(sessionId) {
    currentSessionId = sessionId;
    document.getElementById('align-session-select').value = sessionId;
    log(`Selected session: ${sessionId}`, 'info');
}

// =================== Data Alignment Functions ===================

// Store last aligned file for download
let lastAlignedFile = null;

function updateAlignmentUI() {
    const mode = document.getElementById('align-mode').value;

    // Hide all options
    document.getElementById('align-session-options').style.display = 'none';
    document.getElementById('align-standalone-options').style.display = 'none';
    document.getElementById('align-full-options').style.display = 'none';

    // Show relevant options based on mode
    if (mode === 'session') {
        document.getElementById('align-session-options').style.display = 'block';
        document.getElementById('gcode-line-option').style.display = 'block';
    } else if (mode === 'standalone') {
        document.getElementById('align-standalone-options').style.display = 'block';
        document.getElementById('gcode-line-option').style.display = 'none';
    } else if (mode === 'full') {
        document.getElementById('align-full-options').style.display = 'block';
        document.getElementById('gcode-line-option').style.display = 'none';
    }
}

async function runAlignment() {
    const mode = document.getElementById('align-mode').value;
    const method = document.getElementById('align-method').value;

    try {
        let data;

        if (mode === 'session') {
            // Session-based alignment
            const sessionId = document.getElementById('align-session-select').value;
            if (!sessionId) {
                log('Please select a session to align', 'error');
                return;
            }

            const masterSource = document.getElementById('align-master').value;
            const includeGcode = document.getElementById('align-include-gcode').checked;

            log(`Running session alignment for ${sessionId}...`, 'info');

            data = await apiCall(`/api/session/${sessionId}/align`, 'POST', {
                master_source: masterSource,
                interpolation_method: method,
                include_gcode_lines: includeGcode
            });

            if (data.success) {
                lastAlignedFile = `/api/session/${sessionId}/download`;
            }

        } else if (mode === 'standalone') {
            // Standalone alignment (sensor + MCC only)
            const sensorFile = document.getElementById('align-sensor-file').value;
            if (!sensorFile) {
                log('Please enter a sensor CSV file path', 'error');
                return;
            }

            const mccFile = document.getElementById('align-mcc-file').value;

            log(`Running standalone alignment...`, 'info');

            data = await apiCall('/api/session/align/standalone', 'POST', {
                sensor_file: sensorFile,
                mcc_file: mccFile || null,
                interpolation_method: method
            });

            if (data.success) {
                lastAlignedFile = data.aligned_file;
            }

        } else if (mode === 'full') {
            // Full alignment with G-code position matching
            const sensorFile = document.getElementById('align-full-sensor').value;
            const tinygFile = document.getElementById('align-full-tinyg').value;
            const gcodeFile = document.getElementById('align-full-gcode').value;
            const mccFile = document.getElementById('align-full-mcc').value;

            if (!sensorFile) {
                log('Please enter a sensor CSV file path', 'error');
                return;
            }
            if (!tinygFile) {
                log('Please enter a TinyG CSV file path', 'error');
                return;
            }
            if (!gcodeFile) {
                log('Please enter a G-code file path', 'error');
                return;
            }

            log(`Running full alignment with G-code position matching...`, 'info');

            data = await apiCall('/api/session/align/full', 'POST', {
                sensor_file: sensorFile,
                tinyg_file: tinygFile,
                gcode_file: gcodeFile,
                mcc_file: mccFile || null
            });

            if (data.success) {
                lastAlignedFile = data.aligned_file;
            }
        }

        // Handle result
        if (data.success) {
            log(`Alignment complete: ${data.stats.row_count} rows, ${data.stats.column_count} columns`, 'success');

            // Show alignment result
            const resultDiv = document.getElementById('alignment-result');
            resultDiv.style.display = 'block';
            document.getElementById('aligned-rows').textContent = data.stats.row_count;
            document.getElementById('aligned-cols').textContent = data.stats.column_count;
            document.getElementById('aligned-rate').textContent = data.stats.sample_rate_hz ? `${data.stats.sample_rate_hz} Hz` : 'N/A';

            // Store aligned file info
            resultDiv.dataset.alignedFile = lastAlignedFile;
            resultDiv.dataset.mode = mode;
        } else {
            log(`Alignment failed: ${data.error}`, 'error');
        }
    } catch (error) {
        log(`Alignment error: ${error.message}`, 'error');
    }
}

async function downloadAligned() {
    const resultDiv = document.getElementById('alignment-result');
    const mode = resultDiv.dataset.mode;
    const alignedFile = resultDiv.dataset.alignedFile;

    if (!alignedFile) {
        log('No aligned data available', 'error');
        return;
    }

    try {
        if (mode === 'session') {
            // Session download via API
            window.open(alignedFile, '_blank');
        } else {
            // Direct file download (for standalone/full modes)
            // Create a link to download the file
            const filename = alignedFile.split('/').pop();
            window.open(`/download_log?filename=${encodeURIComponent(filename)}`, '_blank');
        }
        log('Download started', 'success');
    } catch (error) {
        log(`Download failed: ${error.message}`, 'error');
    }
}

function openGcodeBrowserForAlign() {
    // Open G-code browser and set target to full alignment field
    openGcodeBrowser();
    // Store target field for selection
    window.gcodeBrowserTarget = 'align-full-gcode';
}

// =================== G-code File Browser Functions ===================

async function refreshGcodeFiles() {
    try {
        const data = await apiCall('/list_gcode', 'GET');

        if (data.success) {
            const select = document.getElementById('session-gcode-file');
            select.innerHTML = '<option value="">No G-code file</option>';

            data.files.forEach(file => {
                select.innerHTML += `<option value="${file.name}">${file.name} (${formatBytes(file.size)})</option>`;
            });

            log(`Found ${data.count} G-code files`, 'info');
        }
    } catch (error) {
        log(`Failed to load G-code files: ${error.message}`, 'error');
    }
}

function openGcodeBrowser() {
    const modal = document.getElementById('gcode-browser-modal');
    modal.style.display = 'block';
    loadGcodeFileList();
}

function closeGcodeBrowser() {
    document.getElementById('gcode-browser-modal').style.display = 'none';
    selectedGcodeFile = null;
}

async function loadGcodeFileList() {
    const container = document.getElementById('gcode-file-list');

    try {
        const data = await apiCall('/list_gcode', 'GET');

        if (data.success && data.files.length > 0) {
            container.innerHTML = data.files.map(file => `
                <div class="gcode-file-item" style="padding: 10px; border-bottom: 1px solid #eee; cursor: pointer; transition: background 0.2s;"
                     onclick="previewGcodeFile('${file.name}')"
                     onmouseover="this.style.background='#f0f0f0'"
                     onmouseout="this.style.background='transparent'">
                    <div style="display: flex; justify-content: space-between;">
                        <span>${file.name}</span>
                        <span style="color: #888; font-size: 0.9rem;">${formatBytes(file.size)}</span>
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div style="padding: 20px; text-align: center; color: #666;">No G-code files found</div>';
        }
    } catch (error) {
        container.innerHTML = '<div style="padding: 20px; text-align: center; color: #ef4444;">Failed to load files</div>';
    }
}

async function previewGcodeFile(filename) {
    selectedGcodeFile = filename;
    document.getElementById('select-gcode-btn').disabled = false;

    // Highlight selected
    document.querySelectorAll('.gcode-file-item').forEach(el => {
        el.style.background = el.textContent.includes(filename) ? '#e0e7ff' : 'transparent';
    });

    // Show preview (first 20 lines)
    const previewDiv = document.getElementById('gcode-preview');
    const previewPre = previewDiv.querySelector('pre');

    try {
        const response = await fetch(`/api/gcode/preview/${filename}?lines=20`);
        const data = await response.json();

        if (data.success) {
            previewPre.textContent = data.lines.join('\n');
            previewDiv.style.display = 'block';
        } else {
            previewPre.textContent = `// Preview not available: ${data.error}`;
            previewDiv.style.display = 'block';
        }
    } catch (error) {
        previewPre.textContent = `// Failed to load preview`;
        previewDiv.style.display = 'block';
    }
}

function selectGcodeFile() {
    if (selectedGcodeFile) {
        // Determine target field (default to session-gcode-file)
        const targetField = window.gcodeBrowserTarget || 'session-gcode-file';
        const targetElement = document.getElementById(targetField);

        if (targetElement) {
            targetElement.value = selectedGcodeFile;
            log(`Selected G-code file: ${selectedGcodeFile}`, 'info');
        }

        // Reset target
        window.gcodeBrowserTarget = null;
    }
    closeGcodeBrowser();
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// Initialize on page load
window.addEventListener('DOMContentLoaded', () => {
    // Restore dark mode preference
    if (localStorage.getItem('darkMode') === 'enabled') {
        document.body.classList.add('dark-mode');
    }

    log('Flask CNC SCADA System initialized', 'success');
    discoverPorts();
    refreshStatus();

    // Initialize WebSocket for real-time updates
    initWebSocket();

    // Load G-code files for session management
    refreshGcodeFiles();

    // Check for active session
    checkActiveSession();
});

async function checkActiveSession() {
    try {
        const data = await apiCall('/api/session/active', 'GET');
        if (data.success && data.session) {
            currentSessionId = data.session.id;
            document.getElementById('active-session-alert').style.display = 'block';
            document.getElementById('active-session-name').textContent = data.session.name;
            log(`Active session found: ${data.session.name}`, 'info');
        }
    } catch (error) {
        // No active session, that's fine
    }
}

// =================== Soft Limits Functions ===================

let softLimitsEnabled = true;

async function refreshLimits() {
    try {
        const data = await apiCall('/tinyg/limits', 'GET');

        if (data.success) {
            softLimitsEnabled = data.config.enabled;

            // Update status badge
            const statusEl = document.getElementById('soft-limits-status');
            const toggleBtn = document.getElementById('soft-limits-toggle');

            if (softLimitsEnabled) {
                statusEl.className = 'status-badge status-connected';
                statusEl.textContent = 'Enabled';
                toggleBtn.textContent = 'Disable';
            } else {
                statusEl.className = 'status-badge status-disconnected';
                statusEl.textContent = 'Disabled';
                toggleBtn.textContent = 'Enable';
            }

            // Update axis displays
            updateAxisLimitDisplay('x', data.config.x, data.position_status.x, data.position.x);
            updateAxisLimitDisplay('y', data.config.y, data.position_status.y, data.position.y);
            updateAxisLimitDisplay('z', data.config.z, data.position_status.z, data.position.z);

            // Update modal inputs
            document.getElementById('limit-x-min').value = data.config.x.min;
            document.getElementById('limit-x-max').value = data.config.x.max;
            document.getElementById('limit-x-enabled').checked = data.config.x.enabled;
            document.getElementById('limit-y-min').value = data.config.y.min;
            document.getElementById('limit-y-max').value = data.config.y.max;
            document.getElementById('limit-y-enabled').checked = data.config.y.enabled;
            document.getElementById('limit-z-min').value = data.config.z.min;
            document.getElementById('limit-z-max').value = data.config.z.max;
            document.getElementById('limit-z-enabled').checked = data.config.z.enabled;
            document.getElementById('limit-warning').value = Math.round(data.config.warning_threshold * 100);
            document.getElementById('limit-danger').value = Math.round(data.config.danger_threshold * 100);
        }
    } catch (error) {
        // Silently fail for limits refresh
    }
}

function updateAxisLimitDisplay(axis, config, status, position) {
    const zoneEl = document.getElementById(`${axis}-zone`);
    const fillEl = document.getElementById(`${axis}-fill`);
    const markerEl = document.getElementById(`${axis}-marker`);
    const minEl = document.getElementById(`${axis}-min`);
    const maxEl = document.getElementById(`${axis}-max`);
    const posEl = document.getElementById(`${axis}-pos`);

    // Update values
    minEl.textContent = config.min;
    maxEl.textContent = config.max;
    posEl.textContent = position.toFixed(2);

    // Update zone badge
    const zone = status.zone;
    zoneEl.textContent = zone;

    if (zone === 'safe') {
        zoneEl.style.background = '#d1fae5';
        zoneEl.style.color = '#059669';
        fillEl.style.background = '#10b981';
    } else if (zone === 'warning') {
        zoneEl.style.background = '#fef3c7';
        zoneEl.style.color = '#d97706';
        fillEl.style.background = '#f59e0b';
    } else if (zone === 'danger') {
        zoneEl.style.background = '#fee2e2';
        zoneEl.style.color = '#dc2626';
        fillEl.style.background = '#ef4444';
    } else {
        zoneEl.style.background = '#e5e7eb';
        zoneEl.style.color = '#6b7280';
        fillEl.style.background = '#9ca3af';
    }

    // Update fill and marker position
    const percentage = status.percentage || 50;
    fillEl.style.width = `${percentage}%`;
    markerEl.style.left = `${percentage}%`;
}

async function toggleSoftLimits() {
    try {
        const newState = !softLimitsEnabled;
        const data = await apiCall('/tinyg/limits/enable', 'POST', { enabled: newState });

        if (data.success) {
            softLimitsEnabled = newState;
            log(`Soft limits ${newState ? 'enabled' : 'disabled'}`, newState ? 'success' : 'info');
            refreshLimits();
        }
    } catch (error) {
        log(`Failed to toggle soft limits: ${error.message}`, 'error');
    }
}

function openLimitsSettings() {
    document.getElementById('limits-settings-modal').style.display = 'block';
    refreshLimits(); // Ensure latest values
}

function closeLimitsSettings() {
    document.getElementById('limits-settings-modal').style.display = 'none';
}

async function saveLimitsSettings() {
    try {
        // Save X axis
        await apiCall('/tinyg/limits', 'POST', {
            axis: 'x',
            min: parseFloat(document.getElementById('limit-x-min').value),
            max: parseFloat(document.getElementById('limit-x-max').value),
            enabled: document.getElementById('limit-x-enabled').checked
        });

        // Save Y axis
        await apiCall('/tinyg/limits', 'POST', {
            axis: 'y',
            min: parseFloat(document.getElementById('limit-y-min').value),
            max: parseFloat(document.getElementById('limit-y-max').value),
            enabled: document.getElementById('limit-y-enabled').checked
        });

        // Save Z axis
        await apiCall('/tinyg/limits', 'POST', {
            axis: 'z',
            min: parseFloat(document.getElementById('limit-z-min').value),
            max: parseFloat(document.getElementById('limit-z-max').value),
            enabled: document.getElementById('limit-z-enabled').checked
        });

        // Save thresholds
        await apiCall('/tinyg/limits/thresholds', 'POST', {
            warning: parseFloat(document.getElementById('limit-warning').value) / 100,
            danger: parseFloat(document.getElementById('limit-danger').value) / 100
        });

        log('Soft limits settings saved', 'success');
        closeLimitsSettings();
        refreshLimits();
    } catch (error) {
        log(`Failed to save limits: ${error.message}`, 'error');
    }
}

// =================== Dry Run Mode Functions ===================

let dryRunEnabled = false;
let dryRunPosition = { x: 0, y: 0, z: 0 };
let dryRunCommandCount = 0;

async function toggleDryRun() {
    const newState = !dryRunEnabled;

    try {
        const data = await apiCall('/tinyg/dryrun', 'POST', { enabled: newState });

        if (data.success) {
            dryRunEnabled = data.dry_run;

            const statusEl = document.getElementById('dry-run-status');
            const toggleBtn = document.getElementById('dry-run-toggle');
            const infoEl = document.getElementById('dry-run-info');

            if (dryRunEnabled) {
                statusEl.className = 'status-badge status-connected';
                statusEl.textContent = 'Enabled';
                toggleBtn.textContent = 'Disable';
                infoEl.style.display = 'block';
                dryRunPosition = data.position || { x: 0, y: 0, z: 0 };
                dryRunCommandCount = 0;
                log('Dry run mode ENABLED - commands will NOT move machine', 'info');
            } else {
                statusEl.className = 'status-badge status-disconnected';
                statusEl.textContent = 'Disabled';
                toggleBtn.textContent = 'Enable';
                infoEl.style.display = 'none';
                log('Dry run mode DISABLED', 'info');
            }

            updateDryRunDisplay();
        }
    } catch (error) {
        log(`Failed to toggle dry run mode: ${error.message}`, 'error');
    }
}

async function refreshDryRunStatus() {
    try {
        const data = await apiCall('/tinyg/dryrun', 'GET');

        if (data.success) {
            dryRunEnabled = data.dry_run;

            const statusEl = document.getElementById('dry-run-status');
            const toggleBtn = document.getElementById('dry-run-toggle');
            const infoEl = document.getElementById('dry-run-info');

            if (dryRunEnabled) {
                statusEl.className = 'status-badge status-connected';
                statusEl.textContent = 'Enabled';
                toggleBtn.textContent = 'Disable';
                infoEl.style.display = 'block';
                if (data.position) {
                    dryRunPosition = data.position;
                }
            } else {
                statusEl.className = 'status-badge status-disconnected';
                statusEl.textContent = 'Disabled';
                toggleBtn.textContent = 'Enable';
                infoEl.style.display = 'none';
            }

            updateDryRunDisplay();
        }
    } catch (error) {
        console.log('Dry run status check failed:', error.message);
    }
}

function updateDryRunDisplay() {
    const xEl = document.getElementById('dry-x');
    const yEl = document.getElementById('dry-y');
    const zEl = document.getElementById('dry-z');
    const countEl = document.getElementById('dry-count');

    if (xEl) xEl.textContent = dryRunPosition.x.toFixed(3);
    if (yEl) yEl.textContent = dryRunPosition.y.toFixed(3);
    if (zEl) zEl.textContent = dryRunPosition.z.toFixed(3);
    if (countEl) countEl.textContent = dryRunCommandCount;
}

async function simulateDryRunMove(gcode) {
    // Simulate a G-code command via API
    try {
        const data = await apiCall('/tinyg/dryrun/simulate', 'POST', { command: gcode });

        if (data.success) {
            dryRunPosition = data.position_after || dryRunPosition;
            dryRunCommandCount++;
            updateDryRunDisplay();
            log(`[DRY RUN] ${gcode} -> X:${dryRunPosition.x.toFixed(3)} Y:${dryRunPosition.y.toFixed(3)} Z:${dryRunPosition.z.toFixed(3)}`, 'info');
        }
    } catch (error) {
        // Fallback to local simulation if API fails
        const xMatch = gcode.match(/X([-\d.]+)/i);
        const yMatch = gcode.match(/Y([-\d.]+)/i);
        const zMatch = gcode.match(/Z([-\d.]+)/i);

        if (xMatch) dryRunPosition.x = parseFloat(xMatch[1]);
        if (yMatch) dryRunPosition.y = parseFloat(yMatch[1]);
        if (zMatch) dryRunPosition.z = parseFloat(zMatch[1]);

        dryRunCommandCount++;
        updateDryRunDisplay();
    }
}

async function resetDryRunPosition() {
    try {
        const data = await apiCall('/tinyg/dryrun/position', 'POST', { x: 0, y: 0, z: 0 });

        if (data.success) {
            dryRunPosition = data.position || { x: 0, y: 0, z: 0 };
            dryRunCommandCount = 0;
            updateDryRunDisplay();
            log('Dry run position reset to origin', 'info');
        }
    } catch (error) {
        log(`Failed to reset position: ${error.message}`, 'error');
    }
}

// =================== Coolant Control Functions ===================

let coolantState = { mist: false, flood: false };

async function sendCoolant(command) {
    try {
        log(`Sending coolant command: ${command}`, 'info');
        const data = await apiCall('/tinyg/send', 'POST', { command: command });

        if (data.success) {
            // Update state based on command
            if (command === 'M7') {
                coolantState.mist = true;
                document.getElementById('coolant-mist-status').textContent = 'ON';
                document.getElementById('coolant-mist-status').style.color = '#10b981';
            } else if (command === 'M8') {
                coolantState.flood = true;
                document.getElementById('coolant-flood-status').textContent = 'ON';
                document.getElementById('coolant-flood-status').style.color = '#3b82f6';
            } else if (command === 'M9') {
                coolantState.mist = false;
                coolantState.flood = false;
                document.getElementById('coolant-mist-status').textContent = 'OFF';
                document.getElementById('coolant-mist-status').style.color = '#999';
                document.getElementById('coolant-flood-status').textContent = 'OFF';
                document.getElementById('coolant-flood-status').style.color = '#999';
            }
            log(`Coolant ${command} executed`, 'success');
        }
    } catch (error) {
        log(`Coolant command failed: ${error.message}`, 'error');
    }
}

// =================== Auto-Reconnect Functions ===================

let autoReconnectEnabled = true;
let isReconnecting = false;

async function toggleAutoReconnect() {
    const newState = !autoReconnectEnabled;

    try {
        const data = await apiCall('/tinyg/reconnect', 'POST', { enabled: newState });

        if (data.success) {
            autoReconnectEnabled = data.enabled;
            updateReconnectUI();
            log(`Auto-reconnect ${autoReconnectEnabled ? 'enabled' : 'disabled'}`, 'info');
        }
    } catch (error) {
        log(`Failed to toggle auto-reconnect: ${error.message}`, 'error');
    }
}

async function cancelReconnect() {
    try {
        const data = await apiCall('/tinyg/reconnect/cancel', 'POST');

        if (data.success) {
            isReconnecting = false;
            updateReconnectUI();
            log('Reconnection cancelled', 'info');
        }
    } catch (error) {
        log(`Failed to cancel reconnect: ${error.message}`, 'error');
    }
}

async function refreshReconnectStatus() {
    try {
        const data = await apiCall('/tinyg/reconnect', 'GET');

        if (data.success) {
            autoReconnectEnabled = data.enabled;
            isReconnecting = data.reconnecting;
            updateReconnectUI();

            if (isReconnecting) {
                const msgEl = document.getElementById('reconnect-message');
                if (msgEl) {
                    msgEl.textContent = `Attempt ${data.attempts}/${data.max_attempts}...`;
                }
            }
        }
    } catch (error) {
        console.log('Reconnect status check failed:', error.message);
    }
}

function updateReconnectUI() {
    const statusEl = document.getElementById('reconnect-status');
    const toggleBtn = document.getElementById('reconnect-toggle');
    const progressEl = document.getElementById('reconnect-progress');

    if (statusEl) {
        if (isReconnecting) {
            statusEl.className = 'status-badge';
            statusEl.style.background = '#fef3c7';
            statusEl.style.color = '#92400e';
            statusEl.textContent = 'Reconnecting...';
        } else if (autoReconnectEnabled) {
            statusEl.className = 'status-badge status-connected';
            statusEl.style.background = '';
            statusEl.style.color = '';
            statusEl.textContent = 'Enabled';
        } else {
            statusEl.className = 'status-badge status-disconnected';
            statusEl.style.background = '';
            statusEl.style.color = '';
            statusEl.textContent = 'Disabled';
        }
    }

    if (toggleBtn) {
        toggleBtn.textContent = autoReconnectEnabled ? 'Disable' : 'Enable';
    }

    if (progressEl) {
        progressEl.style.display = isReconnecting ? 'block' : 'none';
    }
}

// =============================================================================
// 3D TOOLPATH PREVIEW FUNCTIONS
// =============================================================================

let currentToolpathPlot = null;
let backplotMode = false;
let backplotInterval = null;

// Initialize 3D plot with empty placeholder
function initToolpathPlot() {
    const plotDiv = document.getElementById('toolpath-plot');
    if (!plotDiv || typeof Plotly === 'undefined') {
        console.log('Plotly not loaded yet or plot div not found');
        return;
    }

    // Empty placeholder data
    const data = [{
        type: 'scatter3d',
        mode: 'lines',
        name: 'No Data',
        x: [0],
        y: [0],
        z: [0],
        line: { color: '#667eea', width: 2 }
    }];

    const layout = {
        title: { text: 'Toolpath Preview - Load G-Code to Display', font: { color: '#E0E0E0', size: 16 } },
        scene: {
            xaxis: { title: 'X (mm)', backgroundcolor: 'rgba(20, 30, 40, 0.9)', gridcolor: 'rgba(150, 150, 150, 0.3)', color: '#B0B0B0' },
            yaxis: { title: 'Y (mm)', backgroundcolor: 'rgba(20, 30, 40, 0.9)', gridcolor: 'rgba(150, 150, 150, 0.3)', color: '#B0B0B0' },
            zaxis: { title: 'Z (mm)', backgroundcolor: 'rgba(20, 30, 40, 0.9)', gridcolor: 'rgba(150, 150, 150, 0.3)', color: '#B0B0B0' },
            bgcolor: 'rgba(15, 25, 35, 1)',
            camera: { eye: { x: 1.5, y: 1.5, z: 1.0 }, up: { x: 0, y: 0, z: 1 } },
            aspectmode: 'data'
        },
        paper_bgcolor: 'rgba(20, 30, 40, 1)',
        plot_bgcolor: 'rgba(20, 30, 40, 1)',
        font: { color: '#E0E0E0' },
        legend: { bgcolor: 'rgba(30, 40, 50, 0.8)', bordercolor: '#4A5568', borderwidth: 1, font: { color: '#E0E0E0' } },
        margin: { l: 0, r: 0, t: 40, b: 0 }
    };

    const config = {
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ['toImage', 'sendDataToCloud']
    };

    Plotly.newPlot('toolpath-plot', data, layout, config);
    currentToolpathPlot = plotDiv;
}

// Load G-code from file browser for preview
function loadGcodeForPreview() {
    // Open G-code browser modal (reuse existing function)
    if (typeof openGcodeBrowser === 'function') {
        openGcodeBrowser();
    } else {
        addLog('G-code browser not available', 'error');
    }
}

// Preview G-code from textarea
async function previewGcodeFromTextarea() {
    const textarea = document.getElementById('preview-gcode-input');
    if (!textarea || !textarea.value.trim()) {
        addLog('No G-code entered for preview', 'error');
        return;
    }

    const gcode = textarea.value;
    await visualizeGcode(gcode);
}

// Main visualization function
async function visualizeGcode(gcode) {
    addLog('Generating 3D toolpath preview...', 'info');

    try {
        // Get soft limits for overlay
        let softLimits = null;
        try {
            const limitsResponse = await fetch('/api/tinyg/limits');
            if (limitsResponse.ok) {
                const limitsData = await limitsResponse.json();
                softLimits = limitsData.soft_limits;
            }
        } catch (e) {
            console.log('Could not fetch soft limits:', e);
        }

        // Get current position
        let currentPosition = null;
        try {
            const posResponse = await fetch('/api/tinyg/status');
            if (posResponse.ok) {
                const posData = await posResponse.json();
                currentPosition = {
                    x: posData.position?.x || 0,
                    y: posData.position?.y || 0,
                    z: posData.position?.z || 0
                };
            }
        } catch (e) {
            console.log('Could not fetch position:', e);
        }

        const response = await fetch('/api/gcode/visualize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                gcode: gcode,
                current_position: currentPosition,
                soft_limits: softLimits
            })
        });

        if (!response.ok) {
            throw new Error('Failed to generate visualization');
        }

        const data = await response.json();

        // Update plot
        Plotly.react('toolpath-plot', data.plot.data, data.plot.layout);

        // Update statistics
        updateToolpathStatistics(data.statistics);

        addLog('3D toolpath preview generated successfully', 'success');

    } catch (error) {
        addLog(`Preview error: ${error.message}`, 'error');
        console.error('Visualization error:', error);
    }
}

// Update toolpath statistics display
function updateToolpathStatistics(stats) {
    if (!stats) return;

    document.getElementById('toolpath-total-dist').textContent = `${stats.total_distance} mm`;
    document.getElementById('toolpath-rapid-dist').textContent = `${stats.rapid_distance} mm`;
    document.getElementById('toolpath-feed-dist').textContent = `${stats.feed_distance} mm`;
    document.getElementById('toolpath-arc-dist').textContent = `${stats.arc_distance} mm`;
    document.getElementById('toolpath-segments').textContent = stats.segment_count;

    if (stats.bounds) {
        const bounds = stats.bounds;
        document.getElementById('toolpath-bounds').textContent =
            `X: ${bounds.x[0]} to ${bounds.x[1]} | Y: ${bounds.y[0]} to ${bounds.y[1]} | Z: ${bounds.z[0]} to ${bounds.z[1]}`;
    }
}

// Refresh toolpath preview (reload current preview)
async function refreshToolpathPreview() {
    const textarea = document.getElementById('preview-gcode-input');
    if (textarea && textarea.value.trim()) {
        await visualizeGcode(textarea.value);
    } else {
        addLog('No G-code loaded to refresh', 'info');
    }
}

// Reset camera to default view
function resetPreviewCamera() {
    const plotDiv = document.getElementById('toolpath-plot');
    if (!plotDiv) return;

    const newCamera = {
        eye: { x: 1.5, y: 1.5, z: 1.0 },
        up: { x: 0, y: 0, z: 1 },
        center: { x: 0, y: 0, z: 0 }
    };

    Plotly.relayout('toolpath-plot', { 'scene.camera': newCamera });
    addLog('Camera reset to default view', 'info');
}

// Toggle backplot mode (real-time position tracking)
async function toggleBackplotMode() {
    backplotMode = !backplotMode;
    const textEl = document.getElementById('backplot-mode-text');

    if (backplotMode) {
        textEl.textContent = 'Disable Backplot';

        // Load current G-code into backplot manager
        const textarea = document.getElementById('preview-gcode-input');
        if (textarea && textarea.value.trim()) {
            try {
                await fetch('/api/gcode/backplot/load', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ gcode: textarea.value })
                });

                // Start periodic updates
                backplotInterval = setInterval(updateBackplot, 500);
                addLog('Backplot mode enabled - tracking machine position', 'success');
            } catch (error) {
                addLog('Failed to enable backplot mode', 'error');
                backplotMode = false;
                textEl.textContent = 'Enable Backplot';
            }
        } else {
            addLog('Load G-code first to enable backplot', 'error');
            backplotMode = false;
            textEl.textContent = 'Enable Backplot';
        }
    } else {
        textEl.textContent = 'Enable Backplot';
        if (backplotInterval) {
            clearInterval(backplotInterval);
            backplotInterval = null;
        }

        // Reset backplot
        await fetch('/api/gcode/backplot/reset', { method: 'POST' });
        addLog('Backplot mode disabled', 'info');
    }
}

// Update backplot with current position
async function updateBackplot() {
    if (!backplotMode) return;

    try {
        // Get current position from TinyG
        const posResponse = await fetch('/api/tinyg/status');
        if (!posResponse.ok) return;

        const posData = await posResponse.json();
        const position = {
            x: posData.position?.x || 0,
            y: posData.position?.y || 0,
            z: posData.position?.z || 0
        };

        // Get current line number if running a job
        const lineNumber = posData.current_line || 0;

        // Update backplot
        const response = await fetch('/api/gcode/backplot/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ position: position, line_number: lineNumber })
        });

        if (response.ok) {
            const data = await response.json();
            if (data.plot && data.plot.data) {
                Plotly.react('toolpath-plot', data.plot.data, data.plot.layout);
            }
        }
    } catch (error) {
        console.error('Backplot update error:', error);
    }
}

// =============================================================================
// MTConnect Functions (Industry 4.0)
// =============================================================================

async function refreshMTConnect() {
    try {
        const data = await apiCall('/mtconnect/status');
        if (data) {
            // Update status badge
            const statusEl = document.getElementById('mtconnect-status');
            if (statusEl && data.status === 'running') {
                statusEl.innerHTML = '<span class="status-badge status-connected">Active</span>';
            }

            // Update info fields
            if (data.device) {
                document.getElementById('mtc-device').textContent = data.device.name || '-';
                document.getElementById('mtc-items').textContent = data.device.data_items_count || '-';
            }
            if (data.buffer) {
                document.getElementById('mtc-sequence').textContent = data.buffer.last_sequence || '-';
            }
        }

        // Also fetch execution state
        const execData = await apiCall('/mtconnect/execution');
        if (execData) {
            document.getElementById('mtc-execution').textContent = execData.execution || 'UNAVAILABLE';
        }
    } catch (error) {
        console.error('MTConnect refresh error:', error);
    }
}

// =============================================================================
// OEE Functions (Overall Equipment Effectiveness)
// =============================================================================

async function refreshOEE() {
    try {
        const machineId = currentMachine !== 'all' ? currentMachine : 'machine-01';
        const data = await apiCall(`/analytics/oee/${machineId}?hours=24`);

        if (data && data.oee) {
            const oee = data.oee;
            document.getElementById('oee-overall').textContent = `${oee.oee?.toFixed(1) || 0}%`;
            document.getElementById('oee-availability').textContent = `${oee.availability?.toFixed(1) || 0}%`;
            document.getElementById('oee-performance').textContent = `${oee.performance?.toFixed(1) || 0}%`;
            document.getElementById('oee-quality').textContent = `${oee.quality?.toFixed(1) || 0}%`;

            // Color code OEE value
            const oeeEl = document.getElementById('oee-overall');
            const oeeVal = oee.oee || 0;
            if (oeeVal >= 85) {
                oeeEl.style.color = '#10b981'; // green
            } else if (oeeVal >= 60) {
                oeeEl.style.color = '#f59e0b'; // yellow
            } else {
                oeeEl.style.color = '#ef4444'; // red
            }
        }
    } catch (error) {
        console.error('OEE refresh error:', error);
    }
}

async function refreshFitness() {
    try {
        const data = await apiCall('/api/scheduler/machine-fitness');

        if (data && data.fitness_scores) {
            const machineId = currentMachine !== 'all' ? currentMachine : Object.keys(data.fitness_scores)[0];
            const score = data.fitness_scores[machineId];

            if (score) {
                const percentage = (score.total * 100).toFixed(1);
                document.getElementById('fitness-score').textContent = percentage + '%';
                document.getElementById('fitness-bar').style.width = percentage + '%';

                log(`Fitness ${machineId}: ${percentage}% (OEE: ${(score.oee_score*100).toFixed(0)}%, Util: ${(score.utilization_score*100).toFixed(0)}%)`, 'info');
            }
        }
    } catch (error) {
        console.error('Fitness refresh error:', error);
    }
}

// =============================================================================
// WebSocket MTConnect Streaming
// =============================================================================

function setupMTConnectStreaming() {
    if (typeof socket !== 'undefined') {
        // Listen for MTConnect sample updates
        socket.on('mtconnect:sample', (data) => {
            // Update sequence number in real-time
            if (data.sequence) {
                const seqEl = document.getElementById('mtc-sequence');
                if (seqEl) seqEl.textContent = data.sequence;
            }

            // Update execution state if it's an execution data item
            if (data.dataItemId && data.dataItemId.includes('_exec')) {
                const execEl = document.getElementById('mtc-execution');
                if (execEl) execEl.textContent = data.value || 'UNAVAILABLE';
            }
        });

        // Listen for availability changes
        socket.on('mtconnect:availability', (data) => {
            const statusEl = document.getElementById('mtconnect-status');
            if (statusEl) {
                if (data.available) {
                    statusEl.innerHTML = '<span class="status-badge status-connected">Active</span>';
                } else {
                    statusEl.innerHTML = '<span class="status-badge status-disconnected">Unavailable</span>';
                }
            }
        });

        // Listen for condition changes (alarms)
        socket.on('mtconnect:condition', (data) => {
            if (data.state === 'Fault' || data.state === 'Warning') {
                log(`MTConnect ${data.state}: ${data.type} - ${data.dataItemId}`, data.state === 'Fault' ? 'error' : 'warning');
            }
        });
    }
}

// =============================================================================
// Sensor Widget (Main Page Summary)
// =============================================================================

class SensorWidget {
    constructor() {
        this.sparklineData = {
            ax: [],
            temp: [],
            rms: []
        };
        this.maxPoints = 50;
        this.initialized = false;
    }

    init() {
        if (this.initialized) return;
        this.initialized = true;

        // Initialize sparkline charts
        this.initSparklines();

        // Fetch initial health data
        this.refreshHealth();

        // Subscribe to Socket.IO events if available
        if (typeof socket !== 'undefined') {
            socket.on('sensor:health', (data) => {
                this.updateHealth(data);
            });

            socket.on('sensor:data', (data) => {
                this.updateSparklines(data);
            });

            socket.on('sensor:all', (data) => {
                if (data.sensors) {
                    data.sensors.forEach(sensor => this.updateSparklines(sensor));
                }
            });
        }

        // Periodic health refresh
        setInterval(() => this.refreshHealth(), 10000);
    }

    initSparklines() {
        const sparklineLayout = {
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            margin: { t: 0, r: 0, b: 0, l: 0 },
            xaxis: { visible: false },
            yaxis: { visible: false },
            showlegend: false
        };

        const sparklineConfig = {
            displayModeBar: false,
            responsive: true
        };

        // Initialize empty sparklines
        ['sparkline-ax', 'sparkline-temp', 'sparkline-rms'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                Plotly.newPlot(el, [{
                    y: [],
                    type: 'scatter',
                    mode: 'lines',
                    line: { color: '#3b82f6', width: 1.5 }
                }], sparklineLayout, sparklineConfig);
            }
        });
    }

    async refreshHealth() {
        try {
            const response = await fetch('/api/sensors/health');
            const data = await response.json();

            if (data.success) {
                this.updateHealth(data);
            }
        } catch (error) {
            console.error('Failed to refresh sensor health:', error);
        }
    }

    updateHealth(data) {
        const onlineEl = document.getElementById('sensor-widget-online');
        const pendingEl = document.getElementById('sensor-widget-pending');
        const offlineEl = document.getElementById('sensor-widget-offline');

        if (onlineEl) onlineEl.textContent = data.online || 0;
        if (pendingEl) pendingEl.textContent = data.pending || 0;
        if (offlineEl) offlineEl.textContent = data.offline || 0;
    }

    updateSparklines(data) {
        const timestamp = Date.now();

        // Update Ax sparkline
        if (data.Ax !== undefined) {
            this.sparklineData.ax.push({ x: timestamp, y: data.Ax });
            if (this.sparklineData.ax.length > this.maxPoints) {
                this.sparklineData.ax.shift();
            }
            this.updateSparkline('sparkline-ax', this.sparklineData.ax);
        }

        // Update Temperature sparkline
        if (data.Temperature !== undefined) {
            this.sparklineData.temp.push({ x: timestamp, y: data.Temperature });
            if (this.sparklineData.temp.length > this.maxPoints) {
                this.sparklineData.temp.shift();
            }
            this.updateSparkline('sparkline-temp', this.sparklineData.temp);
        }

        // Update RMS sparkline
        if (data.RMS !== undefined) {
            this.sparklineData.rms.push({ x: timestamp, y: data.RMS });
            if (this.sparklineData.rms.length > this.maxPoints) {
                this.sparklineData.rms.shift();
            }
            this.updateSparkline('sparkline-rms', this.sparklineData.rms);
        }
    }

    updateSparkline(elementId, data) {
        const el = document.getElementById(elementId);
        if (!el || data.length === 0) return;

        Plotly.react(el, [{
            y: data.map(d => d.y),
            type: 'scatter',
            mode: 'lines',
            line: { color: '#3b82f6', width: 1.5 }
        }], {
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            margin: { t: 0, r: 0, b: 0, l: 0 },
            xaxis: { visible: false },
            yaxis: { visible: false },
            showlegend: false
        });
    }
}

// Global sensor widget instance
const sensorWidget = new SensorWidget();

// Initialize soft limits, dry run, auto-reconnect, 3D preview, and Industry 4.0 on page load
window.addEventListener('DOMContentLoaded', () => {
    // Initialize machine selector from localStorage
    initMachineSelector();

    // Refresh limits status
    setTimeout(refreshLimits, 1000);

    // Refresh dry run status
    setTimeout(refreshDryRunStatus, 1000);

    // Refresh reconnect status
    setTimeout(refreshReconnectStatus, 1000);

    // Initialize 3D toolpath plot
    setTimeout(initToolpathPlot, 500);

    // Initialize MTConnect and OEE
    setTimeout(refreshMTConnect, 1500);
    setTimeout(refreshOEE, 2000);
    setTimeout(refreshFitness, 2500);

    // Setup MTConnect WebSocket streaming
    setTimeout(setupMTConnectStreaming, 1000);

    // Initialize sensor widget
    setTimeout(() => sensorWidget.init(), 1500);

    // Refresh limits periodically
    setInterval(refreshLimits, 5000);

    // Refresh dry run status periodically
    setInterval(refreshDryRunStatus, 5000);

    // Refresh reconnect status periodically
    setInterval(refreshReconnectStatus, 3000);

    // Refresh OEE and MTConnect periodically
    setInterval(refreshMTConnect, 10000);
    setInterval(refreshOEE, 30000);
});
