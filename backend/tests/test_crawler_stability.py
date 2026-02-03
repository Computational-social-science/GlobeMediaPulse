import pytest
from unittest.mock import MagicMock, patch
from scrapy.http import Request, HtmlResponse
from scrapy.spiders import Spider
from scrapy.settings import Settings
from backend.crawlers.news_crawlers.middlewares import SmartRetryMiddleware
from backend.crawlers.news_crawlers.spiders.universal_spider import UniversalNewsSpider

class TestSmartRetryMiddleware:
    
    @pytest.fixture
    def middleware(self):
        crawler = MagicMock()
        # Use real Settings object
        crawler.settings = Settings({'RETRY_HTTP_CODES': [500, 502, 503, 504, 522, 524, 408, 429], 'RETRY_ENABLED': True})
        crawler.stats = MagicMock()
        
        mw = SmartRetryMiddleware.from_crawler(crawler)
        return mw
        
    @pytest.fixture
    def spider(self):
        spider = Spider(name="test_spider")
        return spider
        
    @pytest.fixture
    def request_obj(self):
        return Request(url="http://example.com", meta={"retry_times": 0})
        
    def test_429_retry_no_blocking(self, middleware, spider, request_obj):
        """Test that 429 triggers retry without blocking (no time.sleep)."""
        response = HtmlResponse(url="http://example.com", status=429, body=b"")
        
        with patch('time.sleep') as mock_sleep:
            with patch.object(middleware, '_retry', return_value=Request(url="http://example.com")) as mock_retry:
                retry_req = middleware.process_response(request_obj, response, spider)
                assert isinstance(retry_req, Request)
                mock_sleep.assert_not_called()
                mock_retry.assert_called_once()
            
    def test_403_no_retry(self, middleware, spider, request_obj):
        """Test that 403 does NOT trigger retry."""
        response = HtmlResponse(url="http://example.com", status=403, body=b"")
        result = middleware.process_response(request_obj, response, spider)
        assert result == response
        
    def test_500_retry(self, middleware, spider, request_obj):
        """Test that 500 triggers retry."""
        response = HtmlResponse(url="http://example.com", status=500, body=b"")
        with patch.object(middleware, '_retry', return_value=Request(url="http://example.com")):
            retry_req = middleware.process_response(request_obj, response, spider)
            assert isinstance(retry_req, Request)

class TestUniversalNewsSpider:
    
    @pytest.fixture
    def spider(self):
        with patch('backend.operators.intelligence.source_classifier.source_classifier.sources', {}):
             spider = UniversalNewsSpider()
             spider.seeds = {}
             return spider

    def test_parse_article_success(self, spider):
        response = HtmlResponse(url="http://example.com/article", body=b"<html><head><title>Test Title</title></head><body><p>Test content</p></body></html>", encoding='utf-8')
        
        with patch('trafilatura.extract', return_value="Test content extracted"):
            results = list(spider.parse_article(response))
            assert len(results) >= 1
            assert results[0]['content'] == "Test content extracted"
            assert results[0]['title'] == "Test Title"
            
    def test_parse_article_failure(self, spider):
        response = HtmlResponse(url="http://example.com/article", body=b"<html></html>", encoding='utf-8')
        
        with patch('trafilatura.extract', side_effect=Exception("Parsing error")):
            # Expect log error but no crash
            results = list(spider.parse_article(response))
            assert len(results) == 0
            
    def test_parse_article_empty(self, spider):
        response = HtmlResponse(url="http://example.com/article", body=b"<html></html>", encoding='utf-8')
        
        with patch('trafilatura.extract', return_value=None):
            results = list(spider.parse_article(response))
            assert len(results) == 0