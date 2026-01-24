
import requests
import json
import datetime

API_URL = "http://localhost:8000"

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
        r = requests.get(f"{API_URL}/api/errors?limit=500")
        if r.status_code != 200:
            print(f"❌ Failed to fetch errors: {r.status_code}")
            return

        data = r.json()
        print(f"Fetched {len(data)} error events.")
        
        if not data:
            print("⚠️ No data returned from API.")
            return

        # Check timestamps
        years = {}
        count_2017 = 0
        
        for item in data:
            ts = item.get('timestamp')
            if ts:
                # Handle timestamp format (could be ms integer or string)
                if isinstance(ts, int) or (isinstance(ts, str) and ts.isdigit()):
                    dt = datetime.datetime.fromtimestamp(int(ts)/1000)
                else:
                    try:
                        dt = datetime.datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
                    except:
                        continue
                
                year = dt.year
                years[year] = years.get(year, 0) + 1
                if year == 2017:
                    count_2017 += 1

        print("Data distribution by year:", years)
        
        if count_2017 > 0:
            print(f"✅ Found {count_2017} events from 2017.")
        else:
            print("❌ NO events from 2017 found in the recent list.")
            
    except Exception as e:
        print(f"❌ Error checking data: {e}")

if __name__ == "__main__":
    if check_health():
        check_2017_data()
