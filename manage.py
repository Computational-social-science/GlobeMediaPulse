import click
import sys
import os
import logging
import redis
from sqlalchemy import create_engine, text
from backend.core.config import settings

# Add project root to sys.path
sys.path.append(os.getcwd())

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@click.group()
def cli():
    """GlobeMediaPulse Management CLI"""
    pass

@cli.command(name="health-check")
def health_check():
    """Run system health checks (Database, Redis, etc.)"""
    click.echo("Running System Health Check...")
    
    # 1. Check PostgreSQL
    try:
        url = settings.DATABASE_URL
        if url and url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        click.echo("✅ PostgreSQL: Connected")
    except Exception as e:
        click.echo(f"❌ PostgreSQL: Failed ({e})")
        sys.exit(1)

    # 2. Check Redis
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        r = redis.Redis.from_url(redis_url)
        r.ping()
        click.echo(f"✅ Redis: Connected ({redis_url})")
    except Exception as e:
        click.echo(f"❌ Redis: Failed ({e})")
        sys.exit(1)

    click.echo("System is HEALTHY.")

@cli.command(name="analytics")
def analytics():
    """Show system analytics and statistics"""
    click.echo("Running System Analytics...")
    
    # 1. Media Sources Stats
    try:
        url = settings.DATABASE_URL
        if url and url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        engine = create_engine(url)
        with engine.connect() as conn:
            # Total Sources
            total = conn.execute(text("SELECT count(*) FROM media_sources")).scalar()
            click.echo(f"📊 Total Media Sources: {total}")
            
            # Sources by Tier
            click.echo("   Breakdown by Tier:")
            tier_stats = conn.execute(text("SELECT tier, count(*) FROM media_sources GROUP BY tier ORDER BY tier")).fetchall()
            for tier, count in tier_stats:
                click.echo(f"   - {tier}: {count}")

            # Sources by Country
            click.echo("   Top 5 Countries:")
            country_stats = conn.execute(text("SELECT country_name, count(*) FROM media_sources GROUP BY country_name ORDER BY count(*) DESC LIMIT 5")).fetchall()
            for country, count in country_stats:
                click.echo(f"   - {country}: {count}")
                
    except Exception as e:
        click.echo(f"❌ Database Analytics Failed: {e}")

    # 2. Redis Queue Stats
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        r = redis.Redis.from_url(redis_url)
        # Assuming scrapy-redis uses "queue:items" or similar keys
        # The key name depends on the spider name. UniversalNewsSpider?
        # Typically "spider_name:requests" or "spider_name:items"
        # We can check common keys
        keys = r.keys("*:requests")
        if keys:
            click.echo("🕸️  Crawler Queues:")
            for key in keys:
                count = r.llen(key)
                click.echo(f"   - {key.decode()}: {count} pending requests")
        else:
            click.echo("🕸️  Crawler Queues: Empty (or no active queues)")
            
    except Exception as e:
        click.echo(f"❌ Redis Analytics Failed: {e}")

@cli.command(name="crawl")
@click.argument("spider_name", default="universal_news_spider")
def crawl(spider_name):
    """Start a crawler by name"""
    click.echo(f"🕷️  Starting crawler: {spider_name}")
    # We use subprocess to call scrapy crawl
    import subprocess
    # We need to run this inside backend/crawlers/news_crawlers directory
    cwd = os.path.join(settings.BASE_DIR, "backend", "crawlers", "news_crawlers")
    
    # Ensure cwd exists
    if not os.path.exists(cwd):
        click.echo(f"❌ Crawler directory not found: {cwd}")
        return

    cmd = ["scrapy", "crawl", spider_name]
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Crawler failed with exit code {e.returncode}")
    except KeyboardInterrupt:
        click.echo("\n🛑 Crawler stopped by user")
    except Exception as e:
        click.echo(f"❌ Error running crawler: {e}")

if __name__ == "__main__":
    cli()
