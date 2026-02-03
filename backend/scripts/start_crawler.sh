#!/bin/bash
set -e

# Define persistence directory
JOBDIR="/app/crawlers_jobdir/universal_spider"

echo "Starting Crawler Service..."
echo "Persistence Directory: $JOBDIR"

# Check if JOBDIR exists (implies a previous run)
if [ -d "$JOBDIR" ]; then
    echo "Found existing job directory. Resuming crawl..."
else
    echo "No existing job directory found. Starting fresh crawl..."
fi

# Run Scrapy with JOBDIR for breakpoint resumption
# We use 'universal_spider' as the default spider name, strictly following the codebase
scrapy crawl universal_news_spider -s JOBDIR="$JOBDIR"
