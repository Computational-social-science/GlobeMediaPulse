# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

import sys
import os
import logging
from itemadapter import ItemAdapter

# Add project root to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from backend.operators.storage import storage_operator
from backend.operators.intelligence.source_classifier import source_classifier
from news_crawlers.items import CandidateSourceItem, SourceUpdateItem

logger = logging.getLogger(__name__)

class ClassificationPipeline:
    """
    Enriches the item with Tier info if not present.
    """
    def process_item(self, item, spider):
        if isinstance(item, (CandidateSourceItem, SourceUpdateItem)):
            return item

        adapter = ItemAdapter(item)
        url = adapter.get('url')
        
        if url:
            classification = source_classifier.classify(url)
            if not adapter.get('source_tier'):
                adapter['source_tier'] = classification.get('tier')
            if not adapter.get('source_domain'):
                adapter['source_domain'] = classification.get('source_domain')
                
        return item

class PostgresStoragePipeline:
    """
    Saves the item to PostgreSQL using the existing StorageOperator.
    """
    def process_item(self, item, spider):
        if isinstance(item, CandidateSourceItem):
            adapter = ItemAdapter(item)
            candidate_data = {
                "domain": adapter.get('domain'),
                "found_on": adapter.get('found_on'),
                "tier_suggestion": adapter.get('tier_suggestion'),
            }
            try:
                storage_operator.save_candidate(candidate_data)
                logger.debug(f"Saved candidate: {adapter.get('domain')}")
            except Exception as e:
                logger.error(f"Failed to save candidate {adapter.get('domain')}: {e}")
            return item
            
        if isinstance(item, SourceUpdateItem):
            adapter = ItemAdapter(item)
            update_data = {
                "domain": adapter.get('domain'),
                "logo_url": adapter.get('logo_url'),
                "structure_simhash": adapter.get('structure_simhash'),
            }
            try:
                storage_operator.update_media_source(update_data)
                logger.debug(f"Updated media source: {adapter.get('domain')}")
            except Exception as e:
                logger.error(f"Failed to update media source {adapter.get('domain')}: {e}")
            return item

        adapter = ItemAdapter(item)
        
        # Convert to dict format expected by storage_operator
        article_data = {
            "url": adapter.get('url'),
            "title": adapter.get('title'),
            "content": adapter.get('content'),
            "published_at": adapter.get('published_at'),
            "sourcecountry": adapter.get('country_code'), # Mapping to storage key
            "country_name": adapter.get('country_name'),
            "source_tier": adapter.get('source_tier'),
            "source_domain": adapter.get('source_domain'),
        }
        
        # Save (batch size 1 for now, can be optimized)
        try:
            storage_operator.save_articles([article_data])
            logger.debug(f"Saved article: {adapter.get('url')}")
        except Exception as e:
            logger.error(f"Failed to save article {adapter.get('url')}: {e}")
            
        return item
