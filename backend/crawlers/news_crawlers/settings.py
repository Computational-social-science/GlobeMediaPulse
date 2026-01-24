# Scrapy settings for news_crawlers project
import sys
import os

# Add project root to sys.path to allow imports from backend
# This is necessary because the spider imports from backend.operators
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

BOT_NAME = "GlobeMediaPulse"

SPIDER_MODULES = ["news_crawlers.spiders"]
NEWSPIDER_MODULE = "news_crawlers.spiders"

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Configure maximum concurrent requests performed by Scrapy (default: 16)
CONCURRENT_REQUESTS = 32

# Configure a delay for requests for the same website (default: 0)
DOWNLOAD_DELAY = 1
# The download delay setting will honor only one of:
#CONCURRENT_REQUESTS_PER_DOMAIN = 16
#CONCURRENT_REQUESTS_PER_IP = 16

# Disable cookies (enabled by default)
COOKIES_ENABLED = False

# Telnet Console (enabled by default)
TELNETCONSOLE_ENABLED = False

# Override the default request headers:
DEFAULT_REQUEST_HEADERS = {
   "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
   "Accept-Language": "en",
}

# Enable or disable spider middlewares
#SPIDER_MIDDLEWARES = {
#    "news_crawlers.middlewares.NewsCrawlersSpiderMiddleware": 543,
#}

# Enable or disable downloader middlewares
#DOWNLOADER_MIDDLEWARES = {
#    "news_crawlers.middlewares.NewsCrawlersDownloaderMiddleware": 543,
#}

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {
   "news_crawlers.pipelines.ClassificationPipeline": 300,
   "news_crawlers.pipelines.PostgresStoragePipeline": 400,
   # Store items in Redis for further processing if needed
   # 'scrapy_redis.pipelines.RedisPipeline': 400,
}

# Scrapy-Redis Configuration
# ==========================
# Enables scheduling storing requests queue in redis.
SCHEDULER = "scrapy_redis.scheduler.Scheduler"

# Ensure all spiders share same duplicates filter through redis.
DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"

# Default requests serializer is pickle, but it can be changed to any module
# with loads and dumps functions. Note that pickle is not compatible between
# python versions.
# SCHEDULER_SERIALIZER = "scrapy_redis.picklecompat"

# Don't cleanup redis queues, allows to pause/resume crawls.
SCHEDULER_PERSIST = True

# Schedule requests using a priority queue. (default)
# SCHEDULER_QUEUE_CLASS = 'scrapy_redis.queue.PriorityQueue'

# Alternative: FIFO or LIFO queues.
# SCHEDULER_QUEUE_CLASS = 'scrapy_redis.queue.FifoQueue'
# SCHEDULER_QUEUE_CLASS = 'scrapy_redis.queue.LifoQueue'

# Redis Connection URL
# Assuming Redis is available at redis:6379 (Docker) or localhost:6379
# In docker-compose, hostname is 'redis'.
# But when running locally outside docker, it might be localhost.
# We can use REDIS_URL environment variable or default.
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Set settings whose default value is deprecated to a future-proof value
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

# Playwright Settings (Optional, enabled if needed per spider)
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "timeout": 20000,  # 20 seconds
}
