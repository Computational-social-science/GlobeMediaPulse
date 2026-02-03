#!/bin/bash

# ==============================================================================
# Generate Deployment Report
# Usage: ./generate_report.sh <status> <commit_sha>
# ==============================================================================

STATUS=$1
COMMIT=$2
DATE=$(date -u +"%Y-%m-%d %H:%M UTC")

echo "## Deployment Report"
echo "- **Date:** $DATE"
echo "- **Status:** $STATUS"
echo "- **Commit:** $COMMIT"

if [ "$STATUS" == "failure" ]; then
    echo "🚨 **ALERT:** Deployment Failed. Rollback initiated."
    echo "Check Sentry and GitHub Actions logs for details."
else
    echo "✅ **SUCCESS:** Service is healthy and verified by Smoke Tests."
fi
