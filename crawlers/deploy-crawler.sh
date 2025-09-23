#!/bin/bash
# Deploy crawler service to Google Cloud Run with proxy support

echo "🕷️  Deploying LabelSquor Crawler Service to GCP"
echo "============================================"

# Deploy using Cloud Build
echo "Building and deploying crawler service..."
gcloud builds submit --config cloudbuild.yaml

# Get the service URL
SERVICE_URL=$(gcloud run services describe labelsquor-crawler --region us-central1 --format 'value(status.url)')

echo ""
echo "✅ Crawler service deployed!"
echo "🌐 Service URL: $SERVICE_URL"
echo ""
echo "Test the crawler:"
echo "curl -X POST $SERVICE_URL/crawl/simple \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"retailer\": \"bigbasket\", \"search_terms\": [\"maggi\"], \"max_products\": 5}'"
