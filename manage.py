import click
import sys
import os
import logging
import redis
import requests
import subprocess
import shutil
import datetime
import tempfile
import time
from typing import Any
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

def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime.datetime, datetime.date)):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            out[str(k)] = _jsonable(v)
        return out
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return str(value)

def _run(cmd: list[str], cwd: str | None = None, env: dict[str, str] | None = None, check: bool = True, dry_run: bool = False) -> int:
    rendered = " ".join(cmd)
    click.echo(f"$ {rendered}")
    if dry_run:
        return 0
    resolved_cmd = list(cmd)
    if os.name == "nt" and resolved_cmd:
        exe = resolved_cmd[0]
        if not shutil.which(exe):
            for ext in (".cmd", ".exe", ".bat"):
                candidate = shutil.which(f"{exe}{ext}")
                if candidate:
                    resolved_cmd[0] = candidate
                    break
    try:
        p = subprocess.run(resolved_cmd, cwd=cwd, env=env, check=False)
    except FileNotFoundError:
        if os.name != "nt":
            raise
        p = subprocess.run(subprocess.list2cmdline(resolved_cmd), cwd=cwd, env=env, shell=True, check=False)
    if check and p.returncode != 0:
        raise click.ClickException(f"Command failed ({p.returncode}): {rendered}")
    return int(p.returncode)

def _run_capture(cmd: list[str], cwd: str | None = None, env: dict[str, str] | None = None, dry_run: bool = False) -> tuple[int, str, str]:
    rendered = " ".join(cmd)
    click.echo(f"$ {rendered}")
    if dry_run:
        return 0, "", ""
    resolved_cmd = list(cmd)
    if os.name == "nt" and resolved_cmd:
        exe = resolved_cmd[0]
        if not shutil.which(exe):
            for ext in (".cmd", ".exe", ".bat"):
                candidate = shutil.which(f"{exe}{ext}")
                if candidate:
                    resolved_cmd[0] = candidate
                    break
    try:
        p = subprocess.run(resolved_cmd, cwd=cwd, env=env, capture_output=True, text=True, check=False)
        return int(p.returncode), (p.stdout or ""), (p.stderr or "")
    except FileNotFoundError:
        if os.name != "nt":
            raise
        p = subprocess.run(
            subprocess.list2cmdline(resolved_cmd),
            cwd=cwd,
            env=env,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
        return int(p.returncode), (p.stdout or ""), (p.stderr or "")

def _git_has_changes(dry_run: bool = False) -> bool:
    if dry_run:
        return True
    p = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=False)
    if p.returncode != 0:
        raise click.ClickException("git status failed; ensure git is installed and this is a git repo.")
    return bool((p.stdout or "").strip())

def _git_current_branch(cwd: str, dry_run: bool = False) -> str:
    code, out, err = _run_capture(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd, dry_run=dry_run)
    if code != 0:
        raise click.ClickException(f"git rev-parse failed: {err.strip()}")
    branch = (out or "").strip()
    if not branch or branch == "HEAD":
        raise click.ClickException("Cannot determine current git branch.")
    return branch

def _acquire_sync_lock(lock_name: str, stale_after_s: int = 7200) -> tuple[int, str]:
    lock_path = os.path.join(tempfile.gettempdir(), lock_name)
    now = time.time()
    try:
        st = os.stat(lock_path)
        age = now - float(getattr(st, "st_mtime", now))
        if age > float(stale_after_s):
            try:
                os.remove(lock_path)
            except Exception:
                pass
    except FileNotFoundError:
        pass

    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        os.write(fd, str(os.getpid()).encode("utf-8"))
        return fd, lock_path
    except FileExistsError:
        raise click.ClickException(f"Sync lock is held: {lock_path}")

def _release_sync_lock(fd: int, lock_path: str) -> None:
    try:
        os.close(fd)
    except Exception:
        pass
    try:
        os.remove(lock_path)
    except Exception:
        pass

