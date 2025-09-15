"""
Scrapy settings for LabelSquor crawlers
"""
BOT_NAME = 'labelsquor_crawlers'

SPIDER_MODULES = ['labelsquor_crawlers.spiders']
NEWSPIDER_MODULE = 'labelsquor_crawlers.spiders'

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Configure maximum concurrent requests
CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 2

# Download delay (be polite!)
DOWNLOAD_DELAY = 1
RANDOMIZE_DOWNLOAD_DELAY = True

# Disable cookies (enabled by default)
COOKIES_ENABLED = True

# User agent
USER_AGENT = 'LabelSquor Bot (+https://labelsquor.com/bot)'

# Configure pipelines
ITEM_PIPELINES = {
    'labelsquor_crawlers.pipelines.ValidationPipeline': 100,
    'labelsquor_crawlers.pipelines.CloudStoragePipeline': 200,
    'labelsquor_crawlers.pipelines.LabelSquorAPIPipeline': 300,
}

# Retry configuration
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# AutoThrottle for automatic adjustment of delays
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

# Cache
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 3600  # 1 hour
HTTPCACHE_DIR = 'httpcache'

# Playwright settings for JavaScript sites
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "args": ["--no-sandbox", "--disable-dev-shm-usage"]
}

# Timeout settings
DOWNLOAD_TIMEOUT = 30

# Logging
LOG_LEVEL = 'INFO'

# LabelSquor API settings
LABELSQUOR_API_URL = 'https://api.labelsquor.com'
LABELSQUOR_API_KEY = None  # Set via environment variable

# Cloud storage settings
CLOUD_STORAGE_TYPE = 'local'  # 's3', 'gcs', or 'local'
CLOUD_STORAGE_BUCKET = 'labelsquor-crawl-data'

# Scrapy Cloud settings (if using Scrapy Cloud)
# SHUB_PROJECT_ID = 'your-project-id'

# Export settings (for testing)
FEED_EXPORT_ENCODING = 'utf-8'

# Request fingerprinting (avoid duplicates)
DUPEFILTER_CLASS = 'scrapy.dupefilters.RFPDupeFilter'

# Depth limit
DEPTH_LIMIT = 3

# Close spider after number of items
# CLOSESPIDER_ITEMCOUNT = 1000

# Memory usage monitoring
MEMUSAGE_ENABLED = True
MEMUSAGE_LIMIT_MB = 2048
MEMUSAGE_WARNING_MB = 1536

# Stats collection
STATS_CLASS = 'scrapy.statscollectors.MemoryStatsCollector'

# Telnet console (disable in production)
TELNETCONSOLE_ENABLED = False

# Custom settings per spider can be defined in spider class:
# custom_settings = {
#     'DOWNLOAD_DELAY': 2,
# }
