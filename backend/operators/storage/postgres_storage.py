import logging
import json
import os
import time
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
        data_candidates = [
            os.path.join("data", "countries_data.json"),
            os.path.join("..", "data", "countries_data.json"),
        ]
        data_path = next((p for p in data_candidates if os.path.exists(p)), None)
        geojson_candidates = [
            os.path.join("backend", "data", "countries.geo.json"),
            os.path.join("data", "countries.geo.json"),
            os.path.join("backend", "core", "data", "countries.geo.json"),
            os.path.join("core", "data", "countries.geo.json"),
        ]
        geojson_path = next((p for p in geojson_candidates if os.path.exists(p)), None)

        if data_path:
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
        if geojson_path:
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
                    if (lat is None or lng is None) and isinstance(feature, dict):
                        geometry = feature.get("geometry", {})
                        if isinstance(geometry, dict) and geometry.get("type") in ("Polygon", "MultiPolygon"):
                            coords_list = geometry.get("coordinates")
                            ring = None
                            if geometry.get("type") == "Polygon" and isinstance(coords_list, list) and coords_list and isinstance(coords_list[0], list):
                                ring = coords_list[0]
                            if geometry.get("type") == "MultiPolygon" and isinstance(coords_list, list) and coords_list and isinstance(coords_list[0], list) and coords_list[0] and isinstance(coords_list[0][0], list):
                                ring = coords_list[0][0]
                            if isinstance(ring, list) and ring:
                                lng_sum = 0.0
                                lat_sum = 0.0
                                n = 0
                                for pt in ring:
                                    if not isinstance(pt, list) or len(pt) < 2:
                                        continue
                                    try:
                                        lng_sum += float(pt[0])
                                        lat_sum += float(pt[1])
                                        n += 1
                                    except Exception:
                                        continue
                                if n:
                                    lat = lat if lat is not None else lat_sum / n
                                    lng = lng if lng is not None else lng_sum / n
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
                        SELECT domain, name, abbreviation, tier, country_code, country_name, type, language, logo_url, structure_simhash 
                        FROM media_sources
                    """)
                    rows = cursor.fetchall()
                    
                    columns = [desc[0] for desc in cursor.description]
                    for row in rows:
                        record = dict(zip(columns, row))
                        abbr = record.get("abbreviation")
                        record["abbr"] = abbr
                        record["short_name"] = abbr or record.get("name")
                        sources.append(record)
                        
        except Exception as e:
            logger.error(f"Critical Error: Failed to fetch media sources from DB: {e}")
            
        return sources

    def get_all_candidate_sources(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        try:
            with self.get_connection() as conn:
                if not conn:
                    return []
                with conn.cursor() as cursor:
                    sql = """
                        SELECT domain, found_on, found_at, status, tier_suggestion, citation_count
                        FROM candidate_sources
                        ORDER BY citation_count DESC, found_at DESC
                    """
                    params: tuple[Any, ...] = tuple()
                    if isinstance(limit, int) and limit > 0:
                        sql += " LIMIT %s"
                        params = (limit,)
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    for row in rows:
                        candidates.append(dict(zip(columns, row)))
        except Exception as e:
            logger.error(f"Critical Error: Failed to fetch candidate sources from DB: {e}")
        return candidates

    def bulk_upsert_media_sources(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not sources:
            return {"processed": 0}
        processed = 0
        started_at = time.perf_counter()
        try:
            with self.get_connection() as conn:
                if not conn:
                    return {"processed": 0, "error": "db_unavailable"}
                with conn.cursor() as cursor:
                    rows: List[tuple[Any, ...]] = []
                    for s in sources:
                        if not isinstance(s, dict):
                            continue
                        domain = s.get("domain")
                        name = s.get("name")
                        if not domain or not name:
                            continue
                        rows.append(
                            (
                                str(domain).lower(),
                                str(name),
                                s.get("abbreviation") or s.get("abbr"),
                                s.get("country_code"),
                                s.get("country_name"),
                                s.get("language"),
                                s.get("tier"),
                                s.get("type"),
                                s.get("logo_url"),
                                s.get("logo_hash"),
                                s.get("copyright_text"),
                                s.get("structure_simhash"),
                            )
                        )
                    if not rows:
                        return {"processed": 0}
                    cursor.executemany(
                        """
                        INSERT INTO media_sources (
                            domain, name, abbreviation, country_code, country_name, language,
                            tier, type, logo_url, logo_hash, copyright_text, structure_simhash, created_at, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                        ON CONFLICT (domain) DO UPDATE SET
                            name = EXCLUDED.name,
                            abbreviation = COALESCE(EXCLUDED.abbreviation, media_sources.abbreviation),
                            country_code = COALESCE(EXCLUDED.country_code, media_sources.country_code),
                            country_name = COALESCE(EXCLUDED.country_name, media_sources.country_name),
                            language = COALESCE(EXCLUDED.language, media_sources.language),
                            tier = COALESCE(EXCLUDED.tier, media_sources.tier),
                            type = COALESCE(EXCLUDED.type, media_sources.type),
                            logo_url = COALESCE(EXCLUDED.logo_url, media_sources.logo_url),
                            logo_hash = COALESCE(EXCLUDED.logo_hash, media_sources.logo_hash),
                            copyright_text = COALESCE(EXCLUDED.copyright_text, media_sources.copyright_text),
                            structure_simhash = COALESCE(EXCLUDED.structure_simhash, media_sources.structure_simhash),
                            updated_at = NOW()
                        """,
                        rows,
                    )
                    processed = len(rows)
                    conn.commit()
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            self.record_src_metric(
                action="write",
                status="ok",
                latency_ms=elapsed_ms,
                delta_count=processed,
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            self.record_src_metric(action="write", status="error", latency_ms=elapsed_ms, error_message=str(e))
            logger.error(f"Bulk upsert media sources failed: {e}")
            return {"processed": processed, "error": str(e)}
        return {"processed": processed}

    def bulk_upsert_candidate_sources(self, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not candidates:
            return {"processed": 0}
        processed = 0
        try:
            with self.get_connection() as conn:
                if not conn:
                    return {"processed": 0, "error": "db_unavailable"}
                with conn.cursor() as cursor:
                    rows: List[tuple[Any, ...]] = []
                    for c in candidates:
                        if not isinstance(c, dict):
                            continue
                        domain = c.get("domain")
                        if not domain:
                            continue
                        citation = c.get("citation_count")
                        try:
                            citation_i = int(citation) if citation is not None else None
                        except Exception:
                            citation_i = None
                        rows.append(
                            (
                                str(domain).lower(),
                                c.get("found_on"),
                                c.get("status"),
                                c.get("tier_suggestion"),
                                citation_i,
                            )
                        )
                    if not rows:
                        return {"processed": 0}
                    cursor.executemany(
                        """
                        INSERT INTO candidate_sources (domain, found_on, status, tier_suggestion, citation_count, found_at)
                        VALUES (%s, %s, COALESCE(%s, 'pending'), %s, COALESCE(%s, 1), NOW())
                        ON CONFLICT (domain) DO UPDATE SET
                            found_on = COALESCE(EXCLUDED.found_on, candidate_sources.found_on),
                            tier_suggestion = COALESCE(EXCLUDED.tier_suggestion, candidate_sources.tier_suggestion),
                            citation_count = GREATEST(candidate_sources.citation_count, EXCLUDED.citation_count),
                            status = CASE
                                WHEN candidate_sources.status IN ('approved', 'rejected') THEN candidate_sources.status
                                WHEN EXCLUDED.status IS NULL OR EXCLUDED.status = '' THEN candidate_sources.status
                                ELSE EXCLUDED.status
                            END
                        """,
                        rows,
                    )
                    processed = len(rows)
                    conn.commit()
        except Exception as e:
            logger.error(f"Bulk upsert candidate sources failed: {e}")
            return {"processed": processed, "error": str(e)}
        return {"processed": processed}

    def get_sync_counts(self) -> Dict[str, int]:
        out = {"media_sources": 0, "candidate_sources": 0, "news_articles": 0}
        try:
            with self.get_connection() as conn:
                if not conn:
                    return out
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM media_sources")
                    out["media_sources"] = int(cursor.fetchone()[0] or 0)
                    cursor.execute("SELECT COUNT(*) FROM candidate_sources")
                    out["candidate_sources"] = int(cursor.fetchone()[0] or 0)
                    cursor.execute("SELECT COUNT(*) FROM news_articles")
                    out["news_articles"] = int(cursor.fetchone()[0] or 0)
        except Exception:
            return out
        return out

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
        started_at = time.perf_counter()
        try:
            with self.get_connection() as conn:
                if not conn:
                    return {}
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM news_articles")
                    total_articles = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM media_sources")
                    total_sources = cursor.fetchone()[0]
                    cursor.execute(
                        """
                        SELECT COUNT(*)
                        FROM media_sources
                        WHERE country_code IS NOT NULL AND country_code != 'UNK'
                        """
                    )
                    effective_sources = cursor.fetchone()[0]
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            self.record_src_metric(
                action="read",
                status="ok",
                latency_ms=elapsed_ms,
                total_sources=int(total_sources or 0),
                effective_sources=int(effective_sources or 0),
            )
            return {
                "total_articles": total_articles,
                "total_sources": total_sources,
                "effective_sources": effective_sources
            }
        except Exception as e:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            self.record_src_metric(action="read", status="error", latency_ms=elapsed_ms, error_message=str(e))
            logger.error(f"Error retrieving system stats: {e}")
            return {}

    def get_growth_recent(self, days: int = 7) -> List[Dict[str, Any]]:
        window_days = max(1, int(days or 7))
        try:
            with self.get_connection() as conn:
                if not conn:
                    return []
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        WITH days AS (
                            SELECT date_trunc('day', NOW()) - (interval '1 day' * generate_series(0, %s)) AS day
                        ),
                        media_net AS (
                            SELECT date_trunc('day', created_at) AS day, COUNT(*) AS net
                            FROM media_sources
                            WHERE created_at >= NOW() - interval %s
                            GROUP BY 1
                        ),
                        media AS (
                            SELECT d.day, COALESCE(m.net, 0) AS net
                            FROM days d LEFT JOIN media_net m ON m.day = d.day
                        ),
                        media_cum AS (
                            SELECT day, net, SUM(net) OVER (ORDER BY day) AS total
                            FROM media
                        ),
                        cand_net AS (
                            SELECT date_trunc('day', found_at) AS day, COUNT(*) AS net
                            FROM candidate_sources
                            WHERE found_at >= NOW() - interval %s
                            GROUP BY 1
                        ),
                        cand AS (
                            SELECT d.day, COALESCE(c.net, 0) AS net
                            FROM days d LEFT JOIN cand_net c ON c.day = d.day
                        ),
                        cand_cum AS (
                            SELECT day, net, SUM(net) OVER (ORDER BY day) AS total
                            FROM cand
                        ),
                        art_net AS (
                            SELECT date_trunc('day', COALESCE(scraped_at, published_at)) AS day, COUNT(*) AS net
                            FROM news_articles
                            WHERE COALESCE(scraped_at, published_at) >= NOW() - interval %s
                            GROUP BY 1
                        ),
                        art AS (
                            SELECT d.day, COALESCE(a.net, 0) AS net
                            FROM days d LEFT JOIN art_net a ON a.day = d.day
                        ),
                        art_cum AS (
                            SELECT day, net, SUM(net) OVER (ORDER BY day) AS total
                            FROM art
                        )
                        SELECT
                            m.day::date AS day,
                            m.net AS media_sources_net,
                            c.net AS candidate_sources_net,
                            a.net AS news_articles_net,
                            m.total AS media_sources_count,
                            c.total AS candidate_sources_count,
                            a.total AS news_articles_count,
                            CASE WHEN c.total > 0 THEN c.net::float / c.total ELSE 0 END AS candidate_sources_growth_rate
                        FROM media_cum m
                        JOIN cand_cum c ON c.day = m.day
                        JOIN art_cum a ON a.day = m.day
                        ORDER BY m.day DESC
                        """,
                        (window_days - 1, f"{window_days} days", f"{window_days} days", f"{window_days} days"),
                    )
                    rows = cursor.fetchall()
                    out: List[Dict[str, Any]] = []
                    for row in rows:
                        out.append(
                            {
                                "day": row[0].isoformat() if row[0] else None,
                                "media_sources_net": int(row[1] or 0),
                                "candidate_sources_net": int(row[2] or 0),
                                "news_articles_net": int(row[3] or 0),
                                "media_sources_count": int(row[4] or 0),
                                "candidate_sources_count": int(row[5] or 0),
                                "news_articles_count": int(row[6] or 0),
                                "candidate_sources_growth_rate": float(row[7] or 0),
                            }
                        )
                    return out
        except Exception as e:
            logger.error(f"Error retrieving growth stats: {e}")
            return []

    def record_src_metric(
        self,
        action: str,
        status: str,
        latency_ms: float | None = None,
        error_message: str | None = None,
        delta_count: int | None = None,
        total_sources: int | None = None,
        effective_sources: int | None = None,
    ) -> None:
        try:
            with self.get_connection() as conn:
                if not conn:
                    return
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        CREATE TABLE IF NOT EXISTS src_metrics (
                            id SERIAL PRIMARY KEY,
                            action TEXT NOT NULL,
                            status TEXT NOT NULL,
                            latency_ms DOUBLE PRECISION,
                            error_message TEXT,
                            delta_count INTEGER,
                            total_sources INTEGER,
                            effective_sources INTEGER,
                            created_at TIMESTAMP DEFAULT NOW()
                        )
                        """
                    )
                    cursor.execute(
                        """
                        INSERT INTO src_metrics (
                            action, status, latency_ms, error_message, delta_count,
                            total_sources, effective_sources, created_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                        """,
                        (
                            action,
                            status,
                            latency_ms,
                            error_message,
                            delta_count,
                            total_sources,
                            effective_sources,
                        ),
                    )
                    conn.commit()
        except Exception:
            return

    def get_src_metrics_recent(self, days: int = 7, bucket: str = "hour") -> List[Dict[str, Any]]:
        window_days = max(1, int(days or 7))
        bucket_unit = (bucket or "hour").strip().lower()
        if bucket_unit not in ("hour", "day"):
            bucket_unit = "hour"
        try:
            with self.get_connection() as conn:
                if not conn:
                    return []
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            date_trunc(%s, created_at) AS bucket,
                            action,
                            COUNT(*) AS total_requests,
                            SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) AS ok_requests,
                            SUM(CASE WHEN status != 'ok' THEN 1 ELSE 0 END) AS error_requests,
                            AVG(latency_ms) AS avg_latency_ms,
                            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms,
                            SUM(COALESCE(delta_count, 0)) AS delta_total
                        FROM src_metrics
                        WHERE created_at >= NOW() - interval %s
                        GROUP BY 1, 2
                        ORDER BY 1 DESC, 2 ASC
                        """,
                        (bucket_unit, f"{window_days} days"),
                    )
                    rows = cursor.fetchall()
                    out: List[Dict[str, Any]] = []
                    for row in rows:
                        bucket_ts = row[0].isoformat() if row[0] else None
                        total = int(row[2] or 0)
                        error_count = int(row[4] or 0)
                        qps = (float(total) / 3600.0) if bucket_unit == "hour" else (float(total) / 86400.0)
                        error_rate = (float(error_count) / float(total)) if total else 0.0
                        out.append(
                            {
                                "bucket": bucket_ts,
                                "action": row[1],
                                "total": total,
                                "ok": int(row[3] or 0),
                                "error": error_count,
                                "qps": qps,
                                "avg_latency_ms": float(row[5] or 0),
                                "p95_latency_ms": float(row[6] or 0),
                                "error_rate": error_rate,
                                "delta_total": int(row[7] or 0),
                                "bucket_unit": bucket_unit,
                            }
                        )
                    return out
        except Exception as e:
            logger.error(f"Error retrieving src metrics: {e}")
            return []

    def get_src_alert(self, window_minutes: int = 30) -> Dict[str, Any]:
        window_minutes = max(1, int(window_minutes or 30))
        try:
            with self.get_connection() as conn:
                if not conn:
                    return {"window_minutes": window_minutes, "status": "no_connection"}
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            COUNT(*) AS total_requests,
                            SUM(CASE WHEN action = 'write' THEN 1 ELSE 0 END) AS write_requests,
                            SUM(CASE WHEN action = 'write' THEN COALESCE(delta_count, 0) ELSE 0 END) AS write_delta,
                            AVG(CASE WHEN action = 'write' THEN latency_ms END) AS write_avg_latency_ms,
                            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) FILTER (WHERE action = 'write') AS write_p95_latency_ms,
                            MAX(created_at) AS last_metric_at
                        FROM src_metrics
                        WHERE created_at >= NOW() - interval %s
                        """,
                        (f"{window_minutes} minutes",),
                    )
                    row = cursor.fetchone() or ()
                    total_requests = int(row[0] or 0)
                    write_requests = int(row[1] or 0)
                    write_delta = int(row[2] or 0)
                    write_avg = float(row[3] or 0)
                    write_p95 = float(row[4] or 0)
                    last_metric_at = row[5].isoformat() if row[5] else None
                    no_change = write_delta == 0
                    return {
                        "window_minutes": window_minutes,
                        "total_requests": total_requests,
                        "write_requests": write_requests,
                        "write_delta": write_delta,
                        "write_avg_latency_ms": write_avg,
                        "write_p95_latency_ms": write_p95,
                        "last_metric_at": last_metric_at,
                        "no_change": no_change,
                    }
        except Exception as e:
            logger.error(f"Error retrieving src alert: {e}")
            return {"window_minutes": window_minutes, "status": "error", "error": str(e)}

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
