import os
import sys
import pytest
from unittest.mock import MagicMock, patch
from scrapy.utils.project import get_project_settings

# Add project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

def test_media_cloud_api_key_injection():
    """Verify MEDIA_CLOUD_API_KEY is loaded from env."""
    os.environ["MEDIA_CLOUD_API_KEY"] = "test_key_123"
    
    # Reload settings module to pick up env var
    if 'backend.crawlers.news_crawlers.settings' in sys.modules:
        del sys.modules['backend.crawlers.news_crawlers.settings']
        
    from backend.crawlers.news_crawlers import settings
    assert settings.MEDIA_CLOUD_API_KEY == "test_key_123"

def test_scrapy_settings_robustness():
    """Verify robust Scrapy settings."""
    os.environ["MEDIA_CLOUD_API_KEY"] = "test_key_123"
    if 'backend.crawlers.news_crawlers.settings' in sys.modules:
        del sys.modules['backend.crawlers.news_crawlers.settings']
        
    from backend.crawlers.news_crawlers import settings
    
    assert settings.RETRY_ENABLED is True
    assert settings.RETRY_TIMES == 3
    assert settings.DOWNLOAD_TIMEOUT == 30
    assert settings.CONCURRENT_REQUESTS == 8
    assert "news_crawlers.middlewares.ScrapyErrMonitorMiddleware" in settings.DOWNLOADER_MIDDLEWARES

def test_media_cloud_retry_logic():
    """Verify MediaCloudIntegrator retries on failure."""
    from backend.operators.intelligence.media_cloud_client import MediaCloudIntegrator
    
    # Mock API to fail twice then succeed
    mock_api = MagicMock()
    # 1. Fail 1
    # 2. Fail 2
    # 3. Success (First call in logic) -> returns empty results
    # 4. Success (Second call in logic - Fallback) -> returns empty results
    mock_api.collection_list.side_effect = [Exception("Fail 1"), Exception("Fail 2"), {"results": []}, {"results": []}]
    
    with patch("mediacloud.api.DirectoryApi", return_value=mock_api):
        client = MediaCloudIntegrator(api_key="test")
        
        # Should succeed eventually (return None as nothing found, but no exception)
        client.get_national_collection_id("TestLand")
        
        # Verify call count
        # 1. Fail -> Retry
        # 2. Fail -> Retry
        # 3. Success (Call 1)
        # 4. Success (Call 2)
        assert mock_api.collection_list.call_count == 4
