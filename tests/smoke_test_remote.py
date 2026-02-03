import sys
import requests
import time
import argparse

def smoke_test(url, retries=5, delay=5):
    """
    Verifies that the backend API is reachable and returns healthy status.
    """
    endpoint = f"{url.rstrip('/')}/health"
    print(f"Testing connectivity to: {endpoint}")

    for i in range(retries):
        try:
            # Simple Health Check (assuming FastAPI /health or / endpoint)
            # Adjust endpoint as per actual API implementation
            response = requests.get(endpoint, timeout=5)
            
            if response.status_code == 200:
                print(f"✅ [Attempt {i+1}] Success: Service is healthy.")
                return True
            else:
                print(f"⚠️ [Attempt {i+1}] Warning: Status code {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ [Attempt {i+1}] Connection failed: {e}")
        
        if i < retries - 1:
            print(f"Retrying in {delay} seconds...")
            time.sleep(delay)

    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remote Smoke Test")
    parser.add_argument("--url", required=True, help="Base URL of the deployed backend")
    args = parser.parse_args()

    if smoke_test(args.url):
        sys.exit(0)
    else:
        print("⛔ Smoke Test Failed after multiple retries.")
        sys.exit(1)
