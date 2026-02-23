/**
 * LEGO Factory API Client
 * ========================
 * Base API client class with fetch wrapper, JWT token management,
 * error handling with retry logic, and base URL configuration.
 */

class APIClient {
    constructor(options = {}) {
        this.baseURL = options.baseURL || '/api';
        this.timeout = options.timeout || 30000;
        this.maxRetries = options.maxRetries || 3;
        this.retryDelay = options.retryDelay || 1000;
        this.tokenKey = options.tokenKey || 'lego_factory_token';
        this.refreshTokenKey = options.refreshTokenKey || 'lego_factory_refresh_token';
        this.tokenExpireKey = options.tokenExpireKey || 'lego_factory_token_expire';

        // Request interceptors
        this.requestInterceptors = [];
        // Response interceptors
        this.responseInterceptors = [];

        // Token refresh promise (prevents multiple simultaneous refresh attempts)
        this._refreshPromise = null;
    }

    // =========================================================================
    // Token Management
    // =========================================================================

    /**
     * Get the stored JWT access token
     * @returns {string|null}
     */
    getToken() {
        return localStorage.getItem(this.tokenKey);
    }

    /**
     * Set the JWT access token
     * @param {string} token
     * @param {number} expiresIn - Expiration time in seconds
     */
    setToken(token, expiresIn = 3600) {
        localStorage.setItem(this.tokenKey, token);
        const expireTime = Date.now() + (expiresIn * 1000);
        localStorage.setItem(this.tokenExpireKey, expireTime.toString());
    }

    /**
     * Get the stored refresh token
     * @returns {string|null}
     */
    getRefreshToken() {
        return localStorage.getItem(this.refreshTokenKey);
    }

    /**
     * Set the refresh token
     * @param {string} token
     */
    setRefreshToken(token) {
        localStorage.setItem(this.refreshTokenKey, token);
    }

    /**
     * Clear all tokens (logout)
     */
    clearTokens() {
        localStorage.removeItem(this.tokenKey);
        localStorage.removeItem(this.refreshTokenKey);
        localStorage.removeItem(this.tokenExpireKey);
    }

    /**
     * Check if the access token is expired
     * @returns {boolean}
     */
    isTokenExpired() {
        const expireTime = localStorage.getItem(this.tokenExpireKey);
        if (!expireTime) return true;
        // Consider expired if within 30 seconds of expiration
        return Date.now() >= (parseInt(expireTime) - 30000);
    }

    /**
     * Check if user is authenticated
     * @returns {boolean}
     */
    isAuthenticated() {
        return !!this.getToken() && !this.isTokenExpired();
    }

    /**
     * Refresh the access token using the refresh token
     * @returns {Promise<string>} - New access token
     */
    async refreshAccessToken() {
        // If already refreshing, return the existing promise
        if (this._refreshPromise) {
            return this._refreshPromise;
        }

        const refreshToken = this.getRefreshToken();
        if (!refreshToken) {
            throw new APIError('No refresh token available', 401, 'AUTH_ERROR');
        }

        this._refreshPromise = this._doRefresh(refreshToken);

        try {
            const result = await this._refreshPromise;
            return result;
        } finally {
            this._refreshPromise = null;
        }
    }

