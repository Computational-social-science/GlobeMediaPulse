# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy

class NewsArticleItem(scrapy.Item):
    """
    Data model for a crawled news article.
    
    Research Motivation:
        - Captures both metadata (title, date, source) and payload (content).
        - Note: 'content' is used for analysis/classification but strictly excluded from permanent storage.
    """
    url = scrapy.Field()
    title = scrapy.Field()
    content = scrapy.Field()
    published_at = scrapy.Field()
    scraped_at = scrapy.Field()
    
    # Enriched Metadata
    source_domain = scrapy.Field()
    source_tier = scrapy.Field()
    language = scrapy.Field()
    country_code = scrapy.Field()
    country_name = scrapy.Field()
    country_confidence = scrapy.Field() # 'high' (Seed/Override), 'medium' (GeoJSON), 'low' (TLD), 'unknown'
    
    # Debugging Data
    raw_html = scrapy.Field()

class CandidateSourceItem(scrapy.Item):
    """
    Data model for a potential new media source discovered via Snowball Sampling.
    
    Research Motivation:
        - Used to expand the Media Source Library (Tier-2 discovery).
        - 'tier_suggestion' allows the crawler to propose a classification based on citation context.
    """
    domain = scrapy.Field()
    found_on = scrapy.Field()
    tier_suggestion = scrapy.Field()

class SourceUpdateItem(scrapy.Item):
    """
    Data model for updating metadata of an existing MediaSource.
    
    Research Motivation:
        - Keeps the source library up-to-date with dynamic attributes like visual identity (Logo)
          and structural fingerprints (SimHash).
    """
    domain = scrapy.Field()
    logo_url = scrapy.Field()
    logo_hash = scrapy.Field()          # Visual Fingerprint (pHash)
    copyright_text = scrapy.Field()     # Textual Fingerprint
    structure_simhash = scrapy.Field()
    http_status = scrapy.Field()
