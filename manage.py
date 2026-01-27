import click
import sys
import os
import logging
import redis
import requests
import subprocess
import datetime
from urllib.parse import urlsplit, urlunsplit
from sqlalchemy import create_engine, text
from backend.core.config import settings
from backend.operators.storage import storage_operator

# Add project root to sys.path
sys.path.append(os.getcwd())

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _redact_url(url: str) -> str:
    try:
        parts = urlsplit(url or "")
        if not parts.scheme or not parts.netloc:
            return url
        username = parts.username
        hostname = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
        auth = ""
        if username:
            auth = f"{username}:***@"
        netloc = f"{auth}{hostname}{port}"
        return urlunsplit((parts.scheme, netloc, "", "", ""))
    except Exception:
        return "<redacted>"

def _run(cmd: list[str], cwd: str | None = None, env: dict[str, str] | None = None, check: bool = True, dry_run: bool = False) -> int:
    rendered = " ".join(cmd)
    click.echo(f"$ {rendered}")
    if dry_run:
        return 0
    p = subprocess.run(cmd, cwd=cwd, env=env, check=False)
    if check and p.returncode != 0:
        raise click.ClickException(f"Command failed ({p.returncode}): {rendered}")
    return int(p.returncode)

def _git_has_changes(dry_run: bool = False) -> bool:
    if dry_run:
        return True
    p = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=False)
    if p.returncode != 0:
        raise click.ClickException("git status failed; ensure git is installed and this is a git repo.")
    return bool((p.stdout or "").strip())

def _docker_compose_cmd() -> list[str]:
    p = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True, check=False)
    if p.returncode == 0:
        return ["docker", "compose"]
    return ["docker-compose"]

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
        click.echo(f"❌ PostgreSQL: Failed ({type(e).__name__})")
        sys.exit(1)

    # 2. Check Redis
    try:
        redis_url = settings.REDIS_URL
        r = redis.Redis.from_url(redis_url)
        r.ping()
        click.echo(f"✅ Redis: Connected ({_redact_url(redis_url)})")
    except Exception as e:
        click.echo(f"❌ Redis: Failed ({type(e).__name__})")
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
        redis_url = settings.REDIS_URL
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

@cli.command(name="sync-to-remote")
@click.option("--remote-api", default=lambda: os.getenv("REMOTE_API_URL", "https://globe-media-pulse.fly.dev/api"), show_default=True)
@click.option("--token", default=lambda: os.getenv("SYNC_TOKEN", ""), show_default=False)
@click.option("--include-candidates/--no-candidates", default=True, show_default=True)
@click.option("--candidates-limit", default=5000, show_default=True, type=int)
@click.option("--timeout", default=30, show_default=True, type=int)
def sync_to_remote(remote_api: str, token: str, include_candidates: bool, candidates_limit: int, timeout: int):
    if not token or not token.strip():
        click.echo("❌ Missing SYNC_TOKEN (set env var or pass --token).")
        sys.exit(1)
    remote_api = (remote_api or "").rstrip("/")
    headers = {"X-Sync-Token": token.strip()}

    click.echo(f"Exporting local media_sources...")
    media_sources = storage_operator.get_all_media_sources()
    click.echo(f"Local media_sources: {len(media_sources)}")

    click.echo("Pushing media_sources to remote...")
    r = requests.post(
        f"{remote_api}/system/sync/media-sources",
        json=media_sources,
        headers=headers,
        timeout=timeout,
    )
    if r.status_code != 200:
        click.echo(f"❌ Remote sync failed (media_sources): HTTP {r.status_code}")
        click.echo(r.text)
        sys.exit(1)
    resp_media = r.json()
    click.echo(f"✅ Remote media_sources sync: {resp_media.get('processed', 0)} processed")

    if include_candidates:
        click.echo("Exporting local candidate_sources...")
        candidates = storage_operator.get_all_candidate_sources(limit=candidates_limit)
        click.echo(f"Local candidate_sources: {len(candidates)}")

        click.echo("Pushing candidate_sources to remote...")
        r2 = requests.post(
            f"{remote_api}/system/sync/candidate-sources",
            json=candidates,
            headers=headers,
            timeout=timeout,
        )
        if r2.status_code != 200:
            click.echo(f"❌ Remote sync failed (candidate_sources): HTTP {r2.status_code}")
            click.echo(r2.text)
            sys.exit(1)
        resp_candidates = r2.json()
        click.echo(f"✅ Remote candidate_sources sync: {resp_candidates.get('processed', 0)} processed")

    click.echo("Fetching remote counts...")
    r3 = requests.get(f"{remote_api}/system/sync/counts", headers=headers, timeout=timeout)
    if r3.status_code == 200:
        click.echo(f"✅ Remote counts: {r3.json().get('counts')}")
    else:
        click.echo(f"⚠️  Remote counts unavailable: HTTP {r3.status_code}")

    click.echo("Checking remote crawler status...")
    r4 = requests.get(f"{remote_api}/system/crawler/status", timeout=timeout)
    if r4.status_code == 200:
        click.echo(f"✅ Remote crawler status: {r4.json()}")
    else:
        click.echo(f"⚠️  Remote crawler status unavailable: HTTP {r4.status_code}")