    async _doRefresh(refreshToken) {
        try {
            const response = await fetch(`${this.baseURL}/auth/refresh`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ refresh_token: refreshToken }),
            });

            if (!response.ok) {
                this.clearTokens();
                throw new APIError('Token refresh failed', response.status, 'AUTH_ERROR');
            }

            const data = await response.json();
            this.setToken(data.access_token, data.expires_in || 3600);

            if (data.refresh_token) {
                this.setRefreshToken(data.refresh_token);
            }

            return data.access_token;
        } catch (error) {
            this.clearTokens();
            throw error;
        }
    }

    // =========================================================================
    // Interceptors
    // =========================================================================

    /**
     * Add a request interceptor
     * @param {Function} interceptor - Function that receives and returns config
     */
    addRequestInterceptor(interceptor) {
        this.requestInterceptors.push(interceptor);
    }

    /**
     * Add a response interceptor
     * @param {Function} onSuccess - Function called on successful response
     * @param {Function} onError - Function called on error
     */
    addResponseInterceptor(onSuccess, onError) {
        this.responseInterceptors.push({ onSuccess, onError });
    }

    // =========================================================================
    // Core Request Methods
    // =========================================================================

    /**
     * Make an HTTP request with retry logic
     * @param {string} endpoint - API endpoint
     * @param {object} options - Fetch options
     * @returns {Promise<any>}
     */
    async request(endpoint, options = {}) {
        const url = endpoint.startsWith('http') ? endpoint : `${this.baseURL}${endpoint}`;

        let config = {
            method: options.method || 'GET',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
            ...options,
        };

        // Add authorization header if token exists and is valid
        const token = this.getToken();
        if (token && token !== 'null' && token !== 'undefined' && !this.isTokenExpired() && !config.headers['Authorization']) {
            config.headers['Authorization'] = `Bearer ${token}`;
        }

        // Remove Content-Type for FormData
        if (config.body instanceof FormData) {
            delete config.headers['Content-Type'];
        }

        // Run request interceptors
        for (const interceptor of this.requestInterceptors) {
            config = await interceptor(config);
        }

        // Execute with retry logic
        let lastError;
        for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
            try {
                const response = await this._fetchWithTimeout(url, config);
                return await this._handleResponse(response);
            } catch (error) {
                lastError = error;

                // Handle token expiration
                if (error.status === 401 && this.getRefreshToken()) {
                    try {
                        await this.refreshAccessToken();
                        // Retry with new token
                        config.headers['Authorization'] = `Bearer ${this.getToken()}`;
                        const response = await this._fetchWithTimeout(url, config);
                        return await this._handleResponse(response);
                    } catch (refreshError) {
                        // Refresh failed, propagate error
                        throw refreshError;
                    }
                }

                // Don't retry for client errors (except 401 which is handled above)
                if (error.status >= 400 && error.status < 500) {
                    throw error;
                }

                // Don't retry if max attempts reached
                if (attempt >= this.maxRetries) {
                    throw error;
                }

                // Wait before retry with exponential backoff
                await this._sleep(this.retryDelay * Math.pow(2, attempt));
            }
        }

        throw lastError;
    }

    /**
     * Fetch with timeout
     */
    async _fetchWithTimeout(url, config) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        try {
            const response = await fetch(url, {
                ...config,
                signal: controller.signal,
            });
            return response;
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new APIError('Request timeout', 408, 'TIMEOUT');
            }
            throw new APIError(error.message, 0, 'NETWORK_ERROR');
        } finally {
            clearTimeout(timeoutId);
        }
    }

    /**
     * Handle API response
     */
    async _handleResponse(response) {
        let data;
        const contentType = response.headers.get('content-type');

        if (contentType && contentType.includes('application/json')) {
            data = await response.json();
        } else {
            data = await response.text();
        }

        if (!response.ok) {
            const error = new APIError(
                data.error || data.message || `HTTP ${response.status}`,
                response.status,
                data.code || 'API_ERROR',
                data
            );

            // Run error interceptors
            for (const interceptor of this.responseInterceptors) {
                if (interceptor.onError) {
                    const result = await interceptor.onError(error);
                    if (result !== undefined) {
                        return result;
                    }
                }
            }

            throw error;
        }

        // Run success interceptors
        for (const interceptor of this.responseInterceptors) {
            if (interceptor.onSuccess) {
                data = await interceptor.onSuccess(data, response);
            }
        }

        return data;
    }

    /**
     * Sleep helper
     */
    _sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // =========================================================================
    // Convenience Methods
    // =========================================================================

    /**
     * GET request
     */
    async get(endpoint, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;
        return this.request(url, { method: 'GET' });
    }

    /**
     * POST request
     */
    async post(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    /**
     * PUT request
     */
    async put(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    }

    /**
     * PATCH request
     */
    async patch(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'PATCH',
            body: JSON.stringify(data),
        });
    }

    /**
     * DELETE request
     */
    async delete(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'DELETE',
            body: Object.keys(data).length ? JSON.stringify(data) : undefined,
        });
    }

    /**
     * Upload file(s)
     */
    async upload(endpoint, files, additionalData = {}) {
        const formData = new FormData();

        if (Array.isArray(files)) {
            files.forEach((file, index) => {
                formData.append(`files[${index}]`, file);
            });
        } else {
            formData.append('file', files);
        }

        Object.entries(additionalData).forEach(([key, value]) => {
            formData.append(key, value);
        });

        return this.request(endpoint, {
            method: 'POST',
            body: formData,
        });
    }

    /**
     * Download file
     */
    async download(endpoint, filename) {
        const response = await fetch(`${this.baseURL}${endpoint}`, {
            headers: {
                'Authorization': `Bearer ${this.getToken()}`,
            },
        });

        if (!response.ok) {
            throw new APIError('Download failed', response.status, 'DOWNLOAD_ERROR');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
    }
}

