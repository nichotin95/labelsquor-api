# Deploy LabelSquor API to Railway (Free)

## 🚀 Railway Deployment - Recommended

Railway offers $5/month free credits and automatic deployments from GitHub.

### Step 1: Setup Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login
```

### Step 2: Create Project

```bash
# In your labelsquor-api directory
railway init

# Connect to your GitHub repo
railway connect
```

### Step 3: Add PostgreSQL Database

```bash
# Add PostgreSQL service
railway add postgresql

# Get database URL
railway variables
```

### Step 4: Configure Environment Variables

```bash
# Set required variables
railway variables set GOOGLE_API_KEY="your-gemini-api-key"
railway variables set SECRET_KEY="your-32-char-secret-key"
railway variables set ADMIN_API_KEY="your-admin-api-key"
railway variables set FRONTEND_URL="https://your-frontend.netlify.app"
railway variables set ENVIRONMENT="production"
```

### Step 5: Deploy

```bash
# Deploy from current directory
railway up

# Or auto-deploy from GitHub
railway connect github
```

### Step 6: Run Migrations

```bash
# Connect to your deployed service
railway shell

# Run migrations
alembic upgrade head

# Seed initial data
python scripts/reset_database.py
```

### Your API will be available at:
```
https://labelsquor-api-production.up.railway.app
```

## 🔧 Railway Configuration

Railway automatically detects Python and runs:
```bash
pip install -r requirements/production.txt
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## 📊 Free Tier Limits

- **$5/month** in usage credits
- **Automatic scaling** up to 8GB RAM
- **Custom domains** supported
- **GitHub auto-deployment**
- **PostgreSQL included**

## 🎯 Perfect for LabelSquor because:
- ✅ Easy setup with GitHub integration
- ✅ Built-in PostgreSQL database
- ✅ Automatic HTTPS certificates
- ✅ Environment variable management
- ✅ Logs and monitoring dashboard
- ✅ Free tier sufficient for development/testing
