# Deploy LabelSquor API: Railway + Supabase

## 🎯 Perfect Combo: Railway (API) + Supabase (Database)

You already have Supabase for PostgreSQL, so we'll use Railway just for API hosting.

### Step 1: Get Supabase Database URL

1. Go to your Supabase dashboard
2. Navigate to **Settings** → **Database**
3. Copy the **Connection string** (URI format)
4. It looks like: `postgresql://postgres:[password]@[host]:5432/postgres`

### Step 2: Setup Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and create project
cd /Users/nitinchopra/Downloads/labelsquor-api
railway login
railway init labelsquor-api
```

### Step 3: Configure Environment Variables

```bash
# Database (your existing Supabase)
railway variables set DATABASE_URL="postgresql://postgres:[YOUR-PASSWORD]@[YOUR-HOST]:5432/postgres"

# Security
railway variables set SECRET_KEY="your-32-character-secret-key"
railway variables set ADMIN_API_KEY="your-admin-api-key"

# AI Service
railway variables set GOOGLE_API_KEY="your-gemini-api-key"

# Frontend
railway variables set FRONTEND_URL="https://your-frontend.netlify.app"

# Environment
railway variables set ENVIRONMENT="production"

# Optional: Supabase Storage (for images)
railway variables set SUPABASE_URL="https://your-project.supabase.co"
railway variables set SUPABASE_ANON_KEY="your-supabase-anon-key"
railway variables set ENABLE_IMAGE_HOSTING="true"
```

### Step 4: Deploy

```bash
# Deploy your API
railway up

# Check deployment status
railway status

# View logs
railway logs
```

### Step 5: Run Database Migrations

```bash
# Option 1: Connect to Railway shell
railway shell
alembic upgrade head

# Option 2: Run locally against Supabase
export DATABASE_URL="your-supabase-connection-string"
alembic upgrade head
```

## 🎉 **Benefits of This Setup:**

### **Railway Advantages:**
- ✅ **$5/month free credits** (sufficient for API)
- ✅ **No database costs** (using your Supabase)
- ✅ **GitHub auto-deployment**
- ✅ **Custom domains**
- ✅ **No sleep issues**

### **Supabase Advantages:**
- ✅ **You already have it configured**
- ✅ **Built-in image storage** (when ready)
- ✅ **Real-time features** (future use)
- ✅ **Dashboard for database management**
- ✅ **Automatic backups**

## 📊 **Cost Breakdown:**

- **Railway**: $5/month free credits → $0 cost for small API
- **Supabase**: Free tier (500MB database, 1GB storage)
- **Total**: **$0/month** for development/testing

## 🔧 **Your API Endpoints:**

Once deployed, your API will be available at:
```
https://labelsquor-api-production.up.railway.app
```

### **Consumer Endpoints (Public):**
```bash
# Search products
curl "https://labelsquor-api-production.up.railway.app/api/v1/products/search"

# Get product details
curl "https://labelsquor-api-production.up.railway.app/api/v1/products/{id}"

# Health check
curl "https://labelsquor-api-production.up.railway.app/api/v1/health"
```

### **Admin Endpoints (API Key Required):**
```bash
# Crawl products (requires X-API-Key header)
curl -X POST "https://labelsquor-api-production.up.railway.app/api/v1/crawler/crawl/category" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-admin-api-key" \
  -d '{"category": "snacks", "retailers": ["bigbasket"], "max_products": 10}'
```

## 🎯 **Next Steps:**

1. **Deploy API to Railway** (using existing Supabase DB)
2. **Update frontend** to use production API URL
3. **Test end-to-end** functionality
4. **Set up image hosting** in Supabase Storage
5. **Monitor usage** and optimize as needed

**This setup gives you a professional, scalable API with your existing Supabase infrastructure!** 🚀
