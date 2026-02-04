#!/bin/bash
set -e

# ==============================================================================
# Backend Rollback Script
# Usage: ./rollback_remote.sh
# ==============================================================================

echo "🚨 Initiating Rollback Sequence..."

# 1. Resolve rollback target from deployment history
HISTORY_FILE=".deploy_history"
ROLLBACK_REF=""
if [ -f "$HISTORY_FILE" ]; then
    ROLLBACK_REF="$(sed -n '2p' "$HISTORY_FILE" | tr -d '\r' | xargs || true)"
fi
if [ -z "$ROLLBACK_REF" ]; then
    ROLLBACK_REF="$(git rev-parse HEAD@{1} 2>/dev/null || true)"
fi
if [ -z "$ROLLBACK_REF" ]; then
    echo "❌ No rollback target found."
    exit 1
fi

echo "Rolling back to: $ROLLBACK_REF"
git fetch --all --tags
git checkout "$ROLLBACK_REF"
git reset --hard "$ROLLBACK_REF"

# 2. Rebuild and Restart Services
echo "Rebuilding services with previous stable commit..."
if command -v docker-compose >/dev/null 2>&1; then
    docker-compose up -d --build --remove-orphans
else
    docker compose up -d --build --remove-orphans
fi

# 3. Verify Health
echo "Verifying service health after rollback..."
# Wait a bit for services to start
sleep 10
python3 tests/smoke_test_remote.py --url http://localhost:8000

echo "✅ Rollback Successful. Service restored to previous state."
