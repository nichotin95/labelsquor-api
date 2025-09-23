# LabelSquor API Deployment

## 🚀 Quick Deploy (Google Cloud Run + Supabase)

**Cost: FREE** - Google Cloud Run free tier + your existing Supabase database

### 1. Setup Google Cloud

```bash
# Install CLI
brew install google-cloud-sdk

# Login and create project
gcloud auth login
gcloud projects create labelsquor-api
gcloud config set project labelsquor-api
gcloud services enable run.googleapis.com
```

### 2. Deploy API

```bash
# From your labelsquor-api directory
gcloud run deploy labelsquor-api \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 1Gi
```

### 3. Set Environment Variables

```bash
gcloud run services update labelsquor-api \
  --set-env-vars="DATABASE_URL=your-supabase-connection-string,GOOGLE_API_KEY=your-gemini-key,SECRET_KEY=your-secret,ADMIN_API_KEY=your-admin-key,FRONTEND_URL=https://your-frontend.com" \
  --region us-central1
```

### 4. Run Database Migrations

```bash
# Set local environment to run migrations against Supabase
export DATABASE_URL="your-supabase-connection-string"
alembic upgrade head
```

## 🎯 Your API is live at:
```
https://labelsquor-api-[hash]-uc.a.run.app
```

## 📱 Frontend Integration

```javascript
const API_BASE = 'https://labelsquor-api-[hash]-uc.a.run.app';

// Public endpoints (no auth needed)
fetch(`${API_BASE}/api/v1/products/search?q=millet`)
fetch(`${API_BASE}/api/v1/products/${productId}`)

// Admin endpoints (need X-API-Key header)
fetch(`${API_BASE}/api/v1/crawler/crawl/category`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'your-admin-key'
  },
  body: JSON.stringify({category: 'snacks', retailers: ['bigbasket']})
})
```

## 💰 Free Tier Limits

- **2 million requests/month** FREE
- **180,000 vCPU-seconds/month** FREE
- **No sleep issues** (instant response)
- **Automatic scaling**

**Perfect for LabelSquor!** 🎉

## 🕷️ Crawler Deployment & Testing

### Option 1: GitHub Actions (Recommended for GCP blocking)
```bash
# The crawlers are already configured in .github/workflows/crawl-products.yml
# Just push code and trigger:
gh workflow run crawl-products -f retailer=bigbasket -f search_terms="maggi,lays"
```

### Option 2: Run on Cloud Run (with anti-blocking)
```bash
# Deploy crawler service
cd crawlers
gcloud run deploy labelsquor-crawler \
  --source . \
  --platform managed \
  --region us-central1 \
  --memory 2Gi \
  --timeout 3600 \
  --set-env-vars="LABELSQUOR_API_URL=https://labelsquor-api-[hash]-uc.a.run.app,LABELSQUOR_API_KEY=your-admin-key"

# Test crawler (will auto-detect GCP and enable proxies)
gcloud run jobs execute labelsquor-crawler \
  --args="python,run_crawler.py,bigbasket,--search-terms,maggi"
```

### Test the deployed crawler
```bash
# Check if products are being received
curl https://labelsquor-api-[hash]-uc.a.run.app/api/v1/crawler/products/recent

# Monitor logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=labelsquor-api" --limit 50 --format json | jq '.[] | select(.jsonPayload.path | contains("/crawler/products"))'
```

The anti-blocking features are automatic on GCP!
