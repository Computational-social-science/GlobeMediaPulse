import sys
import requests
import time
import argparse

def smoke_test(url, retries=5, delay=5):
    endpoint = f"{url.rstrip('/')}/health"
    full_endpoint = f"{url.rstrip('/')}/health/full"
    print(f"Testing connectivity to: {endpoint}")
    print(f"Testing connectivity to: {full_endpoint}")

    for i in range(retries):
        try:
            response = requests.get(endpoint, timeout=5)
            if response.status_code != 200:
                print(f"⚠️ [Attempt {i+1}] Warning: Status code {response.status_code}")
                raise requests.exceptions.RequestException("health endpoint error")
            full_response = requests.get(full_endpoint, timeout=5)
            if full_response.status_code != 200:
                print(f"⚠️ [Attempt {i+1}] Warning: Status code {full_response.status_code}")
                raise requests.exceptions.RequestException("health full endpoint error")
            data = full_response.json()
            status = str(data.get("status") or "").lower()
            if status in ("ok", "healthy", "online", "pass"):
                print(f"✅ [Attempt {i+1}] Success: Service is healthy.")
                return True
            print(f"⚠️ [Attempt {i+1}] Warning: Full health status {status or 'unknown'}")
        except requests.exceptions.RequestException as e:
            print(f"❌ [Attempt {i+1}] Connection failed: {e}")
        except ValueError:
            print(f"❌ [Attempt {i+1}] Invalid JSON from full health.")

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
