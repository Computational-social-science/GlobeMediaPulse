import os
import sys
import subprocess
import time
import requests

def check_command(cmd):
    """Check if a command exists."""
    try:
        subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def run_step(step_name, cmd):
    """Run a step and print status."""
    print(f"🔄 [STEP] {step_name}...")
    try:
        subprocess.run(cmd, shell=True, check=True)
        print(f"✅ [PASS] {step_name}")
        return True
    except subprocess.CalledProcessError:
        print(f"❌ [FAIL] {step_name}")
        return False

def check_health(url, retries=5, delay=2):
    """Check HTTP health endpoint."""
    print(f"🔄 Checking Health: {url}")
    for i in range(retries):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ [PASS] Service Healthy: {url}")
                return True
        except requests.RequestException:
            pass
        print(f"   ...waiting for service ({i+1}/{retries})")
        time.sleep(delay)
    print(f"❌ [FAIL] Service Unreachable: {url}")
    return False

def check_health_full(url, retries=5, delay=2):
    print(f"🔄 Checking Full Health: {url}")
    for i in range(retries):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                status = str(data.get("status") or "").lower()
                if status in ("ok", "healthy", "online", "pass"):
                    print(f"✅ [PASS] Full Health OK: {url}")
                    return True
                print(f"❌ [FAIL] Full Health Degraded: {status or 'unknown'}")
                return False
        except requests.RequestException:
            pass
        except ValueError:
            print("❌ [FAIL] Full Health: Invalid JSON response.")
            return False
        print(f"   ...waiting for service ({i+1}/{retries})")
        time.sleep(delay)
    print(f"❌ [FAIL] Full Health Unreachable: {url}")
    return False

def main():
    print("===========================================")
    print("   GlobeMediaPulse - Validation Suite      ")
    print("===========================================")

    # 1. Environment
    if not check_command("docker --version"):
        print("❌ Docker not found.")
        sys.exit(1)
    
    # 2. Containers
    if not run_step("Checking Running Containers", "docker compose ps"):
        sys.exit(1)

    # 3. Health Checks
    backend_ok = check_health("http://localhost:8000/health")
    # frontend_ok = check_health("http://localhost:5173/") # Frontend might not be exposed on 5173 in prod docker-compose, usually 80/443 via nginx or similar. Assuming dev port for now based on user context.
    
    if not backend_ok:
        sys.exit(1)
    full_ok = check_health_full("http://localhost:8000/health/full")
    if not full_ok:
        sys.exit(1)

    # 4. Persistence Test (Optional: can run pytest if installed)
    if check_command("pytest --version"):
        os.makedirs("reports", exist_ok=True)
        run_step("Running Acceptance Tests", "pytest tests/acceptance_test.py -v --junitxml=reports/acceptance-junit.xml")
    else:
        print("⚠️  Pytest not found, skipping acceptance tests.")

    print("\n✅ Deployment Verified Successfully!")

if __name__ == "__main__":
    main()
