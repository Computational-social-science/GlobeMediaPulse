
import requests
import json
import datetime

API_URL = "http://localhost:8002"

def check_health():
    try:
        r = requests.get(f"{API_URL}/docs")
        if r.status_code == 200:
            print("✅ Backend is up and running.")
            return True
        else:
            print(f"❌ Backend returned status code {r.status_code}")
            return False
    except Exception as e:
        print(f"❌ Backend connection failed: {e}")
        return False

def check_2017_data():
    print("\nChecking for 2017 data...")
    try:
        # Fetch errors with a large limit to see what we have
        r = requests.get(f"{API_URL}/api/map-data")
        if r.status_code != 200:
            print(f"❌ Failed to fetch map data: {r.status_code}")
            return

        data = r.json()
        print(f"Fetched map data keys: {list(data.keys())}.")
        
        heatmap = requests.get(f"{API_URL}/api/stats/heatmap")
        if heatmap.status_code == 200:
            heatmap_data = heatmap.json()
            print(f"Fetched {len(heatmap_data)} heatmap entries.")
        else:
            print(f"❌ Failed to fetch heatmap data: {heatmap.status_code}")
            
    except Exception as e:
        print(f"❌ Error checking data: {e}")

if __name__ == "__main__":
    if check_health():
        check_2017_data()
