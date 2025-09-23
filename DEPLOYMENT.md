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

