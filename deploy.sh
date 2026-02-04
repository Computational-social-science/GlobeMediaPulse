#!/bin/bash
set -e

# ==============================================================================
# GlobeMediaPulse - Zero-Threshold Deployment Script
# Usage: ./deploy.sh
# ==============================================================================

echo "========================================================"
echo "   GlobeMediaPulse - Automated Deployment System"
echo "========================================================"

# Optional: pin deployment to a specific ref (tag/sha/branch)
DEPLOY_REF="${DEPLOY_REF:-${1:-}}"

# 1. Environment Check
echo "[1/5] Checking Environment Prerequisites..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Installing..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo "⚠️  Please log out and log back in to apply Docker group changes."
    exit 1
fi

# 2. Configuration Setup
echo "[2/5] Setting up Configuration..."
if [ ! -f .env ]; then
    echo "Creating .env from example..."
    cp .env.example .env
fi

# 2.1 Track deployment history (for fast rollback)
HISTORY_FILE=".deploy_history"
PRE_DEPLOY_REF="$(git rev-parse HEAD 2>/dev/null || true)"

# 2.2 Update git ref if requested (tag/sha), otherwise use current branch HEAD
if [ -n "$DEPLOY_REF" ]; then
    echo "Checking out deploy ref: $DEPLOY_REF"
    git fetch --all --tags
    git checkout "$DEPLOY_REF"
    git reset --hard "$DEPLOY_REF"
else
    git fetch origin main --tags
    git checkout main
    git reset --hard origin/main
fi

POST_DEPLOY_REF="$(git rev-parse HEAD 2>/dev/null || true)"
if [ -n "$POST_DEPLOY_REF" ]; then
    {
        echo "$POST_DEPLOY_REF"
        if [ -n "$PRE_DEPLOY_REF" ] && [ "$PRE_DEPLOY_REF" != "$POST_DEPLOY_REF" ]; then
            echo "$PRE_DEPLOY_REF"
        elif [ -f "$HISTORY_FILE" ]; then
            sed -n '1,2p' "$HISTORY_FILE" | tail -n 1
        fi
    } | awk 'NF' | head -n 2 > "${HISTORY_FILE}.tmp" || true
    if [ -s "${HISTORY_FILE}.tmp" ]; then
        mv "${HISTORY_FILE}.tmp" "$HISTORY_FILE"
    else
        rm -f "${HISTORY_FILE}.tmp"
    fi
fi

# 3. Build & Start Services
echo "[3/5] Building and Starting Services..."
if command -v docker-compose >/dev/null 2>&1; then
    docker-compose down --remove-orphans
    docker-compose up -d --build
else
    docker compose down --remove-orphans
    docker compose up -d --build
fi

# 4. Wait for Health Checks
echo "[4/5] Waiting for System Health..."
./scripts/validate_deployment.sh

# 5. Final Status
echo "========================================================"
echo "✅ Deployment Complete!"
echo "   - Backend API: http://localhost:8000"
echo "   - Frontend:    http://localhost:5173 (if running dev)"
echo "   - Health Check: http://localhost:8000/health"
echo "========================================================"
