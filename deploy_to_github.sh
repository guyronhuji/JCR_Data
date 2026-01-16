#!/bin/bash
set -e

# Check for ~/.env and source it
if [ -f "$HOME/.env" ]; then
    echo "Loading environment from ~/.env"
    set -a
    source "$HOME/.env"
    set +a
fi

# Configuration
REPO_HOST="github.com/guyronhuji/JCR_Data.git"
BRANCH="main"

if [ -z "$GITHUB_TOKEN" ]; then
    echo "GITHUB_TOKEN is not set."
    echo "To avoid manual login issues, please enter your GitHub Personal Access Token."
    echo "You can generate one here: https://github.com/settings/tokens (Select 'repo' scope)"
    read -sp "Token: " GITHUB_TOKEN
    echo ""
    
    if [ -z "$GITHUB_TOKEN" ]; then
        echo "No token provided. Attempting standard HTTPS (may fail if you don't have a credential helper)..."
        REPO_URL="https://$REPO_HOST"
    else
         REPO_URL="https://oauth2:$GITHUB_TOKEN@$REPO_HOST"
    fi
else
    echo "Using provided GITHUB_TOKEN environment variable."
    REPO_URL="https://oauth2:$GITHUB_TOKEN@$REPO_HOST"
fi

echo "Using repository: $REPO_URL"

# Initialize Git if not already done
if [ ! -d ".git" ]; then
    echo "Initializing new git repository..."
    git init
else
    echo "Git repository already initialized."
fi

# Configure Remote
if git remote | grep -q "^origin$"; then
    echo "Remote 'origin' already exists. Updating URL..."
    git remote set-url origin "$REPO_URL"
else
    echo "Adding remote 'origin'..."
    git remote add origin "$REPO_URL"
fi

# Add changes
echo "Adding files..."
git add .

# Commit (allow empty if nothing changed)
echo "Committing changes..."
if ! git diff-index --quiet HEAD; then
    git commit -m "Deploy: Updated project files and build configuration"
else
    echo "No changes to commit."
fi

# Rename branch to main
git branch -M "$BRANCH"

# Push
echo "Pushing to $BRANCH..."
git push -u origin "$BRANCH"

echo "----------------------------------------"
echo "Deployment complete!"
echo "Check your Actions tab here: https://github.com/guyronhuji/SJR_Data/actions"
