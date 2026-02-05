# Configuration for frontend application

# Base URL for API requests - can be overridden via window.CONFIG if set in HTML
try:
    from browser import window
    BASE_URL = window.CONFIG.BASE_URL if hasattr(window, 'CONFIG') and hasattr(window.CONFIG, 'BASE_URL') else 'http://localhost:8000'
except:
    BASE_URL = 'http://localhost:8000'
