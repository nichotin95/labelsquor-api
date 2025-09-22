# Self-Hosted Deployment with Docker

## 🐳 Docker Deployment (Completely Free)

Deploy on your own server, VPS, or even locally for development.

### Prerequisites

- Docker and Docker Compose installed
- Server with public IP (VPS, cloud instance, or local with port forwarding)

### Step 1: Clone and Configure

```bash
# Clone your repository
git clone https://github.com/nichotin95/labelsquor-api.git
cd labelsquor-api

# Copy environment template
cp env.example .env

# Edit environment variables
nano .env
```

### Step 2: Configure Environment

Edit `.env` file:
```bash
# Required
DATABASE_URL=postgresql://postgres:postgres@db:5432/labelsquor
GOOGLE_API_KEY=your-gemini-api-key
SECRET_KEY=your-32-character-secret-key
ADMIN_API_KEY=your-admin-api-key

# Frontend
FRONTEND_URL=https://your-frontend-domain.com

# Optional
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### Step 3: Deploy with Docker Compose

```bash
# Build and start services
docker-compose up -d

# Check logs
docker-compose logs -f api

# Check health
curl http://localhost:8000/api/v1/health
```

### Step 4: Run Database Migrations

```bash
# Connect to API container
docker-compose exec api bash

# Run migrations
alembic upgrade head

# Seed initial data (optional)
python scripts/reset_database.py
```

### Step 5: Configure Reverse Proxy (Nginx)

Create `/etc/nginx/sites-available/labelsquor-api`:

```nginx
server {
    listen 80;
    server_name api.labelsquor.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/labelsquor-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Step 6: SSL Certificate (Free with Let's Encrypt)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d api.labelsquor.com
```

## 🎯 VPS Providers (Free/Cheap Options)

### 1. **Oracle Cloud Always Free**
- **2 AMD instances** (1/8 OCPU, 1GB RAM each)
- **200GB storage**
- **10TB bandwidth/month**
- **Completely free forever**

### 2. **Google Cloud Free Tier**
- **1 f1-micro instance** (1 vCPU, 0.6GB RAM)
- **30GB storage**
- **1GB network egress/month**
- **Free for 12 months + always free tier**

### 3. **AWS Free Tier**
- **1 t2.micro instance** (1 vCPU, 1GB RAM)
- **30GB storage**
- **15GB bandwidth/month**
- **Free for 12 months**

### 4. **DigitalOcean**
- **$4/month** for basic droplet
- **1GB RAM, 1 vCPU, 25GB SSD**
- **1TB transfer**

## 🔧 Production Setup Commands

```bash
# Quick setup
make docker-build
make docker-run

# Check status
make docker-logs

# Stop services
make docker-stop

# Full reset
docker-compose down -v
make docker-run
```

## 📊 Resource Requirements

**Minimum**:
- **512MB RAM** (for API + small DB)
- **1 CPU core**
- **10GB storage**

**Recommended**:
- **1GB RAM** (better performance)
- **2 CPU cores** (concurrent requests)
- **20GB storage** (room for growth)

## 🎯 Perfect for:
- ✅ Full control over deployment
- ✅ No vendor lock-in
- ✅ Custom domain configuration
- ✅ SSL certificate management
- ✅ Cost-effective scaling
