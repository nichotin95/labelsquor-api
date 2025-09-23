# Testing Anti-Blocking Crawlers with the API

## How It Works

The new anti-blocking system works transparently with your API:

```
[Scrapy Crawler with Anti-Block] → [API Endpoint] → [AI Analysis Pipeline]
         ↓                              ↓                    ↓
   (Proxy rotation)            (/crawler/products)    (Product Analysis)
   (User agent switch)         (/crawler/sessions)
   (Retry strategies)
```

## Quick Test Guide

### 1. Start the API Server

```bash
cd /Users/nitinchopra/Downloads/labelsquor-api
uvicorn app.main:app --reload
```

### 2. Test Crawler Locally (Direct API Integration)

```bash
cd /Users/nitinchopra/Downloads/labelsquor-api/crawlers

# Test with local API (your IP works fine)
scrapy crawl bigbasket \
  -s LABELSQUOR_API_URL=http://localhost:8000 \
  -s LABELSQUOR_API_KEY=your-api-key \
  -a search_terms="maggi" \
  -a max_products=5
```

### 3. Test with GCP Settings (Simulated)

```bash
# Force GCP settings even locally to test anti-blocking
scrapy crawl bigbasket \
  -s SCRAPY_SETTINGS_MODULE=labelsquor_crawlers.settings_gcp \
  -s LABELSQUOR_API_URL=http://localhost:8000 \
  -s LOG_LEVEL=DEBUG \
  -a search_terms="maggi" \
  -a max_products=5

# You'll see in logs:
# - "Using proxy: http://..."
# - Different user agents being used
# - Retry attempts if blocked
```

### 4. Test Simple Parser (No Scrapy)

```bash
# Test the simple parser that also works on GCP
python -c "
import requests
from simple_bigbasket_parser import SimpleBigBasketParser

# Parse products
parser = SimpleBigBasketParser()
products = parser.search_products('maggi')

# Send to API
api_url = 'http://localhost:8000'
for product in products[:5]:
    response = requests.post(
        f'{api_url}/api/v1/crawler/products',
        json={
            'source_page': {
                'url': product['url'],
                'retailer': 'bigbasket',
                'title': product['name'],
                'extracted_data': product
            }
        }
    )
    print(f'Sent {product[\"name\"]} - Status: {response.status_code}')
"
```

### 5. Test via API Endpoints

```bash
# Trigger crawl via API (uses orchestrator)
curl -X POST http://localhost:8000/api/v1/crawler/crawl/category \
  -H "Content-Type: application/json" \
  -d '{
    "category": "snacks",
    "retailers": ["bigbasket"],
    "max_products": 10
  }'

# Check status
curl http://localhost:8000/api/v1/crawler/status/{session_id}
```

## Testing Different Scenarios

### Test Proxy Rotation

```python
# crawlers/test_antiblock.py
import asyncio
from labelsquor_crawlers.antiblock.base import RetailerAntiBlockRegistry

async def test_antiblock():
    # Get BigBasket strategy
    strategy = RetailerAntiBlockRegistry.get_strategy('bigbasket')
    
    # Test headers
    print("Headers:", strategy.get_headers(None))
    
    # Test user agents
    print("User Agents:", strategy.get_user_agents()[:3])
    
    # Test proxy config
    print("Proxy Config:", strategy.get_proxy_config())
    
    # Test blocking detection
    class FakeResponse:
        status = 403
        text = "access denied"
    
    print("Is Blocked?", strategy.handle_blocking_response(FakeResponse()))

asyncio.run(test_antiblock())
```

### Test Different Retailers

```bash
# BigBasket (aggressive anti-blocking)
python run_crawler.py bigbasket --search-terms "lays,coca cola"

# Amazon (coming soon - careful approach)
python run_crawler.py amazon --search-terms "maggi noodles"

# All retailers
python run_crawler.py all --max-products 20
```

## Monitoring Anti-Block Performance

### Check API Logs

```bash
# See which products were received
tail -f server.log | grep "crawler/products"

# Check for blocking
tail -f server.log | grep -i "blocked\|denied\|captcha"
```

### Check Crawler Stats

```bash
# Run crawler with stats
scrapy crawl bigbasket -s STATS_CLASS=scrapy.statscollectors.MemoryStatsCollector

# Stats will show:
# - antiblock/bigbasket/requests: 50
# - antiblock/bigbasket/blocked: 2
# - antiblock/bigbasket/success: 48
# - antiblock/bigbasket/proxy_failed: 1
```

## Configuration for Production

### Environment Variables

```bash
# .env file
LABELSQUOR_API_URL=https://api.labelsquor.com
LABELSQUOR_API_KEY=your-production-key
ENABLE_PROXY=true
PROXY_PROVIDERS=free,proxyscrape
```

### Deploy on GCP with Anti-Block

```bash
# Option 1: Use GitHub Actions (recommended)
# Push code and let GitHub Actions run from their IPs

# Option 2: Run directly on GCP with proxies
gcloud compute ssh your-instance
cd labelsquor-api/crawlers
python run_crawler.py bigbasket  # Auto-detects GCP and enables proxies
```

## Troubleshooting

### "Connection refused" to API

```bash
# Check API is running
curl http://localhost:8000/api/v1/health

# Check crawler can reach API
scrapy crawl bigbasket -s LABELSQUOR_API_URL=http://localhost:8000 -L DEBUG
```

### "403 Forbidden" from retailers

```bash
# This means anti-blocking is working! Check logs:
grep "Using proxy" *.log
grep "Retrying" *.log

# If still blocked, use GitHub Actions instead
gh workflow run crawl-products -f retailer=bigbasket
```

### Proxies not working

```bash
# Test proxy fetching
python -c "
from labelsquor_crawlers.middlewares_v2 import GenericAntiBlockMiddleware
m = GenericAntiBlockMiddleware(None)
m._init_proxy_pools()
"
```

## Summary

The anti-blocking system works seamlessly with your API:

1. **Transparent Integration**: Crawlers handle all anti-blocking internally
2. **API Receives Clean Data**: The API just receives product data as before
3. **Multiple Options**: Scrapy crawlers, simple parsers, or GitHub Actions
4. **Extensible**: Easy to add new retailers with custom strategies

Test locally first, then deploy to GCP with confidence!
