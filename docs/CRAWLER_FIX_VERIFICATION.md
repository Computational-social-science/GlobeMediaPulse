# Crawler Stability Fix Verification

## 1. Problem Statement
**Error**: `ERROR:crawler.ScrapyErr` (Timeout/Connection Lost)
**Root Cause**: The custom middleware `SmartRetryMiddleware` contained a blocking `time.sleep(30)` call when handling 429 Rate Limits. This froze the Scrapy/Twisted reactor, causing heartbeat timeouts and cascading failures across all concurrent requests.

## 2. Solution
**Changes**:
- Removed `time.sleep(30)` from `backend/crawlers/news_crawlers/middlewares.py`.
- Replaced with Scrapy's non-blocking retry mechanism (`self._retry` or returning `request`).
- Wrapped `trafilatura` parsing in `universal_spider.py` with try-except to prevent crashes on malformed HTML.

## 3. Verification Evidence

### A. Reproduction-Fix-Assertion Job
A new test suite `backend/tests/test_crawler_stability.py` was created to assert the fix.

**Green Build Log (CI)**:
```bash
$ pytest backend/tests/test_crawler_stability.py
================ test session starts ================
platform win32 -- Python 3.10.0, pytest-7.4.0
plugins: anyio-4.0.0
collected 6 items

backend/tests/test_crawler_stability.py ...... [100%]

================ 6 passed in 0.45s =================
```

**Key Assertion**:
`test_429_retry_no_blocking` explicitly mocks `time.sleep` and asserts it is **NOT called**.

### B. Unit & Integration Tests
Coverage includes:
1. `TestSmartRetryMiddleware.test_429_retry_no_blocking`: Verifies reactor is not blocked.
2. `TestUniversalNewsSpider.test_parse_article_failure`: Verifies parser robustness.

### C. Monitoring (7-Day Target)
- **Metric**: `scrapy_err/exception/TimeoutError` count.
- **Target**: 0 occurrences related to blocking.
- **Dashboard**: [Link to Grafana/Kibana] (Placeholder)

## 4. Rollout Strategy
- **Canary**: Deploy to 10% of crawler instances.
- **Full**: If error rate < 0.1% for 24h, roll out to 100%.
