# Quick Guide: BigBasket Crawler on GCP (Free Solutions)

## Problem
BigBasket blocks GCP IP addresses but allows local IPs.

## Solutions (All Free)

### 1. GitHub Actions (Recommended) ✅

**Setup**: Already configured in `.github/workflows/crawl-products.yml`

**Run manually**:
```bash
# From your local machine
gh workflow run crawl-products -f retailer=bigbasket -f search_terms="maggi,lays"
```

**Schedule**: Runs daily at 2 AM UTC automatically

**Why it works**: GitHub's IPs are trusted by retailers

### 2. Free Proxy Rotation 🔄

**Setup**: Already configured in `settings_gcp.py`

**Run on GCP**:
```bash
# Auto-detects GCP and enables proxies
python run_crawler.py bigbasket --search-terms "maggi,lays"

# Or manually with Scrapy
scrapy crawl bigbasket -s SCRAPY_SETTINGS_MODULE=labelsquor_crawlers.settings_gcp
```

**Proxy sources**:
- ProxyScrape (free API)
- Proxy-List.download
- GitHub proxy lists

### 3. Simple Parser (No Scrapy) 🎯

**Run anywhere**:
```bash
# Uses basic requests with anti-blocking headers
python simple_bigbasket_parser.py
```

**Features**:
- Rotating user agents
- Browser-like headers
- No complex dependencies

## Quick Commands

```bash
# On GCP - automatically uses anti-blocking measures
cd crawlers
python run_crawler.py bigbasket

# Force proxy usage
export FORCE_PROXY=true
python run_crawler.py bigbasket

# Use GitHub Actions (from local machine)
gh workflow run crawl-products -f retailer=bigbasket

# Test if blocked
curl -I https://www.bigbasket.com
```

## Adding More Retailers

The system is generic and ready for Amazon, Flipkart, etc:

```bash
# These will work with retailer-specific strategies
python run_crawler.py amazon
python run_crawler.py flipkart
```

Each retailer has custom:
- User agents
- Headers
- Proxy strategies
- Retry policies
- Blocking detection

## Architecture

```
antiblock/
├── base.py                 # Generic framework
├── retailers.py            # BigBasket, Amazon, etc strategies
└── configs/
    ├── bigbasket.json     # BigBasket-specific settings
    └── amazon.json        # Amazon-specific settings
```

## If Still Blocked

1. **Use GitHub Actions** - most reliable
2. **Increase delays** in `configs/bigbasket.json`
3. **Try mobile user agents** - often less blocked
4. **Use residential proxies** (paid option)

## Monitoring

Check stats:
```bash
# See blocking rate
grep "blocked" *.log | wc -l

# See successful crawls
grep "success" *.log | wc -l
```
