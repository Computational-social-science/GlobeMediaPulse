# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from scrapy import signals
from scrapy.http import Response
from scrapy.exceptions import IgnoreRequest
import time
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
        self.ua_type = crawler.settings.get('RANDOM_UA_TYPE', 'desktop')

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def process_request(self, request, spider):
        # Skip if User-Agent is already set (e.g. by Playwright or custom header)
        if 'User-Agent' in request.headers:
            return
            
        try:
            # Generate random UA
            user_agent = self.ua.random
            request.headers['User-Agent'] = user_agent
            # spider.logger.debug(f"Assigned User-Agent: {user_agent}")
        except Exception as e:
            spider.logger.warning(f"Failed to generate Random User-Agent: {e}")
            # Fallback to default
            request.headers['User-Agent'] = "GlobeMediaPulse/1.0 (+http://www.globemediapulse.org/bot)"

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
        # Capture and log specific spider exceptions
        spider.logger.error(f"Spider Exception: {type(exception).__name__}: {exception} URL: {response.url}")
        pass

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

    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
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
    
    def process_response(self, request, response, spider):
        if request.meta.get('dont_retry', False):
            return response
            
        if response.status in self.retry_http_codes:
            reason = response_status_message(response.status)
            
            # Graded Logic
            if response.status == 429:
                spider.logger.warning(f"Rate Limited (429) by {response.url}. Triggering retry.")
                # Removed blocking time.sleep(30) which freezes the reactor.
                # Rely on Scrapy's retry logic and AutoThrottle.
                return self._retry(request, reason, spider) or response
                
            if response.status == 403:
                spider.logger.warning(f"Access Forbidden (403) by {response.url}. Possible IP Ban.")
                # Do not retry 403 by default unless configured
                return response

            return self._retry(request, reason, spider) or response
            
        return response

    def process_exception(self, request, exception, spider):
        # Categorize Exception for Monitoring
        ex_class = type(exception).__name__
        
        # 1. Network Errors
        if ex_class in ['TimeoutError', 'TCPTimedOutError', 'DNSLookupError', 'ConnectionRefusedError', 'ResponseNeverReceived', 'ConnectionLost']:
            spider.crawler.stats.inc_value(f'scrapy_err/category/network/{ex_class}')
            return self._retry(request, exception, spider)

        # 2. System/Resource Errors
        if ex_class in ['MemoryError', 'OSError']:
            spider.crawler.stats.inc_value(f'scrapy_err/category/system/{ex_class}')
            # Do not retry system errors, let it fail
            return None

        # 3. Other (Parsing/Unknown) - usually caught in SpiderMiddleware, but if here, it's download level
        spider.crawler.stats.inc_value(f'scrapy_err/category/unknown/{ex_class}')
        return self._retry(request, exception, spider)

class ScrapyErrMonitorMiddleware:
    """
    Custom Middleware for monitoring and handling high-frequency ScrapyErr.
    
    Research Motivation:
        - Intercepts non-200 responses and transport level exceptions.
        - Implements custom circuit breaker or degraded mode logging.
    """
    def __init__(self, stats):
        self.stats = stats

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.stats)

    def process_response(self, request, response, spider):
        # Monitor 4xx/5xx
        if response.status >= 400:
            self.stats.inc_value(f'scrapy_err/status/{response.status}')
            if response.status in [403, 429]:
                spider.logger.warning(f"High-Risk Status Code {response.status} from {request.url}. Possible Anti-Bot detection.")
                # Future: Trigger Proxy Rotation or Circuit Breaker here
        return response

    def process_exception(self, request, exception, spider):
        ex_class = type(exception).__name__
        self.stats.inc_value(f'scrapy_err/exception/{ex_class}')
        
        # Log detail for specific high-frequency errors
        if ex_class in ['TimeoutError', 'TCPTimedOutError', 'DNSLookupError']:
             spider.logger.warning(f"Network Error ({ex_class}) for {request.url}: {exception}")
             # Let Scrapy's RetryMiddleware handle it, but log it distinctly
        elif ex_class == 'ResponseNeverReceived':
             spider.logger.warning(f"Connection Reset/Closed for {request.url}")
        
        return None # Continue to other middlewares (e.g. Retry)
