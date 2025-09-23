# Proxy Crawler Service for GCP

This service runs on Google Cloud Run and provides proxy-enabled crawling to bypass IP blocking.

## Architecture

1. **FastAPI Service**: Accepts crawl requests via HTTP
2. **Proxy Rotation**: Automatic proxy rotation when running on GCP
3. **Background Tasks**: Crawls run asynchronously
4. **Direct API Integration**: Sends results directly to the main API

## Endpoints

### Health Check
```bash
GET /
```

### Test Proxy
```bash
GET /test-proxy
```
Tests if proxy is working and can access BigBasket.

### Trigger Crawl (Scrapy with Proxies)
```bash
POST /crawl
{
  "retailer": "bigbasket",
  "search_terms": ["maggi", "lays"],
  "max_products": 10
}
```

### Simple Crawl (Direct HTTP)
```bash
POST /crawl/simple
{
  "retailer": "bigbasket",
  "search_terms": ["maggi"],
  "max_products": 5
}
```

## Deployment

### Deploy to Cloud Run
```bash
cd crawlers
./deploy-crawler.sh
```

Or manually:
```bash
gcloud run deploy labelsquor-crawler \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --set-env-vars="LABELSQUOR_API_URL=https://labelsquor-api-u7wurf5zba-uc.a.run.app,SCRAPY_SETTINGS_MODULE=labelsquor_crawlers.settings_gcp"
```

## Testing

### Test Proxy Functionality
```bash
curl https://labelsquor-crawler-143169591686.us-central1.run.app/test-proxy | jq
```

### Trigger a Crawl
```bash
curl -X POST https://labelsquor-crawler-143169591686.us-central1.run.app/crawl \
  -H "Content-Type: application/json" \
  -d '{
    "retailer": "bigbasket",
    "search_terms": ["maggi"],
    "max_products": 5
  }' | jq
```

## How It Works

1. When deployed on GCP, the `SCRAPY_SETTINGS_MODULE=labelsquor_crawlers.settings_gcp` environment variable activates proxy rotation
2. The `GenericAntiBlockMiddleware` automatically:
   - Rotates user agents
   - Uses free proxy services
   - Implements adaptive delays
   - Handles retries with different proxies

## Monitoring

Check logs:
```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="labelsquor-crawler"' --limit 50
```

## Current Status

- ✅ Service deployed to Cloud Run
- ✅ Proxy middleware configured
- ⚠️  Simple parser doesn't use proxies (httpx direct)
- ✅ Scrapy crawler uses full anti-blocking system

## Next Steps

1. Implement proxy support in simple parser
2. Add more retailers
3. Set up scheduled crawls via Cloud Scheduler
4. Add monitoring and alerts
