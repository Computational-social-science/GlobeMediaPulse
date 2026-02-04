#!/bin/bash
set -e

# Scientific Validation Suite
# Usage: ./validate_deployment.sh

echo "========================================================"
echo "   GlobeMediaPulse - Scientific Validation Suite"
echo "========================================================"

# 1. Environment Check
echo "[1/4] Checking Environment..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found."
    exit 1
fi
if ! command -v python &> /dev/null; then
    echo "❌ Python not found."
    exit 1
fi

# 2. Service Startup
echo "[2/4] Starting Services (Single-Machine)..."
if command -v docker-compose >/dev/null 2>&1; then
  docker-compose up -d --build
else
  docker compose up -d --build
fi
echo "Waiting for services to stabilize (30s)..."
sleep 30

# 3. Running Acceptance Tests
echo "[3/4] Running Acceptance Tests (Pytest)..."
pip install pytest requests sqlalchemy psycopg2-binary
mkdir -p reports
pytest tests/acceptance_test.py -v --junitxml=reports/test_report.xml

# 4. Generate Report
echo "[4/4] Generating Validation Report..."
echo "# Scientific Validation Report" > reports/validation_summary.md
echo "**Date:** $(date)" >> reports/validation_summary.md
echo "**Status:** PASSED" >> reports/validation_summary.md
echo "## Test Results" >> reports/validation_summary.md
echo "- Core Services: ✅ Healthy" >> reports/validation_summary.md
echo "- Database Persistence: ✅ Verified" >> reports/validation_summary.md
echo "- API Connectivity: ✅ Verified" >> reports/validation_summary.md

echo "✅ Validation Complete! System is ready for research data collection."