def _git_integrate_remote(repo_root: str, remote: str, branch: str, conflict_strategy: str, dry_run: bool = False) -> None:
    _run(["git", "checkout", branch], cwd=repo_root, dry_run=dry_run)
    _run(["git", "fetch", remote, branch, "--prune"], cwd=repo_root, check=False, dry_run=dry_run)

    code, _, err = _run_capture(["git", "merge", "--ff-only", f"{remote}/{branch}"], cwd=repo_root, dry_run=dry_run)
    if code == 0:
        return

    code, _, err2 = _run_capture(["git", "rebase", f"{remote}/{branch}"], cwd=repo_root, dry_run=dry_run)
    if code == 0:
        return

    _run(["git", "rebase", "--abort"], cwd=repo_root, check=False, dry_run=dry_run)
    if conflict_strategy in ("ours", "theirs"):
        merge_code, _, merge_err = _run_capture(
            ["git", "merge", f"{remote}/{branch}", "-X", conflict_strategy],
            cwd=repo_root,
            dry_run=dry_run,
        )
        if merge_code == 0:
            return
        raise click.ClickException(f"git merge failed: {merge_err.strip()}")

    raise click.ClickException(f"git rebase failed: {err2.strip() or err.strip()}")

def _git_push_with_retries(repo_root: str, remote: str, branch: str, conflict_strategy: str, max_attempts: int, dry_run: bool = False) -> None:
    for attempt in range(1, int(max_attempts) + 1):
        code, out, err = _run_capture(["git", "push", remote, branch], cwd=repo_root, dry_run=dry_run)
        if code == 0:
            return

        msg = (err or out or "").lower()
        if any(s in msg for s in ("non-fast-forward", "fetch first", "rejected", "remote contains work")):
            _git_integrate_remote(repo_root=repo_root, remote=remote, branch=branch, conflict_strategy=conflict_strategy, dry_run=dry_run)
            continue

        if attempt < int(max_attempts):
            backoff_s = min(30.0, float(2 ** (attempt - 1)))
            time.sleep(backoff_s)
            continue

        raise click.ClickException(f"git push failed: {(err or out).strip()}")

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

@cli.command(name="local-verify")
@click.option("--backend-url", default=lambda: os.getenv("BACKEND_URL", "http://localhost:8000"), show_default=True)
@click.option("--frontend-url", default=lambda: os.getenv("FRONTEND_URL", "http://localhost:5173"), show_default=True)
@click.option("--env-check/--no-env-check", default=True, show_default=True)
@click.option("--db-check/--no-db-check", default=True, show_default=True)
@click.option("--verify-crawler/--no-verify-crawler", default=False, show_default=True)
def local_verify(backend_url: str, frontend_url: str, env_check: bool, db_check: bool, verify_crawler: bool):
    repo_root = os.getcwd()
    env = dict(os.environ)
    env["BACKEND_URL"] = (backend_url or "").rstrip("/") or "http://localhost:8000"
    env["FRONTEND_URL"] = (frontend_url or "").rstrip("/") or "http://localhost:5173"
    env["VERIFY_REQUIRE_CRAWLER"] = "1" if verify_crawler else "0"

    click.echo("Running Local Verification...")
    if env_check:
        _run([sys.executable, os.path.join("scripts", "health_check.py")], cwd=repo_root, env=env, check=False)

    if db_check:
        _run([sys.executable, "manage.py", "health-check"], cwd=repo_root, env=env)

    _run([sys.executable, "verify_full_stack.py"], cwd=repo_root, env=env)
    click.echo("✅ Local Verification Passed.")

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

@cli.command(name="ensure-seed-queue")
def ensure_seed_queue():
    report = None
    try:
        from backend.operators.system.guardian import system_guardian

        report = system_guardian.ensure_seed_queue()
    except Exception as e:
        click.echo(f"❌ Seed queue check failed: {e}")
        sys.exit(1)
    click.echo(f"Seed queue: {report}")

