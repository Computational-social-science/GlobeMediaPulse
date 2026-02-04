import logging
import os
import time
from sqlalchemy.dialects.postgresql import insert as pg_insert
from backend.core.config import settings
from backend.operators.storage import storage_operator
from backend.core.shared_state import country_geo_map
from backend.core.database import engine, SessionLocal
from backend.core.models import Base, MediaSource

logger = logging.getLogger(__name__)


class InitPipeline:
    r"""
    Initialization pipeline for environment bootstrap and shared-state hydration.

    Research motivation: ensure a consistent initialization map
    $m: \mathcal{C} \rightarrow \mathbb{R}^2$ from country codes to geo-centroids,
    which stabilizes downstream spatial joins.
    """

    def __init__(self):
        pass

    def run(self):
        """
        Execute initialization steps.

        Steps:
        1. Ensure data directories exist.
        2. Populate shared state for geographic lookup.
        """
        logger.info("Running Initialization Pipeline...")
        self._ensure_dirs()
        try:
            Base.metadata.create_all(bind=engine)
        except Exception as e:
            logger.error(f"Database schema init failed: {type(e).__name__}: {e}")
        self._ensure_seed_sources()
        self._ensure_seed_queue()
        self._init_global_state()
        logger.info("Initialization complete.")

    def _ensure_dirs(self):
        r"""
        Create required data directories.

        Ensures $D_{\mathrm{data}}$ exists for downstream persistence.
        """
        os.makedirs(settings.DATA_DIR, exist_ok=True)

    def _init_global_state(self):
        r"""
        Populate global shared state for geo lookups.

        Builds a mapping for both ISO codes and uppercase names to
        reduce lookup variance $\mathbb{V}[\hat{g}(c)]$ under noisy inputs.
        """
        count = 0
        for c_name, data in storage_operator.countries_map.items():
            country_geo_map[data["code"]] = {"lat": data["lat"], "lng": data["lng"], "name": c_name}
            country_geo_map[c_name.upper()] = {"lat": data["lat"], "lng": data["lng"], "name": c_name}
            count += 1
        logger.info(f"Initialized Country Geo Map with {count} entries.")

    def _ensure_seed_sources(self):
        max_attempts = int(os.getenv("INIT_RETRY_MAX", "10") or "10")
        delay_s = float(os.getenv("INIT_RETRY_DELAY_S", "0.5") or "0.5")
        for attempt in range(1, max_attempts + 1):
            try:
                try:
                    from backend.scripts.seed_media_sources import SEED_DATA
                except Exception as e:
                    logger.error(f"Seed import failed: {type(e).__name__}: {e}")
                    return

                by_domain: dict[str, dict] = {}
                for data in SEED_DATA:
                    if not isinstance(data, dict):
                        continue
                    domain = (data.get("domain") or "").strip().lower()
                    if not domain:
                        continue
                    if domain in by_domain:
                        continue
                    by_domain[domain] = {
                        "domain": domain,
                        "name": (data.get("name") or domain),
                        "country_name": data.get("country_name"),
                        "country_code": data.get("country_code"),
                        "tier": data.get("tier"),
                        "type": data.get("type"),
                        "language": data.get("language"),
                    }

                rows = list(by_domain.values())
                if not rows:
                    return

                with SessionLocal() as db:
                    stmt = pg_insert(MediaSource).values(rows)
                    stmt = stmt.on_conflict_do_nothing(index_elements=[MediaSource.domain])
                    result = db.execute(stmt)
                    db.commit()
                    inserted = int(getattr(result, "rowcount", 0) or 0)
                    logger.info(f"Seeded {inserted} media sources.")
                return
            except Exception as e:
                logger.error(f"Seeding failed: {type(e).__name__}: {e}")
                if attempt >= max_attempts:
                    return
                time.sleep(delay_s)

    def _ensure_seed_queue(self):
        max_attempts = int(os.getenv("INIT_RETRY_MAX", "10") or "10")
        delay_s = float(os.getenv("INIT_RETRY_DELAY_S", "0.5") or "0.5")
        for attempt in range(1, max_attempts + 1):
            try:
                import redis

                redis_url = (settings.REDIS_URL or "").strip()
                if not redis_url:
                    return
                client = redis.from_url(redis_url)

                key = (settings.SEED_QUEUE_KEY or "universal_news:start_urls").strip()
                current = int(client.llen(key) or 0)
                min_len = int(settings.SEED_QUEUE_MIN or 0)
                target = int(settings.SEED_QUEUE_TARGET or 0)
                if current >= min_len:
                    return

                tiers = [t.strip() for t in (settings.SEED_SOURCE_TIERS or "").split(",") if t.strip()]
                scheme = (settings.SEED_URL_SCHEME or "https").strip()
                if scheme not in ("http", "https"):
                    scheme = "https"

                with SessionLocal() as db:
                    q = db.query(MediaSource.domain)
                    if tiers:
                        q = q.filter(MediaSource.tier.in_(tiers))
                    domains = [row[0] for row in q.all() if row and row[0]]

                if not domains:
                    return

                remaining = max(0, target - current) if target else len(domains)
                if remaining <= 0:
                    remaining = len(domains)
                to_push = domains[:remaining]
                urls = [f"{scheme}://{d}" for d in to_push]
                if urls:
                    client.lpush(key, *urls)
                    logger.info(f"Seeded {len(urls)} URLs into {key}.")
                return
            except Exception as e:
                logger.error(f"Seed queue init failed: {type(e).__name__}: {e}")
                if attempt >= max_attempts:
                    return
                time.sleep(delay_s)


init_pipeline = InitPipeline()
