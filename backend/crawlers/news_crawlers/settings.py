# Scrapy settings for news_crawlers project
import sys
import os

# Path Configuration:
# Add project root to sys.path to allow imports from backend modules.
# Research Motivation: Enables integration of shared backend operators (Intelligence, Storage) into the Scrapy subsystem.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

BOT_NAME = "GlobeMediaPulse"

SPIDER_MODULES = ["backend.crawlers.news_crawlers.spiders"]
NEWSPIDER_MODULE = "backend.crawlers.news_crawlers.spiders"

# Robot Protocol Compliance
ROBOTSTXT_OBEY = True

# Concurrency & Performance Tuning
# Research Motivation: High throughput is required to monitor global media.
# CONCURRENT_REQUESTS: Reduced to 16 to ensure stability with Playwright and prevent resource exhaustion.
CONCURRENT_REQUESTS = 16

# Rate Limiting
# DOWNLOAD_DELAY: Increased to 1.0s to ensure politeness and avoid IP bans.
DOWNLOAD_DELAY = 1.0

# Disable cookies to prevent tracking and session issues
COOKIES_ENABLED = False

# Disable Telnet to reduce attack surface
TELNETCONSOLE_ENABLED = False

# Default Headers
DEFAULT_REQUEST_HEADERS = {
   "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
   "Accept-Language": "en",
}

# Pipeline Configuration
# Research Motivation: Defines the processing chain for crawled items.
# 300: Classification (Enrichment)
# 400: Storage (Persistence)
ITEM_PIPELINES = {
   "news_crawlers.pipelines.ClassificationPipeline": 300,
   "news_crawlers.pipelines.EthicalFirewallPipeline": 320,
   "news_crawlers.pipelines.EntityAlignmentPipeline": 360,
   "news_crawlers.pipelines.PostgresStoragePipeline": 400,
   "news_crawlers.pipelines.RedisPublishPipeline": 410,
}

# Distributed Crawling Configuration (Scrapy-Redis)
# Research Motivation: Enables distributed crawling across multiple containers/VMs using Redis as the shared queue.

# Scheduler: Use Redis-based scheduler
SCHEDULER = "scrapy_redis.scheduler.Scheduler"

# Deduplication: Use Redis for global duplicate filtering
DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"

# Persistence: Keep the queue on disk (Redis AOF/RDB) to survive restarts
SCHEDULER_PERSIST = True

# Redis Connection
# Research Motivation: Dynamic configuration for Container vs Local environments.
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6380")

# Future-proofing settings
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

# Playwright Configuration
# Research Motivation: Necessary for rendering JavaScript-heavy modern news sites (SPA).
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

# Remote Playwright (Docker/Production) vs Local Playwright (Dev)
PLAYWRIGHT_CDP_URL = os.getenv("PLAYWRIGHT_CDP_URL")
if PLAYWRIGHT_CDP_URL:
    # Use remote browser (e.g., browserless/chrome in Docker)
    pass
else:
    # Use local browser
    PLAYWRIGHT_LAUNCH_OPTIONS = {
        "headless": True,
        "timeout": 30000,
        "args": ["--disable-gpu", "--no-sandbox"]
    }
# Optimize Twisted Reactor for high concurrency
REACTOR_THREADPOOL_MAXSIZE = 30
