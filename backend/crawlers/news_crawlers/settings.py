# Scrapy settings for news_crawlers project
import sys
import os
from dotenv import load_dotenv

# Load env vars from .env file if present
if not os.path.exists("/.dockerenv"):
    load_dotenv()

# Path Configuration:
# Add project root to sys.path to allow imports from backend modules.
# Research Motivation: Enables integration of shared backend operators (Intelligence, Storage) into the Scrapy subsystem.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

# ==============================================================================
# 1. MANDATORY SECURITY CONFIGURATION
# ==============================================================================
# Research Motivation:
# Enforce strict API key validation at startup to prevent runtime failures deep in the pipeline.
# The token is masked in logs to comply with security standards.
MEDIA_CLOUD_API_KEY = os.getenv("MEDIA_CLOUD_API_KEY")
if not MEDIA_CLOUD_API_KEY:
    # Changed from CRITICAL ERROR to WARNING to allow crawler to run with limited functionality
    sys.stderr.write("WARNING: MEDIA_CLOUD_API_KEY is missing from environment variables.\n")
    sys.stderr.write("Media Cloud integration will be disabled. Proceeding with limited functionality.\n")
    MEDIA_CLOUD_API_KEY = ""
else:
    # Masking secret for logging (if used elsewhere)
    _MASKED_KEY = f"{MEDIA_CLOUD_API_KEY[:4]}...{MEDIA_CLOUD_API_KEY[-4:]}"
    # print(f"Media Cloud Integration Enabled with Key: {_MASKED_KEY}")

BOT_NAME = "GlobeMediaPulse"

SPIDER_MODULES = ["news_crawlers.spiders"]
NEWSPIDER_MODULE = "news_crawlers.spiders"

# Robot Protocol Compliance
ROBOTSTXT_OBEY = True

# ==============================================================================
# 2. CONCURRENCY & PERFORMANCE TUNING
# ==============================================================================
# Research Motivation:
# - High throughput is required to monitor global media.
# - Stability is prioritized over raw speed to prevent "ScrapyErr" cascades.

# Reduced from 16 to 8 to mitigate ScrapyErr spikes (DNS/Timeout)
CONCURRENT_REQUESTS = 8

# Increase global timeout to handle slow global south servers
DOWNLOAD_TIMEOUT = 30
DNS_TIMEOUT = 10

# ==============================================================================
# 3. ROBUSTNESS & RETRY STRATEGIES (Anti-ScrapyErr)
# ==============================================================================
# Research Motivation:
# - Network instability is expected when crawling diverse global sources.
# - Aggressive retries with backoff reduce transient failures (5xx, DNS).

RETRY_ENABLED = True
RETRY_TIMES = 3  # Increased from default (2)
RETRY_HTTP_CODES = [500, 502, 503, 504, 522, 524, 408, 429]
RETRY_PRIORITY_ADJUST = -1

# Rate Limiting & AutoThrottle
# DOWNLOAD_DELAY: Increased to 1.0s to ensure politeness and avoid IP bans.
DOWNLOAD_DELAY = 1.0

# AutoThrottle: Dynamic adjustment based on load
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 60.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
AUTOTHROTTLE_DEBUG = False  # Set True to debug throttling logic

# Disable cookies to prevent tracking and session issues
COOKIES_ENABLED = False

# Disable Telnet to reduce attack surface
TELNETCONSOLE_ENABLED = False

# Default Headers
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en",
    "User-Agent": "GlobeMediaPulse/1.0 (+http://www.globemediapulse.org/bot)",  # Identify nicely
}

# ==============================================================================
# 4. PIPELINE CONFIGURATION
# ==============================================================================
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

# Enable Custom Middleware
DOWNLOADER_MIDDLEWARES = {
    "news_crawlers.middlewares.RandomUserAgentMiddleware": 400,  # Priority before Retry/Default
    "news_crawlers.middlewares.ScrapyErrMonitorMiddleware": 543,  # Before Retry (550)
    # 'scrapy.downloadermiddlewares.retry.RetryMiddleware': 550, # Disable default
    "news_crawlers.middlewares.SmartRetryMiddleware": 550,  # Use Custom Smart Retry
    "news_crawlers.middlewares.NewsCrawlersDownloaderMiddleware": 560,
}

# ==============================================================================
# 5. DISTRIBUTED CRAWLING (Scrapy-Redis)
# ==============================================================================
# Research Motivation: Enables distributed crawling across multiple containers/VMs using Redis as the shared queue.

# Scheduler: Use Redis-based scheduler
SCHEDULER = "scrapy_redis.scheduler.Scheduler"

# Deduplication: Use Redis for global duplicate filtering
DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"

# Persistence: Keep the queue on disk (Redis AOF/RDB) to survive restarts
SCHEDULER_PERSIST = True

# Redis Connection
# Research Motivation: Dynamic configuration for Container vs Local environments.
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Future-proofing settings
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

# ==============================================================================
# 6. PLAYWRIGHT & BROWSER CONFIGURATION
# ==============================================================================
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
    PLAYWRIGHT_LAUNCH_OPTIONS = {"headless": True, "timeout": 30000, "args": ["--disable-gpu", "--no-sandbox"]}
# Optimize Twisted Reactor for high concurrency
REACTOR_THREADPOOL_MAXSIZE = 30
