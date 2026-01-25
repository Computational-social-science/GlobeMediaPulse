import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.core.database import db_manager
from backend.utils.hashing import generate_url_hash

logger = logging.getLogger(__name__)

class PostgresStorageOperator:
    """
    Primary Persistence Operator for the PostgreSQL Relational Database.
    
    Architectural Role:
    This operator manages the Data Access Layer (DAL) for structured relational data. 
    It abstracts low-level SQL operations and connection pooling mechanics, providing 
    a high-level API for the system's core entities: Articles, Media Sources, and Candidate Sources.
    
    Key Features:
    1.  **Connection Pooling**: Leverages `psycopg2` via `db_manager` for efficient, thread-safe 
        connection management, essential for high-concurrency crawling pipelines.
    2.  **Idempotency & Deduplication**: Implements "Insert-or-Skip" logic using URL Hashes 
        to prevent data duplication, a critical requirement for continuous data ingestion.
    3.  **Snowball Sampling Support**: Manages the `candidate_sources` table, tracking citation 
        counts to support the automated discovery of Tier-2 media nodes.
    4.  **Privacy & Efficiency Policy**: Strictly adheres to the "Metadata Only" storage policy. 
        Article bodies (content) are explicitly EXCLUDED from persistent storage to optimize 
        storage costs and mitigate copyright risks.
    """
    
    def __init__(self):
        self.countries_map = {} 

    def get_connection(self):
        """
        Retrieves a database connection context manager from the global connection pool.
        
        Returns:
            contextlib.contextmanager: A generator yielding a psycopg2 connection object.
        """
        return db_manager.get_connection()

    def get_all_media_sources(self) -> List[Dict[str, Any]]:
        """
        Retrieves the complete catalog of Media Sources from the database.
        
        Operational Context:
        This method is the primary data feed for the `SourceClassifier` initialization. 
        It ensures that the runtime classification logic is synchronized with the latest 
        "Ground Truth" source definitions stored in the system.
        
        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a media source 
                                  with fields like domain, tier, country, and structural fingerprints.
        """
        sources = []
        try:
            with self.get_connection() as conn:
                if not conn:
                    return []
                
                with conn.cursor() as cursor:
                    # Select all fields required for MediaSource model instantiation
                    cursor.execute("""
                        SELECT domain, name, tier, country_code, country_name, type, language, logo_url, structure_simhash 
                        FROM media_sources
                    """)
                    rows = cursor.fetchall()
                    
                    columns = [desc[0] for desc in cursor.description]
                    for row in rows:
                        sources.append(dict(zip(columns, row)))
                        
        except Exception as e:
            logger.error(f"Critical Error: Failed to fetch media sources from DB: {e}")
            
        return sources

    def save_articles(self, articles: List[Dict[str, Any]]) -> int:
        """
        Persists a batch of crawled articles to the database.
        
        Methodology:
        1.  **Hash Generation**: Computes a unique deterministic hash for each URL to serve as a fingerprint.
        2.  **Deduplication (Two-Stage)**:
            -   **Stage 1 (Fingerprint Store)**: Checks the `url_library` table for the hash.
            -   **Stage 2 (Article Table)**: Checks the `news_articles` table for the URL/Hash.
        3.  **Metadata Extraction**: Extracts and maps fields (Title, Country, Date, Tier).
        4.  **Content Exclusion**: Explicitly inserts `None` for the `content` field, enforcing the 
            storage minimization policy.
            
        Args:
            articles (List[Dict[str, Any]]): Batch of article data dictionaries.
            
        Returns:
            int: The count of successfully inserted (new) articles.
        """
        if not articles:
            return 0
        
        count = 0
        try:
            with self.get_connection() as conn:
                if not conn:
                    logger.warning("Database connection unavailable; skipping batch save.")
                    return 0
                
                with conn.cursor() as cursor:
                    for art_data in articles:
                        if not art_data or not art_data.get("url"):
                            continue
                        
                        # Generate Unique URL Hash for Deduplication
                        url = art_data.get("url")
                        url_hash = generate_url_hash(url)
                        
                        # 1. Update UrlLibrary (Global Fingerprint Registry)
                        # Prevents re-crawling of known URLs across different sessions
                        cursor.execute("SELECT 1 FROM url_library WHERE hash = %s", (url_hash,))
                        if not cursor.fetchone():
                            try:
                                cursor.execute(
                                    "INSERT INTO url_library (hash, original_url) VALUES (%s, %s) ON CONFLICT (hash) DO NOTHING",
                                    (url_hash, url)
                                )
                            except Exception as e:
                                logger.warning(f"Failed to register URL hash {url_hash}: {e}")

                        # 2. Check existence in news_articles (Primary Metadata Store)
                        # Uses URL column for legacy compatibility, but hash lookup is preferred for performance.
                        cursor.execute("SELECT 1 FROM news_articles WHERE url = %s", (url,))
                        if cursor.fetchone():
                            continue # Skip duplicates

                        # 3. Insert Article Metadata
                        # Enforces "Metadata Only" policy by setting content=None
                        cursor.execute("""
                            INSERT INTO news_articles (url, title, country_code, country_name, content, published_at, scraped_at, source_tier, source_domain, url_hash)
                            VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s)
                        """, (
                            url,
                            art_data.get("title"),
                            art_data.get("sourcecountry"), # Mapped from GDELT or Scrapy metadata
                            art_data.get("country_name"),
                            None, # CRITICAL: Content is NOT stored.
                            art_data.get("published_at"),
                            art_data.get("source_tier"),
                            art_data.get("source_domain"),
                            url_hash
                        ))
                        count += 1
                    conn.commit()
        except Exception as e:
            logger.error(f"Batch Save Error: {e}")
            # Note: The context manager handles connection cleanup, but explicit transaction management 
            # might be needed for partial failures in future iterations.
            pass
            
        return count

    def save_candidate(self, candidate_data: dict):
        """
        Registers or updates a Candidate Source (Tier-2 Discovery).
        
        Algorithm (Snowball Sampling):
        This method implements the core logic for the "Snowball Sampling" discovery mechanism.
        When a Tier-0 article cites an external domain not in the seed library:
        1.  If the domain is new, it is inserted with `citation_count = 1`.
        2.  If the domain already exists as a candidate, its `citation_count` is incremented.
        
        This accumulation of citations acts as a "Vote of Confidence" from the Tier-0 network,
        allowing the system to automatically identify high-authority local sources.
        
        Args:
            candidate_data (dict): Dictionary containing 'domain', 'found_on' (URL), and 'tier_suggestion'.
        """
        try:
            with self.get_connection() as conn:
                if not conn:
                    return
                with conn.cursor() as cursor:
                    domain = candidate_data.get("domain")
                    if not domain:
                        return

                    # Upsert Logic: Insert or Increment Citation Count
                    cursor.execute("""
                        INSERT INTO candidate_sources (domain, found_on, status, tier_suggestion, citation_count)
                        VALUES (%s, %s, 'pending', %s, 1)
                        ON CONFLICT (domain) DO UPDATE 
                        SET citation_count = candidate_sources.citation_count + 1,
                            found_on = EXCLUDED.found_on -- Update 'found_on' to the most recent citation source
                    """, (domain, candidate_data.get("found_on"), candidate_data.get("tier_suggestion")))
                    conn.commit()
        except Exception as e:
            logger.error(f"Error saving candidate source {candidate_data.get('domain')}: {e}")

    def update_media_source(self, update_data: dict):
        """
        Updates dynamic metadata attributes (Logo, Structural Fingerprint) for an existing Media Source.
        
        Use Case:
        Allows the system to self-correct and enrich the seed library as it crawls, 
        capturing updated branding (logos) or structural changes (SimHash) in the target websites.
        """
        try:
            with self.get_connection() as conn:
                if not conn:
                    return
                with conn.cursor() as cursor:
                    domain = update_data.get("domain")
                    if not domain:
                        return
                        
                    # Conditional Update: Only update fields if new values are provided
                    cursor.execute("""
                        UPDATE media_sources
                        SET logo_url = COALESCE(%s, logo_url),
                            structure_simhash = COALESCE(%s, structure_simhash),
                            updated_at = NOW()
                        WHERE domain = %s
                    """, (update_data.get("logo_url"), update_data.get("structure_simhash"), domain))
                    conn.commit()
        except Exception as e:
            logger.error(f"Error updating media source {update_data.get('domain')}: {e}")
         
    def get_stats(self) -> Dict[str, Any]:
        """
        Aggregates system-wide statistics for monitoring dashboards.
        
        Returns:
            Dict[str, Any]: Basic metrics like 'total_articles'.
        """
        try:
            with self.get_connection() as conn:
                if not conn: return {}
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM news_articles")
                    total = cursor.fetchone()[0]
                    return {"total_articles": total}
        except Exception as e:
            logger.error(f"Error retrieving system stats: {e}")
            return {}

    def prune_old_articles(self, retention_hours: int = 12) -> int:
        """
        Executes the Data Hygiene Strategy by pruning ephemeral Tier-2 content.
        
        Scientific Rationale:
        Tier-2 (Local) news often has high velocity but low long-term archival value compared 
        to Tier-0 global events. To maintain database performance and manage storage costs, 
        this method enforces a strict retention window for lower-tier data.
        
        Args:
            retention_hours (int): The maximum age (in hours) for Tier-2 articles. Defaults to 12.
            
        Returns:
            int: The number of records deleted.
        """
        deleted_count = 0
        try:
            with self.get_connection() as conn:
                if not conn: return 0
                with conn.cursor() as cursor:
                    cursor.execute("""
                        DELETE FROM news_articles 
                        WHERE source_tier = 'Tier-2' 
                        AND scraped_at < NOW() - INTERVAL '%s hours'
                    """, (retention_hours,))
                    deleted_count = cursor.rowcount
                    conn.commit()
                    logger.info(f"Data Hygiene: Pruned {deleted_count} expired Tier-2 articles (> {retention_hours}h).")
        except Exception as e:
            logger.error(f"Error during article pruning: {e}")
        return deleted_count

# Global Singleton Instance
storage_operator = PostgresStorageOperator()
