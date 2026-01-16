#!/bin/bash
set -e

echo "🚀 Starting Deployment..."

# 3. Push to GitHub
echo "📦 Pushing code to GitHub..."
git add .

# Check if there are changes to commit
if git diff-index --quiet HEAD --; then
    echo "No changes to commit. Pushing anyway..."
else
    # Use the first argument as commit message, or default to "Update site"
    MSG="$1"
    if [ -z "$MSG" ]; then
        MSG="Update site $(date +'%Y-%m-%d %H:%M:%S')"
    fi
    git commit -m "$MSG"
fi

# Ensure remote 'origin' exists and points to the correct URL
if ! git remote | grep -q "^origin$"; then
    git remote add origin git@github.com:guyronhuji/JCR_Data.git
else
    git remote set-url origin git@github.com:guyronhuji/JCR_Data.git
fi

git push -u origin main --force

echo "✅ Pushed successfully!"
