/**
 * LEGO Factory Dashboard Common Utilities
 * ========================================
 * Common dashboard utilities including loading spinners, toast notifications,
 * table pagination helpers, and Chart.js configuration helpers.
 */

// =============================================================================
// Loading Spinners
// =============================================================================

const LoadingSpinner = {
    /**
     * Create a loading spinner element
     * @param {string} size - 'sm', 'md', 'lg'
     * @param {string} variant - Bootstrap color variant
     * @returns {HTMLElement}
     */
    create(size = 'md', variant = 'primary') {
        const sizes = { sm: '1rem', md: '2rem', lg: '3rem' };
        const spinner = document.createElement('div');
        spinner.className = `spinner-border text-${variant}`;
        spinner.style.width = sizes[size] || sizes.md;
        spinner.style.height = sizes[size] || sizes.md;
        spinner.setAttribute('role', 'status');
        spinner.innerHTML = '<span class="visually-hidden">Loading...</span>';
        return spinner;
    },

    /**
     * Show loading overlay on an element
     * @param {HTMLElement|string} element - Element or selector
     * @param {string} message - Optional loading message
     * @returns {HTMLElement} - Overlay element
     */
    show(element, message = 'Loading...') {
        const el = typeof element === 'string' ? document.querySelector(element) : element;
        if (!el) return null;

        // Ensure relative positioning
        const position = getComputedStyle(el).position;
        if (position === 'static') {
            el.style.position = 'relative';
        }

        // Create overlay
        const overlay = document.createElement('div');
        overlay.className = 'loading-overlay';
        overlay.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(255, 255, 255, 0.9);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            border-radius: inherit;
        `;

        const spinner = this.create('md', 'primary');
        overlay.appendChild(spinner);

        if (message) {
            const text = document.createElement('div');
            text.className = 'mt-2 text-muted';
            text.textContent = message;
            overlay.appendChild(text);
        }

        el.appendChild(overlay);
        el._loadingOverlay = overlay;
        return overlay;
    },

    /**
     * Hide loading overlay from an element
     * @param {HTMLElement|string} element - Element or selector
     */
    hide(element) {
        const el = typeof element === 'string' ? document.querySelector(element) : element;
        if (!el || !el._loadingOverlay) return;

        el._loadingOverlay.remove();
        delete el._loadingOverlay;
    },

    /**
     * Show inline loading spinner
     * @param {HTMLElement|string} element - Element or selector
     * @returns {Object} - Object with restore method
     */
    inline(element) {
        const el = typeof element === 'string' ? document.querySelector(element) : element;
        if (!el) return { restore: () => {} };

        const originalContent = el.innerHTML;
        const originalDisabled = el.disabled;

        el.disabled = true;
        el.innerHTML = `
            <span class="spinner-border spinner-border-sm me-2" role="status"></span>
            Loading...
        `;

        return {
            restore: () => {
                el.innerHTML = originalContent;
                el.disabled = originalDisabled;
            }
        };
    },

    /**
     * Show button loading state
     * @param {HTMLElement} button - Button element
     * @param {string} loadingText - Text to show while loading
     * @returns {Function} - Function to restore button
     */
    button(button, loadingText = 'Loading...') {
        const originalContent = button.innerHTML;
        const originalDisabled = button.disabled;
        const originalWidth = button.style.minWidth;

        button.style.minWidth = button.offsetWidth + 'px';
        button.disabled = true;
        button.innerHTML = `
            <span class="spinner-border spinner-border-sm me-2" role="status"></span>
            ${loadingText}
        `;

        return () => {
            button.innerHTML = originalContent;
            button.disabled = originalDisabled;
            button.style.minWidth = originalWidth;
        };
    }
};

// =============================================================================
// Toast Notifications
// =============================================================================

const Toast = {
    container: null,

    /**
     * Initialize toast container
     */
    init() {
        if (this.container) return;

        this.container = document.createElement('div');
        this.container.className = 'toast-container position-fixed top-0 end-0 p-3';
        this.container.style.zIndex = '9999';
        document.body.appendChild(this.container);
    },

    /**
     * Show a toast notification
     * @param {string} message - Toast message
     * @param {string} type - 'success', 'error', 'warning', 'info'
     * @param {number} duration - Auto-hide duration in ms (0 to disable)
     * @returns {HTMLElement} - Toast element
     */
    show(message, type = 'info', duration = 5000) {
        this.init();

        const typeConfig = {
            success: { bg: 'bg-success', icon: 'bi-check-circle-fill' },
            error: { bg: 'bg-danger', icon: 'bi-x-circle-fill' },
            warning: { bg: 'bg-warning', icon: 'bi-exclamation-triangle-fill' },
            info: { bg: 'bg-info', icon: 'bi-info-circle-fill' },
        };

        const config = typeConfig[type] || typeConfig.info;

        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white ${config.bg} border-0 show`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="bi ${config.icon} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;

        this.container.appendChild(toast);

        // Initialize Bootstrap toast
        const bsToast = new bootstrap.Toast(toast, {
            autohide: duration > 0,
            delay: duration,
        });
        bsToast.show();

        // Clean up on hide
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });

        // Close button handler
        toast.querySelector('.btn-close').addEventListener('click', () => {
            bsToast.hide();
        });

        return toast;
    },

    /**
     * Show success toast
     */
    success(message, duration = 5000) {
        return this.show(message, 'success', duration);
    },

    /**
     * Show error toast
     */
    error(message, duration = 8000) {
        return this.show(message, 'error', duration);
    },

    /**
     * Show warning toast
     */
    warning(message, duration = 6000) {
        return this.show(message, 'warning', duration);
    },

    /**
     * Show info toast
     */
    info(message, duration = 5000) {
        return this.show(message, 'info', duration);
    },

    /**
     * Show toast from API error
     * @param {APIError|Error} error
     */
    apiError(error) {
        const message = error.getUserMessage ? error.getUserMessage() : error.message;
        return this.error(message);
    },

    /**
     * Clear all toasts
     */
    clear() {
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
};

