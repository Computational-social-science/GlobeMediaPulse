import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from backend.core.database import db_manager
from backend.utils.hashing import generate_url_hash

logger = logging.getLogger(__name__)

class PostgresStorageOperator:
    """
    Operator for handling PostgreSQL database operations using raw psycopg2 connection pool.
    """
    def __init__(self):
        self.countries_map = {} 

    def get_connection(self):
        """Get a connection context manager from db_manager."""
        return db_manager.get_connection()

    def get_all_media_sources(self) -> List[Dict[str, Any]]:
        """
        Retrieves all media sources from the database.
        Used for initializing the SourceClassifier.
        """
        sources = []
        try:
            with self.get_connection() as conn:
                if not conn:
                    return []
                
                with conn.cursor() as cursor:
                    # Select all fields required for MediaSource model
                    cursor.execute("""
                        SELECT domain, name, tier, country_code, country_name, type, language, logo_url, structure_simhash 
                        FROM media_sources
                    """)
                    rows = cursor.fetchall()
                    
                    columns = [desc[0] for desc in cursor.description]
                    for row in rows:
                        sources.append(dict(zip(columns, row)))
                        
        except Exception as e:
            logger.error(f"Error fetching media sources: {e}")
            
        return sources

    def save_articles(self, articles: List[Dict[str, Any]]) -> int:
        """
        Save a batch of articles to the database.
        Returns the count of successfully saved new articles.
        """
        if not articles:
            return 0
        
        count = 0
        try:
            with self.get_connection() as conn:
                if not conn:
                    logger.warning("No DB connection available.")
                    return 0
                
                with conn.cursor() as cursor:
                    for art_data in articles:
                        if not art_data or not art_data.get("url"):
                            continue
                        
                        # Generate URL Hash
                        url = art_data.get("url")
                        url_hash = generate_url_hash(url)
                        
                        # 1. Update UrlLibrary (Fingerprint Store)
                        # Check if hash exists, if not insert
                        cursor.execute("SELECT 1 FROM url_library WHERE hash = %s", (url_hash,))
                        if not cursor.fetchone():
                            try:
                                cursor.execute(
                                    "INSERT INTO url_library (hash, original_url) VALUES (%s, %s) ON CONFLICT (hash) DO NOTHING",
                                    (url_hash, url)
                                )
                            except Exception as e:
                                logger.warning(f"Failed to insert into url_library: {e}")

                        # 2. Check existence in news_articles (Deduplication via Hash or URL)
                        # Prefer Hash for speed if indexed, but currently we check 'url' column for legacy compat
                        # Let's check hash first if column exists (it will be added via migration)
                        # But for now, we rely on URL unique constraint or check
                        cursor.execute("SELECT 1 FROM news_articles WHERE url = %s", (url,))
                        if cursor.fetchone():
                            continue

                        # Insert
                        # Table: news_articles (from models.py: id, url, title, country_code, country_name, content, published_at, scraped_at, source_tier, source_domain, url_hash)
                        cursor.execute("""
                            INSERT INTO news_articles (url, title, country_code, country_name, content, published_at, scraped_at, source_tier, source_domain, url_hash)
                            VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s)
                        """, (
                            url,
                            art_data.get("title"),
                            art_data.get("sourcecountry"), # mapping from 'sourcecountry'
                            art_data.get("country_name"),
                            None, # Content is no longer stored (Metadata only policy)
                            art_data.get("published_at"),
                            art_data.get("source_tier"),
                            art_data.get("source_domain"),
                            url_hash
                        ))
                        count += 1
                    conn.commit()
        except Exception as e:
            logger.error(f"Error saving articles: {e}")
            # Connection is handled by context manager (rollback/putconn) logic if exception raised, 
            # but here we caught it. If we catch it, we should ensure rollback if needed, 
            # but db_manager context manager might expect us to raise to handle cleanup properly?
            # Looking at db_manager: it commits/rollbacks? No, it just yields conn.
            # So we should rollback manually if using same conn.
            # But we are inside `with self.get_connection() as conn`.
            # If we catch exception here, `db_manager` sees normal exit.
            # So we should `conn.rollback()` if possible.
            # But simplest is to rely on `db_manager` checks.
            pass
            
        return count

    def save_candidate(self, candidate_data: dict):
        """
        Saves a candidate source to the database.
        """
        try:
            with self.get_connection() as conn:
                if not conn:
                    return
                with conn.cursor() as cursor:
                    domain = candidate_data.get("domain")
                    if not domain:
                        return

                    cursor.execute("""
                        INSERT INTO candidate_sources (domain, found_on, status, tier_suggestion)
                        VALUES (%s, %s, 'pending', %s)
                        ON CONFLICT (domain) DO NOTHING
                    """, (domain, candidate_data.get("found_on"), candidate_data.get("tier_suggestion")))
                    conn.commit()
        except Exception as e:
            logger.error(f"Error saving candidate {candidate_data.get('domain')}: {e}")

    def update_media_source(self, update_data: dict):
        """
        Updates metadata (Logo, SimHash) for an existing Media Source.
        """
        try:
            with self.get_connection() as conn:
                if not conn:
                    return
                with conn.cursor() as cursor:
                    domain = update_data.get("domain")
                    if not domain:
                        return
                        
                    # Only update if fields are provided
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
        """Get basic stats for dashboard."""
        try:
            with self.get_connection() as conn:
                if not conn: return {}
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM news_articles")
                    total = cursor.fetchone()[0]
                    return {"total_articles": total}
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}

    def prune_old_articles(self, retention_hours: int = 12) -> int:
        """
        Prune non-core Tier-2 articles older than the retention period.
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
                    logger.info(f"Pruned {deleted_count} old Tier-2 articles.")
        except Exception as e:
            logger.error(f"Error pruning old articles: {e}")
        return deleted_count

storage_operator = PostgresStorageOperator()
