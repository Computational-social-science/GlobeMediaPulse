import scrapy
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from backend.operators.intelligence.source_classifier import source_classifier
from news_crawlers.items import NewsArticleItem, CandidateSourceItem, SourceUpdateItem
import trafilatura
from urllib.parse import urlparse
from backend.utils.simhash import compute_structural_simhash

class UniversalNewsSpider(scrapy.Spider):
    name = "universal_news"
    
    def __init__(self, *args, **kwargs):
        super(UniversalNewsSpider, self).__init__(*args, **kwargs)
        # Load seeds from the centralized library
        self.seeds = source_classifier.sources
        self.start_urls = []
        
        # Initialize start URLs from seeds (Tier-0/1)
        for domain, source in self.seeds.items():
            # Basic heuristic to construct URL
            url = f"https://{domain}"
            self.start_urls.append(url)
            
    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse_homepage, meta={"playwright": True})

    def parse_homepage(self, response):
        """
        Parse homepage to find article links and potential new sources.
        Also computes structural fingerprint (SimHash) and extracts Logo.
        """
        # 0. Extract Source Metadata (SimHash & Logo)
        current_domain = source_classifier.classify(response.url)['source_domain']
        
        # SimHash
        html_content = response.text
        simhash = compute_structural_simhash(html_content)
        
        # Logo (Heuristic)
        logo_url = response.css('link[rel="icon"]::attr(href)').get() or \
                   response.css('link[rel="shortcut icon"]::attr(href)').get() or \
                   response.css('meta[property="og:image"]::attr(content)').get()
        
        if logo_url:
            logo_url = response.urljoin(logo_url)
            
        # Yield Update Item
        update_item = SourceUpdateItem()
        update_item['domain'] = current_domain
        update_item['logo_url'] = logo_url
        update_item['structure_simhash'] = simhash
        yield update_item

        # Extract all links
        links = response.css('a::attr(href)').getall()
        
        for link in links:
            url = response.urljoin(link)
            parsed_url = urlparse(url)
            
            # Skip invalid URLs
            if not parsed_url.netloc:
                continue

            link_domain = parsed_url.netloc.replace('www.', '')
            
            # 1. Check if it's an internal link (Article Candidate)
            if link_domain == current_domain:
                 # Path length heuristic for articles
                 if len(parsed_url.path) > 10:
                     yield scrapy.Request(url, callback=self.parse_article)
            
            # 2. Check if it's an external link (Source Candidate)
            else:
                # Check if this domain is already known
                if link_domain not in self.seeds:
                    # Yield as candidate source
                    item = CandidateSourceItem()
                    item['domain'] = link_domain
                    item['found_on'] = response.url
                    item['tier_suggestion'] = 'Tier-2' # Assumption: Tier-0 links to Tier-1/2
                    yield item

    def parse_article(self, response):
        """
        Extract content using Trafilatura.
        """
        downloaded = response.body
        result = trafilatura.extract(downloaded, include_comments=False, include_tables=False, no_fallback=True)
        
        if result:
            item = NewsArticleItem()
            item['url'] = response.url
            item['title'] = response.css('title::text').get()
            item['content'] = result
            item['scraped_at'] = None # Will be set by DB default or pipeline
            
            # Metadata extraction from Trafilatura (if using bare_extraction) or Scrapy
            # Here we keep it simple
            
            yield item
