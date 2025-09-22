# Deploy LabelSquor API to Render (100% Free)

## 🆓 Render Free Tier Deployment

Render offers completely free hosting for small applications.

### Step 1: Create Render Account

1. Go to [render.com](https://render.com)
2. Sign up with GitHub
3. Connect your `labelsquor-api` repository

### Step 2: Create PostgreSQL Database

1. Click **"New +"** → **"PostgreSQL"**
2. Name: `labelsquor-db`
3. Database: `labelsquor`
4. User: `labelsquor`
5. Region: Choose closest to your users
6. **Plan: Free** (100MB storage, 1 month retention)

### Step 3: Create Web Service

1. Click **"New +"** → **"Web Service"**
2. Connect your GitHub repo: `labelsquor-api`
3. Configure:
   - **Name**: `labelsquor-api`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements/production.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free (512MB RAM, sleeps after 15min inactivity)

### Step 4: Environment Variables

In Render dashboard, add environment variables:

```bash
DATABASE_URL=postgresql://labelsquor:password@host/labelsquor  # Auto-generated
GOOGLE_API_KEY=your-gemini-api-key
SECRET_KEY=your-32-character-secret-key
ADMIN_API_KEY=your-admin-api-key-for-crawler-endpoints
FRONTEND_URL=https://your-frontend.netlify.app
ENVIRONMENT=production
PYTHON_VERSION=3.11.0
```

### Step 5: Deploy

Render automatically deploys when you push to main branch:

```bash
git push origin main
```

### Your API will be available at:
```
https://labelsquor-api.onrender.com
```

## 📊 Free Tier Limits

- **512MB RAM** per service
- **100GB bandwidth/month**
- **PostgreSQL**: 100MB storage
- **Sleeps after 15min** inactivity (30s cold start)
- **Custom domains** supported
- **Automatic HTTPS**

## 🎯 Perfect for:
- ✅ Development and testing
- ✅ Small-scale production
- ✅ Proof of concept
- ✅ Portfolio projects

## ⚠️ Limitations:
- Service sleeps after 15min (30s wake-up time)
- Limited database storage (100MB)
- Single instance only

## 🚀 Upgrade Path:
When you need more:
- **Starter Plan**: $7/month (no sleep, 1GB RAM)
- **Standard Plan**: $25/month (4GB RAM, multiple instances)
