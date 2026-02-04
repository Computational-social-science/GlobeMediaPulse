# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from scrapy import signals
import os
import logging

logger = logging.getLogger(__name__)

from fake_useragent import UserAgent


class RandomUserAgentMiddleware:
    """
    Middleware to rotate User-Agent headers.
    Uses `fake-useragent` library to generate realistic browser signatures.
    """

    def __init__(self, crawler):
        self.ua = UserAgent()
        self.ua_type = crawler.settings.get("RANDOM_UA_TYPE", "desktop")

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def process_request(self, request, spider):
        # Skip if User-Agent is already set (e.g. by Playwright or custom header)
        if "User-Agent" in request.headers:
            return

        try:
            # Generate random UA
            user_agent = self.ua.random
            request.headers["User-Agent"] = user_agent
            # spider.logger.debug(f"Assigned User-Agent: {user_agent}")
        except Exception as e:
            spider.logger.warning(f"Failed to generate Random User-Agent: {e}")
            # Fallback to default
            request.headers["User-Agent"] = "GlobeMediaPulse/1.0 (+http://www.globemediapulse.org/bot)"


class NewsCrawlersSpiderMiddleware:
    """
    Standard Scrapy Spider Middleware.

    Research Motivation:
        - Hooks into the spider processing lifecycle.
        - Currently used for logging and basic signal handling.
        - Can be extended for custom request/response transformation.
    """

    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        return None

    def process_spider_output(self, response, result, spider):
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        ex_class = type(exception).__name__
        try:
            spider.crawler.stats.inc_value(f"scrapy_err/spider_exception/{ex_class}")
        except Exception:
            pass
        spider.logger.error(f"Spider Exception: {ex_class}: {exception} URL: {response.url}")
        return []

    def process_start_requests(self, start_requests, spider):
        for r in start_requests:
            yield r

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class NewsCrawlersDownloaderMiddleware:
    """
    Standard Scrapy Downloader Middleware.

    Research Motivation:
        - Hooks into the download process.
        - Can be used for custom proxy rotation, user-agent spoofing, or request signing.
    """

    def __init__(self, crawler):
        self._proxy_idx = 0
        proxy_urls = (os.getenv("PROXY_URLS") or "").strip()
        self._proxies = [p.strip() for p in proxy_urls.split(",") if p.strip()] if proxy_urls else []
        self._ua = None
        try:
            self._ua = UserAgent()
        except Exception:
            self._ua = None

    @classmethod
    def from_crawler(cls, crawler):
        s = cls(crawler)
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        if self._proxies and (request.meta.get("gmp_force_new_proxy") or "proxy" not in request.meta):
            request.meta.pop("gmp_force_new_proxy", None)
            request.meta["proxy"] = self._proxies[self._proxy_idx % len(self._proxies)]
            self._proxy_idx += 1

        if self._ua and "User-Agent" not in request.headers:
            request.headers["User-Agent"] = self._ua.random
        return None

    def process_response(self, request, response, spider):
        return response

    def process_exception(self, request, exception, spider):
        pass

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message


