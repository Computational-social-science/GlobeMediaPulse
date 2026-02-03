import scrapy
from scrapy_redis.spiders import RedisSpider
from scrapy_redis.utils import bytes_to_str
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from backend.operators.intelligence.source_classifier import source_classifier
from news_crawlers.items import NewsArticleItem, CandidateSourceItem, SourceUpdateItem
import trafilatura
from trafilatura.feeds import find_feed_urls
from urllib.parse import urlparse
from backend.utils.simhash import compute_structural_simhash, is_similar

class UniversalNewsSpider(RedisSpider):
    """
    Core Scrapy Spider for Global Media Monitoring.
    
    Research Motivation:
        - **Universal Crawling**: Designed to ingest content from any news website without custom parsers,
          leveraging `trafilatura` for generic content extraction.
        - **Snowball Sampling**: Implements a network-based discovery algorithm. By crawling 'Tier-0' (Global)
          and 'Tier-1' (National) sources, it automatically identifies 'Tier-2' (Local) sources via citation analysis.
        - **Structural Fingerprinting**: Computes SimHash of the DOM structure to detect layout changes
          and potentially classify source types (e.g., distinguishing blogs from news portals).
        - **Distributed Architecture**: Inherits from `RedisSpider` to support distributed, persistent crawling.
    """
    name = "universal_news"
    redis_key = "universal_news:start_urls"
    
    def __init__(self, *args, **kwargs):
        super(UniversalNewsSpider, self).__init__(*args, **kwargs)
        # Load seeds from the centralized library (Source of Truth)
        # Used for classification in parse_homepage
        self.seeds = source_classifier.sources
            
    def make_request_from_data(self, data):
        """
        Overrides RedisSpider method to ensure Playwright is used for all start URLs.
        """
        url = bytes_to_str(data, self.redis_encoding)
        return scrapy.Request(url, callback=self.parse_homepage, meta={"playwright": True})

    def parse_homepage(self, response):
        """
        Parse homepage to discover article links and new candidate sources.
        
        Methodology:
            1. **Metadata Extraction**: Compute structural SimHash and extract visual identity (Logo).
            2. **Link Analysis**:
               - **Internal Links**: Analyzed as potential articles based on URL path depth.
               - **External Links**: Analyzed as potential 'Candidate Sources' for the snowball sampling algorithm.
        """
        # 0. Extract Source Metadata (SimHash & Logo)
        current_domain = source_classifier.classify(response.url)['source_domain']
        
        # Compute Structural SimHash (Research: DOM-based classification)
        html_content = response.text
        simhash = compute_structural_simhash(html_content)
        
        # Extract Logo URL (Heuristic: Standard HTML meta tags)
        logo_url = response.css('link[rel="icon"]::attr(href)').get() or \
                   response.css('link[rel="shortcut icon"]::attr(href)').get() or \
                   response.css('meta[property="og:image"]::attr(content)').get()
        
        if logo_url:
            logo_url = response.urljoin(logo_url)
            
        # Extract Copyright Text (Textual Fingerprint)
        # copyright_text = visual_fingerprinter.extract_copyright(response.text)
        copyright_text = None
            
        # Check if structure has changed before updating (Incremental Update Strategy)
        should_update = True
        if current_domain in self.seeds:
            cached_source = self.seeds[current_domain]
            # If we have a stored SimHash and it is similar to the new one, skip update
            # hasattr check for safety if model definition varies
            if hasattr(cached_source, 'structure_simhash') and cached_source.structure_simhash:
                if is_similar(simhash, cached_source.structure_simhash):
                    should_update = False
                    self.logger.debug(f"Structure SimHash unchanged for {current_domain}. Skipping metadata update.")

        if should_update:
            # Yield Source Update Item (for metadata persistence)
            update_item = SourceUpdateItem()
            update_item['domain'] = current_domain
            update_item['logo_url'] = logo_url
            update_item['copyright_text'] = copyright_text
            update_item['structure_simhash'] = simhash
            yield update_item
        else:
             # Research Motivation: Bandwidth & Compute Optimization
             # If structure (SimHash) matches the previous crawl, it implies the homepage layout AND content links
             # (which are part of the SimHash features) haven't significantly changed.
             # Thus, we can safely skip crawling deep links to avoid redundant processing of old news.
             self.logger.info(f"SimHash match for {current_domain}. Skipping deep crawling.")
             return

        # Extract all hyperlinks for traversal
        links = response.css('a::attr(href)').getall()
        
        for link in links:
            url = response.urljoin(link)
            parsed_url = urlparse(url)
            
            # Skip invalid URLs
            if not parsed_url.netloc:
                continue

            link_domain = parsed_url.netloc.replace('www.', '')
            
            # 1. Internal Link Processing (Article Discovery)
            if link_domain == current_domain:
                 # Heuristic: Articles usually have deeper path structures than section headers
                 if len(parsed_url.path) > 10:
                     yield scrapy.Request(url, callback=self.parse_article)
            
            # 2. External Link Processing (Snowball Discovery)
            else:
                # Check if this domain is a known seed
                if link_domain not in self.seeds:
                    # Yield as candidate source for Tier-2 evaluation
                    item = CandidateSourceItem()
                    item['domain'] = link_domain
                    item['found_on'] = response.url
                    item['tier_suggestion'] = 'Tier-2' # Hypothesis: Tier-0/1 sources cite Tier-2 sources
                    yield item

    def parse_feed(self, response):
        """
        Parse RSS/Atom feed to discover new candidate sources.
        
        Methodology:
            - **Feed-Based Discovery**: RSS feeds often link to external sources (e.g. "Planet" aggregators)
              or contain cross-references.
            - **Protocol Agnostic**: Handles both RSS (<item><link>) and Atom (<entry><link>).
        """
        # Register Atom namespace for XPath
        response.selector.register_namespace('atom', 'http://www.w3.org/2005/Atom')
        
        # Extract links from items/entries
        links = set()
        # RSS <link>
        links.update(response.xpath('//item/link/text()').getall())
        # Atom <link href="...">
        links.update(response.xpath('//atom:entry/atom:link/@href').getall())
        
        origin_domain = response.meta.get('source_domain')
        if not origin_domain:
            parsed = urlparse(response.url)
            origin_domain = parsed.netloc.replace('www.', '')
        
        for link in links:
             # Basic validation
             if not link.startswith('http'):
                 continue
                 
             try:
                 parsed = urlparse(link)
                 if not parsed.netloc:
                     continue
                     
                 link_domain = parsed.netloc.replace('www.', '')
                 
                 # If link points to external domain -> Candidate!
                 if link_domain != origin_domain and link_domain not in self.seeds:
                      cand = CandidateSourceItem()
                      cand['domain'] = link_domain
                      cand['found_on'] = response.url
                      cand['tier_suggestion'] = 'Tier-2'
                      yield cand
             except:
                 continue

    def parse_article(self, response):
        """
        Extract article content and perform deep citation analysis.
        
        Methodology:
            1. **Content Extraction**: Uses `trafilatura` for high-precision text extraction.
            2. **Snowball Sampling (Deep)**: Scans the article body for outlinks.
               - Assumption: Links embedded in article text (citations) are stronger quality signals
                 than sidebar/footer links.
        """
        # 1. Content Extraction
        downloaded = response.body
        # include_comments=False: Focus on journalistic content
        try:
            result = trafilatura.extract(downloaded, include_comments=False, include_tables=False, no_fallback=True)
        except Exception as e:
            self.logger.error(f"Trafilatura extraction failed for {response.url}: {e}")
            result = None
        
        if result:
            item = NewsArticleItem()
            item['url'] = response.url
            item['title'] = response.css('title::text').get()
            item['content'] = result # Policy: Content passed to pipeline but NOT stored permanently
            item['scraped_at'] = None 
            yield item

            # 2. Snowball Sampling: Extract Outlinks from Article Body
            # Heuristic: Links inside paragraphs (p > a) are high-probability citations
            outlinks = response.css('p a::attr(href)').getall()
            
            # Filter Noise: Common social media and tech platforms
            IGNORED_DOMAINS = {'facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com', 'youtube.com', 'google.com', 't.co', 'bit.ly', 'apple.com', 'amazon.com', 'microsoft.com'}
            
            # Normalize current domain
            parsed_current = urlparse(response.url)
            current_domain = parsed_current.netloc.replace('www.', '').lower()

            for link in outlinks:
                url = response.urljoin(link)
                parsed = urlparse(url)
                
                if not parsed.netloc:
                    continue
                    
                link_domain = parsed.netloc.replace('www.', '').lower()
                
                # Filtering Logic:
                # 1. External links only
                # 2. Exclude ignored platforms
                # 3. Exclude known seeds (already monitored)
                
                if (link_domain != current_domain and 
                    link_domain not in IGNORED_DOMAINS and 
                    link_domain not in self.seeds):
                    
                    # Yield Candidate Source for network expansion
                    cand_item = CandidateSourceItem()
                    cand_item['domain'] = link_domain
                    cand_item['found_on'] = response.url
                    cand_item['tier_suggestion'] = 'Tier-2'
                    yield cand_item
        else:
            self.logger.warning(f"Empty content extracted for {response.url}")