// =============================================================================
// Custom Error Class
// =============================================================================

class APIError extends Error {
    constructor(message, status, code, data = null) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.code = code;
        this.data = data;
        this.timestamp = new Date().toISOString();
    }

    /**
     * Check if error is a network error
     */
    isNetworkError() {
        return this.code === 'NETWORK_ERROR' || this.status === 0;
    }

    /**
     * Check if error is an authentication error
     */
    isAuthError() {
        return this.status === 401 || this.code === 'AUTH_ERROR';
    }

    /**
     * Check if error is a validation error
     */
    isValidationError() {
        return this.status === 422 || this.code === 'VALIDATION_ERROR';
    }

    /**
     * Check if error is a server error
     */
    isServerError() {
        return this.status >= 500;
    }

    /**
     * Get user-friendly error message
     */
    getUserMessage() {
        if (this.isNetworkError()) {
            return 'Network error. Please check your connection and try again.';
        }
        if (this.isAuthError()) {
            return 'Authentication required. Please log in again.';
        }
        if (this.isValidationError()) {
            return this.data?.details || 'Please check your input and try again.';
        }
        if (this.isServerError()) {
            return 'Server error. Please try again later.';
        }
        return this.message;
    }
}

// =============================================================================
// Domain-Specific API Clients
// =============================================================================

/**
 * SCADA API Client
 */
class SCADAClient extends APIClient {
    constructor(options = {}) {
        super({ ...options, baseURL: options.baseURL || '/api/scada' });
    }

    // Machines
    async getMachines() {
        return this.get('/machines');
    }

    async getMachine(machineId) {
        return this.get(`/machines/${machineId}`);
    }

    async connectMachine(machineId) {
        return this.post(`/machines/${machineId}/connect`);
    }

    async disconnectMachine(machineId) {
        return this.post(`/machines/${machineId}/disconnect`);
    }

    async homeMachine(machineId) {
        return this.post(`/machines/${machineId}/home`);
    }

    async jogMachine(machineId, axis, distance, feedRate) {
        return this.post(`/machines/${machineId}/jog`, { axis, distance, feed_rate: feedRate });
    }

    async getMachineStatus(machineId) {
        return this.get(`/machines/${machineId}/status`);
    }

    // Alarms
    async getAlarms(params = {}) {
        return this.get('/alarms', params);
    }

    async getAlarm(alarmId) {
        return this.get(`/alarms/${alarmId}`);
    }

    async acknowledgeAlarm(alarmId, userId) {
        return this.post(`/alarms/${alarmId}/acknowledge`, { user_id: userId });
    }

    async acknowledgeAlarms(alarmIds, userId) {
        return this.post('/alarms/acknowledge-batch', { alarm_ids: alarmIds, user_id: userId });
    }

    async getAlarmSummary() {
        return this.get('/alarms/summary');
    }

    async getAlarmHistory(params = {}) {
        return this.get('/alarms/history', params);
    }

    async exportAlarms(format = 'csv') {
        return this.download(`/alarms/export?format=${format}`, `alarms.${format}`);
    }

    // Tags
    async getTags(params = {}) {
        return this.get('/tags', params);
    }

    async getTag(tagId) {
        return this.get(`/tags/${tagId}`);
    }

    async writeTag(tagId, value) {
        return this.post(`/tags/${tagId}/write`, { value });
    }

    // Historian
    async getHistorianData(tagIds, startTime, endTime, interval = '1m') {
        return this.get('/historian/data', {
            tag_ids: tagIds.join(','),
            start_time: startTime,
            end_time: endTime,
            interval,
        });
    }

    // Serial ports
    async getSerialPorts() {
        return this.get('/serial-ports');
    }
}

/**
 * MES API Client
 */
class MESClient extends APIClient {
    constructor(options = {}) {
        super({ ...options, baseURL: options.baseURL || '/api/mes' });
    }

    // Work Orders
    async getWorkOrders(params = {}) {
        return this.get('/work-orders', params);
    }

    async getWorkOrder(woNumber) {
        return this.get(`/work-orders/${woNumber}`);
    }

    async createWorkOrder(data) {
        return this.post('/work-orders', data);
    }

    async updateWorkOrder(woNumber, data) {
        return this.put(`/work-orders/${woNumber}`, data);
    }

    async releaseWorkOrder(woNumber) {
        return this.post(`/work-orders/${woNumber}/release`);
    }

    async startWorkOrder(woNumber, machineId = null) {
        return this.post(`/work-orders/${woNumber}/start`, { machine_id: machineId });
    }

