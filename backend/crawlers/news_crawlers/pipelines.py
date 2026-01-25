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
    Intelligence Pipeline Stage 1: Metadata Enrichment.
    
    Research Motivation:
        - Enhances raw crawled items with intelligence data (Tier, Country, Domain).
        - Ensures consistent data labeling before storage or further processing.
    """
    def process_item(self, item, spider):
        # Skip enrichment for structural/candidate items
        if isinstance(item, (CandidateSourceItem, SourceUpdateItem)):
            return item

        adapter = ItemAdapter(item)
        url = adapter.get('url')
        
        if url:
            # Query the SourceClassifier for metadata
            classification = source_classifier.classify(url)
            if not adapter.get('source_tier'):
                adapter['source_tier'] = classification.get('tier')
            if not adapter.get('source_domain'):
                adapter['source_domain'] = classification.get('source_domain')
                
        return item

class PostgresStoragePipeline:
    """
    Storage Pipeline Stage 2: Database Persistence.
    
    Research Motivation:
        - **Persistence Layer**: Commits validated data to PostgreSQL.
        - **Separation of Concerns**: Decouples crawling logic from storage logic.
        - **Candidate Management**: Handles the registration of new 'Candidate Sources' discovered via snowball sampling.
    """
    def process_item(self, item, spider):
        # Case 1: New Candidate Source Discovered
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
            
        # Case 2: Existing Source Metadata Update
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

        # Case 3: News Article Metadata (No Content Stored)
        adapter = ItemAdapter(item)
        
        # Transform to storage schema
        article_data = {
            "url": adapter.get('url'),
            "title": adapter.get('title'),
            "content": adapter.get('content'), # Content is passed but filtered by storage policy
            "published_at": adapter.get('published_at'),
            "sourcecountry": adapter.get('country_code'),
            "country_name": adapter.get('country_name'),
            "source_tier": adapter.get('source_tier'),
            "source_domain": adapter.get('source_domain'),
        }
        
        try:
            storage_operator.save_articles([article_data])
            logger.debug(f"Saved article: {adapter.get('url')}")
        except Exception as e:
            logger.error(f"Failed to save article {adapter.get('url')}: {e}")
            
        return item