// Global toast function
window.showToast = (message, type = 'info', duration = 5000) => {
    return Toast.show(message, type, duration);
};

// =============================================================================
// Table Pagination
// =============================================================================

class TablePagination {
    constructor(options = {}) {
        this.container = options.container;
        this.tableBody = options.tableBody;
        this.pageSize = options.pageSize || 10;
        this.currentPage = 1;
        this.totalItems = 0;
        this.totalPages = 0;
        this.onPageChange = options.onPageChange || (() => {});
        this.onPageSizeChange = options.onPageSizeChange || (() => {});
    }

    /**
     * Update pagination state
     * @param {number} totalItems - Total number of items
     * @param {number} currentPage - Current page (1-indexed)
     */
    update(totalItems, currentPage = 1) {
        this.totalItems = totalItems;
        this.currentPage = currentPage;
        this.totalPages = Math.ceil(totalItems / this.pageSize);
        this.render();
    }

    /**
     * Set page size
     * @param {number} size
     */
    setPageSize(size) {
        this.pageSize = size;
        this.currentPage = 1;
        this.totalPages = Math.ceil(this.totalItems / this.pageSize);
        this.render();
        this.onPageSizeChange(size);
    }

    /**
     * Go to specific page
     * @param {number} page
     */
    goToPage(page) {
        if (page < 1 || page > this.totalPages) return;
        this.currentPage = page;
        this.render();
        this.onPageChange(page);
    }

    /**
     * Go to next page
     */
    nextPage() {
        this.goToPage(this.currentPage + 1);
    }

    /**
     * Go to previous page
     */
    prevPage() {
        this.goToPage(this.currentPage - 1);
    }

