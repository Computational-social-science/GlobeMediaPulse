import logging
import json
import os
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
        self._load_countries_map()

    def _load_countries_map(self):
        self.countries_map = {}
        data_path = os.path.join("data", "countries_data.json")
        geojson_path = os.path.join("backend", "data", "countries.geo.json")
        if os.path.exists(data_path):
            try:
                with open(data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                countries = data.get("COUNTRIES") if isinstance(data, dict) else data
                if isinstance(countries, list):
                    for c in countries:
                        code = c.get("code")
                        name = c.get("name")
                        lat = c.get("lat")
                        lng = c.get("lng")
                        region = c.get("region") or "Unknown"
                        if not code or not name or lat is None or lng is None:
                            continue
                        entry = {
                            "code": code,
                            "name": name,
                            "lat": float(lat),
                            "lng": float(lng),
                            "region": region
                        }
                        self.countries_map[name] = entry
                        official_name = c.get("official_name")
                        if official_name and official_name != name:
                            self.countries_map[official_name] = entry
                return
            except Exception as e:
                logger.error(f"Failed to load countries_data.json: {e}")
        if os.path.exists(geojson_path):
            try:
                with open(geojson_path, "r", encoding="utf-8") as f:
                    geo_data = json.load(f)
                for feature in geo_data.get("features", []):
                    code = feature.get("id")
                    props = feature.get("properties", {})
                    name = props.get("name")
                    lat = props.get("lat")
                    lng = props.get("lng")
                    region = props.get("region") or "Unknown"
                    if not code or not name or lat is None or lng is None:
                        continue
                    self.countries_map[name] = {
                        "code": code,
                        "name": name,
                        "lat": float(lat),
                        "lng": float(lng),
                        "region": region
                    }
            except Exception as e:
                logger.error(f"Failed to load countries.geo.json: {e}")

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
                            INSERT INTO news_articles (
                                url, title, country_code, country_name, content, published_at, scraped_at, 
                                source_tier, source_domain, url_hash,
                                entities, sentiment_score, safety_label, safety_score
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            url,
                            art_data.get("title"),
                            art_data.get("sourcecountry"), # Mapped from GDELT or Scrapy metadata
                            art_data.get("country_name"),
                            None, # CRITICAL: Content is NOT stored.
                            art_data.get("published_at"),
                            art_data.get("source_tier"),
                            art_data.get("source_domain"),
                            url_hash,
                            json.dumps(art_data.get("entities")) if art_data.get("entities") else None,
                            art_data.get("sentiment_score"),
                            art_data.get("safety_label"),
                            art_data.get("safety_score")
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
                        RETURNING citation_count
                    """, (domain, candidate_data.get("found_on"), candidate_data.get("tier_suggestion")))
                    
                    citation_count = cursor.fetchone()[0]
                    conn.commit()

                    # Auto-Promotion Logic: If citation count >= Threshold, promote to Tier-2 Source
                    # Using Threshold = 1 for immediate gratification based on user feedback.
                    if citation_count >= 1:
                        self._promote_candidate_to_source(cursor, domain, candidate_data)
                        conn.commit()
                        
        except Exception as e:
            logger.error(f"Error saving candidate source {candidate_data.get('domain')}: {e}")

    def _promote_candidate_to_source(self, cursor, domain: str, candidate_data: dict):
        """
        Internal method to promote a Candidate to a full Media Source.
        """
        try:
            # Check if already in media_sources
            cursor.execute("SELECT 1 FROM media_sources WHERE domain = %s", (domain,))
            if cursor.fetchone():
                return

            # Promote
            cursor.execute("""
                INSERT INTO media_sources (domain, name, country_code, country_name, tier, type, created_at)
                VALUES (%s, %s, 'UNK', 'Unknown', 'Tier-2', 'General', NOW())
            """, (domain, domain))
            
            # Update candidate status
            cursor.execute("""
                UPDATE candidate_sources SET status = 'promoted' WHERE domain = %s
            """, (domain,))
            
            logger.info(f"Auto-Promoted Candidate to Tier-2 Source: {domain}")
        except Exception as e:
            logger.error(f"Failed to promote candidate {domain}: {e}")

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
                            logo_hash = COALESCE(%s, logo_hash),
                            copyright_text = COALESCE(%s, copyright_text),
                            structure_simhash = COALESCE(%s, structure_simhash),
                            updated_at = NOW()
                        WHERE domain = %s
                    """, (
                        update_data.get("logo_url"), 
                        update_data.get("logo_hash"),
                        update_data.get("copyright_text"),
                        update_data.get("structure_simhash"), 
                        domain
                    ))
                    conn.commit()
        except Exception as e:
            logger.error(f"Error updating media source {update_data.get('domain')}: {e}")
         
    def get_stats(self) -> Dict[str, Any]:
        """
        Aggregates system-wide statistics for monitoring dashboards.
        
        Returns:
            Dict[str, Any]: Basic metrics like 'total_articles', 'total_sources'.
        """
        try:
            with self.get_connection() as conn:
                if not conn: return {}
                with conn.cursor() as cursor:
                    # 1. Total Articles
                    cursor.execute("SELECT COUNT(*) FROM news_articles")
                    total_articles = cursor.fetchone()[0]
                    
                    # 2. Total Media Sources
                    cursor.execute("SELECT COUNT(*) FROM media_sources")
                    total_sources = cursor.fetchone()[0]
                    
                    return {
                        "total_articles": total_articles,
                        "total_sources": total_sources
                    }
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
        except Exception as e:
            logger.error(f"Pruning Error: {e}")
            
        return deleted_count

    def update_media_source_country(self, domain: str, country_code: str, country_name: str = None) -> bool:
        """
        Updates the country information for a specific media source (Loop-Back Learning).
        
        Research Motivation:
        -   **Self-Improving Knowledge Base**: Allows the system to permanently learn from runtime 
            inferences (TLD/GeoJSON matching), refining the "Ground Truth" over time.
            
        Args:
            domain (str): The domain of the media source.
            country_code (str): The inferred ISO-3 country code.
            country_name (str, optional): The full country name.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            with self.get_connection() as conn:
                if not conn: return False
                with conn.cursor() as cursor:
                    # Check if exists
                    cursor.execute("SELECT domain FROM media_sources WHERE domain = %s", (domain,))
                    if cursor.fetchone():
                        cursor.execute("""
                            UPDATE media_sources 
                            SET country_code = %s, country_name = COALESCE(%s, country_name)
                            WHERE domain = %s
                        """, (country_code, country_name, domain))
                    else:
                        # Insert new minimal source (Auto-Discovery)
                        cursor.execute("""
                            INSERT INTO media_sources (domain, country_code, country_name, tier, type, created_at)
                            VALUES (%s, %s, %s, 'Tier-2', 'General', NOW())
                        """, (domain, country_code, country_name))
                    
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"Failed to update media source country for {domain}: {e}")
            return False

    def get_brain_stats(self) -> Dict[str, Any]:
        """
        Retrieves aggregated stats for the "Brain" module (Entities & Narrative).
        """
        stats = {
            "top_entities": [],
            "narrative_divergence": []
        }
        try:
            with self.get_connection() as conn:
                if not conn: return stats
                with conn.cursor() as cursor:
                    # 1. Top Entities (Global Heatmap)
                    # Note: entities is JSONB list of dicts. We need to unnest.
                    # Use jsonb_array_elements
                    cursor.execute("""
                        SELECT e->>'text' as entity, COUNT(*) as c
                        FROM news_articles, jsonb_array_elements(entities) as e
                        WHERE published_at > NOW() - INTERVAL '24 HOURS'
                        GROUP BY entity
                        ORDER BY c DESC
                        LIMIT 10;
                    """)
                    stats["top_entities"] = [{"entity": r[0], "count": r[1]} for r in cursor.fetchall()]

                    # 2. Narrative Divergence (Tier-0 vs Tier-2)
                    # Avg sentiment per tier
                    cursor.execute("""
                        SELECT source_tier, AVG(sentiment_score) as avg_sentiment
                        FROM news_articles
                        WHERE published_at > NOW() - INTERVAL '24 HOURS'
                        AND sentiment_score IS NOT NULL
                        GROUP BY source_tier;
                    """)
                    rows = cursor.fetchall()
                    tier_sentiment = {r[0]: r[1] for r in rows}
                    
                    # Calculate divergence if both exist
                    t0 = tier_sentiment.get('Tier-0', 0.0)
                    t2 = tier_sentiment.get('Tier-2', 0.0)
                    divergence = abs(t0 - t2)
                    
                    stats["narrative_divergence"] = {
                        "tier_0_sentiment": t0,
                        "tier_2_sentiment": t2,
                        "divergence": divergence,
                        "alert": divergence > 0.5 # Threshold
                    }
        except Exception as e:
            logger.error(f"Error fetching brain stats: {e}")
            
        return stats

storage_operator = PostgresStorageOperator()