@cli.command(name="remote-status")
@click.option("--remote-api", default=lambda: os.getenv("REMOTE_API_URL", "https://globe-media-pulse.fly.dev/api"), show_default=True)
@click.option("--timeout", default=15, show_default=True, type=int)
def remote_status(remote_api: str, timeout: int):
    remote_api = (remote_api or "").rstrip("/")
    r = requests.get(f"{remote_api}/system/crawler/status", timeout=timeout)
    if r.status_code != 200:
        click.echo(f"❌ Remote status check failed: HTTP {r.status_code}")
        click.echo(r.text)
        sys.exit(1)
    click.echo(f"Remote crawler status: {r.json()}")

@cli.command(name="sync-all")
@click.option("--remote-api", default=lambda: os.getenv("REMOTE_API_URL", "https://globe-media-pulse.fly.dev/api"), show_default=True)
@click.option("--sync-token", default=lambda: os.getenv("SYNC_TOKEN", ""), show_default=False)
@click.option("--run-tests/--no-tests", default=True, show_default=True)
@click.option("--docker/--no-docker", "do_docker", default=True, show_default=True)
@click.option("--github/--no-github", "do_github", default=True, show_default=True)
@click.option("--git-commit/--no-git-commit", default=False, show_default=True)
@click.option("--git-push/--no-git-push", default=False, show_default=True)
@click.option("--fly/--no-fly", "do_fly", default=True, show_default=True)
@click.option("--fly-deploy/--no-fly-deploy", default=True, show_default=True)
@click.option("--sync-data/--no-sync-data", default=True, show_default=True)
@click.option("--branch", default="", show_default=False)
@click.option("--message", default="", show_default=False)
@click.option("--dry-run", is_flag=True, default=False)
def sync_all(
    remote_api: str,
    sync_token: str,
    run_tests: bool,
    do_docker: bool,
    do_github: bool,
    git_commit: bool,
    git_push: bool,
    do_fly: bool,
    fly_deploy: bool,
    sync_data: bool,
    branch: str,
    message: str,
    dry_run: bool,
):
    repo_root = os.getcwd()
    remote_api = (remote_api or "").rstrip("/")

    if run_tests:
        _run([sys.executable, "-m", "pytest", "backend\\tests", "-q"], cwd=repo_root, dry_run=dry_run)
        _run(["npm", "run", "lint", "--prefix", "frontend"], cwd=repo_root, dry_run=dry_run)
        _run(["npm", "run", "typecheck", "--prefix", "frontend"], cwd=repo_root, dry_run=dry_run)
        _run(["npm", "run", "build", "--prefix", "frontend"], cwd=repo_root, dry_run=dry_run)

    if do_docker:
        dc = _docker_compose_cmd()
        _run([*dc, "up", "-d", "--build"], cwd=repo_root, dry_run=dry_run)

    if do_github:
        _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_root, dry_run=dry_run)
        _run(["git", "fetch", "--all", "--prune"], cwd=repo_root, check=False, dry_run=dry_run)
        if git_commit:
            if not message:
                today = datetime.date.today().isoformat()
                message = f"sync: {today}"
            if _git_has_changes(dry_run=dry_run):
                _run(["git", "add", "-A"], cwd=repo_root, dry_run=dry_run)
                _run(["git", "commit", "-m", message], cwd=repo_root, check=False, dry_run=dry_run)
        if git_push:
            if branch:
                _run(["git", "push", "-u", "origin", branch], cwd=repo_root, dry_run=dry_run)
            else:
                _run(["git", "push"], cwd=repo_root, dry_run=dry_run)

    if do_fly:
        if sync_data:
            if not sync_token or not sync_token.strip():
                click.echo("⚠️  SYNC_TOKEN missing; skipping data sync to Fly.")
            else:
                env = os.environ.copy()
                env["SYNC_TOKEN"] = sync_token.strip()
                _run([sys.executable, "manage.py", "sync-to-remote", "--remote-api", remote_api], cwd=repo_root, env=env, dry_run=dry_run)
        if fly_deploy:
            _run(["fly", "deploy"], cwd=repo_root, dry_run=dry_run)
        _run([sys.executable, "manage.py", "remote-status", "--remote-api", remote_api], cwd=repo_root, dry_run=dry_run)

if __name__ == "__main__":
    cli()
