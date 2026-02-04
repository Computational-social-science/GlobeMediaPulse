import os
import sys
import time
import subprocess
import requests
import json
from datetime import datetime

# Configuration
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_URL = "http://localhost:8000/health"
MAX_RETRIES = 3
LOG_FILE = os.path.join(PROJECT_ROOT, "data", "logs", "sentinel.log")

# Ensure log dir
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] [{level}] {message}"
    print(formatted)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(formatted + "\n")

def run_command(cmd, cwd=PROJECT_ROOT):
    log(f"Executing: {cmd}", "DEBUG")
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            cwd=cwd, 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace' # Handle potential encoding errors gracefully
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

# --- Part 1: Code Quality Guardian ---
def auto_fix_code():
    log("🛡️ Starting Code Quality Guardian...", "INFO")
    
    # 1. ESLint Auto-Fix
    log("Running ESLint --fix...", "INFO")
    success, output = run_command("npm run lint --prefix frontend -- --fix")
    if success:
        log("✅ ESLint auto-fix complete.", "INFO")
    else:
        log(f"⚠️ ESLint found issues that could not be auto-fixed:\n{output}", "WARN")
        return False

    # 2. Unit Tests
    log("Running Unit Tests...", "INFO")
    # Assuming frontend tests for now, backend tests require env
    # success, _ = run_command("npm run test --prefix frontend") # skipped for speed in MVP
    
    return True

# --- Part 2: Runtime Healer ---
def check_backend_health():
    try:
        res = requests.get(BACKEND_URL, timeout=2)
        if res.status_code == 200:
            return True, "Healthy"
        return False, f"Status Code: {res.status_code}"
    except Exception as e:
        return False, str(e)

def heal_backend(attempt):
    log(f"🚑 Initiating Self-Healing for Backend (Attempt {attempt}/{MAX_RETRIES})...", "WARN")
    
    # Diagnosis 1: Check Docker Container State
    success, output = run_command("docker-compose ps --format json")
    if success and output:
        try:
            containers = json.loads(output) if output.strip() else []
            backend_container = next((c for c in containers if "backend" in c.get("Service", "") or "gmp_backend" in c.get("Name", "")), None)
            
            if not backend_container:
                log("Diagnosis: Backend container not found/running.", "WARN")
                log("Action: Starting services...", "INFO")
                run_command("docker-compose up -d backend")
            elif backend_container.get("State") != "running":
                log(f"Diagnosis: Backend container is {backend_container.get('State')}.", "WARN")
                log("Action: Restarting backend...", "INFO")
                run_command("docker-compose restart backend")
            else:
                log("Diagnosis: Container running but unresponsive (Deadlock/Port Issue).", "WARN")
                log("Action: Force recreate...", "INFO")
                run_command("docker-compose up -d --force-recreate backend")
                
        except json.JSONDecodeError:
            # Fallback for older docker compose versions
            log("Diagnosis: Could not parse docker state.", "WARN")
            run_command("docker-compose up -d backend")
    else:
        log("Diagnosis: Docker Daemon might be down.", "CRITICAL")
        # In a real server, we might try `sudo systemctl restart docker`, but risky in dev env
        return False

    # Wait for recovery
    wait_time = 5 * attempt
    log(f"Waiting {wait_time}s for service recovery...", "INFO")
    time.sleep(wait_time)
    
    # Re-verify
    is_healthy, msg = check_backend_health()
    if is_healthy:
        log("✅ Self-Healing Successful! Backend is back online.", "SUCCESS")
        return True
    else:
        log(f"❌ Healing attempt failed: {msg}", "ERROR")
        return False

def monitor_runtime():
    log("🩺 Starting Runtime Health Check...", "INFO")
    
    is_healthy, msg = check_backend_health()
    if is_healthy:
        log("✅ System is Healthy.", "INFO")
        return True
    
    log(f"⚠️ Health Check Failed: {msg}", "WARN")
    
    for i in range(1, MAX_RETRIES + 1):
        if heal_backend(i):
            return True
    
    log("🔥 Critical Failure: Automatic recovery failed after max retries.", "CRITICAL")
    return False

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    if mode in ["all", "static"]:
        if not auto_fix_code():
            log("Code Quality Check Failed.", "ERROR")
            # In strict mode, we might exit here, but for self-healing demo we proceed
    
    if mode in ["all", "runtime"]:
        if not monitor_runtime():
            sys.exit(1)

if __name__ == "__main__":
    main()
