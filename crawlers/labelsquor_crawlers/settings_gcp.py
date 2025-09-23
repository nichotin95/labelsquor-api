"""
GCP-specific settings for LabelSquor crawlers
This extends the base settings with anti-blocking measures for cloud deployment
"""
from .settings import *

# Enable proxy rotation for GCP deployment
DOWNLOADER_MIDDLEWARES.update({
    # Enable proxy rotation - choose one:
    'labelsquor_crawlers.middlewares.RotatingProxyMiddleware': 350,  # Multiple free proxies
    # OR use API-based proxies (comment above and uncomment below):
    # 'labelsquor_crawlers.middlewares.FreeProxyAPIMiddleware': 350,
})

# More aggressive retry settings for cloud
RETRY_TIMES = 5
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429, 403]  # Added 403

# Increase delays for cloud deployment
DOWNLOAD_DELAY = 2
RANDOMIZE_DOWNLOAD_DELAY = True
DOWNLOAD_DELAY_RANDOMIZATION_FACTOR = 2  # 1-4 seconds

# Lower concurrent requests to be more polite
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 1

# Longer timeouts for proxy connections
DOWNLOAD_TIMEOUT = 60

# AutoThrottle settings for cloud
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2
AUTOTHROTTLE_MAX_DELAY = 30
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0

# Disable cookies to appear less trackable
COOKIES_ENABLED = False

# Custom settings for specific spiders when running on GCP
SPIDER_CUSTOM_SETTINGS = {
    'bigbasket': {
        'DOWNLOAD_DELAY': 3,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
    },
    'bigbasket_discovery': {
        'DOWNLOAD_DELAY': 3,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
    }
}

# Log level for debugging
LOG_LEVEL = 'DEBUG'  # Change to 'INFO' in production