    /**
     * Render pagination controls
     */
    render() {
        if (!this.container) return;

        const container = typeof this.container === 'string'
            ? document.querySelector(this.container)
            : this.container;

        if (!container) return;

        const startItem = ((this.currentPage - 1) * this.pageSize) + 1;
        const endItem = Math.min(this.currentPage * this.pageSize, this.totalItems);

        container.innerHTML = `
            <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
                <div class="d-flex align-items-center gap-2">
                    <span class="text-muted">Show</span>
                    <select class="form-select form-select-sm" style="width: auto;" id="pageSizeSelect">
                        <option value="10" ${this.pageSize === 10 ? 'selected' : ''}>10</option>
                        <option value="25" ${this.pageSize === 25 ? 'selected' : ''}>25</option>
                        <option value="50" ${this.pageSize === 50 ? 'selected' : ''}>50</option>
                        <option value="100" ${this.pageSize === 100 ? 'selected' : ''}>100</option>
                    </select>
                    <span class="text-muted">
                        Showing ${this.totalItems > 0 ? startItem : 0} to ${endItem} of ${this.totalItems} entries
                    </span>
                </div>
                <nav>
                    <ul class="pagination pagination-sm mb-0">
                        <li class="page-item ${this.currentPage === 1 ? 'disabled' : ''}">
                            <a class="page-link" href="#" data-page="prev">Previous</a>
                        </li>
                        ${this._renderPageNumbers()}
                        <li class="page-item ${this.currentPage === this.totalPages ? 'disabled' : ''}">
                            <a class="page-link" href="#" data-page="next">Next</a>
                        </li>
                    </ul>
                </nav>
            </div>
        `;

        // Bind events
        container.querySelector('#pageSizeSelect').addEventListener('change', (e) => {
            this.setPageSize(parseInt(e.target.value));
        });

        container.querySelectorAll('.page-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const page = e.target.dataset.page;
                if (page === 'prev') {
                    this.prevPage();
                } else if (page === 'next') {
                    this.nextPage();
                } else if (page) {
                    this.goToPage(parseInt(page));
                }
            });
        });
    }

    /**
     * Render page number buttons
     */
    _renderPageNumbers() {
        const pages = [];
        const maxVisible = 5;
        let start = Math.max(1, this.currentPage - Math.floor(maxVisible / 2));
        let end = Math.min(this.totalPages, start + maxVisible - 1);

        if (end - start + 1 < maxVisible) {
            start = Math.max(1, end - maxVisible + 1);
        }

        if (start > 1) {
            pages.push(`<li class="page-item"><a class="page-link" href="#" data-page="1">1</a></li>`);
            if (start > 2) {
                pages.push(`<li class="page-item disabled"><span class="page-link">...</span></li>`);
            }
        }

        for (let i = start; i <= end; i++) {
            pages.push(`
                <li class="page-item ${i === this.currentPage ? 'active' : ''}">
                    <a class="page-link" href="#" data-page="${i}">${i}</a>
                </li>
            `);
        }

        if (end < this.totalPages) {
            if (end < this.totalPages - 1) {
                pages.push(`<li class="page-item disabled"><span class="page-link">...</span></li>`);
            }
            pages.push(`
                <li class="page-item">
                    <a class="page-link" href="#" data-page="${this.totalPages}">${this.totalPages}</a>
                </li>
            `);
        }

        return pages.join('');
    }

    /**
     * Get current pagination params for API request
     * @returns {Object}
     */
    getParams() {
        return {
            page: this.currentPage,
            page_size: this.pageSize,
            offset: (this.currentPage - 1) * this.pageSize,
            limit: this.pageSize,
        };
    }
}

// =============================================================================
// Chart.js Configuration Helpers
// =============================================================================

