# Anti-Blocking Guide for LabelSquor Crawlers

## Overview

This guide explains how to use the generic anti-blocking system that helps crawlers work on cloud platforms (like GCP) where IPs are often blocked by retailers.

## Architecture

```
antiblock/
├── base.py              # Base classes and registry
├── retailers.py         # Retailer-specific strategies
└── configs/            # Per-retailer configurations
    ├── bigbasket.json
    ├── amazon.json
    └── ...
```

## Free Solutions for GCP Blocking

### 1. GitHub Actions (Recommended) ✅

**Why it works**: GitHub's IP addresses are rarely blocked as they're associated with legitimate developer activity.

```bash
# Manual trigger
gh workflow run crawl-products -f retailer=bigbasket -f search_terms="maggi,lays"

# Or use GitHub UI: Actions tab → Product Crawler → Run workflow
```

**Advantages**:
- Completely free
- No proxy needed
- Reliable IPs
- Easy scheduling
- Built-in artifact storage

### 2. Free Proxy Rotation 🔄

The system automatically fetches and rotates free proxies from multiple sources:

```python
# Enable in settings_gcp.py
DOWNLOADER_MIDDLEWARES['labelsquor_crawlers.middlewares_v2.GenericAntiBlockMiddleware'] = 400
```

**Proxy sources used**:
- ProxyScrape API (free tier)
- Proxy-List.download
- TheSpeedX proxy list

### 3. Adaptive Strategies 🧠

Each retailer has custom anti-blocking measures:

```python
# BigBasket: Aggressive proxy rotation + mobile user agents
# Amazon: Careful delays + session persistence
# Flipkart: API-specific headers
# Blinkit/Zepto: Mobile-first approach
```

## Usage

### Running with Anti-Block Measures

1. **Local Development** (your IP works):
```bash
scrapy crawl bigbasket -L INFO
```

2. **GCP Deployment** (use special settings):
```bash
# Use GCP-specific settings with proxy rotation
scrapy crawl bigbasket -s SCRAPY_SETTINGS_MODULE=labelsquor_crawlers.settings_gcp

# Or set environment variable
export SCRAPY_SETTINGS_MODULE=labelsquor_crawlers.settings_gcp
scrapy crawl bigbasket
```

3. **GitHub Actions** (recommended for GCP):
```yaml
# See .github/workflows/crawl-products.yml
# Runs from GitHub's infrastructure
```

### Adding a New Retailer

1. Create strategy class:
```python
# In antiblock/retailers.py
class MyRetailerAntiBlockStrategy(BaseAntiBlockStrategy):
    def get_user_agents(self) -> List[str]:
        return ["Custom user agents..."]
    
    def handle_blocking_response(self, response: Response) -> bool:
        # Custom blocking detection
        return 'blocked' in response.text

# Register it
RetailerAntiBlockRegistry.register('myretailer', MyRetailerAntiBlockStrategy)
```

2. Create configuration:
```json
// In antiblock/configs/myretailer.json
{
  "enabled": true,
  "download_delay": 2.0,
  "force_proxy": true,
  "blocking_patterns": ["access denied", "captcha"]
}
```

3. Update spider:
```python
class MyRetailerSpider(AntiBlockSpider):
    name = 'myretailer'
    retailer = 'myretailer'  # Links to strategy
```

## Configuration Options

### Per-Retailer Settings

```json
{
  "enabled": true,                    // Enable anti-block measures
  "download_delay": 2.0,              // Base delay between requests
  "delay_randomization": 1.0,         // Random delay factor
  "proxy_probability": 1.0,           // Chance of using proxy (0-1)
  "force_proxy": true,                // Always use proxy
  "proxy_type": "rotating",           // Proxy rotation type
  "proxy_providers": ["free"],        // Proxy sources to use
  "retry_times": 5,                   // Max retries
  "retry_codes": [403, 429, 503],     // HTTP codes to retry
  "blocking_patterns": ["captcha"],   // Text patterns indicating blocking
  "concurrent_requests": 1,           // Requests per domain
  "cookies_enabled": false            // Enable cookies
}
```

## Monitoring & Debugging

### Check Spider Stats

```python
# Stats are automatically collected
'antiblock/bigbasket/requests': 100
'antiblock/bigbasket/blocked': 5
'antiblock/bigbasket/success': 95
'antiblock/bigbasket/proxy_failed': 2
```

### Debug Mode

```bash
# Enable debug logging
scrapy crawl bigbasket -L DEBUG

# Check proxy usage
scrapy crawl bigbasket -L DEBUG 2>&1 | grep "Using proxy"
```

### Test Blocking Detection

```python
# Run test script
python -c "
from simple_bigbasket_parser import SimpleBigBasketParser
parser = SimpleBigBasketParser()
products = parser.search_products('maggi')
print(f'Success! Found {len(products)} products')
"
```

## Best Practices

1. **Start with GitHub Actions** for reliability
2. **Use simple parsers** when possible (no Scrapy overhead)
3. **Respect rate limits** - more delays are better than getting blocked
4. **Monitor success rates** - adjust strategies based on stats
5. **Rotate everything** - user agents, proxies, request patterns

## Troubleshooting

### "Access Denied" on GCP

```bash
# Solution 1: Use GitHub Actions
gh workflow run crawl-products

# Solution 2: Enable proxy in settings
export ENABLE_PROXY=true
scrapy crawl bigbasket

# Solution 3: Use simple parser with requests
python simple_bigbasket_parser.py
```

### Proxies Not Working

```bash
# Test proxy manually
curl -x http://proxy:port https://www.bigbasket.com

# Increase proxy timeout
-s PROXY_TIMEOUT=60
```

### Still Getting Blocked

1. Increase delays: `-s DOWNLOAD_DELAY=5`
2. Reduce concurrency: `-s CONCURRENT_REQUESTS=1`
3. Try mobile user agents
4. Use GitHub Actions instead

## Cost Analysis

| Solution | Cost | Reliability | Speed |
|----------|------|-------------|-------|
| GitHub Actions | Free | High | Medium |
| Free Proxies | Free | Low | Slow |
| Premium Proxies | $50+/mo | High | Fast |
| Residential IPs | $200+/mo | Very High | Fast |

**Recommendation**: Start with GitHub Actions (free & reliable)
