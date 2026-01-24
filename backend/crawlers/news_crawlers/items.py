# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy

class NewsArticleItem(scrapy.Item):
    url = scrapy.Field()
    title = scrapy.Field()
    content = scrapy.Field()
    published_at = scrapy.Field()
    scraped_at = scrapy.Field()
    
    # Metadata
    source_domain = scrapy.Field()
    source_tier = scrapy.Field()
    language = scrapy.Field()
    country_code = scrapy.Field()
    country_name = scrapy.Field()
    
    # Raw data for debugging
    raw_html = scrapy.Field()

class CandidateSourceItem(scrapy.Item):
    domain = scrapy.Field()
    found_on = scrapy.Field()
    tier_suggestion = scrapy.Field()

class SourceUpdateItem(scrapy.Item):
    """
    Item for updating existing MediaSource metadata.
    """
    domain = scrapy.Field()
    logo_url = scrapy.Field()
    structure_simhash = scrapy.Field()
    http_status = scrapy.Field()
