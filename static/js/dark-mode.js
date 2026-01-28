/**
 * Dark Mode Manager for Flask CNC SCADA
 * ======================================
 * Handles theme switching with persistence and system preference detection
 *
 * Themes:
 * - light: Standard light theme
 * - dark: Dark theme for reduced eye strain
 * - night-shift: Extra dark with warm colors for night shifts
 * - auto: Follow system preference
 */

class ThemeManager {
    constructor() {
        this.themes = ['light', 'dark', 'night-shift'];
        this.storageKey = 'cnc-scada-theme';
        this.currentTheme = this.loadTheme();

        // Initialize
        this.applyTheme(this.currentTheme);
        this.setupSystemPreferenceListener();
        this.createToggleButton();

        console.log('ThemeManager initialized:', this.currentTheme);
    }

    /**
     * Load theme from storage or detect from system
     */
    loadTheme() {
        // Check localStorage
        const stored = localStorage.getItem(this.storageKey);
        if (stored && (this.themes.includes(stored) || stored === 'auto')) {
            if (stored === 'auto') {
                return this.detectSystemPreference();
            }
            return stored;
        }

        // Check time of day for automatic night shift
        const hour = new Date().getHours();
        if (hour >= 22 || hour < 6) {
            return 'night-shift';
        } else if (hour >= 18 || hour < 7) {
            return 'dark';
        }

        // Detect system preference
        return this.detectSystemPreference();
    }

    /**
     * Detect system dark mode preference
     */
    detectSystemPreference() {
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return 'dark';
        }
        return 'light';
    }

    /**
     * Listen for system preference changes
     */
    setupSystemPreferenceListener() {
        if (window.matchMedia) {
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
                const stored = localStorage.getItem(this.storageKey);
                if (stored === 'auto' || !stored) {
                    this.applyTheme(e.matches ? 'dark' : 'light');
                }
            });
        }
    }

    /**
     * Apply theme to document
     */
    applyTheme(theme) {
        // Remove existing theme
        document.documentElement.removeAttribute('data-theme');

        // Apply new theme (light is default, no attribute needed)
        if (theme !== 'light') {
            document.documentElement.setAttribute('data-theme', theme);
        }

        this.currentTheme = theme;
        this.updateToggleButton();

        // Dispatch event for other components
        window.dispatchEvent(new CustomEvent('themechange', {
            detail: { theme }
        }));

        console.log('Theme applied:', theme);
    }

    /**
     * Save theme preference
     */
    saveTheme(theme) {
        localStorage.setItem(this.storageKey, theme);
    }

    /**
     * Cycle through themes
     */
    cycleTheme() {
        const currentIndex = this.themes.indexOf(this.currentTheme);
        const nextIndex = (currentIndex + 1) % this.themes.length;
        const nextTheme = this.themes[nextIndex];

        this.applyTheme(nextTheme);
        this.saveTheme(nextTheme);

        // Show notification
        this.showNotification(`Theme: ${this.getThemeDisplayName(nextTheme)}`);
    }

    /**
     * Set specific theme
     */
    setTheme(theme) {
        if (this.themes.includes(theme) || theme === 'auto') {
            if (theme === 'auto') {
                this.applyTheme(this.detectSystemPreference());
            } else {
                this.applyTheme(theme);
            }
            this.saveTheme(theme);
        }
    }

    /**
     * Get display name for theme
     */
    getThemeDisplayName(theme) {
        const names = {
            'light': 'Light Mode',
            'dark': 'Dark Mode',
            'night-shift': 'Night Shift'
        };
        return names[theme] || theme;
    }

    /**
     * Create floating toggle button
     */
    createToggleButton() {
        // Check if button already exists
        if (document.getElementById('theme-toggle')) {
            return;
        }

        const button = document.createElement('button');
        button.id = 'theme-toggle';
        button.className = 'theme-toggle';
        button.setAttribute('aria-label', 'Toggle theme');
        button.innerHTML = `
            <span class="icon-light">☀️</span>
            <span class="icon-dark">🌙</span>
            <span class="icon-night">🌃</span>
        `;

        button.addEventListener('click', () => this.cycleTheme());

        // Add tooltip on hover
        button.title = 'Click to change theme';

        document.body.appendChild(button);
        this.toggleButton = button;
        this.updateToggleButton();
    }

    /**
     * Update toggle button appearance
     */
    updateToggleButton() {
        if (!this.toggleButton) return;

        // Update title
        this.toggleButton.title = `Current: ${this.getThemeDisplayName(this.currentTheme)}\nClick to change`;
    }

    /**
     * Show theme change notification
     */
    showNotification(message) {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = 'theme-notification';
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            bottom: 80px;
            right: 20px;
            background-color: var(--bg-card);
            color: var(--text-primary);
            padding: 10px 20px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            box-shadow: var(--shadow-md);
            z-index: 1001;
            opacity: 0;
            transform: translateY(10px);
            transition: all 0.3s ease;
        `;

        document.body.appendChild(notification);

        // Animate in
        requestAnimationFrame(() => {
            notification.style.opacity = '1';
            notification.style.transform = 'translateY(0)';
        });

        // Remove after delay
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transform = 'translateY(10px)';
            setTimeout(() => notification.remove(), 300);
        }, 2000);
    }

    /**
     * Schedule automatic night shift
     */
    scheduleNightShift(startHour = 22, endHour = 6) {
        const checkTime = () => {
            const hour = new Date().getHours();
            const stored = localStorage.getItem(this.storageKey);

            // Only auto-switch if user hasn't explicitly set a theme
            if (stored === 'auto' || !stored) {
                if (hour >= startHour || hour < endHour) {
                    this.applyTheme('night-shift');
                } else if (hour >= 18) {
                    this.applyTheme('dark');
                } else {
                    this.applyTheme('light');
                }
            }
        };

        // Check immediately
        checkTime();

        // Check every hour
        setInterval(checkTime, 3600000);
    }
}

// Theme selector dropdown component
class ThemeSelector {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (this.container) {
            this.render();
        }
    }

    render() {
        this.container.innerHTML = `
            <div class="theme-selector">
                <label for="theme-select">Theme:</label>
                <select id="theme-select" class="form-control">
                    <option value="light">☀️ Light</option>
                    <option value="dark">🌙 Dark</option>
                    <option value="night-shift">🌃 Night Shift</option>
                    <option value="auto">🔄 Auto</option>
                </select>
            </div>
        `;

        const select = this.container.querySelector('#theme-select');
        const stored = localStorage.getItem('cnc-scada-theme') || 'auto';
        select.value = stored;

        select.addEventListener('change', (e) => {
            if (window.themeManager) {
                window.themeManager.setTheme(e.target.value);
            }
        });
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.themeManager = new ThemeManager();

    // Schedule automatic night shift mode
    window.themeManager.scheduleNightShift(22, 6);
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ThemeManager, ThemeSelector };
}
