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

# Optional Spacy Import
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    
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
        - [NEW] Vectorizes entity mentions to align cross-lingual narratives (e.g., 'Biden' vs '拜登').
    """
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.device = "cpu"

    def open_spider(self, spider):
        # Lazy load the model to avoid overhead if not used or if dependencies missing
        try:
            from transformers import AutoTokenizer, AutoModel
            import torch
            
            # Use a lightweight multilingual model: 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
            # Or a smaller one: 'sentence-transformers/all-MiniLM-L6-v2' (mostly English but handles some others)
            # For true cross-lingual, we need a multilingual model.
            # Using a widely cached/available small model name.
            model_name = "sentence-transformers/all-MiniLM-L6-v2" 
            
            logger.info(f"Initializing Cross-Lingual Vectorizer: {model_name}")
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name)
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model.to(self.device)
            logger.info(f"Vectorizer initialized on {self.device}")
            
        except ImportError:
            logger.warning("Transformers library not found. Cross-lingual vectorization disabled.")
        except Exception as e:
            logger.warning(f"Failed to load vectorization model: {e}")

    def process_item(self, item, spider):
        if isinstance(item, (CandidateSourceItem, SourceUpdateItem)):
            return item
            
        adapter = ItemAdapter(item)
        text_content = f"{adapter.get('title', '')} {adapter.get('description', '')}"
        
        # 1. Standard Entity Extraction
        entities = entity_aligner.extract_and_align(text_content)
        adapter['entities'] = entities
        
        # 2. Cross-Lingual Vectorization
        # Research Goal: Compute Cosine Similarity: $ \text{sim}(A, B) = \frac{A \cdot B}{\|A\| \|B\|} $
        if self.model and text_content.strip():
            try:
                embedding = self._vectorize(text_content)
                # Store the embedding (as a list/bytes) for downstream storage or comparison
                # Note: Storing raw floats in DB can be heavy. Usually we store in Vector DB.
                # Here we attach it to the item for potential real-time comparison.
                adapter['narrative_vector'] = embedding
            except Exception as e:
                logger.error(f"Vectorization failed: {e}")
        
        return item

    def _vectorize(self, text):
        """
        Computes the dense vector representation of the text using Mean Pooling.
        Mathematical Formalism:
        Given input tokens $ X = \{x_1, ..., x_n\} $, the sentence embedding $ v $ is:
        $$ v = \frac{1}{n} \sum_{i=1}^{n} \text{BERT}(x_i) $$
        """
        import torch
        inputs = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=128).to(self.device)
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        # Mean Pooling - Take attention mask into account for correct averaging
        token_embeddings = outputs.last_hidden_state
        attention_mask = inputs['attention_mask']
        
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
        sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
        
        mean_pooled = sum_embeddings / sum_mask
        return mean_pooled[0].cpu().tolist()

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
        if isinstance(item, (CandidateSourceItem, SourceUpdateItem)):
            return item
            
        adapter = ItemAdapter(item)
        
        # Publish minimal event data
        event_data = {
            "title": adapter.get('title'),
            "url": adapter.get('url'),
            "source_domain": adapter.get('source_domain'),
            "tier": adapter.get('tier'),
            "language": adapter.get('language'),
            "country": adapter.get('country_code', 'UNK'), # Standardized to country_code
            "confidence": adapter.get('country_confidence', 'unknown'), # For Visual Tiering (Solid vs Dashed)
            "timestamp": adapter.get('publish_date'),
            "logo_url": adapter.get('logo_url')
        }
        
        try:
            import json
            self.redis_client.publish("news_pulse", json.dumps(event_data))
        except Exception as e:
            spider.logger.error(f"Failed to publish to Redis: {e}")
            
        return item

class VisualFingerprintPipeline:
    """
    Intelligence Pipeline Stage 2: Visual & Textual Fingerprinting.
    
    Research Motivation:
        - Downloads logos and computes pHash for 'Sockpuppet' detection.
    """
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        
        # 1. Fallback Logo Extraction (Favicon)
        # If no logo is explicitly found, guess the favicon location
        if not adapter.get('logo_url'):
            url = adapter.get('url')
            if url:
                try:
                    parsed = urlparse(url)
                    # Simple favicon guess: scheme://domain/favicon.ico
                    adapter['logo_url'] = f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
                except Exception:
                    pass

        # 2. Existing Compute Hash Logic (only if we have a URL)
        if isinstance(item, SourceUpdateItem):
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
            
            # 1. Seed/Classifier Match (High Confidence)
            if classification.get('country'):
                adapter['country_code'] = classification.get('country')
                adapter['country_confidence'] = 'high'
            else:
                adapter['country_confidence'] = 'unknown'
            
            # TLD Fallback for Country (Enhanced)
            # If country is missing or UNK, try to infer from Top Level Domain using enhanced logic
            if not adapter.get('country_code') or adapter.get('country_code') == 'UNK':
                adapter['country_code'] = self._infer_country_from_tld(url)
                if adapter['country_code'] != 'UNK':
                    adapter['country_confidence'] = 'low'
            
            # Final Fallback: Check against GeoJSON Name Map & Manual Overrides
            if (not adapter.get('country_code') or adapter.get('country_code') == 'UNK'):
                domain = adapter.get('source_domain') or urlparse(url).netloc
                domain_lower = domain.lower()
                
                # 1. Check Manual Overrides (Fastest & Most Accurate for Majors)
                if hasattr(self, 'domain_overrides'):
                    for key, code in self.domain_overrides.items():
                        if key in domain_lower:
                            adapter['country_code'] = code
                            adapter['country_confidence'] = 'high' # Manual overrides are trusted
                            # logger.debug(f"Country inferred via Override: {domain} -> {code}")
                            break
                
                # 2. Check GeoJSON Name Map (Broadest)
                if (not adapter.get('country_code') or adapter.get('country_code') == 'UNK') and hasattr(self, 'country_code_map'):
                    for name, code in self.country_code_map.items():
                        # Use word boundary check or strict inclusion to avoid false positives?
                        # For now, simple inclusion but ensuring some length to avoid matching "in" to "India" or "us" to "Cyprus" (unlikely with full names)
                        if len(name) > 3 and name in domain_lower:
                            adapter['country_code'] = code
                            adapter['country_confidence'] = 'medium' # Inferred from name
                            # logger.debug(f"Country inferred via GeoJSON: {domain} -> {code}")
                            break

            # --- Content-Based Geolocation (New Feature) ---
            # If confidence is low or unknown, try to validate/infer using content scanning
            current_conf = adapter.get('country_confidence')
            if current_conf in ['low', 'unknown']:
                content_text = (adapter.get('title') or "") + " " + (adapter.get('content') or "")
                # Limit scan to first 1000 chars for performance
                content_text = content_text[:1000] 
                
                inferred_code = self._infer_country_from_content(content_text)
                
                if inferred_code:
                    # Case A: Confirmation (TLD said 'low', Content agrees) -> Upgrade to 'medium'
                    if current_conf == 'low' and adapter.get('country_code') == inferred_code:
                        adapter['country_confidence'] = 'medium'
                        # logger.debug(f"Confidence Upgrade (TLD+Content): {url} -> {inferred_code}")
                    
                    # Case B: New Inference (Was 'unknown', Content found match) -> Set to 'medium'
                    elif current_conf == 'unknown':
                        adapter['country_code'] = inferred_code
                        adapter['country_confidence'] = 'medium'
                        # logger.debug(f"Content Inference: {url} -> {inferred_code}")

        return item

    def _infer_country_from_content(self, text):
        """
        Scans text for Country Names using Spacy NER or fallback dictionary.
        Returns the country code if a significant match is found (Subject Country).
        """
        if not text:
            return None
        
        # 1. Spacy NER (Preferred)
        if getattr(self, 'nlp', None):
            try:
                doc = self.nlp(text)
                # Count GPE entities
                gpe_counts = Counter()
                
                for ent in doc.ents:
                    if ent.label_ == 'GPE':
                        # Clean text: remove 'the', punctuation, etc if needed. Spacy usually gives clean entities.
                        name_lower = ent.text.lower().strip()
                        # Map to Code
                        if hasattr(self, 'country_code_map') and name_lower in self.country_code_map:
                             gpe_counts[self.country_code_map[name_lower]] += 1
                
                # Get most frequent
                if gpe_counts:
                    # Return the most common one
                    return gpe_counts.most_common(1)[0][0]
                    
            except Exception as e:
                # logger.warning(f"NER failed: {e}")
                pass
        
        # 2. Fallback: Keyword Frequency (Heuristic)
        if not hasattr(self, 'country_code_map'):
             return None
             
        text_lower = text.lower()
        keyword_counts = Counter()
        
        for name, code in self.country_code_map.items():
             if len(name) < 4: continue
             
             # Count occurrences (non-overlapping)
             # Adding spaces to ensure word boundary
             count = text_lower.count(f" {name} ")
             if count > 0:
                 keyword_counts[code] += count
        
        if keyword_counts:
            return keyword_counts.most_common(1)[0][0]
            
        return None

    def _infer_country_from_tld(self, url):
        """
        Infers ISO-3 country code from URL TLD.
        Enhanced to load from backend/data/countries.geo.json if available for high precision.
        """
        try:
            domain = urlparse(url).netloc
            # Get the last part of the domain (TLD)
            parts = domain.split('.')
            if len(parts) < 2:
                return 'UNK'
            tld = parts[-1].lower()
            
            # 1. Enhanced TLD Map (Common + Specific)
            tld_map = {
                # Asia
                'jp': 'JPN', 'cn': 'CHN', 'in': 'IND', 'kr': 'KOR', 'id': 'IDN', 
                'ph': 'PHL', 'vn': 'VNM', 'th': 'THA', 'my': 'MYS', 'sg': 'SGP',
                'pk': 'PAK', 'bd': 'BGD', 'lk': 'LKA', 'np': 'NPL', 'tw': 'TWN',
                'hk': 'HKG', 'sa': 'SAU', 'ae': 'ARE', 'ir': 'IRN', 'tr': 'TUR',
                'il': 'ISR', 'qa': 'QAT', 'kw': 'KWT', 'om': 'OMN', 'jo': 'JOR',
                
                # Europe
                'uk': 'GBR', 'de': 'DEU', 'fr': 'FRA', 'it': 'ITA', 'es': 'ESP',
                'nl': 'NLD', 'be': 'BEL', 'ch': 'CHE', 'at': 'AUT', 'se': 'SWE',
                'no': 'NOR', 'dk': 'DNK', 'fi': 'FIN', 'ie': 'IRL', 'pt': 'PRT',
                'pl': 'POL', 'cz': 'CZE', 'hu': 'HUN', 'ro': 'ROU', 'gr': 'GRC',
                'ua': 'UKR', 'ru': 'RUS', 'by': 'BLR', 'rs': 'SRB', 'hr': 'HRV',
                
                # Americas
                'ca': 'CAN', 'br': 'BRA', 'mx': 'MEX', 'ar': 'ARG', 'co': 'COL',
                'cl': 'CHL', 'pe': 'PER', 've': 'VEN', 'ec': 'ECU', 'uy': 'URY',
                
                # Africa
                'za': 'ZAF', 'ng': 'NGA', 'eg': 'EGY', 'ke': 'KEN', 'gh': 'GHA',
                'ma': 'MAR', 'dz': 'DZA', 'tn': 'TUN', 'et': 'ETH', 'tz': 'TZA',
                
                # Oceania
                'au': 'AUS', 'nz': 'NZL', 'fj': 'FJI'
            }
            
            # 2. Check Map
            if tld in tld_map:
                return tld_map[tld]
            
            # 3. Special Case: .com/.net/.org usually implies Global or US, but let's default to UNK
            # to encourage specific resolution unless we have domain-specific rules.
            if tld in ['com', 'net', 'org', 'info', 'biz']:
                # TODO: In the future, match against a specific domain list loaded from JSON
                pass
                
            return 'UNK'
        except Exception:
            return 'UNK'

    def open_spider(self, spider):
        # Pre-load country codes from geojson if possible
        try:
            import json
            # Adjust path to point to backend/data/countries.geo.json
            # pipelines.py is in backend/crawlers/news_crawlers/
            # Go up 3 levels to reach backend/
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            geo_path = os.path.join(backend_dir, 'data', 'countries.geo.json')
            
            self.country_code_map = {}
            
            # 1. Manual Overrides for Major Global Media (High Precision)
            self.domain_overrides = {
                'nytimes': 'USA', 'wsj': 'USA', 'washingtonpost': 'USA', 'cnn': 'USA', 'foxnews': 'USA', 'usatoday': 'USA', 'nbcnews': 'USA', 'cnbc': 'USA', 'bloomberg': 'USA', 'apnews': 'USA', 'npr': 'USA',
                'bbc': 'GBR', 'reuters': 'GBR', 'theguardian': 'GBR', 'independent': 'GBR', 'dailymail': 'GBR', 'telegraph': 'GBR', 'skynews': 'GBR',
                'aljazeera': 'QAT',
                'rt': 'RUS', 'sputniknews': 'RUS', 'tass': 'RUS', 'moscowtimes': 'RUS',
                'xinhuanet': 'CHN', 'chinadaily': 'CHN', 'globaltimes': 'CHN', 'scmp': 'HKG',
                'dw': 'DEU', 'spiegel': 'DEU', 'bild': 'DEU',
                'france24': 'FRA', 'lemonde': 'FRA', 'lefigaro': 'FRA',
                'kyodonews': 'JPN', 'japantimes': 'JPN', 'asahi': 'JPN', 'mainichi': 'JPN', 'nikkei': 'JPN',
                'yonhap': 'KOR', 'koreaherald': 'KOR', 'koreatimes': 'KOR',
                'timesofindia': 'IND', 'thehindu': 'IND', 'hindustantimes': 'IND',
                'straitstimes': 'SGP', 'channelnewsasia': 'SGP',
                'cbc': 'CAN', 'theglobeandmail': 'CAN',
                'abc': 'AUS', 'smh': 'AUS', 'theage': 'AUS', # abc.net.au
                'folha': 'BRA', 'globo': 'BRA',
                'elwatannews': 'EGY', 'ahram': 'EGY'
            }
            
            if os.path.exists(geo_path):
                with open(geo_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for feature in data['features']:
                        props = feature.get('properties', {})
                        code = feature.get('id')
                        name = props.get('name')
                        if code and name:
                            # Standard Map
                            self.country_code_map[name.lower()] = code
                            
                            # Add 'name_zh' to map if exists
                            if props.get('name_zh'):
                                self.country_code_map[props.get('name_zh').lower()] = code
                            
                            # Add 'aliases' to map if exists
                            if props.get('aliases'):
                                for alias in props.get('aliases'):
                                    self.country_code_map[alias.lower()] = code
                            
                            # Heuristic: Add variations for better matching
                            # e.g., "Republic of Serbia" -> "Serbia"
                            simple_name = name.replace('Republic of', '').replace('Kingdom of', '').replace('United Republic of', '').strip()
                            if simple_name != name:
                                self.country_code_map[simple_name.lower()] = code
            else:
                logger.warning(f"countries.geo.json not found at {geo_path}")

            # --- Load Spacy for NER ---
            self.nlp = None
            if SPACY_AVAILABLE:
                try:
                    logger.info("Loading Spacy 'en_core_web_sm' for NER...")
                    # Disable heavy components to save memory/time
                    self.nlp = spacy.load("en_core_web_sm", disable=["parser", "tagger", "lemmatizer", "textcat"])
                    logger.info("Spacy NER loaded.")
                except Exception as e:
                    logger.warning(f"Failed to load Spacy model: {e}. Falling back to keyword match.")
                    self.nlp = None

        except Exception as e:
            logger.error(f"Failed to initialize ClassificationPipeline resources: {e}")
            self.country_code_map = {}

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
