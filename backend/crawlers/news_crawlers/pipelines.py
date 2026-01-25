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
from backend.operators.vision.fingerprinter import visual_fingerprinter
from backend.operators.security.ethical_firewall import ethical_firewall
from backend.operators.intelligence.entity_aligner import entity_aligner
from backend.operators.intelligence.narrative_analyst import narrative_analyst
from news_crawlers.items import CandidateSourceItem, SourceUpdateItem
from scrapy.exceptions import DropItem

logger = logging.getLogger(__name__)

class EthicalFirewallPipeline:
    """
    Intelligence Pipeline Stage 1.5: Ethical Firewall.
    
    Research Motivation:
        - Filters out NSFW, Toxic, or Extremist content using 'safety-bert'.
        - Prevents pollution of the dataset with high-risk material.
    """
    def process_item(self, item, spider):
        if isinstance(item, (CandidateSourceItem, SourceUpdateItem)):
            return item
            
        adapter = ItemAdapter(item)
        text_content = f"{adapter.get('title', '')} {adapter.get('description', '')}"
        
        is_safe, label, score = ethical_firewall.check_safety(text_content)
        
        # Enforce Firewall
        if not is_safe:
            spider.logger.warning(f"Ethical Firewall Dropped: {adapter.get('url')} [{label}:{score:.2f}]")
            raise DropItem(f"Unsafe content detected: {label}")
            
        # Enrich with Safety Metadata
        adapter['safety_label'] = label
        adapter['safety_score'] = score
        
        return item

class EntityAlignmentPipeline:
    """
    Intelligence Pipeline Stage 3: Cross-Lingual Entity Alignment.
    
    Research Motivation:
        - Maps entities to Wikidata QIDs for global aggregation.
    """
    def process_item(self, item, spider):
        if isinstance(item, (CandidateSourceItem, SourceUpdateItem)):
            return item
            
        adapter = ItemAdapter(item)
        text_content = f"{adapter.get('title', '')} {adapter.get('description', '')}"
        
        entities = entity_aligner.extract_and_align(text_content)
        adapter['entities'] = entities
        
        return item

class NarrativeAnalysisPipeline:
    """
    Intelligence Pipeline Stage 4: Narrative Divergence Analysis.
    
    Research Motivation:
        - Computes sentiment scores to track narrative stance.
    """
    def process_item(self, item, spider):
        if isinstance(item, (CandidateSourceItem, SourceUpdateItem)):
            return item
            
        adapter = ItemAdapter(item)
        text_content = f"{adapter.get('title', '')} {adapter.get('description', '')}"
        
        sentiment_score = narrative_analyst.analyze_sentiment(text_content)
        adapter['sentiment_score'] = sentiment_score
        
        return item

class VisualFingerprintPipeline:
    """
    Intelligence Pipeline Stage 2: Visual & Textual Fingerprinting.
    
    Research Motivation:
        - Downloads logos and computes pHash for 'Sockpuppet' detection.
    """
    def process_item(self, item, spider):
        if isinstance(item, SourceUpdateItem):
            adapter = ItemAdapter(item)
            logo_url = adapter.get('logo_url')
            
            if logo_url:
                logger.debug(f"Computing logo hash for {logo_url}")
                logo_hash = visual_fingerprinter.compute_logo_hash(logo_url)
                adapter['logo_hash'] = logo_hash
                
        return item

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
                "logo_hash": adapter.get('logo_hash'),
                "copyright_text": adapter.get('copyright_text'),
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
            # Brain Metadata
            "entities": adapter.get('entities'),
            "sentiment_score": adapter.get('sentiment_score'),
            "safety_label": adapter.get('safety_label'),
            "safety_score": adapter.get('safety_score'),
        }
        
        try:
            storage_operator.save_articles([article_data])
            logger.debug(f"Saved article: {adapter.get('url')}")
        except Exception as e:
            logger.error(f"Failed to save article {adapter.get('url')}: {e}")
            
        return item
