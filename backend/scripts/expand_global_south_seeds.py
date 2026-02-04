
import os
import sys
import json
import time
import logging
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Load env vars from .env file in root
load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))

from backend.operators.intelligence.media_cloud_client import MediaCloudIntegrator
from backend.core.database import SessionLocal
from backend.core.models import MediaSource

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _load_country_index() -> dict[str, dict]:
    data_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/countries_data.json"))
    if not os.path.exists(data_path):
        return {}
    with open(data_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    countries = raw.get("COUNTRIES") if isinstance(raw, dict) else raw
    if not isinstance(countries, list):
        return {}
    index = {}
    for entry in countries:
        name = (entry.get("name") or "").strip()
        code = (entry.get("code") or "").strip()
        if not name or not code:
            continue
        index[name.lower()] = {"name": name, "code": code}
    return index

def _get_source_counts() -> tuple[int, int]:
    db = SessionLocal()
    try:
        total = int(db.query(MediaSource).count() or 0)
        effective = int(
            db.query(MediaSource)
            .filter(MediaSource.country_code.isnot(None), MediaSource.country_code != "UNK")
            .count()
        )
        return total, effective
    finally:
        db.close()

def get_seed_metrics() -> dict:
    total, effective = _get_source_counts()
    min_effective = int(os.getenv("SEED_EFFECTIVE_MIN", "10000") or "10000")
    target_total = int(os.getenv("SEED_TARGET_TOTAL", "50000") or "50000")
    return {
        "total_sources": total,
        "effective_sources": effective,
        "min_effective": min_effective,
        "target_total": target_total,
    }

def expand_global_south():
    logger.info("Starting Global South Seed Expansion...")
    
    mc = MediaCloudIntegrator()
    if not mc.api_key:
        logger.error("Media Cloud API Key missing!")
        return

    country_index = _load_country_index()
    total_before, effective_before = _get_source_counts()
    logger.info(f"Initial counts: total_sources={total_before} effective_sources={effective_before}")

    min_effective = int(os.getenv("SEED_EFFECTIVE_MIN", "10000") or "10000")
    target_total = int(os.getenv("SEED_TARGET_TOTAL", "50000") or "50000")
    force_expand = (os.getenv("SEED_FORCE_EXPAND", "") or "").strip().lower() in ("1", "true", "yes", "y")

    if effective_before >= min_effective and total_before >= target_total and not force_expand:
        logger.info("Seed pool already above thresholds. Skipping expansion.")
        return {
            "status": "skipped",
            "total_before": total_before,
            "effective_before": effective_before,
            "total_after": total_before,
            "effective_after": effective_before,
            "curve": [],
        }

    priority_countries = [
        "Brazil", "South Africa", "Nigeria", "Indonesia", "Egypt",
        "Argentina", "Saudi Arabia", "Turkey", "Thailand", "Mexico"
    ]
    fallback_countries = [c["name"] for c in country_index.values()]
    ordered_countries = []
    seen = set()
    for name in priority_countries + fallback_countries:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered_countries.append(name)

    total_new = 0
    curve = []
    for country in ordered_countries:
        current_total, current_effective = _get_source_counts()
        if current_total >= target_total and not force_expand:
            break
        logger.info(f"Processing {country}...")
        col_id = mc.get_national_collection_id(country)
        if not col_id:
            logger.warning(f"  No collection ID found for {country}")
            continue

        remaining = max(0, target_total - current_total)
        per_country_limit = max(200, min(2000, remaining // max(1, len(ordered_countries)) + 200))
        sources = mc.fetch_sources_from_collection(col_id, limit=per_country_limit)
        logger.info(f"  Fetched {len(sources)} sources from collection {col_id}")
        if not sources:
            logger.warning(f"  No sources found for {country}")
            continue

        meta = country_index.get(country.lower())
        code = meta["code"] if meta else "UNK"
        new_count, updated_count = mc.sync_sources_to_db(sources, default_tier=2, country_code=code)
        logger.info(f"  {country} ({code}): Added {new_count}, Updated {updated_count}")
        total_new += new_count

        after_total, after_effective = _get_source_counts()
        curve.append(
            {
                "timestamp": time.time(),
                "country": country,
                "total_sources": after_total,
                "effective_sources": after_effective,
                "added": int(new_count or 0),
                "updated": int(updated_count or 0),
            }
        )

    total_after, effective_after = _get_source_counts()
    logger.info(f"Global South Expansion Complete. Total new sources: {total_new}")
    logger.info(f"Final counts: total_sources={total_after} effective_sources={effective_after}")
    if curve:
        logger.info(f"SRC_curve={json.dumps(curve, ensure_ascii=False)}")
    return {
        "status": "ok",
        "total_before": total_before,
        "effective_before": effective_before,
        "total_after": total_after,
        "effective_after": effective_after,
        "curve": curve,
    }

if __name__ == "__main__":
    expand_global_south()
