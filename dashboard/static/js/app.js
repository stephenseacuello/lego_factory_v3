/**
 * LEGO MCP Dashboard - Main Application JavaScript
 * Version 7.0
 */

// =============================================================================
// APP NAMESPACE
// =============================================================================

const App = {
    // Configuration
    config: {
        apiBase: '/api',
        wsUrl: null,
        refreshInterval: 30000
    },
    
    // State
    state: {
        theme: 'auto',
        sidebarCollapsed: false,
        connected: false,
        loading: false
    },
    
    // WebSocket
    socket: null,
    
    // Initialize
    init() {
        this.initTheme();
        this.initSidebar();
        this.initSearch();
        this.initWebSocket();
        this.initTooltips();
        this.initKeyboardShortcuts();
        this.initLoadingStates();
        this.initHelpModal();
        
        console.log('🧱 LEGO MCP Dashboard v7.0 initialized');
    },
    
    // ==========================================================================
    // KEYBOARD SHORTCUTS
    // ==========================================================================
    
    initKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ignore if typing in input/textarea
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                if (e.key === 'Escape') {
                    e.target.blur();
                }
                return;
            }
            
            // Ignore if modal is open
            if (document.querySelector('.modal-overlay[style*="flex"]')) {
                if (e.key === 'Escape') {
                    this.closeModal();
                }
                return;
            }
            
            // Navigation shortcuts
            const shortcuts = {
                'w': '/workspace/',
                's': '/scan/',
                'c': '/collection/',
                'b': '/builds/',
                'i': '/insights/',
                'k': '/catalog/',
                'h': '/history/',
                't': '/tools/',
            };
            
            const key = e.key.toLowerCase();
            
            // ? or F1 = Help
            if (key === '?' || e.key === 'F1') {
                e.preventDefault();
                this.showHelpModal();
                return;
            }
            
            // / = Focus search
            if (key === '/') {
                e.preventDefault();
                document.getElementById('globalSearch')?.focus();
                return;
            }
            
            // Escape = Close modals
            if (e.key === 'Escape') {
                this.closeModal();
                return;
            }
            
            // Navigation (without modifiers)
            if (!e.ctrlKey && !e.altKey && !e.metaKey && shortcuts[key]) {
                // Only if not already on that page
                if (!window.location.pathname.startsWith(shortcuts[key])) {
                    window.location.href = shortcuts[key];
                }
            }
            
            // Ctrl+Z = Undo
            if (e.ctrlKey && key === 'z' && !e.shiftKey) {
                e.preventDefault();
                this.undo();
            }
            
            // Ctrl+Shift+Z or Ctrl+Y = Redo
            if ((e.ctrlKey && e.shiftKey && key === 'z') || (e.ctrlKey && key === 'y')) {
                e.preventDefault();
                this.redo();
            }
        });
    },
    
    // Undo/Redo
    undo() {
        fetch('/api/mcp/execute', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({tool: 'undo', params: {}})
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                this.toast('Undone', 'success');
            }
        })
        .catch(() => this.toast('Undo failed', 'error'));
    },
    
    redo() {
        fetch('/api/mcp/execute', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({tool: 'redo', params: {}})
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                this.toast('Redone', 'success');
            }
        })
        .catch(() => this.toast('Redo failed', 'error'));
    },
    
    // ==========================================================================
    // LOADING STATES
    // ==========================================================================
    
    initLoadingStates() {
        // Add loading class to buttons when clicked
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('button[data-loading], .btn[data-loading]');
            if (btn && !btn.classList.contains('loading')) {
                this.setButtonLoading(btn, true);
            }
        });
    },
    
    setButtonLoading(btn, loading) {
        if (loading) {
            btn.classList.add('loading');
            btn.dataset.originalText = btn.innerHTML;
            btn.innerHTML = '<span class="spinner"></span> Loading...';
            btn.disabled = true;
        } else {
            btn.classList.remove('loading');
            btn.innerHTML = btn.dataset.originalText || btn.innerHTML;
            btn.disabled = false;
        }
    },
    
    // Global loading overlay
    showLoading(message = 'Loading...') {
        let overlay = document.getElementById('loadingOverlay');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.id = 'loadingOverlay';
            overlay.className = 'loading-overlay';
            overlay.innerHTML = `
                <div class="loading-content">
                    <div class="loading-spinner"></div>
                    <div class="loading-message">${message}</div>
                </div>
            `;
            document.body.appendChild(overlay);
        } else {
            overlay.querySelector('.loading-message').textContent = message;
        }
        overlay.style.display = 'flex';
        this.state.loading = true;
    },
    
    hideLoading() {
        const overlay = document.getElementById('loadingOverlay');
        if (overlay) {
            overlay.style.display = 'none';
        }
        this.state.loading = false;
    },
    
    // ==========================================================================
    // HELP MODAL
    // ==========================================================================
    
    initHelpModal() {
        // Create help modal if it doesn't exist
        if (!document.getElementById('helpModal')) {
            const modal = document.createElement('div');
            modal.id = 'helpModal';
            modal.className = 'modal-overlay';
            modal.style.display = 'none';
            modal.innerHTML = `
                <div class="modal modal-medium">
                    <div class="modal-header">
                        <h3>⌨️ Keyboard Shortcuts</h3>
                        <button class="modal-close" onclick="App.closeHelpModal()">&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="shortcuts-grid">
                            <div class="shortcut-section">
                                <h4>Navigation</h4>
                                <div class="shortcut"><kbd>W</kbd> Workspace</div>
                                <div class="shortcut"><kbd>S</kbd> Scan</div>
                                <div class="shortcut"><kbd>C</kbd> Collection</div>
                                <div class="shortcut"><kbd>B</kbd> Builds</div>
                                <div class="shortcut"><kbd>I</kbd> Insights</div>
                                <div class="shortcut"><kbd>K</kbd> Catalog</div>
                            </div>
                            <div class="shortcut-section">
                                <h4>Actions</h4>
                                <div class="shortcut"><kbd>/</kbd> Search</div>
                                <div class="shortcut"><kbd>?</kbd> Help</div>
                                <div class="shortcut"><kbd>Esc</kbd> Close modal</div>
                                <div class="shortcut"><kbd>Ctrl+Z</kbd> Undo</div>
                                <div class="shortcut"><kbd>Ctrl+Shift+Z</kbd> Redo</div>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-primary" onclick="App.closeHelpModal()">Got it!</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }
    },
    
    showHelpModal() {
        document.getElementById('helpModal').style.display = 'flex';
    },
    
    closeHelpModal() {
        document.getElementById('helpModal').style.display = 'none';
    },
    
    // ==========================================================================
    // THEME
    // ==========================================================================
    
    initTheme() {
        const saved = localStorage.getItem('theme') || 'auto';
        this.setTheme(saved);
        
        document.getElementById('themeToggle')?.addEventListener('click', () => {
            const themes = ['auto', 'light', 'dark'];
            const current = document.documentElement.dataset.theme || 'auto';
            const next = themes[(themes.indexOf(current) + 1) % themes.length];
            this.setTheme(next);
        });
    },
    
    setTheme(theme) {
        document.documentElement.dataset.theme = theme;
        localStorage.setItem('theme', theme);
        this.state.theme = theme;
        
        // Update icon
        const toggle = document.getElementById('themeToggle');
        if (toggle) {
            const icons = { auto: '🌓', light: '☀️', dark: '🌙' };
            const icon = toggle.querySelector('.theme-icon');
            if (icon) icon.textContent = icons[theme] || '🌓';
        }
        
        // Update server
        fetch('/settings/theme', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({theme})
        }).catch(() => {});
    },
    
    // ==========================================================================
    // SIDEBAR
    // ==========================================================================
    
    initSidebar() {
        const toggle = document.getElementById('sidebarToggle');
        const sidebar = document.getElementById('sidebar');
        
        if (toggle && sidebar) {
            // Load saved state
            const collapsed = localStorage.getItem('sidebarCollapsed') === 'true';
            if (collapsed) {
                sidebar.classList.add('collapsed');
            }
            
            toggle.addEventListener('click', () => {
                sidebar.classList.toggle('collapsed');
                const isCollapsed = sidebar.classList.contains('collapsed');
                localStorage.setItem('sidebarCollapsed', isCollapsed);
            });
        }
    },
    
    // ==========================================================================
    // SEARCH
    // ==========================================================================
    
    initSearch() {
        const searchInput = document.getElementById('globalSearch');
        const searchResults = document.getElementById('searchResults');
        
        if (!searchInput || !searchResults) return;
        
        let debounceTimer;
        
        searchInput.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            const query = e.target.value.trim();
            
            if (query.length < 2) {
                searchResults.style.display = 'none';
                return;
            }
            
            debounceTimer = setTimeout(() => {
                fetch(`/catalog/search?q=${encodeURIComponent(query)}&limit=8`)
                    .then(r => r.json())
                    .then(results => {
                        if (results.length > 0) {
                            searchResults.innerHTML = results.map(brick => `
                                <a href="/catalog/${brick.id}" class="search-result">
                                    <span class="result-name">${brick.name}</span>
                                    <span class="result-dims">${brick.studs_x}×${brick.studs_y}</span>
                                </a>
                            `).join('');
                            searchResults.style.display = 'block';
                        } else {
                            searchResults.innerHTML = '<div class="search-empty">No results</div>';
                            searchResults.style.display = 'block';
                        }
                    })
                    .catch(() => {
                        searchResults.style.display = 'none';
                    });
            }, 200);
        });
        
        // Hide on click outside
        document.addEventListener('click', (e) => {
            if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
                searchResults.style.display = 'none';
            }
        });
        
        // Keyboard navigation
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                searchResults.style.display = 'none';
                searchInput.blur();
            }
        });
    },
    
    // ==========================================================================
    // WEBSOCKET - Real-time Updates
    // ==========================================================================

    initWebSocket() {
        // Check if Socket.IO is available
        if (typeof io === 'undefined') {
            console.warn('Socket.IO not loaded - falling back to polling');
            this.startPolling();
            return;
        }

        try {
            // Connect to Socket.IO server
            this.socket = io({
                transports: ['websocket', 'polling'],
                reconnection: true,
                reconnectionDelay: 1000,
                reconnectionDelayMax: 5000,
                reconnectionAttempts: 10
            });

            // Connection events
            this.socket.on('connect', () => {
                console.log('WebSocket connected');
                this.state.connected = true;
                this.updateConnectionStatus(true);
                this.toast('Connected to server', 'success', 2000);
            });

            this.socket.on('disconnect', (reason) => {
                console.log('WebSocket disconnected:', reason);
                this.state.connected = false;
                this.updateConnectionStatus(false);
                if (reason !== 'io client disconnect') {
                    this.toast('Connection lost - reconnecting...', 'warning');
                }
            });

            this.socket.on('connect_error', (error) => {
                console.error('WebSocket connection error:', error);
                this.state.connected = false;
                this.updateConnectionStatus(false);
            });

            // Real-time event handlers
            this.socket.on('status_update', (data) => {
                this.handleStatusUpdate(data);
            });

            this.socket.on('operation_progress', (data) => {
                this.handleOperationProgress(data);
            });

            this.socket.on('file_created', (data) => {
                this.handleFileCreated(data);
            });

            this.socket.on('brick_created', (data) => {
                this.handleBrickCreated(data);
            });

            this.socket.on('error', (data) => {
                this.handleServerError(data);
            });

        } catch (error) {
            console.error('Failed to initialize WebSocket:', error);
            this.startPolling();
        }
    },

    updateConnectionStatus(connected) {
        const statusDots = document.querySelectorAll('.status-dot');
        // Update UI to reflect connection state
        document.body.classList.toggle('ws-connected', connected);
        document.body.classList.toggle('ws-disconnected', !connected);
    },

    handleStatusUpdate(data) {
        // Update service status indicators
        if (data.services) {
            this.updateStatusIndicators({ services: data.services });
        }
    },

    handleOperationProgress(data) {
        // Show/update progress indicator
        const { operation_id, step, total_steps, message, percent } = data;

        let progressContainer = document.getElementById('progressContainer');
        if (!progressContainer) {
            progressContainer = document.createElement('div');
            progressContainer.id = 'progressContainer';
            progressContainer.className = 'progress-container';
            document.body.appendChild(progressContainer);
        }

        let progressEl = document.getElementById(`progress-${operation_id}`);
        if (!progressEl) {
            progressEl = document.createElement('div');
            progressEl.id = `progress-${operation_id}`;
            progressEl.className = 'operation-progress';
            progressContainer.appendChild(progressEl);
        }

        if (percent >= 100) {
            // Complete - remove after delay
            progressEl.classList.add('complete');
            setTimeout(() => progressEl.remove(), 2000);
        } else {
            progressEl.innerHTML = `
                <div class="progress-info">
                    <span class="progress-message">${message || 'Processing...'}</span>
                    <span class="progress-percent">${Math.round(percent)}%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${percent}%"></div>
                </div>
                ${step && total_steps ? `<span class="progress-steps">Step ${step}/${total_steps}</span>` : ''}
            `;
        }
    },

    handleFileCreated(data) {
        const { path, type, size_kb } = data;
        const filename = path.split('/').pop();
        this.toast(`File created: ${filename} (${size_kb} KB)`, 'success');

        // Refresh file list if on files page
        if (window.location.pathname.includes('/files')) {
            this.refreshFileList?.();
        }
    },

    handleBrickCreated(data) {
        const { component_name, dimensions } = data;
        this.toast(`Brick created: ${component_name}`, 'success');
    },

    handleServerError(data) {
        const { message, code } = data;
        this.toast(`Error: ${message}`, 'error');
        console.error('Server error:', code, message);
    },

    startPolling() {
        // Fallback polling if WebSocket unavailable
        console.log('Using polling fallback (30s interval)');
        setInterval(() => {
            this.checkStatus();
        }, this.config.refreshInterval);
    },

    checkStatus() {
        fetch('/api/status')
            .then(r => r.json())
            .then(status => {
                this.updateStatusIndicators(status);
            })
            .catch(() => {});
    },

    updateStatusIndicators(status) {
        const indicators = document.querySelectorAll('.status-dot');
        indicators.forEach(dot => {
            const service = dot.title?.split(':')[0]?.toLowerCase();
            if (service && status.services?.[service]) {
                const s = status.services[service].status;
                dot.className = 'status-dot ' + s;
                dot.title = `${service}: ${s}`;
            }
        });
    },
    
    // ==========================================================================
    // TOOLTIPS
    // ==========================================================================
    
    initTooltips() {
        // Simple tooltip implementation
        document.querySelectorAll('[title]').forEach(el => {
            // Could enhance with custom tooltip library
        });
    },
    
    // ==========================================================================
    // TOAST NOTIFICATIONS
    // ==========================================================================
    
    toast(message, type = 'info', duration = 3000) {
        const container = document.getElementById('toastContainer');
        if (!container) return;
        
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icon = {
            success: '✓',
            error: '✗',
            warning: '⚠',
            info: 'ℹ'
        }[type] || 'ℹ';
        
        toast.innerHTML = `
            <span class="toast-icon">${icon}</span>
            <span class="toast-message">${message}</span>
            <button class="toast-close" onclick="this.parentElement.remove()">×</button>
        `;
        
        container.appendChild(toast);
        
        // Animate in
        setTimeout(() => toast.classList.add('show'), 10);
        
        // Auto dismiss
        if (duration > 0) {
            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => toast.remove(), 300);
            }, duration);
        }
    },
    
    // ==========================================================================
    // MODAL
    // ==========================================================================
    
    modal(title, content, buttons = []) {
        const overlay = document.getElementById('modalOverlay');
        const modal = document.getElementById('modal');
        const titleEl = document.getElementById('modalTitle');
        const bodyEl = document.getElementById('modalBody');
        const footerEl = document.getElementById('modalFooter');
        
        if (!overlay || !modal) return;
        
        titleEl.textContent = title;
        bodyEl.innerHTML = content;
        
        // Build footer buttons
        footerEl.innerHTML = '';
        buttons.forEach(btn => {
            const button = document.createElement('button');
            button.className = `btn ${btn.class || 'btn-secondary'}`;
            button.textContent = btn.text;
            button.onclick = () => {
                if (btn.action === 'close') {
                    this.closeModal();
                } else if (typeof btn.action === 'function') {
                    btn.action();
                }
            };
            footerEl.appendChild(button);
        });
        
        // Show modal
        overlay.classList.add('show');
        
        // Close handlers
        document.getElementById('modalClose').onclick = () => this.closeModal();
        overlay.onclick = (e) => {
            if (e.target === overlay) this.closeModal();
        };
    },
    
    closeModal() {
        const overlay = document.getElementById('modalOverlay');
        if (overlay) {
            overlay.classList.remove('show');
        }
    },
    
    // ==========================================================================
    // API HELPERS
    // ==========================================================================
    
    async api(endpoint, options = {}) {
        const url = this.config.apiBase + endpoint;
        
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },
    
    async get(endpoint) {
        return this.api(endpoint);
    },
    
    async post(endpoint, data) {
        return this.api(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    // ==========================================================================
    // UTILITIES
    // ==========================================================================
    
    formatSize(bytes) {
        const units = ['B', 'KB', 'MB', 'GB'];
        let size = bytes;
        let unit = 0;
        while (size >= 1024 && unit < units.length - 1) {
            size /= 1024;
            unit++;
        }
        return `${size.toFixed(1)} ${units[unit]}`;
    },
    
    formatDate(timestamp) {
        const date = new Date(timestamp * 1000);
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
        
        return date.toLocaleDateString();
    },
    
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },
    
    copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            this.toast('Copied to clipboard', 'success');
        }).catch(() => {
            this.toast('Failed to copy', 'error');
        });
    }
};

// =============================================================================
// STL VIEWER COMPONENT
// =============================================================================

class STLViewer {
    constructor(container, options = {}) {
        this.container = typeof container === 'string' 
            ? document.getElementById(container) 
            : container;
        
        if (!this.container) return;
        
        this.options = {
            backgroundColor: 0xf5f5f5,
            modelColor: 0xe3000b, // LEGO red
            wireframe: false,
            ...options
        };
        
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.mesh = null;
        
        this.init();
    }
    
    init() {
        if (typeof THREE === 'undefined') {
            console.warn('Three.js not loaded');
            return;
        }
        
        const width = this.container.clientWidth;
        const height = this.container.clientHeight || 400;
        
        // Scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(this.options.backgroundColor);
        
        // Camera
        this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
        this.camera.position.set(50, 50, 50);
        
        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(width, height);
        this.container.appendChild(this.renderer.domElement);
        
        // Lights
        const ambientLight = new THREE.AmbientLight(0x404040, 0.5);
        this.scene.add(ambientLight);
        
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(1, 1, 1);
        this.scene.add(directionalLight);
        
        // Controls (simple orbit)
        this.setupControls();
        
        // Animate
        this.animate();
        
        // Resize handler
        window.addEventListener('resize', () => this.onResize());
    }
    
    setupControls() {
        // Simple mouse controls
        let isDragging = false;
        let previousMousePosition = { x: 0, y: 0 };
        
        this.container.addEventListener('mousedown', (e) => {
            isDragging = true;
            previousMousePosition = { x: e.clientX, y: e.clientY };
        });
        
        document.addEventListener('mouseup', () => {
            isDragging = false;
        });
        
        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            
            const deltaX = e.clientX - previousMousePosition.x;
            const deltaY = e.clientY - previousMousePosition.y;
            
            if (this.mesh) {
                this.mesh.rotation.y += deltaX * 0.01;
                this.mesh.rotation.x += deltaY * 0.01;
            }
            
            previousMousePosition = { x: e.clientX, y: e.clientY };
        });
        
        // Zoom with wheel
        this.container.addEventListener('wheel', (e) => {
            e.preventDefault();
            this.camera.position.multiplyScalar(e.deltaY > 0 ? 1.1 : 0.9);
        });
    }
    
    loadSTL(url) {
        if (typeof THREE.STLLoader === 'undefined') {
            console.warn('STLLoader not loaded');
            return;
        }
        
        const loader = new THREE.STLLoader();
        
        loader.load(url, (geometry) => {
            // Remove existing mesh
            if (this.mesh) {
                this.scene.remove(this.mesh);
            }
            
            // Center geometry
            geometry.computeBoundingBox();
            const center = geometry.boundingBox.getCenter(new THREE.Vector3());
            geometry.translate(-center.x, -center.y, -center.z);
            
            // Create mesh
            const material = new THREE.MeshPhongMaterial({
                color: this.options.modelColor,
                wireframe: this.options.wireframe
            });
            
            this.mesh = new THREE.Mesh(geometry, material);
            this.scene.add(this.mesh);
            
            // Fit camera
            const size = geometry.boundingBox.getSize(new THREE.Vector3());
            const maxDim = Math.max(size.x, size.y, size.z);
            this.camera.position.setLength(maxDim * 2.5);
        });
    }
    
    setWireframe(enabled) {
        if (this.mesh && this.mesh.material) {
            this.mesh.material.wireframe = enabled;
        }
    }
    
    setView(view) {
        const distance = this.camera.position.length();
        
        switch (view) {
            case 'front':
                this.camera.position.set(0, 0, distance);
                break;
            case 'top':
                this.camera.position.set(0, distance, 0);
                break;
            case 'right':
                this.camera.position.set(distance, 0, 0);
                break;
            case 'iso':
                this.camera.position.set(distance * 0.6, distance * 0.6, distance * 0.6);
                break;
        }
        
        this.camera.lookAt(0, 0, 0);
    }
    
    animate() {
        requestAnimationFrame(() => this.animate());
        this.renderer.render(this.scene, this.camera);
    }
    
    onResize() {
        const width = this.container.clientWidth;
        const height = this.container.clientHeight || 400;
        
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }
    
    dispose() {
        if (this.renderer) {
            this.renderer.dispose();
        }
    }
}

// =============================================================================
// JSON VIEWER COMPONENT
// =============================================================================

class JSONViewer {
    constructor(container, data) {
        this.container = typeof container === 'string'
            ? document.getElementById(container)
            : container;
        
        if (this.container && data) {
            this.render(data);
        }
    }
    
    render(data) {
        const html = this.format(data);
        this.container.innerHTML = `<pre class="json-content">${html}</pre>`;
    }
    
    format(data, indent = 0) {
        const type = typeof data;
        const spaces = '  '.repeat(indent);
        
        if (data === null) {
            return '<span class="json-null">null</span>';
        }
        
        if (type === 'boolean') {
            return `<span class="json-boolean">${data}</span>`;
        }
        
        if (type === 'number') {
            return `<span class="json-number">${data}</span>`;
        }
        
        if (type === 'string') {
            return `<span class="json-string">"${this.escape(data)}"</span>`;
        }
        
        if (Array.isArray(data)) {
            if (data.length === 0) return '[]';
            
            const items = data.map(item => 
                spaces + '  ' + this.format(item, indent + 1)
            ).join(',\n');
            
            return `[\n${items}\n${spaces}]`;
        }
        
        if (type === 'object') {
            const keys = Object.keys(data);
            if (keys.length === 0) return '{}';
            
            const items = keys.map(key =>
                `${spaces}  <span class="json-key">"${key}"</span>: ${this.format(data[key], indent + 1)}`
            ).join(',\n');
            
            return `{\n${items}\n${spaces}}`;
        }
        
        return String(data);
    }
    
    escape(str) {
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }
}

// =============================================================================
// INITIALIZE ON LOAD
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
    App.init();
});

// Export for global access
window.App = App;
window.STLViewer = STLViewer;
window.JSONViewer = JSONViewer;
