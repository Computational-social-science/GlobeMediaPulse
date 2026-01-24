import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.storage import DataStorage

def check_logs():
    storage = DataStorage()
    with storage.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status, fetcher, COUNT(*) FROM fetch_logs GROUP BY status, fetcher")
        rows = cursor.fetchall()
        print("Fetch Logs Summary:")
        for r in rows:
            print(f"Status: {r[0]}, Fetcher: {r[1]}, Count: {r[2]}")
            
        # Show a few examples
        print("\nExamples:")
        cursor.execute("SELECT * FROM fetch_logs LIMIT 5")
        for r in cursor.fetchall():
            print(r)

if __name__ == "__main__":
    check_logs()