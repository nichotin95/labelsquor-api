# LabelSquor Scrapy Crawlers

This directory contains Scrapy spiders for crawling Indian e-commerce sites.

## Architecture

```
crawlers/
├── labelsquor_crawlers/
│   ├── spiders/
│   │   ├── bigbasket.py
│   │   ├── blinkit.py
│   │   ├── zepto.py
│   │   └── amazon_in.py
│   ├── items.py          # Data models
│   ├── pipelines.py      # Send to LabelSquor API
│   └── settings.py       # Scrapy settings
├── requirements.txt
├── scrapy.cfg
└── Dockerfile
```

## Deployment Options

### 1. Scrapy Cloud (Easiest)
```bash
# Install shub
pip install shub

# Deploy to Scrapy Cloud
shub deploy
```

### 2. Self-Hosted on AWS/GCP
```bash
# Build Docker image
docker build -t labelsquor-crawlers .

# Deploy to Cloud Run / ECS / Kubernetes
```

### 3. GitHub Actions (Scheduled Crawls)
- Use GitHub Actions for scheduled crawls
- Free for public repos
- Runs in GitHub's cloud

## Usage

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run a spider
scrapy crawl bigbasket

# Run with API pipeline
scrapy crawl bigbasket -s API_URL=http://localhost:8000
```

### Cloud Deployment (Scrapyd)
```bash
# Deploy spider
scrapyd-deploy production

# Schedule a crawl
curl http://your-scrapyd:6800/schedule.json \
  -d project=labelsquor_crawlers \
  -d spider=bigbasket
```

## Features

- **Polite Crawling**: Respects robots.txt and rate limits
- **JavaScript Support**: Uses Scrapy-Playwright for dynamic sites
- **Automatic Retries**: Built-in retry middleware
- **Data Pipeline**: Sends directly to LabelSquor API
- **Cloud Storage**: Saves HTML/images to S3/GCS
- **Monitoring**: Scrapy stats and error tracking