const ChartHelpers = {
    // LEGO Factory color palette
    colors: {
        primary: '#3b82f6',
        success: '#10b981',
        warning: '#f59e0b',
        danger: '#ef4444',
        info: '#0dcaf0',
        secondary: '#6c757d',
        lego: {
            red: '#E3000B',
            yellow: '#FFD700',
            blue: '#006CB7',
            green: '#4DB848',
        },
    },

    // Chart color arrays
    colorPalette: [
        '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
        '#0dcaf0', '#6c757d', '#E3000B', '#FFD700', '#006CB7',
    ],

    /**
     * Get default Chart.js options for dark theme
     * @returns {Object}
     */
    getDarkThemeDefaults() {
        return {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: {
                        color: '#94a3b8',
                    },
                },
                tooltip: {
                    backgroundColor: 'rgba(30, 41, 59, 0.95)',
                    titleColor: '#e2e8f0',
                    bodyColor: '#e2e8f0',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                },
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)',
                    },
                    ticks: {
                        color: '#94a3b8',
                    },
                },
                y: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)',
                    },
                    ticks: {
                        color: '#94a3b8',
                    },
                },
            },
        };
    },

    /**
     * Get default Chart.js options for light theme
     * @returns {Object}
     */
    getLightThemeDefaults() {
        return {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: {
                        color: '#495057',
                    },
                },
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)',
                    },
                    ticks: {
                        color: '#495057',
                    },
                },
                y: {
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)',
                    },
                    ticks: {
                        color: '#495057',
                    },
                },
            },
        };
    },

    /**
     * Create a line chart configuration
     * @param {Object} options
     * @returns {Object}
     */
    createLineConfig(options = {}) {
        const theme = options.darkTheme ? this.getDarkThemeDefaults() : this.getLightThemeDefaults();
        return {
            type: 'line',
            data: {
                labels: options.labels || [],
                datasets: [{
                    label: options.label || 'Data',
                    data: options.data || [],
                    borderColor: options.color || this.colors.primary,
                    backgroundColor: options.fill
                        ? `${options.color || this.colors.primary}20`
                        : 'transparent',
                    fill: options.fill || false,
                    tension: options.tension || 0.4,
                    pointRadius: options.pointRadius || 3,
                    pointHoverRadius: options.pointHoverRadius || 5,
                }],
            },
            options: {
                ...theme,
                ...options.chartOptions,
            },
        };
    },

    /**
     * Create a bar chart configuration
     * @param {Object} options
     * @returns {Object}
     */
    createBarConfig(options = {}) {
        const theme = options.darkTheme ? this.getDarkThemeDefaults() : this.getLightThemeDefaults();
        return {
            type: 'bar',
            data: {
                labels: options.labels || [],
                datasets: [{
                    label: options.label || 'Data',
                    data: options.data || [],
                    backgroundColor: options.colors || this.colorPalette.slice(0, options.data?.length || 5),
                    borderRadius: options.borderRadius || 4,
                }],
            },
            options: {
                ...theme,
                indexAxis: options.horizontal ? 'y' : 'x',
                ...options.chartOptions,
            },
        };
    },

    /**
     * Create a doughnut/pie chart configuration
     * @param {Object} options
     * @returns {Object}
     */
    createDoughnutConfig(options = {}) {
        const theme = options.darkTheme ? this.getDarkThemeDefaults() : this.getLightThemeDefaults();
        return {
            type: options.pie ? 'pie' : 'doughnut',
            data: {
                labels: options.labels || [],
                datasets: [{
                    data: options.data || [],
                    backgroundColor: options.colors || this.colorPalette.slice(0, options.data?.length || 5),
                    borderWidth: options.borderWidth || 2,
                    borderColor: options.darkTheme ? '#1e293b' : '#ffffff',
                }],
            },
            options: {
                ...theme,
                cutout: options.pie ? 0 : (options.cutout || '60%'),
                plugins: {
                    ...theme.plugins,
                    legend: {
                        position: options.legendPosition || 'right',
                        ...theme.plugins.legend,
                    },
                },
                ...options.chartOptions,
            },
        };
    },

    /**
     * Create OEE gauge chart configuration
     * @param {number} value - OEE value (0-100)
     * @param {Object} options
     * @returns {Object}
     */
    createOEEGauge(value, options = {}) {
        const color = value >= 85 ? this.colors.success
            : value >= 70 ? this.colors.info
            : value >= 50 ? this.colors.warning
            : this.colors.danger;

        return {
            type: 'doughnut',
            data: {
                datasets: [{
                    data: [value, 100 - value],
                    backgroundColor: [color, 'rgba(255, 255, 255, 0.1)'],
                    borderWidth: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                circumference: 180,
                rotation: 270,
                cutout: '75%',
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: false },
                },
                ...options.chartOptions,
            },
        };
    },

    /**
     * Create stacked bar chart for alarm history
     * @param {Object} options
     * @returns {Object}
     */
    createStackedBarConfig(options = {}) {
        const theme = options.darkTheme ? this.getDarkThemeDefaults() : this.getLightThemeDefaults();
        return {
            type: 'bar',
            data: {
                labels: options.labels || [],
                datasets: options.datasets || [],
            },
            options: {
                ...theme,
                scales: {
                    x: { ...theme.scales.x, stacked: true },
                    y: { ...theme.scales.y, stacked: true, beginAtZero: true },
                },
                ...options.chartOptions,
            },
        };
    },

    /**
     * Update chart data with animation
     * @param {Chart} chart - Chart.js instance
     * @param {Object} newData - New data object
     */
    updateChartData(chart, newData) {
        if (newData.labels) {
            chart.data.labels = newData.labels;
        }
        if (newData.datasets) {
            newData.datasets.forEach((dataset, index) => {
                if (chart.data.datasets[index]) {
                    Object.assign(chart.data.datasets[index], dataset);
                }
            });
        }
        if (newData.data && chart.data.datasets[0]) {
            chart.data.datasets[0].data = newData.data;
        }
        chart.update('default');
    },

    /**
     * Add data point to real-time chart
     * @param {Chart} chart - Chart.js instance
     * @param {string} label - New label
     * @param {number|Array} data - New data point(s)
     * @param {number} maxPoints - Maximum points to keep
     */
    addDataPoint(chart, label, data, maxPoints = 50) {
        chart.data.labels.push(label);

        const dataArray = Array.isArray(data) ? data : [data];
        dataArray.forEach((value, index) => {
            if (chart.data.datasets[index]) {
                chart.data.datasets[index].data.push(value);
            }
        });

        // Remove old data points
        while (chart.data.labels.length > maxPoints) {
            chart.data.labels.shift();
            chart.data.datasets.forEach(dataset => {
                dataset.data.shift();
            });
        }

        chart.update('none'); // No animation for real-time updates
    }
};