@cli.command(name="drill-low-seed")
@click.option("--queue-key", default="", show_default=False)
@click.option("--min-len", default=10, show_default=True, type=int)
@click.option("--target-len", default=50, show_default=True, type=int)
@click.option("--tiers", default="", show_default=False)
@click.option("--scheme", default="", show_default=False)
@click.option("--trim/--no-trim", default=True, show_default=True)
def drill_low_seed(queue_key: str, min_len: int, target_len: int, tiers: str, scheme: str, trim: bool):
    try:
        from backend.operators.system.guardian import system_guardian
    except Exception as e:
        click.echo(f"❌ Seed queue drill unavailable: {e}")
        sys.exit(1)

    queue_key = (queue_key or settings.SEED_QUEUE_KEY or "universal_news:start_urls").strip()
    tiers_value = (tiers or settings.SEED_SOURCE_TIERS or "Tier-0,Tier-1").strip()
    scheme_value = (scheme or settings.SEED_URL_SCHEME or "https").strip() or "https"

    settings.SEED_QUEUE_KEY = queue_key
    settings.SEED_SOURCE_TIERS = tiers_value
    settings.SEED_QUEUE_MIN = int(min_len)
    settings.SEED_QUEUE_TARGET = int(target_len)
    settings.SEED_URL_SCHEME = scheme_value

    redis_url = settings.REDIS_URL
    r = redis.Redis.from_url(redis_url)
    try:
        before_len = int(r.llen(queue_key) or 0)
    except Exception as e:
        click.echo(f"❌ Redis unavailable: {e}")
        sys.exit(1)

    if trim:
        keep = max(int(min_len) - 1, 0)
        if keep == 0:
            r.delete(queue_key)
        else:
            r.ltrim(queue_key, 0, keep - 1)

    after_trim = int(r.llen(queue_key) or 0)
    report = system_guardian.ensure_seed_queue()
    final_len = int(r.llen(queue_key) or 0)
    click.echo(f"Low-seed drill: before={before_len} after_trim={after_trim} after_fill={final_len} report={report}")

@cli.command(name="drill-remote-disconnect")
@click.option("--remote-api", default="http://127.0.0.1:9", show_default=True)
@click.option("--queue-key", default="", show_default=False)
@click.option("--min-len", default=10, show_default=True, type=int)
@click.option("--target-len", default=50, show_default=True, type=int)
@click.option("--tiers", default="", show_default=False)
@click.option("--scheme", default="", show_default=False)
@click.option("--trim/--no-trim", default=True, show_default=True)
@click.option("--force-remote/--no-force-remote", default=True, show_default=True)
@click.option("--timeout", default=2, show_default=True, type=int)
def drill_remote_disconnect(
    remote_api: str,
    queue_key: str,
    min_len: int,
    target_len: int,
    tiers: str,
    scheme: str,
    trim: bool,
    force_remote: bool,
    timeout: int,
):
    try:
        from backend.operators.system.guardian import system_guardian
    except Exception as e:
        click.echo(f"❌ Remote disconnect drill unavailable: {e}")
        sys.exit(1)

    queue_key = (queue_key or settings.SEED_QUEUE_KEY or "universal_news:start_urls").strip()
    tiers_value = (tiers or settings.SEED_SOURCE_TIERS or "Tier-0,Tier-1").strip()
    scheme_value = (scheme or settings.SEED_URL_SCHEME or "https").strip() or "https"

    original_remote = settings.SOT_REMOTE_API_URL
    original_tiers = settings.SEED_SOURCE_TIERS

    settings.SOT_REMOTE_API_URL = (remote_api or "").rstrip("/")
    settings.SEED_QUEUE_KEY = queue_key
    settings.SEED_QUEUE_MIN = int(min_len)
    settings.SEED_QUEUE_TARGET = int(target_len)
    settings.SEED_URL_SCHEME = scheme_value
    settings.SEED_SOURCE_TIERS = "Tier-9" if force_remote else tiers_value

    redis_url = settings.REDIS_URL
    r = redis.Redis.from_url(redis_url)
    try:
        before_len = int(r.llen(queue_key) or 0)
    except Exception as e:
        settings.SOT_REMOTE_API_URL = original_remote
        settings.SEED_SOURCE_TIERS = original_tiers
        click.echo(f"❌ Redis unavailable: {e}")
        sys.exit(1)

    try:
        requests.get(f"{settings.SOT_REMOTE_API_URL}/system/export/media-sources", timeout=timeout)
    except Exception:
        pass

    if trim:
        keep = max(int(min_len) - 1, 0)
        if keep == 0:
            r.delete(queue_key)
        else:
            r.ltrim(queue_key, 0, keep - 1)

    after_trim = int(r.llen(queue_key) or 0)
    report = None
    final_len = after_trim
    try:
        report = system_guardian.ensure_seed_queue()
        final_len = int(r.llen(queue_key) or 0)
    finally:
        settings.SOT_REMOTE_API_URL = original_remote
        settings.SEED_SOURCE_TIERS = original_tiers

    click.echo(
        "Remote disconnect drill: "
        f"remote={remote_api} before={before_len} after_trim={after_trim} after_fill={final_len} report={report}"
    )

