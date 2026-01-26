# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

import sys
import os
import logging
from urllib.parse import urlparse
from collections import Counter
from itemadapter import ItemAdapter

# Add project root to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

logger = logging.getLogger(__name__)

# Optional Spacy Import
try:
    import spacy
    SPACY_AVAILABLE = True
except Exception as e:
    logger.warning(f"Spacy import failed: {e}. Geolocation might be limited.")
    SPACY_AVAILABLE = False
    
from backend.operators.intelligence.geoparsing import GeoParser
from backend.operators.storage import storage_operator
from backend.operators.intelligence.source_classifier import source_classifier
# from backend.operators.vision.fingerprinter import visual_fingerprinter
from backend.operators.security.ethical_firewall import ethical_firewall
from backend.operators.intelligence.entity_aligner import entity_aligner
# Narrative Analysis removed
from news_crawlers.items import CandidateSourceItem, SourceUpdateItem
from scrapy.exceptions import DropItem

# logger = logging.getLogger(__name__) # Moved up

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
        - [NEW] Vectorizes entity mentions to align cross-lingual narratives (e.g., 'Biden' vs '拜登').
    """
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.device = "cpu"

    def open_spider(self, spider):
        # Heavy ML dependencies (Transformers/Torch) are disabled for lightweight operation.
        # This pipeline stage is now a pass-through for vectorization.
        logger.info("Cross-Lingual Vectorization disabled (Lightweight Mode).")
        self.model = None

    def process_item(self, item, spider):
        if isinstance(item, (CandidateSourceItem, SourceUpdateItem)):
            return item
            
        adapter = ItemAdapter(item)
        text_content = f"{adapter.get('title', '')} {adapter.get('description', '')}"
        
        # 1. Standard Entity Extraction
        entities = entity_aligner.extract_and_align(text_content)
        adapter['entities'] = entities
        
        # 2. Cross-Lingual Vectorization (Disabled)
        # narrative_vector remains None
        
        return item

    def _vectorize(self, text):
        return None


class RedisPublishPipeline:
    """
    Intelligence Pipeline Stage 5: Real-time Event Publishing.
    
    Research Motivation:
        - Publishes crawled article events to Redis for real-time frontend visualization.
        - Enables "Data Flow" animation (Source -> Server).
    """
    def __init__(self, redis_url):
        self.redis_url = redis_url
        self.redis_client = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            redis_url=crawler.settings.get('REDIS_URL')
        )

    def open_spider(self, spider):
        import redis
        self.redis_client = redis.from_url(self.redis_url)

    def process_item(self, item, spider):
        if isinstance(item, SourceUpdateItem):
            return item
            
        adapter = ItemAdapter(item)
        import time
        
        # Handle CandidateSourceItem
        if isinstance(item, CandidateSourceItem):
            event_data = {
                "title": f"New Source: {adapter.get('domain')}",
                "url": f"http://{adapter.get('domain')}",
                "source_domain": adapter.get('domain'),
                "tier": "Candidate",
                "language": "en",
                "country": adapter.get('country_code', 'UNK'),
                "confidence": adapter.get('country_confidence', 'unknown'),
                "lat": adapter.get('country_lat'),
                "lng": adapter.get('country_lng'),
                "timestamp": time.time(),
                "logo_url": None,
                "type": "discovery" # Marker for frontend to potentially treat differently
            }
        else:
            # News Article
            event_data = {
                "title": adapter.get('title'),
                "url": adapter.get('url'),
                "source_domain": adapter.get('source_domain'),
                "tier": adapter.get('source_tier'),
                "language": adapter.get('language'),
                "country": adapter.get('country_code', 'UNK'),
                "confidence": adapter.get('country_confidence', 'unknown'),
                "lat": adapter.get('country_lat'),
                "lng": adapter.get('country_lng'),
                "timestamp": adapter.get('published_at') or time.time(), # Fixed field name
                "logo_url": None,
                "type": "news" # Explicit type for frontend
            }
        
        try:
            import json
            self.redis_client.publish("news_pulse", json.dumps(event_data))
            spider.logger.info(f"Published to Redis: {event_data.get('title')} -> {event_data.get('country')}")
        except Exception as e:
            spider.logger.error(f"Failed to publish to Redis: {e}")
            
        return item

class ClassificationPipeline:
    """
    Intelligence Pipeline Stage 1: Metadata Enrichment.
    
    Research Motivation:
        - Enhances raw crawled items with intelligence data (Tier, Country, Domain).
        - Ensures consistent data labeling before storage or further processing.
        - [NEW] Uses Advanced GeoParser (Geograpy3 + WHOIS + Consensus) for location.
    """
    def __init__(self):
        self.geo_parser = None
        # Manual Overrides for Major Global Media (High Precision)
        self.domain_overrides = {
            'nytimes': 'USA', 'wsj': 'USA', 'washingtonpost': 'USA', 'cnn': 'USA', 'foxnews': 'USA', 'usatoday': 'USA', 'nbcnews': 'USA', 'cnbc': 'USA', 'bloomberg': 'USA', 'apnews': 'USA', 'npr': 'USA',
            'bbc': 'GBR', 'reuters': 'GBR', 'theguardian': 'GBR', 'independent': 'GBR', 'dailymail': 'GBR', 'telegraph': 'GBR', 'skynews': 'GBR',
            'aljazeera': 'QAT',
            'rt': 'RUS', 'sputniknews': 'RUS', 'tass': 'RUS', 'moscowtimes': 'RUS',
            'xinhua': 'CHN', 'chinadaily': 'CHN', 'scmp': 'HKG', 'globaltimes': 'CHN',
            'dw': 'DEU', 'france24': 'FRA', 'euronews': 'FRA',
            'kyodonews': 'JPN', 'japantimes': 'JPN', 'asahi': 'JPN',
            'yonhap': 'KOR', 'koreaherald': 'KOR',
            'thehindu': 'IND', 'timesofindia': 'IND', 'hindustantimes': 'IND',
            'straitstimes': 'SGP', 'bangkokpost': 'THA', 'jakartapost': 'IDN',
            'smh': 'AUS', 'abc': 'AUS',
            'globeandmail': 'CAN', 'cbc': 'CAN',
            'folha': 'BRA', 'clarin': 'ARG'
        }

    def open_spider(self, spider):
        # Initialize GeoParser with Redis URL from settings
        redis_url = spider.settings.get('REDIS_URL')
        self.geo_parser = GeoParser(redis_url)

    def process_item(self, item, spider):
        # Skip enrichment for structural items
        if isinstance(item, SourceUpdateItem):
            return item
            
        adapter = ItemAdapter(item)
        
        # Case 1: Candidate Source (Geoparse Domain)
        if isinstance(item, CandidateSourceItem):
            domain = adapter.get('domain')
            if domain:
                # Construct pseudo-URL for Geoparsing
                pseudo_url = f"http://{domain}"
                country_code, confidence = self.geo_parser.resolve(
                    url=pseudo_url,
                    text="", # No content
                    tier=2,  # Default tier for candidates
                    existing_code='UNK'
                )
                adapter['country_code'] = country_code
                adapter['country_confidence'] = confidence
                
                # [NEW] Inject Lat/Lng
                coords = self.geo_parser.get_coords(country_code)
                if coords:
                    adapter['country_lat'] = coords.get('lat')
                    adapter['country_lng'] = coords.get('lng')
                    
            return item
            
        # Case 2: News Article
        url = adapter.get('url')
        if url:
            # 1. Basic Metadata from SourceClassifier
            classification = source_classifier.classify(url)
            if not adapter.get('source_tier'):
                adapter['source_tier'] = classification.get('tier')
            if not adapter.get('source_domain'):
                adapter['source_domain'] = classification.get('source_domain')
            
            # 2. Determine Initial 'Existing Code'
            # Priority: Classifier > Domain Override > TLD
            existing_code = 'UNK'
            
            # A. Classifier
            if classification.get('country'):
                existing_code = classification.get('country')
            
            # B. Domain Override (if UNK)
            if existing_code == 'UNK':
                domain = adapter.get('source_domain') or urlparse(url).netloc
                domain_lower = domain.lower()
                for key, code in self.domain_overrides.items():
                    if key in domain_lower:
                        existing_code = code
                        break
            
            # C. TLD (if UNK)
            if existing_code == 'UNK':
                existing_code = self.geo_parser.infer_from_tld(url)
            
            # 3. Advanced Geoparsing (Consensus: Existing + WHOIS + Text)
            # Prepare text content for extraction
            # CandidateSourceItem might not have content, so use title or empty string
            text_content = (adapter.get('title') or "") + " " + (adapter.get('content') or "")
            # Limit text length to avoid performance hit
            text_content = text_content[:5000]
            
            # Resolve
            # Default tier to 2 if not found
            tier = adapter.get('source_tier') or 2
            country_code, confidence = self.geo_parser.resolve(
                url=url,
                text=text_content,
                tier=tier,
                existing_code=existing_code
            )
            
            adapter['country_code'] = country_code
            adapter['country_confidence'] = confidence

            # [NEW] Inject Lat/Lng
            coords = self.geo_parser.get_coords(country_code)
            if coords:
                adapter['country_lat'] = coords.get('lat')
                adapter['country_lng'] = coords.get('lng')

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
        
        # Loop-Back Learning: If we inferred the country (medium/low confidence), update the source definition
        confidence = adapter.get('country_confidence')
        country_code = adapter.get('country_code')
        domain = adapter.get('source_domain')
        
        if country_code and country_code != 'UNK' and confidence in ['medium', 'low'] and domain:
            try:
                storage_operator.update_media_source_country(domain, country_code)
                logger.debug(f"Loop-Back Learning: Updated {domain} -> {country_code} ({confidence})")
            except Exception as e:
                logger.warning(f"Loop-Back Learning Failed for {domain}: {e}")
        
        # Transform to storage schema
        article_data = {
            "url": adapter.get('url'),
            "title": adapter.get('title'),
            "content": adapter.get('content'), # Content is passed but filtered by storage policy
            "published_at": adapter.get('published_at'),
            "sourcecountry": adapter.get('country_code'), # Mapped from GDELT or Scrapy metadata
            "country_name": adapter.get('country_name'),
            "source_tier": adapter.get('source_tier'),
            "source_domain": adapter.get('source_domain'),
            # Brain Metadata
            "entities": adapter.get('entities'),
            "narrative_vector": adapter.get('narrative_vector'), # Store the cross-lingual vector
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
