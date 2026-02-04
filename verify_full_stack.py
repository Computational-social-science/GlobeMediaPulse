import requests
import time
import sys
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
API_BASE_URL = os.getenv("API_BASE_URL", "").strip().rstrip("/") or f"{BACKEND_URL}/api"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
TIMEOUT_S = float(os.getenv("VERIFY_TIMEOUT_S", "5") or "5")
PIPELINE_TIMEOUT_S = float(os.getenv("VERIFY_PIPELINE_TIMEOUT_S", "10") or "10")
REQUIRE_CRAWLER = os.getenv("VERIFY_REQUIRE_CRAWLER", "0").strip().lower() in ("1", "true", "yes", "on")
STABILITY_MINUTES = float(os.getenv("VERIFY_CRAWLER_STABILITY_MINUTES", "0") or "0")
STABILITY_INTERVAL_S = float(os.getenv("VERIFY_CRAWLER_STABILITY_INTERVAL_S", "30") or "30")
REQUIRE_READY = os.getenv("VERIFY_CRAWLER_REQUIRE_READY", "1").strip().lower() in ("1", "true", "yes", "on")

def log(msg, status="INFO"):
    print(f"[{status}] {msg}")

def _try_json(response: requests.Response):
    try:
        return response.json()
    except Exception:
        return None

def test_endpoint(url, description, method="GET", expect_json=True, timeout_s=TIMEOUT_S):
    try:
        start = time.time()
        response = requests.request(method, url, timeout=float(timeout_s))
        duration = time.time() - start
        ok = response.status_code == 200
        payload = _try_json(response) if expect_json else None
        if ok:
            log(f"{description}: SUCCESS ({duration:.2f}s)")
            return True, payload
        log(f"{description}: FAILED (Status {response.status_code})", "ERROR")
        body = response.text if response is not None else ""
        if body:
            print(body)
        return False, payload
    except Exception as e:
        log(f"{description}: EXCEPTION ({e})", "ERROR")
        return False, None

def _derive_system_status(health_full):
    status = str((health_full or {}).get("status") or "").lower()
    if status == "ok":
        return "ONLINE"
    if status == "degraded":
        return "DEGRADED"
    return "OFFLINE"

def _is_crawler_ready(health_full, crawler_status):
    services = (health_full or {}).get("services") or {}
    threads = (health_full or {}).get("threads") or {}
    system_status = str((health_full or {}).get("status") or "").lower()
    crawler_service_ok = str(services.get("crawler") or "").lower() == "ok"
    crawler_thread = str(threads.get("crawler") or "").lower()
    crawler_thread_ok = crawler_thread in ("running", "active", "ok")
    crawler_running = bool((crawler_status or {}).get("running"))
    return system_status == "ok" and crawler_service_ok and crawler_thread_ok and crawler_running

def run_crawler_stability_check():
    if STABILITY_MINUTES <= 0:
        return 0
    failures = 0
    end_at = time.time() + (STABILITY_MINUTES * 60.0)
    attempt = 0
    log(f"Crawler Stability Check: {STABILITY_MINUTES:.1f}min @ {STABILITY_INTERVAL_S:.0f}s", "INFO")
    while time.time() < end_at:
        attempt += 1
        ok_health, health_full = test_endpoint(
            f"{BACKEND_URL}/health/full",
            f"Health Sample {attempt}",
            expect_json=True,
            timeout_s=TIMEOUT_S,
        )
        ok_crawler, crawler = test_endpoint(
            f"{API_BASE_URL}/system/crawler/status",
            f"Crawler Sample {attempt}",
            expect_json=True,
            timeout_s=TIMEOUT_S,
        )
        if not ok_health or not ok_crawler:
            failures += 1
        else:
            system_status = _derive_system_status(health_full)
            ready = _is_crawler_ready(health_full, crawler)
            if REQUIRE_READY and not ready:
                failures += 1
                log(f"Crawler READY: FAIL | System={system_status} | Threads={health_full.get('threads')} | Services={health_full.get('services')}", "ERROR")
            else:
                log(f"Crawler READY: PASS | System={system_status}", "INFO")
        time.sleep(STABILITY_INTERVAL_S)
    if failures:
        log(f"Crawler Stability Check: FAILED ({failures} issues)", "ERROR")
    else:
        log("Crawler Stability Check: PASSED", "SUCCESS")
    return failures

def run_verification():
    log("Starting Full Stack Verification...", "INFO")
    failures = 0

    success, _ = test_endpoint(FRONTEND_URL, "Frontend Service", expect_json=False)
    if not success:
        failures += 1

    success, health_full = test_endpoint(f"{BACKEND_URL}/health/full", "Backend Health (Full)", expect_json=True)
    if not success:
        failures += 1
    elif isinstance(health_full, dict):
        status = health_full.get("status")
        if status and str(status).lower() not in ("ok", "healthy", "online", "pass"):
            log(f"Backend Health (Full): DEGRADED ({status})", "WARN")

    success, _ = test_endpoint(f"{API_BASE_URL}/health", "Backend Health (API)", expect_json=True)
    if not success:
        failures += 1

    success, data = test_endpoint(f"{API_BASE_URL}/metadata/countries", "Backend Metadata (Health)")
    if not success:
        log("Backend seems down or misconfigured. Aborting.", "CRITICAL")
        sys.exit(1)
    
    success, stats = test_endpoint(f"{API_BASE_URL}/map-data", "Global Stats")
    if success:
        if isinstance(stats, dict):
            keys = list(stats.keys())
            log(f"Stats received keys: {keys}", "INFO")
        else:
            log("Stats received.", "INFO")

    success, crawler = test_endpoint(f"{API_BASE_URL}/system/crawler/status", "Crawler Status", expect_json=True)
    if success and isinstance(crawler, dict):
        running = bool(crawler.get("running"))
        if REQUIRE_CRAWLER and not running:
            failures += 1
            log(f"Crawler Status: NOT RUNNING ({crawler})", "ERROR")
        else:
            log(f"Crawler Status: {crawler}", "INFO")
    elif not success:
        failures += 1

    success, pipeline = test_endpoint(
        f"{API_BASE_URL}/debug/fetch-news",
        "Pipeline Trigger (Debug)",
        method="POST",
        expect_json=True,
        timeout_s=PIPELINE_TIMEOUT_S,
    )
    if success and isinstance(pipeline, dict):
        if str(pipeline.get("status") or "").strip().lower() == "deprecated":
            log(f"Pipeline Trigger (Debug): DEPRECATED ({pipeline.get('message')})", "WARN")
        else:
            log(f"Pipeline Trigger (Debug): {pipeline}", "INFO")

    success, heatmap = test_endpoint(f"{API_BASE_URL}/stats/heatmap", "Heatmap Data Verification")
    if success:
        if isinstance(heatmap, list):
            log(f"Retrieved {len(heatmap)} heatmap points.", "INFO")
        else:
            log("Heatmap data received.", "INFO")
    else:
        failures += 1

    failures += run_crawler_stability_check()

    if failures:
        log(f"Verification Complete with {failures} failure(s).", "ERROR")
        sys.exit(1)
    log("Verification Complete.", "SUCCESS")

if __name__ == "__main__":
    run_verification()
