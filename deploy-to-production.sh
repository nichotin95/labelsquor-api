#!/bin/bash
# Deploy to Production Script
# This script merges main into production and triggers deployment

set -e  # Exit on error

echo "🚀 LabelSquor API - Deploy to Production"
echo "========================================"
echo ""

# Check if we're on main branch
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "❌ Error: You must be on the 'main' branch to deploy"
    echo "   Current branch: $CURRENT_BRANCH"
    echo "   Run: git checkout main"
    exit 1
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "❌ Error: You have uncommitted changes"
    echo "   Please commit or stash your changes before deploying"
    exit 1
fi

# Fetch latest changes
echo "📥 Fetching latest changes..."
git fetch origin main production

# Check if main is up to date
LOCAL_MAIN=$(git rev-parse main)
REMOTE_MAIN=$(git rev-parse origin/main)
if [ "$LOCAL_MAIN" != "$REMOTE_MAIN" ]; then
    echo "❌ Error: Your main branch is not up to date"
    echo "   Run: git pull origin main"
    exit 1
fi

# Create temporary branch for merge
TEMP_BRANCH="deploy-$(date +%Y%m%d-%H%M%S)"
echo ""
echo "🔀 Creating deployment branch: $TEMP_BRANCH"
git checkout -b "$TEMP_BRANCH"

# Merge production to get infrastructure files
echo ""
echo "📦 Merging infrastructure from production..."
git merge origin/production --no-commit --no-ff || true

# Reset business logic files to main version
echo ""
echo "🔧 Keeping business logic from main..."
# Keep all Python files from main
git checkout main -- "*.py"
git checkout main -- "app/"
git checkout main -- "tests/"
git checkout main -- "scripts/"

# Keep infrastructure files from production
echo ""
echo "🏗️  Keeping infrastructure from production..."
git checkout origin/production -- Dockerfile 2>/dev/null || true
git checkout origin/production -- .github/workflows/deploy-to-gcp.yml 2>/dev/null || true
git checkout origin/production -- .gcloudignore 2>/dev/null || true
git checkout origin/production -- GITHUB_DEPLOYMENT_SETUP.md 2>/dev/null || true

# Handle requirements carefully
echo ""
echo "📋 Merging requirements..."
# Start with production requirements
git checkout origin/production -- requirements/ 2>/dev/null || true
# Add google-genai if missing
if ! grep -q "google-genai" requirements/base.txt; then
    echo "google-genai==1.37.0" >> requirements/base.txt
fi

# Stage all changes
git add -A

# Show what will be deployed
echo ""
echo "📊 Changes to be deployed:"
git status --short

# Commit the merge
echo ""
git commit -m "Deploy: Merge main into production $(date +%Y-%m-%d)" || {
    echo "ℹ️  No changes to deploy"
    git checkout main
    git branch -D "$TEMP_BRANCH"
    exit 0
}

# Ask for confirmation
echo ""
echo "🤔 Ready to deploy these changes to production?"
echo "   This will:"
echo "   1. Push to production branch"
echo "   2. Trigger automatic deployment to Google Cloud Run"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Deployment cancelled"
    git checkout main
    git branch -D "$TEMP_BRANCH"
    exit 1
fi

# Push to production
echo ""
echo "🚀 Pushing to production branch..."
git push origin "$TEMP_BRANCH":production --force-with-lease

# Clean up
echo ""
echo "🧹 Cleaning up..."
git checkout main
git branch -D "$TEMP_BRANCH"

# Show deployment status
echo ""
echo "✅ Deployment initiated!"
echo ""
echo "📊 Monitor deployment at:"
echo "   https://github.com/nichotin95/labelsquor-api/actions"
echo ""
echo "🔍 View logs with:"
echo "   gh run list --workflow=deploy-to-gcp.yml --branch production --limit 1"
echo ""
echo "🌐 API will be available at:"
echo "   https://labelsquor-api-u7wurf5zba-uc.a.run.app"
