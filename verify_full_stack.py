import requests
import time
import sys

BASE_URL = "http://localhost:8002/api"
FRONTEND_URL = "http://localhost:5174"

def log(msg, status="INFO"):
    print(f"[{status}] {msg}")

def test_endpoint(url, description):
    try:
        start = time.time()
        response = requests.get(url)
        duration = time.time() - start
        if response.status_code == 200:
            log(f"{description}: SUCCESS ({duration:.2f}s)")
            return True, response.json()
        else:
            log(f"{description}: FAILED (Status {response.status_code})", "ERROR")
            print(response.text)
            return False, None
    except Exception as e:
        log(f"{description}: EXCEPTION ({e})", "ERROR")
        return False, None

def run_verification():
    log("Starting Full Stack Verification...", "INFO")

    # 1. Frontend Check
    try:
        resp = requests.get(FRONTEND_URL)
        if resp.status_code == 200:
            log("Frontend Service: UP", "SUCCESS")
        else:
            log(f"Frontend Service: DOWN (Status {resp.status_code})", "ERROR")
    except Exception as e:
        log(f"Frontend Service: UNREACHABLE ({e})", "ERROR")

    # 2. Backend Health (Metadata)
    success, data = test_endpoint(f"{BASE_URL}/metadata/countries", "Backend Metadata (Health)")
    if not success:
        log("Backend seems down or misconfigured. Aborting.", "CRITICAL")
        sys.exit(1)
    
    # 3. Stats Check
    success, stats = test_endpoint(f"{BASE_URL}/map-data", "Global Stats")
    if success:
        log(f"Stats received: {stats}", "INFO")

    # 4. Pipeline Trigger (Manual Fetch)
    log("Triggering manual news fetch pipeline...", "INFO")
    try:
        resp = requests.post(f"{BASE_URL}/debug/fetch-news")
        if resp.status_code == 200:
            result = resp.json()
            log(f"Pipeline Trigger: SUCCESS - {result}", "SUCCESS")
        else:
            log(f"Pipeline Trigger: FAILED (Status {resp.status_code})", "ERROR")
            print(resp.text)
    except Exception as e:
        log(f"Pipeline Trigger: EXCEPTION ({e})", "ERROR")

    # 5. Verify Heatmap Data
    success, heatmap = test_endpoint(f"{BASE_URL}/stats/heatmap", "Heatmap Data Verification")
    if success:
        log(f"Retrieved {len(heatmap)} heatmap points.", "INFO")

    log("Verification Complete.", "INFO")

if __name__ == "__main__":
    run_verification()