class SmartRetryMiddleware(RetryMiddleware):
    """
    Enhanced Retry Middleware with Graded Backoff and Error Classification.

    Strategies:
    1. Network Errors (DNS, Timeout) -> Standard Retry (Immediate/Short Backoff).
    2. Server Errors (500, 502) -> Standard Retry (Short Backoff).
    3. Rate Limits (429) -> Long Backoff (30s+).
    4. Anti-Bot (403) -> No Retry (or specialized proxy rotation if enabled).
    """

    def __init__(self, settings, crawler):
        super().__init__(settings)
        self._retry_403_enabled = bool(settings.getbool("RETRY_403_ENABLED", False))
        self._retry_403_times = int(settings.getint("RETRY_403_TIMES", 1))
        self.crawler = crawler

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings, crawler)

    def process_response(self, request, response, spider):
        if request.meta.get("dont_retry", False):
            return response

        if response.status == 403:
            spider.logger.warning(f"Access Forbidden (403) by {response.url}. Possible IP Ban.")
            retry_times = int(request.meta.get("retry_times") or 0)
            if self._retry_403_enabled and retry_times < self._retry_403_times:
                request.meta["gmp_force_new_proxy"] = True
                reason = response_status_message(response.status)
                return self._retry(request, reason) or response
            return response

        if response.status in self.retry_http_codes:
            reason = response_status_message(response.status)

            # Graded Logic
            if response.status == 429:
                spider.logger.warning(f"Rate Limited (429) by {response.url}. Triggering retry.")
                request.meta["gmp_force_new_proxy"] = True
                return self._retry(request, reason) or response

            return self._retry(request, reason) or response

        return response

    def process_exception(self, request, exception, spider):
        # Categorize Exception for Monitoring
        ex_class = type(exception).__name__

        # 1. Network Errors
        if ex_class in [
            "TimeoutError",
            "TCPTimedOutError",
            "DNSLookupError",
            "ConnectionRefusedError",
            "ResponseNeverReceived",
            "ConnectionLost",
        ]:
            spider.crawler.stats.inc_value(f"scrapy_err/category/network/{ex_class}")
            return self._retry(request, exception)

        # 2. System/Resource Errors
        if ex_class in ["MemoryError", "OSError"]:
            spider.crawler.stats.inc_value(f"scrapy_err/category/system/{ex_class}")
            # Do not retry system errors, let it fail
            return None

        # 3. Other (Parsing/Unknown) - usually caught in SpiderMiddleware, but if here, it's download level
        spider.crawler.stats.inc_value(f"scrapy_err/category/unknown/{ex_class}")
        return self._retry(request, exception)


class ScrapyErrMonitorMiddleware:
    """
    Custom Middleware for monitoring and handling high-frequency ScrapyErr.

    Research Motivation:
        - Intercepts non-200 responses and transport level exceptions.
        - Implements custom circuit breaker or degraded mode logging.
    """

    def __init__(self, stats, alert_threshold: int):
        self.stats = stats
        self.alert_threshold = int(alert_threshold) if int(alert_threshold) > 0 else 50

    @classmethod
    def from_crawler(cls, crawler):
        threshold = int(crawler.settings.getint("GMP_CRAWLER_ALERT_THRESHOLD", 50))
        return cls(crawler.stats, threshold)

    def process_response(self, request, response, spider):
        if response.status >= 400:
            self.stats.inc_value(f"scrapy_err/status/{response.status}")
            try:
                current = int(self.stats.get_value(f"scrapy_err/status/{response.status}") or 0)
            except Exception:
                current = 0
            if current and self.alert_threshold and (current % self.alert_threshold == 0):
                spider.logger.error(f"GMP_ALERT status={response.status} count={current} url={response.url}")
            if response.status == 403:
                return response
            if response.status == 429:
                backoff = int(request.meta.get("gmp_retry_backoff", 1))
                request.meta["gmp_retry_backoff"] = min(backoff * 2, 64)
                request.priority = int(request.priority) - (request.meta["gmp_retry_backoff"] * 100)
        return response

    def process_exception(self, request, exception, spider):
        ex_class = type(exception).__name__
        self.stats.inc_value(f"scrapy_err/exception/{ex_class}")
        try:
            current = int(self.stats.get_value(f"scrapy_err/exception/{ex_class}") or 0)
        except Exception:
            current = 0
        if current and self.alert_threshold and (current % self.alert_threshold == 0):
            spider.logger.error(f"GMP_ALERT exception={ex_class} count={current} url={request.url}")

        # Log detail for specific high-frequency errors
        if ex_class in ["TimeoutError", "TCPTimedOutError", "DNSLookupError"]:
            spider.logger.warning(f"Network Error ({ex_class}) for {request.url}: {exception}")
            # Let Scrapy's RetryMiddleware handle it, but log it distinctly
        elif ex_class == "ResponseNeverReceived":
            spider.logger.warning(f"Connection Reset/Closed for {request.url}")

        return None  # Continue to other middlewares (e.g. Retry)
