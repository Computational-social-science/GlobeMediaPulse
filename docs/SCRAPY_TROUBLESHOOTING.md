# Scrapy Troubleshooting & Maintenance Guide

## 1. Top High-Frequency Errors & Fixes

### A. Media Cloud API Failures (4xx/5xx)
*   **Symptom**: `ScrapyErr` logs containing `mediacloud.api.DirectoryApi` exceptions.
*   **Root Cause**: API Rate limits, transient network issues, or missing API Key.
*   **Fix**:
    *   **Retry Logic**: Implemented `retry_with_backoff` decorator in `backend/operators/intelligence/media_cloud_client.py`.
    *   **Configuration**: `MEDIA_CLOUD_API_KEY` is now mandatory in `.env`.
    *   **Monitoring**: Check logs for "Retry X/3" warnings.

### B. DNS & Connection Timeouts
*   **Symptom**: `DNSLookupError`, `TCPTimedOutError`.
*   **Root Cause**: Slow DNS resolution for global south domains or aggressive concurrency.
*   **Fix**:
    *   Reduced `CONCURRENT_REQUESTS` from 16 to 8.
    *   Increased `DNS_TIMEOUT` to 10s.
    *   Enabled `AUTOTHROTTLE` to dynamically adjust speed.

### C. Anti-Bot Blocking (403/429)
*   **Symptom**: High number of `403 Forbidden` responses.
*   **Fix**:
    *   Enabled `RandomUserAgentMiddleware` to rotate UAs.
    *   Increased `DOWNLOAD_DELAY` to 1.0s.

## 2. Configuration Injection
The `MEDIA_CLOUD_API_KEY` is injected via environment variables.
*   **Local**: `.env` file.
*   **Docker**: `docker-compose.yml` passes it to the container.
*   **Scrapy**: `settings.py` validates existence at startup.

## 3. Monitoring & Alerts
*   **ScrapyErrMonitorMiddleware**: Captures high-risk status codes (403, 429) and network exceptions.
*   **Metrics**:
    *   `scrapy_err/status/4xx`
    *   `scrapy_err/exception/TimeoutError`
*   **Alerting Levels**:
    *   **P0 (Critical)**: `MEDIA_CLOUD_API_KEY` missing (Process Crash).
    *   **P1 (High)**: >10% failure rate in 1 hour (Check Logs).
    *   **P2 (Medium)**: Individual spider failure (Retry).

## 4. Maintenance
*   **Quarterly**: Review `RETRY_HTTP_CODES` and Proxy budget.
*   **Daily**: Check `scrapy_exceptions_total` in dashboard.
