# LabelSquor API Production Deployment Guide

## 🚀 Deployment Options

### Option 1: **Railway** (Recommended for Simplicity)
```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login and create project
railway login
railway init labelsquor-api

# 3. Add environment variables
railway variables set DATABASE_URL="postgresql://..."
railway variables set GOOGLE_API_KEY="your-key"
railway variables set SECRET_KEY="your-secret"
railway variables set ADMIN_API_KEY="your-admin-key"
railway variables set FRONTEND_URL="https://your-frontend.com"

# 4. Deploy
railway up
```

### Option 2: **Render** (Free Tier Available)
```bash
# 1. Connect GitHub repo to Render
# 2. Create PostgreSQL database
# 3. Create web service with:
#    - Build Command: pip install -r requirements/production.txt
#    - Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 4
# 4. Set environment variables in Render dashboard
```

### Option 3: **Heroku**
```bash
# 1. Create Heroku app
heroku create labelsquor-api

# 2. Add PostgreSQL addon
heroku addons:create heroku-postgresql:mini

# 3. Set environment variables
heroku config:set GOOGLE_API_KEY="your-key"
heroku config:set SECRET_KEY="your-secret"
heroku config:set ADMIN_API_KEY="your-admin-key"
heroku config:set FRONTEND_URL="https://your-frontend.com"

# 4. Deploy
git push heroku main
```

### Option 4: **DigitalOcean App Platform**
```yaml
# app.yaml
name: labelsquor-api
services:
- name: api
  source_dir: /
  github:
    repo: your-username/labelsquor-api
    branch: main
  run_command: uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 4
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs
  envs:
  - key: DATABASE_URL
    value: ${db.DATABASE_URL}
  - key: GOOGLE_API_KEY
    value: your-key
    type: SECRET
databases:
- name: db
  engine: PG
  version: "14"
```

---

## 🔧 Environment Configuration

### Required Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Security
SECRET_KEY=your-super-secret-key-minimum-32-characters
ADMIN_API_KEY=admin-key-for-crawler-endpoints

# AI Services  
GOOGLE_API_KEY=your-google-gemini-api-key

# Frontend
FRONTEND_URL=https://your-frontend-domain.com
```

### Optional Environment Variables

```bash
# Server
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8000
WORKERS=4

# Database Pool
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# Image Storage
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-supabase-anon-key
ENABLE_IMAGE_HOSTING=false

# Monitoring
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
ENABLE_METRICS=true

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

---

## 🔒 Security Configuration

### API Authentication

**Consumer Endpoints** (No auth required):
```bash
# Public access for frontend
GET /api/v1/products/search
GET /api/v1/products/{id}
GET /api/v1/products/filters/options
GET /api/v1/health
```

**Admin Endpoints** (API Key required):
```bash
# Requires X-API-Key header
POST /api/v1/crawler/crawl/category
POST /api/v1/crawler/search/product
GET /api/v1/crawler/status/{session_id}
GET /api/v1/crawler/products/recent
```

### Frontend Integration

**React/Vue/Angular Example:**
```javascript
// Consumer endpoints (no auth)
const searchProducts = async (query) => {
  const response = await fetch(`${API_BASE_URL}/api/v1/products/search?q=${query}`);
  return response.json();
};

// Admin endpoints (with API key)
const triggerCrawl = async (category) => {
  const response = await fetch(`${API_BASE_URL}/api/v1/crawler/crawl/category`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': 'your-admin-api-key'
    },
    body: JSON.stringify({ category, retailers: ['bigbasket'], max_products: 10 })
  });
  return response.json();
};
```

### CORS Configuration

The API automatically allows requests from:
- Your configured `FRONTEND_URL`
- Common development servers (localhost:3000, localhost:5173)
- Your deployed frontend domains

---

## 🗄️ Database Setup

### Production Database

**Recommended**: Use managed PostgreSQL service:
- **Railway**: Built-in PostgreSQL
- **Render**: PostgreSQL addon
- **Heroku**: Heroku Postgres
- **DigitalOcean**: Managed Database
- **Supabase**: PostgreSQL with built-in features

### Database Migration

```bash
# After deployment, run migrations
alembic upgrade head

# Or use the API endpoint (with admin key)
curl -X POST "https://your-api.com/api/v1/admin/migrate" \
  -H "X-API-Key: your-admin-key"
```

---

## 📊 Monitoring & Health Checks

### Health Check Endpoint
```bash
curl "https://your-api.com/api/v1/health"
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-09-22T16:00:00Z",
  "database": "connected",
  "version": "1.0.0"
}
```

### Monitoring Setup

1. **Sentry** for error tracking
2. **Prometheus metrics** (if enabled)
3. **Database connection monitoring**
4. **API response time tracking**

---

## 🎯 Frontend Integration Examples

### Product Search Page
```javascript
// Search with filters
const searchProducts = async (filters) => {
  const params = new URLSearchParams({
    q: filters.query || '',
    brand: filters.brand || '',
    category: filters.category || '',
    min_score: filters.minScore || '',
    sort_by: filters.sortBy || 'score',
    page: filters.page || 1,
    page_size: 20
  });
  
  const response = await fetch(`${API_BASE_URL}/api/v1/products/search?${params}`);
  return response.json();
};
```

### Product Detail Page
```javascript
// Get complete product details
const getProductDetail = async (productId) => {
  const response = await fetch(`${API_BASE_URL}/api/v1/products/${productId}`);
  return response.json();
};
```

### Filter Components
```javascript
// Get filter options for UI
const getFilterOptions = async () => {
  const response = await fetch(`${API_BASE_URL}/api/v1/products/filters/options`);
  return response.json();
};
```

---

## 🔄 CI/CD Pipeline

### GitHub Actions Example
```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to Railway
        run: |
          npm install -g @railway/cli
          railway login --token ${{ secrets.RAILWAY_TOKEN }}
          railway up
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
```

---

## 🚨 Production Checklist

### Before Deployment:
- [ ] Set all required environment variables
- [ ] Configure CORS for your frontend domain
- [ ] Set up production database
- [ ] Configure monitoring (Sentry)
- [ ] Test API endpoints
- [ ] Set up SSL certificate (automatic with most platforms)

### After Deployment:
- [ ] Run database migrations
- [ ] Test health endpoint
- [ ] Verify CORS configuration
- [ ] Test consumer endpoints from frontend
- [ ] Test admin endpoints with API key
- [ ] Monitor error rates and performance

---

## 📱 API Base URLs

### Development
```
http://localhost:8000
```

### Production Examples
```
https://labelsquor-api.railway.app
https://labelsquor-api.onrender.com  
https://labelsquor-api.herokuapp.com
https://labelsquor-api-xyz.ondigitalocean.app
```

---

## 🎯 Next Steps

1. **Choose deployment platform** (Railway recommended)
2. **Set up production database**
3. **Configure environment variables**
4. **Deploy API**
5. **Update frontend to use production API URL**
6. **Test end-to-end functionality**

**Your LabelSquor API is ready for production deployment!** 🚀
