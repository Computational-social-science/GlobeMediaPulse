#!/bin/bash
set -e

# ==============================================================================
# Backend Rollback Script
# Usage: ./rollback_remote.sh
# ==============================================================================

echo "🚨 Initiating Rollback Sequence..."

# 1. Revert to previous commit
# Assuming the repo is already present and git history is available
git reset --hard HEAD@{1}

# 2. Rebuild and Restart Services
echo "Rebuilding services with previous stable commit..."
docker-compose up -d --build --remove-orphans

# 3. Verify Health
echo "Verifying service health after rollback..."
# Wait a bit for services to start
sleep 10
python3 tests/smoke_test_remote.py --url http://localhost:8000

echo "✅ Rollback Successful. Service restored to previous state."
