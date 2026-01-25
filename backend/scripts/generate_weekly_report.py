import os
import sys
import logging
import json
from datetime import datetime, timedelta
import psycopg2
from collections import defaultdict

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "reports")
os.makedirs(REPORT_DIR, exist_ok=True)

def get_db_connection():
    return psycopg2.connect(settings.DATABASE_URL)

def generate_weekly_report():
    """
    Generates a weekly scientific report on media ecosystem expansion.
    """
    logger.info("Generating Weekly Ecosystem Report...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    report_lines = []
    report_lines.append(f"# Global Media Ecosystem Report: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    report_lines.append(f"**Generated at**: {end_date.strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
    
    # 1. New Candidate Discovery Stats
    cursor.execute("""
        SELECT COUNT(*) FROM candidate_sources 
        WHERE found_at >= %s
    """, (start_date,))
    new_candidates = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM candidate_sources
    """)
    total_candidates = cursor.fetchone()[0]
    
    report_lines.append("## 1. Discovery Metrics (Snowball Sampling)")
    report_lines.append(f"- **New Candidates Discovered**: {new_candidates}")
    report_lines.append(f"- **Total Candidates Pending Review**: {total_candidates}")
    
    # 2. Media Library Expansion
    cursor.execute("""
        SELECT COUNT(*) FROM media_sources 
        WHERE created_at >= %s
    """, (start_date,))
    new_sources = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT tier, COUNT(*) FROM media_sources 
        GROUP BY tier
    """)
    tier_stats = cursor.fetchall()
    
    report_lines.append("\n## 2. Verified Media Library Status")
    report_lines.append(f"- **New Sources Added (Last 7 Days)**: {new_sources}")
    report_lines.append("\n### Distribution by Tier")
    for tier, count in tier_stats:
        report_lines.append(f"- **{tier}**: {count}")
        
    # 3. Geographic Coverage
    cursor.execute("""
        SELECT country_name, COUNT(*) as c 
        FROM media_sources 
        GROUP BY country_name 
        ORDER BY c DESC 
        LIMIT 10
    """)
    geo_stats = cursor.fetchall()
    
    report_lines.append("\n## 3. Top Geographic Coverage")
    report_lines.append("| Country | Source Count |")
    report_lines.append("|---------|--------------|")
    for country, count in geo_stats:
        report_lines.append(f"| {country or 'Unknown'} | {count} |")

    # 4. Coordination Network Detection (Visual Fingerprinting)
    report_lines.append("\n## 4. Coordination Network Detection (Beta)")
    report_lines.append("> Analysis of visual fingerprints (Logo pHash) to identify potential 'sockpuppet' networks.")
    
    cursor.execute("""
        SELECT logo_hash, COUNT(*) as c, string_agg(domain, ', ') 
        FROM media_sources 
        WHERE logo_hash IS NOT NULL 
        GROUP BY logo_hash 
        HAVING COUNT(*) > 1 
        ORDER BY c DESC
        LIMIT 5
    """)
    clusters = cursor.fetchall()
    
    if clusters:
        for phash, count, domains in clusters:
            report_lines.append(f"- **Cluster {phash[:8]}**: {count} sites share identical branding.")
            report_lines.append(f"  - *Examples*: {domains[:100]}...")
    else:
        report_lines.append("- No significant coordination clusters detected this week.")

    # Write Report
    filename = f"Weekly_Report_{end_date.strftime('%Y_%m_%d')}.md"
    filepath = os.path.join(REPORT_DIR, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
        
    logger.info(f"Report generated: {filepath}")
    
    conn.close()

if __name__ == "__main__":
    generate_weekly_report()
