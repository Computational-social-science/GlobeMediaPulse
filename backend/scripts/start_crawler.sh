#!/bin/bash
set -e

# Define persistence directory
JOBDIR="/app/crawlers_jobdir/universal_news"

echo "Starting Crawler Service..."
echo "Persistence Directory: $JOBDIR"

# Check if JOBDIR exists (implies a previous run)
if [ -d "$JOBDIR" ]; then
    echo "Found existing job directory. Resuming crawl..."
else
    echo "No existing job directory found. Starting fresh crawl..."
fi

# Heartbeat to Redis so backend can observe external crawler liveness
CRAWLER_HEARTBEAT_KEY="${CRAWLER_HEARTBEAT_KEY:-gmp:crawler:heartbeat}"
CRAWLER_HEARTBEAT_INTERVAL_S="${CRAWLER_HEARTBEAT_INTERVAL_S:-10}"

python - <<'PY' &
import os
import time

import redis

redis_url = (os.getenv("REDIS_URL") or "").strip()
if not redis_url:
    time.sleep(365 * 24 * 3600)

key = (os.getenv("CRAWLER_HEARTBEAT_KEY") or "gmp:crawler:heartbeat").strip()
interval_s = float(os.getenv("CRAWLER_HEARTBEAT_INTERVAL_S") or "10")
ttl_s = max(5, int(interval_s * 3))

r = redis.from_url(redis_url)
while True:
    r.set(key, str(time.time()), ex=ttl_s)
    time.sleep(interval_s)
PY
HEARTBEAT_PID=$!
trap 'kill "$HEARTBEAT_PID" >/dev/null 2>&1 || true' EXIT

# Run Scrapy with JOBDIR for breakpoint resumption
# We use 'universal_news' as the spider name, matching UniversalNewsSpider.name
scrapy crawl universal_news -s JOBDIR="$JOBDIR"
