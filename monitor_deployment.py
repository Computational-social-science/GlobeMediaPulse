import sys
import time
import requests

def check_health(url, name):
    print(f"Checking {name} at {url}...")
    try:
        # Check backend root (health check) or frontend
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print(f"✅ {name} is ONLINE! ({response.status_code})")
            if "status" in response.json() and response.json().get("status") == "online":
                 print(f"   System: {response.json().get('system')}")
                 print(f"   Data Loaded: {response.json().get('data_loaded')} records")
            return True
        else:
            print(f"⚠️ {name} returned status code {response.status_code}")
    except Exception as e:
        print(f"❌ {name} is unreachable: {e}")
    return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python monitor_deployment.py <BACKEND_URL> <FRONTEND_URL>")
        print("Example: python monitor_deployment.py https://my-api.onrender.com https://my-app.vercel.app")
        sys.exit(1)

    backend_url = sys.argv[1]
    frontend_url = sys.argv[2]

    print("--- Starting Deployment Monitor ---")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            b_status = check_health(backend_url, "Backend")
            print("-" * 30)
            f_status = check_health(frontend_url, "Frontend")
            
            if b_status and f_status:
                print("\n🚀 ALL SYSTEMS GO! Deployment successful.")
                break
            
            print("\nWaiting 30 seconds before next check...")
            time.sleep(30)
    except KeyboardInterrupt:
        print("\nMonitor stopped.")