    async holdWorkOrder(woNumber, reason = '') {
        return this.post(`/work-orders/${woNumber}/hold`, { reason });
    }

    async resumeWorkOrder(woNumber) {
        return this.post(`/work-orders/${woNumber}/resume`);
    }

    async completeWorkOrder(woNumber) {
        return this.post(`/work-orders/${woNumber}/complete`);
    }

    async cancelWorkOrder(woNumber, reason = '') {
        return this.post(`/work-orders/${woNumber}/cancel`, { reason });
    }

    async getWorkOrderSummary() {
        return this.get('/work-orders/summary');
    }

    // OEE
    async getOEE(machineId = null, params = {}) {
        if (machineId) {
            return this.get(`/oee/machines/${machineId}/current`, params);
        }
        return this.get('/oee/current', params);
    }

    async getOEEHistory(params = {}) {
        return this.get('/oee/history', params);
    }

    async getOEETrend(machineId = null, period = 'week') {
        const endpoint = machineId
            ? `/oee/machines/${machineId}/trend`
            : '/oee/trend';
        return this.get(endpoint, { period });
    }

    async getOEEByMachine() {
        return this.get('/oee/by-machine');
    }

    // Downtime
    async getDowntimeEvents(params = {}) {
        return this.get('/downtime/events', params);
    }

    async startDowntime(machineId, reason, category) {
        return this.post('/downtime/start', { machine_id: machineId, reason, category });
    }

    async endDowntime(downtimeId) {
        return this.post(`/downtime/${downtimeId}/end`);
    }

    async getDowntimePareto(params = {}) {
        return this.get('/downtime/analytics/pareto', params);
    }

    // Production
    async recordProduction(woNumber, quantity, status = 'good') {
        return this.post('/production/record', { wo_number: woNumber, quantity, status });
    }

    async getProductionSummary(woNumber) {
        return this.get(`/production/summary/${woNumber}`);
    }
}

/**
 * OEE API Client (specialized)
 */
class OEEClient extends APIClient {
    constructor(options = {}) {
        super({ ...options, baseURL: options.baseURL || '/api/mes' });
    }

    async getCurrent(machineId = null) {
        const params = {};
        if (machineId) params.machine_id = machineId;
        return this.get('/oee', params);
    }

    async getTrend(period = 'week', machineId = null) {
        // Trend computed client-side from current OEE data
        const params = {};
        if (machineId) params.machine_id = machineId;
        return this.get('/oee', params);
    }

    async getHistory(startDate, endDate, machineId = null) {
        const params = { start_date: startDate, end_date: endDate };
        if (machineId) params.machine_id = machineId;
        return this.get('/oee', params);
    }

    async getLosses(machineId = null) {
        const params = {};
        if (machineId) params.machine_id = machineId;
        return this.get('/oee', params);
    }

    async getByMachine() {
        return this.get('/oee/summary');
    }

    async exportReport(format = 'pdf', params = {}) {
        console.log('OEE export not yet implemented');
    }
}

/**
 * Auth API Client
 */
class AuthClient extends APIClient {
    constructor(options = {}) {
        super({ ...options, baseURL: options.baseURL || '/api/auth' });
    }

    async login(username, password) {
        const response = await this.post('/login', { username, password });
        if (response.access_token) {
            this.setToken(response.access_token, response.expires_in);
            if (response.refresh_token) {
                this.setRefreshToken(response.refresh_token);
            }
        }
        return response;
    }

    async logout() {
        try {
            await this.post('/logout');
        } finally {
            this.clearTokens();
        }
    }

    async register(userData) {
        return this.post('/register', userData);
    }

    async getCurrentUser() {
        return this.get('/me');
    }

    async updateProfile(data) {
        return this.put('/profile', data);
    }

    async changePassword(oldPassword, newPassword) {
        return this.post('/change-password', {
            old_password: oldPassword,
            new_password: newPassword,
        });
    }

    async forgotPassword(email) {
        return this.post('/forgot-password', { email });
    }

    async resetPassword(token, newPassword) {
        return this.post('/reset-password', { token, new_password: newPassword });
    }
}

// =============================================================================
// Global API Instance
// =============================================================================

// Create global API client instances
const api = new APIClient();
const scadaApi = new SCADAClient();
const mesApi = new MESClient();
const oeeApi = new OEEClient();
const authApi = new AuthClient();

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        APIClient,
        APIError,
        SCADAClient,
        MESClient,
        OEEClient,
        AuthClient,
        api,
        scadaApi,
        mesApi,
        oeeApi,
        authApi,
    };
}