@cli.command(name="net-growth")
@click.option("--days", default=14, show_default=True, type=int)
@click.option("--day", default="", show_default=False)
def net_growth(days: int, day: str):
    day_s = (day or "").strip() or None
    recorded = storage_operator.record_daily_growth_metrics(day=day_s)
    if recorded.get("status") != "ok":
        click.echo(f"❌ Failed to record growth metrics: {recorded}")
        sys.exit(1)

    recent = storage_operator.get_recent_growth_metrics(days=int(days))
    click.echo(f"Today: {recorded}")
    if not recent:
        return

    last3 = recent[:3]
    avg_media_net = sum(int(r.get("media_sources_net") or 0) for r in last3) / float(len(last3))
    avg_cand_growth = sum(float(r.get("candidate_sources_growth_rate") or 0.0) for r in last3) / float(len(last3))
    avg_art_net = sum(int(r.get("news_articles_net") or 0) for r in last3) / float(len(last3))

    current_promo = int(os.getenv("CANDIDATE_PROMOTION_THRESHOLD", "5") or "5")
    current_simhash = int(os.getenv("SIMHASH_SIMILARITY_THRESHOLD", "3") or "3")

    plateau = avg_media_net <= 0.0
    suggestions: dict[str, Any] = {
        "plateau": plateau,
        "avg_media_sources_net_3d": avg_media_net,
        "avg_candidate_sources_growth_rate_3d": avg_cand_growth,
        "avg_news_articles_net_3d": avg_art_net,
        "recommend": {},
    }

    if plateau and avg_cand_growth >= 0.02:
        suggestions["recommend"]["CANDIDATE_PROMOTION_THRESHOLD"] = max(2, current_promo - 1)

    if plateau and avg_art_net <= 0.0:
        suggestions["recommend"]["SIMHASH_SIMILARITY_THRESHOLD"] = max(1, current_simhash - 1)

    click.echo(f"Suggested tuning: {suggestions}")

@cli.command(name="sync-to-remote")
@click.option("--remote-api", default=lambda: os.getenv("REMOTE_API_URL", ""), show_default=False)
@click.option("--token", default=lambda: os.getenv("SYNC_TOKEN", ""), show_default=False)
@click.option("--include-candidates/--no-candidates", default=True, show_default=True)
@click.option("--candidates-limit", default=5000, show_default=True, type=int)
@click.option("--batch-size", default=2000, show_default=True, type=int)
@click.option("--timeout", default=30, show_default=True, type=int)
@click.option("--force", is_flag=True, default=False)
def sync_to_remote(remote_api: str, token: str, include_candidates: bool, candidates_limit: int, batch_size: int, timeout: int, force: bool):
    if (settings.SOT_ROLE or "").strip().lower() != "source" and not force:
        click.echo("❌ Remote write blocked (remote is the SoT). Use --force to override.")
        sys.exit(1)
    if not token or not token.strip():
        click.echo("❌ Missing SYNC_TOKEN (set env var or pass --token).")
        sys.exit(1)
    remote_api = (remote_api or "").rstrip("/")
    if not remote_api:
        click.echo("❌ Missing remote API base URL (set REMOTE_API_URL or pass --remote-api).")
        sys.exit(1)
    headers = {"X-Sync-Token": token.strip()}

    click.echo(f"Exporting local media_sources...")
    media_sources = storage_operator.get_all_media_sources()
    click.echo(f"Local media_sources: {len(media_sources)}")

    click.echo("Pushing media_sources to remote...")
    total = len(media_sources)
    size = int(batch_size) if isinstance(batch_size, int) and batch_size > 0 else 2000
    processed_total = 0
    for start in range(0, total, size):
        batch = media_sources[start : start + size]
        batch_payload = [_jsonable(item) for item in batch]
        r = requests.post(
            f"{remote_api}/system/sync/media-sources",
            json=batch_payload,
            headers=headers,
            timeout=timeout,
        )
        if r.status_code != 200:
            click.echo(f"❌ Remote sync failed (media_sources): HTTP {r.status_code}")
            click.echo(r.text)
            sys.exit(1)
        resp_media = r.json()
        err = resp_media.get("error")
        if err:
            click.echo(f"❌ Remote sync error (media_sources): {err}")
            sys.exit(1)
        processed_total += int(resp_media.get("processed", 0) or 0)
        click.echo(f"  media_sources batch: {min(start + size, total)}/{total}")
    click.echo(f"✅ Remote media_sources sync: {processed_total} processed")

    if include_candidates:
        click.echo("Exporting local candidate_sources...")
        candidates = storage_operator.get_all_candidate_sources(limit=candidates_limit)
        click.echo(f"Local candidate_sources: {len(candidates)}")

        click.echo("Pushing candidate_sources to remote...")
        total2 = len(candidates)
        processed_total2 = 0
        for start in range(0, total2, size):
            batch = candidates[start : start + size]
            batch_payload = [_jsonable(item) for item in batch]
            r2 = requests.post(
                f"{remote_api}/system/sync/candidate-sources",
                json=batch_payload,
                headers=headers,
                timeout=timeout,
            )
            if r2.status_code != 200:
                click.echo(f"❌ Remote sync failed (candidate_sources): HTTP {r2.status_code}")
                click.echo(r2.text)
                sys.exit(1)
            resp_candidates = r2.json()
            err2 = resp_candidates.get("error")
            if err2:
                click.echo(f"❌ Remote sync error (candidate_sources): {err2}")
                sys.exit(1)
            processed_total2 += int(resp_candidates.get("processed", 0) or 0)
            click.echo(f"  candidate_sources batch: {min(start + size, total2)}/{total2}")
        click.echo(f"✅ Remote candidate_sources sync: {processed_total2} processed")

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

