// Theme management
class ThemeManager {
    constructor() {
        this.currentTheme = 'light';
        this.init();
    }

    init() {
        this.loadTheme();
        
        window.addEventListener('storage', (e) => {
            if (e.key === 'theme') {
                this.setTheme(e.newValue, false);
            }
        });
    }

    async loadTheme() {
        const savedTheme = localStorage.getItem('theme');
        
        if (savedTheme) {
            this.setTheme(savedTheme, false);
        } else {
            try {
                const response = await fetch('/api/theme');
                const data = await response.json();
                this.setTheme(data.theme, false);
            } catch (error) {
                console.error('Error loading theme:', error);
            }
        }
    }

    setTheme(theme, broadcast = true) {
        this.currentTheme = theme;
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);

        const toggleSlider = document.querySelector('.theme-toggle-slider');
        if (toggleSlider) {
            toggleSlider.innerHTML = theme === 'dark' ? '🌙' : '☀️';
        }

        if (broadcast) {
            fetch('/api/theme', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ theme })
            });
        }
    }

    toggle() {
        const newTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        this.setTheme(newTheme);
    }
}

const themeManager = new ThemeManager();

document.addEventListener('DOMContentLoaded', () => {
    const createThemeToggle = () => {
        const toggle = document.createElement('button');
        toggle.className = 'theme-toggle';
        toggle.onclick = () => themeManager.toggle();
        toggle.innerHTML = '<div class="theme-toggle-slider">☀️</div>';
        return toggle;
    };

    const headerNav = document.querySelector('.header-nav');
    if (headerNav && !document.querySelector('.theme-toggle')) {
        headerNav.appendChild(createThemeToggle());
    }
});
