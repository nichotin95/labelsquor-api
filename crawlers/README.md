# LabelSquor Scrapy Crawlers

This directory contains Scrapy spiders for crawling Indian e-commerce sites with advanced anti-blocking measures for cloud deployments.

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
- **Anti-Blocking**: Advanced measures for cloud deployments
- **Free Proxy Rotation**: Automatic proxy management
- **Retailer-Specific Strategies**: Custom handling per retailer

## Anti-Blocking Solutions (NEW!)

**Problem**: Retailers block cloud IPs (GCP, AWS, etc.)

**Free Solutions**:
1. **GitHub Actions** - Run from GitHub's trusted IPs
2. **Free Proxy Rotation** - Automatic proxy management
3. **Smart Detection** - Auto-adapts to environment

**Quick Start**:
```bash
# Auto-detects environment and applies appropriate strategy
python run_crawler.py bigbasket

# Or use GitHub Actions (most reliable)
gh workflow run crawl-products -f retailer=bigbasket
```

See [ANTIBLOCK_GUIDE.md](ANTIBLOCK_GUIDE.md) for details.