@cli.command(name="sync-from-remote")
@click.option("--remote-api", default=lambda: os.getenv("REMOTE_API_URL", settings.SOT_REMOTE_API_URL), show_default=True)
@click.option("--token", default=lambda: os.getenv("SYNC_TOKEN", ""), show_default=False)
@click.option("--tiers", default="Tier-0,Tier-1", show_default=True)
@click.option("--limit", default=0, show_default=True, type=int)
@click.option("--include-candidates/--no-candidates", default=False, show_default=True)
@click.option("--candidates-limit", default=5000, show_default=True, type=int)
@click.option("--timeout", default=30, show_default=True, type=int)
def sync_from_remote(
    remote_api: str,
    token: str,
    tiers: str,
    limit: int,
    include_candidates: bool,
    candidates_limit: int,
    timeout: int,
):
    if not token or not token.strip():
        click.echo("❌ Missing SYNC_TOKEN (set env var or pass --token).")
        sys.exit(1)
    remote_api = (remote_api or "").rstrip("/")
    headers = {"X-Sync-Token": token.strip()}

    r = requests.get(
        f"{remote_api}/system/export/media-sources",
        params={"tiers": tiers or "", "limit": int(limit)},
        headers=headers,
        timeout=timeout,
    )
    if r.status_code != 200:
        click.echo(f"❌ Remote export failed (media_sources): HTTP {r.status_code}")
        click.echo(r.text)
        sys.exit(1)
    media_sources = r.json()
    if not isinstance(media_sources, list):
        click.echo("❌ Remote export invalid (media_sources).")
        sys.exit(1)
    upserted = storage_operator.bulk_upsert_media_sources(media_sources)
    click.echo(f"✅ Local media_sources updated: {upserted}")

    if include_candidates:
        r2 = requests.get(
            f"{remote_api}/system/export/candidate-sources",
            params={"limit": int(candidates_limit)},
            headers=headers,
            timeout=timeout,
        )
        if r2.status_code != 200:
            click.echo(f"❌ Remote export failed (candidate_sources): HTTP {r2.status_code}")
            click.echo(r2.text)
            sys.exit(1)
        candidates = r2.json()
        if not isinstance(candidates, list):
            click.echo("❌ Remote export invalid (candidate_sources).")
            sys.exit(1)
        upserted2 = storage_operator.bulk_upsert_candidate_sources(candidates)
        click.echo(f"✅ Local candidate_sources updated: {upserted2}")

@cli.command(name="remote-status")
@click.option("--remote-api", default=lambda: os.getenv("REMOTE_API_URL", ""), show_default=False)
@click.option("--timeout", default=15, show_default=True, type=int)
def remote_status(remote_api: str, timeout: int):
    remote_api = (remote_api or "").rstrip("/")
    if not remote_api:
        click.echo("❌ Missing remote API base URL (set REMOTE_API_URL or pass --remote-api).")
        sys.exit(1)
    r = requests.get(f"{remote_api}/system/crawler/status", timeout=timeout)
    if r.status_code != 200:
        click.echo(f"❌ Remote status check failed: HTTP {r.status_code}")
        click.echo(r.text)
        sys.exit(1)
    click.echo(f"Remote crawler status: {r.json()}")