// =============================================================================
// Utility Functions
// =============================================================================

const DashboardUtils = {
    /**
     * Format date/time for display
     * @param {string|Date} date
     * @param {string} format - 'datetime', 'date', 'time', 'relative'
     * @returns {string}
     */
    formatDateTime(date, format = 'datetime') {
        const d = new Date(date);
        const now = new Date();

        switch (format) {
            case 'date':
                return d.toLocaleDateString();
            case 'time':
                return d.toLocaleTimeString();
            case 'relative':
                const diff = now - d;
                const minutes = Math.floor(diff / 60000);
                const hours = Math.floor(diff / 3600000);
                const days = Math.floor(diff / 86400000);

                if (minutes < 1) return 'Just now';
                if (minutes < 60) return `${minutes}m ago`;
                if (hours < 24) return `${hours}h ago`;
                if (days < 7) return `${days}d ago`;
                return d.toLocaleDateString();
            default:
                return d.toLocaleString();
        }
    },

    /**
     * Format number with appropriate suffix (K, M, B)
     * @param {number} num
     * @param {number} decimals
     * @returns {string}
     */
    formatNumber(num, decimals = 1) {
        if (num >= 1e9) return (num / 1e9).toFixed(decimals) + 'B';
        if (num >= 1e6) return (num / 1e6).toFixed(decimals) + 'M';
        if (num >= 1e3) return (num / 1e3).toFixed(decimals) + 'K';
        return num.toString();
    },

    /**
     * Format percentage
     * @param {number} value
     * @param {number} decimals
     * @returns {string}
     */
    formatPercent(value, decimals = 1) {
        return value.toFixed(decimals) + '%';
    },

    /**
     * Format duration from seconds
     * @param {number} seconds
     * @returns {string}
     */
    formatDuration(seconds) {
        if (seconds < 60) return `${seconds}s`;
        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return `${hours}h ${minutes % 60}m`;
        const days = Math.floor(hours / 24);
        return `${days}d ${hours % 24}h`;
    },

    /**
     * Debounce function
     * @param {Function} func
     * @param {number} wait
     * @returns {Function}
     */
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

    /**
     * Throttle function
     * @param {Function} func
     * @param {number} limit
     * @returns {Function}
     */
    throttle(func, limit) {
        let inThrottle;
        return function executedFunction(...args) {
            if (!inThrottle) {
                func(...args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },

    /**
     * Deep merge objects
     * @param {Object} target
     * @param {Object} source
     * @returns {Object}
     */
    deepMerge(target, source) {
        const output = { ...target };
        for (const key in source) {
            if (source[key] instanceof Object && key in target) {
                output[key] = this.deepMerge(target[key], source[key]);
            } else {
                output[key] = source[key];
            }
        }
        return output;
    },

    /**
     * Get query parameter from URL
     * @param {string} name
     * @returns {string|null}
     */
    getQueryParam(name) {
        const params = new URLSearchParams(window.location.search);
        return params.get(name);
    },

    /**
     * Update query parameters without reload
     * @param {Object} params
     */
    setQueryParams(params) {
        const url = new URL(window.location);
        Object.entries(params).forEach(([key, value]) => {
            if (value === null || value === undefined) {
                url.searchParams.delete(key);
            } else {
                url.searchParams.set(key, value);
            }
        });
        window.history.pushState({}, '', url);
    },

    /**
     * Copy text to clipboard
     * @param {string} text
     * @returns {Promise<boolean>}
     */
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            Toast.success('Copied to clipboard');
            return true;
        } catch (err) {
            Toast.error('Failed to copy to clipboard');
            return false;
        }
    },

    /**
     * Download data as file
     * @param {string} content
     * @param {string} filename
     * @param {string} contentType
     */
    downloadFile(content, filename, contentType = 'text/plain') {
        const blob = new Blob([content], { type: contentType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        URL.revokeObjectURL(url);
        a.remove();
    },

    /**
     * Create a confirmation modal
     * @param {string} message
     * @param {Object} options
     * @returns {Promise<boolean>}
     */
    confirm(message, options = {}) {
        return new Promise((resolve) => {
            const modal = document.createElement('div');
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">${options.title || 'Confirm'}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p>${message}</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                                ${options.cancelText || 'Cancel'}
                            </button>
                            <button type="button" class="btn btn-${options.confirmVariant || 'primary'}" id="confirmBtn">
                                ${options.confirmText || 'Confirm'}
                            </button>
                        </div>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);
            const bsModal = new bootstrap.Modal(modal);

            modal.querySelector('#confirmBtn').addEventListener('click', () => {
                bsModal.hide();
                resolve(true);
            });

            modal.addEventListener('hidden.bs.modal', () => {
                modal.remove();
                resolve(false);
            });

            bsModal.show();
        });
    }
};

// =============================================================================
// Data Table Helper
// =============================================================================

class DataTable {
    constructor(tableId, options = {}) {
        this.table = document.getElementById(tableId);
        this.tbody = this.table?.querySelector('tbody');
        this.options = {
            columns: options.columns || [],
            emptyMessage: options.emptyMessage || 'No data available',
            rowClass: options.rowClass || '',
            onRowClick: options.onRowClick || null,
            ...options,
        };
        this.data = [];
    }

    /**
     * Set table data
     * @param {Array} data
     */
    setData(data) {
        this.data = data;
        this.render();
    }

    /**
     * Render table
     */
    render() {
        if (!this.tbody) return;

        if (this.data.length === 0) {
            this.tbody.innerHTML = `
                <tr>
                    <td colspan="${this.options.columns.length}" class="text-center text-muted py-4">
                        ${this.options.emptyMessage}
                    </td>
                </tr>
            `;
            return;
        }

        this.tbody.innerHTML = this.data.map((row, index) => {
            const cells = this.options.columns.map(col => {
                const value = col.render
                    ? col.render(row[col.key], row, index)
                    : (row[col.key] ?? '-');
                return `<td class="${col.className || ''}">${value}</td>`;
            }).join('');

            return `<tr class="${this.options.rowClass}" data-index="${index}">${cells}</tr>`;
        }).join('');

        // Bind row click events
        if (this.options.onRowClick) {
            this.tbody.querySelectorAll('tr').forEach(tr => {
                tr.style.cursor = 'pointer';
                tr.addEventListener('click', () => {
                    const index = parseInt(tr.dataset.index);
                    this.options.onRowClick(this.data[index], index);
                });
            });
        }
    }

    /**
     * Add a row
     * @param {Object} row
     */
    addRow(row) {
        this.data.push(row);
        this.render();
    }

    /**
     * Update a row
     * @param {number} index
     * @param {Object} row
     */
    updateRow(index, row) {
        if (this.data[index]) {
            this.data[index] = row;
            this.render();
        }
    }

    /**
     * Remove a row
     * @param {number} index
     */
    removeRow(index) {
        this.data.splice(index, 1);
        this.render();
    }

    /**
     * Clear all data
     */
    clear() {
        this.data = [];
        this.render();
    }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        LoadingSpinner,
        Toast,
        TablePagination,
        ChartHelpers,
        DashboardUtils,
        DataTable,
    };
}
