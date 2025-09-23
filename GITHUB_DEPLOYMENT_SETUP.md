# GitHub to Google Cloud Run Deployment Setup

This guide helps you set up automatic deployment from GitHub to Google Cloud Run.

## Prerequisites

1. Google Cloud Project: `labelsquor-api-1758544444`
2. GitHub repository with admin access
3. Google Cloud CLI installed locally

## Setup Steps

### 1. Create Service Account for GitHub Actions

```bash
# Create service account
gcloud iam service-accounts create github-actions \
    --display-name="GitHub Actions Deployment" \
    --project=labelsquor-api-1758544444

# Grant necessary permissions
gcloud projects add-iam-policy-binding labelsquor-api-1758544444 \
    --member="serviceAccount:github-actions@labelsquor-api-1758544444.iam.gserviceaccount.com" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding labelsquor-api-1758544444 \
    --member="serviceAccount:github-actions@labelsquor-api-1758544444.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding labelsquor-api-1758544444 \
    --member="serviceAccount:github-actions@labelsquor-api-1758544444.iam.gserviceaccount.com" \
    --role="roles/artifactregistry.admin"

gcloud projects add-iam-policy-binding labelsquor-api-1758544444 \
    --member="serviceAccount:github-actions@labelsquor-api-1758544444.iam.gserviceaccount.com" \
    --role="roles/cloudbuild.builds.editor"

gcloud projects add-iam-policy-binding labelsquor-api-1758544444 \
    --member="serviceAccount:github-actions@labelsquor-api-1758544444.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding labelsquor-api-1758544444 \
    --member="serviceAccount:github-actions@labelsquor-api-1758544444.iam.gserviceaccount.com" \
    --role="roles/serviceusage.serviceUsageConsumer"

# Create and download service account key
gcloud iam service-accounts keys create github-key.json \
    --iam-account=github-actions@labelsquor-api-1758544444.iam.gserviceaccount.com
```

### 2. Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add these secrets:

1. **GCP_SA_KEY**
   - Copy the entire contents of `github-key.json`
   - Paste as the secret value

2. **DATABASE_URL**
   - Your Supabase PostgreSQL connection string
   - Format: `postgresql://user:password@host:port/database`

3. **GOOGLE_API_KEY**
   - Your Google Gemini API key
   - Get from: https://makersuite.google.com/app/apikey

4. **SECRET_KEY**
   - A secure random string for JWT tokens
   - Generate: `openssl rand -hex 32`

5. **ADMIN_API_KEY**
   - A secure API key for admin endpoints
   - Generate: `openssl rand -hex 32`

6. **FRONTEND_URL**
   - Your frontend URL (e.g., https://labelsquor.com)

### 3. Deploy

1. Commit and push to the production branch:
```bash
git add .
git commit -m "Setup Google Cloud deployment"
git push origin production
```

2. The GitHub Action will automatically:
   - Build the Docker image
   - Push to Google Container Registry
   - Deploy to Cloud Run
   - Run health checks

### 4. Monitor Deployment

- GitHub Actions: Check the Actions tab in your repository
- Cloud Run: https://console.cloud.google.com/run
- Logs: https://console.cloud.google.com/logs

## Troubleshooting

### Common Issues

1. **Permission Denied**
   - Ensure all IAM roles are granted to the service account
   - Wait 1-2 minutes for permissions to propagate

2. **Container fails to start**
   - Check Cloud Run logs for import errors
   - Verify all environment variables are set

3. **Build timeout**
   - Increase timeout in deploy command
   - Optimize Docker layers

### Manual Deployment

If automatic deployment fails, you can deploy manually:

```bash
# Build and push
docker build -t gcr.io/labelsquor-api-1758544444/labelsquor-api:latest .
docker push gcr.io/labelsquor-api-1758544444/labelsquor-api:latest

# Deploy
gcloud run deploy labelsquor-api \
    --image gcr.io/labelsquor-api-1758544444/labelsquor-api:latest \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --port 8000
```
