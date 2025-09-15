# Cloud Deployment Options for LabelSquor Crawlers

## 1. 🚀 Scrapy Cloud (Easiest - Recommended)

[Scrapy Cloud](https://scrapinghub.com/scrapy-cloud) is a managed platform by Zyte (creators of Scrapy).

**Pros:**
- Zero infrastructure management
- Built-in monitoring and stats
- Automatic retries and error handling
- API access to results
- Pay per use

**Setup:**
```bash
# Install shub
pip install shub

# Login to Scrapy Cloud
shub login

# Deploy
shub deploy

# Schedule periodic runs via their web UI or API
```

## 2. 🌐 GitHub Actions (Free for Public Repos)

Already configured in `.github/workflows/crawl-products.yml`

**Pros:**
- Completely free for public repos
- No infrastructure needed
- Easy scheduling with cron
- Built-in secrets management

**Usage:**
```bash
# Manual trigger
gh workflow run crawl-products -f spider=bigbasket

# Runs automatically daily at 2 AM UTC
```

## 3. ☁️ AWS Options

### EC2 + Scrapyd
```bash
# Deploy using AWS CLI
aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type t3.medium \
  --user-data file://deploy-scrapyd.sh
```

### AWS Batch
Perfect for scheduled large-scale crawls
```yaml
# Create job definition
aws batch register-job-definition \
  --job-definition-name labelsquor-crawler \
  --type container \
  --container-properties file://job-definition.json
```

### AWS Lambda (Serverless)
Using [Scrapy Lambda](https://github.com/jorgebastida/scrapy-lambda)
- Good for small, quick crawls
- 15-minute time limit

## 4. 🐳 Google Cloud Run

```bash
# Build and push image
gcloud builds submit --tag gcr.io/PROJECT_ID/labelsquor-crawler

# Deploy to Cloud Run
gcloud run deploy labelsquor-crawler \
  --image gcr.io/PROJECT_ID/labelsquor-crawler \
  --platform managed \
  --memory 2Gi \
  --timeout 3600 \
  --max-instances 10
```

## 5. 🎯 Kubernetes (For Scale)

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: labelsquor-crawler
spec:
  schedule: "0 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: crawler
            image: labelsquor/crawler:latest
            args: ["scrapy", "crawl", "bigbasket"]
```

## 6. 🔧 Self-Hosted Scrapyd

On any VPS (DigitalOcean, Linode, etc.):

```bash
# Install Scrapyd
pip install scrapyd

# Start Scrapyd
scrapyd

# Deploy spider
scrapyd-deploy production -p labelsquor_crawlers

# Schedule crawl via API
curl http://your-server:6800/schedule.json \
  -d project=labelsquor_crawlers \
  -d spider=bigbasket
```

## 7. 🌊 Temporal/Airflow Integration

For complex workflows:

```python
# Airflow DAG
from airflow import DAG
from airflow.operators.bash import BashOperator

dag = DAG('crawl_products', schedule_interval='@daily')

crawl_task = BashOperator(
    task_id='crawl_bigbasket',
    bash_command='scrapy crawl bigbasket',
    dag=dag
)
```

## 📊 Monitoring & Alerts

### Scrapy Stats to Prometheus
```python
# In settings.py
STATS_CLASS = 'scrapy_prometheus.PrometheusStatsCollector'
```

### Sentry Integration
```python
# In settings.py
import sentry_sdk
sentry_sdk.init("YOUR_SENTRY_DSN")
```

## 🔑 Environment Variables

Set these in your cloud platform:

```bash
LABELSQUOR_API_URL=https://api.labelsquor.com
LABELSQUOR_API_KEY=your-api-key
CLOUD_STORAGE_TYPE=s3
CLOUD_STORAGE_BUCKET=labelsquor-crawl-data
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
```

## 💰 Cost Comparison

| Platform | Cost | Best For |
|----------|------|----------|
| GitHub Actions | Free | Small-scale, scheduled |
| Scrapy Cloud | $9/unit | Medium-scale, managed |
| AWS Lambda | $0.20/1M requests | Event-driven, small |
| Cloud Run | $0.00002/vCPU-second | Auto-scaling |
| VPS | $5-20/month | Full control |

## 🚦 Quick Start

1. **For testing**: Use GitHub Actions
2. **For production**: Start with Scrapy Cloud
3. **For scale**: Move to Kubernetes
