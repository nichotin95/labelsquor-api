# LabelSquor API Deployment Workflow

## Overview
The deployment workflow ensures that business logic from `main` branch is deployed to production while maintaining production-specific infrastructure configurations.

## Branch Strategy
- **`main`**: Development branch with latest business logic
- **`production`**: Deployment branch with infrastructure configs + business logic from main

## Deployment Process

### Quick Deploy
```bash
# Deploy main to production
make deploy
```

### Manual Deploy
```bash
# Ensure you're on main and up-to-date
git checkout main
git pull origin main

# Run deployment script
./deploy-to-production.sh
```

### Check Deployment Status
```bash
# View deployment status
make deploy-status

# Or view in browser
open https://github.com/nichotin95/labelsquor-api/actions
```

## What Happens During Deployment

1. **Validation**:
   - Ensures you're on `main` branch
   - Checks for uncommitted changes
   - Verifies main is up-to-date

2. **Merge Process**:
   - Creates temporary deployment branch
   - Merges infrastructure from `production`
   - Keeps business logic from `main`
   - Preserves these production files:
     - `Dockerfile`
     - `.github/workflows/deploy-to-gcp.yml`
     - `.gcloudignore`
     - Infrastructure documentation

3. **Requirements Handling**:
   - Merges requirements intelligently
   - Ensures `google-genai` package is included
   - Removes non-existent packages

4. **Deployment**:
   - Pushes to `production` branch
   - Triggers GitHub Actions workflow
   - Deploys to Google Cloud Run

## Important Notes

- **Never push directly to `production`** - always use the deployment script
- The deployment requires confirmation before pushing
- GitHub Actions will automatically deploy when `production` is updated
- The API URL remains constant: https://labelsquor-api-u7wurf5zba-uc.a.run.app

## Monitoring

After deployment:
1. Check GitHub Actions: https://github.com/nichotin95/labelsquor-api/actions
2. Monitor Cloud Run logs:
   ```bash
   gcloud logging read "resource.type=cloud_run_revision" \
     --project labelsquor-api-1758544444 --limit 50
   ```
3. Test the API:
   ```bash
   curl https://labelsquor-api-u7wurf5zba-uc.a.run.app/api/v1/health
   ```

## Rollback

If deployment fails:
1. Check the error in GitHub Actions logs
2. Fix the issue in `main` branch
3. Run deployment again

To rollback to previous version:
```bash
# On Google Cloud Console, revert to previous revision
# Or use gcloud CLI to route traffic to previous revision
```