@cli.command(name="sync-all")
@click.option("--remote-api", default=lambda: os.getenv("REMOTE_API_URL", ""), show_default=False)
@click.option("--sync-token", default=lambda: os.getenv("SYNC_TOKEN", ""), show_default=False)
@click.option("--run-tests/--no-tests", default=True, show_default=True)
@click.option("--docker/--no-docker", "do_docker", default=True, show_default=True)
@click.option("--github/--no-github", "do_github", default=True, show_default=True)
@click.option("--git-commit/--no-git-commit", default=False, show_default=True)
@click.option("--git-push/--no-git-push", default=False, show_default=True)
@click.option("--sync-data/--no-sync-data", default=False, show_default=True)
@click.option("--branch", default="", show_default=False)
@click.option("--conflict-strategy", type=click.Choice(["ours", "theirs", "manual"]), default="ours", show_default=True)
@click.option("--push-retries", default=3, show_default=True, type=int)
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
    sync_data: bool,
    branch: str,
    conflict_strategy: str,
    push_retries: int,
    message: str,
    dry_run: bool,
):
    repo_root = os.getcwd()
    remote_api = (remote_api or "").rstrip("/")

    if do_github:
        lock_fd = None
        lock_path = ""
        try:
            lock_fd, lock_path = _acquire_sync_lock("globemediapulse_sync.lock")
        except Exception:
            raise

        try:
            _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_root, dry_run=dry_run)
            _run(["git", "fetch", "--all", "--prune"], cwd=repo_root, check=False, dry_run=dry_run)
            active_branch = (branch or _git_current_branch(repo_root, dry_run=dry_run)).strip()
            _git_integrate_remote(
                repo_root=repo_root,
                remote="origin",
                branch=active_branch,
                conflict_strategy=conflict_strategy,
                dry_run=dry_run,
            )
            if git_commit:
                if not message:
                    today = datetime.date.today().isoformat()
                    message = f"sync: {today}"
                if _git_has_changes(dry_run=dry_run):
                    _run(["git", "add", "-A"], cwd=repo_root, dry_run=dry_run)
                    _run(["git", "commit", "-m", message], cwd=repo_root, check=False, dry_run=dry_run)
            if git_push:
                _git_push_with_retries(
                    repo_root=repo_root,
                    remote="origin",
                    branch=active_branch,
                    conflict_strategy=conflict_strategy,
                    max_attempts=push_retries,
                    dry_run=dry_run,
                )
        finally:
            if lock_fd is not None and lock_path:
                _release_sync_lock(lock_fd, lock_path)

    if run_tests:
        _run([sys.executable, "-m", "pytest", "backend\\tests", "-q"], cwd=repo_root, dry_run=dry_run)
        _run(["npm", "run", "lint", "--prefix", "frontend"], cwd=repo_root, dry_run=dry_run)
        _run(["npm", "run", "typecheck", "--prefix", "frontend"], cwd=repo_root, dry_run=dry_run)
        _run([sys.executable, "scripts\\build_frontend_data.py"], cwd=repo_root, dry_run=dry_run)
        _run(["npm", "run", "build", "--prefix", "frontend"], cwd=repo_root, dry_run=dry_run)

    if do_docker:
        dc = _docker_compose_cmd()
        _run([*dc, "up", "-d", "--build"], cwd=repo_root, dry_run=dry_run)

    if sync_data:
        if not remote_api:
            raise click.ClickException("Missing remote API base URL (set REMOTE_API_URL or pass --remote-api).")
        if not sync_token:
            raise click.ClickException("Missing SYNC_TOKEN (set env var or pass --sync-token).")
        if (settings.SOT_ROLE or "").strip().lower() == "source":
            sync_to_remote(
                remote_api=remote_api,
                token=sync_token,
                include_candidates=True,
                candidates_limit=5000,
                batch_size=2000,
                timeout=30,
                force=False,
            )
        else:
            sync_from_remote(
                remote_api=remote_api,
                token=sync_token,
                tiers="Tier-0,Tier-1",
                limit=0,
                include_candidates=False,
                candidates_limit=5000,
                timeout=30,
            )

if __name__ == "__main__":
    cli()
