import os
import sys
import argparse
from datetime import datetime, timedelta

# Add backend directory to path to import storage
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import storage

def cleanup_old_data(days=365):
    """Delete error_events older than 'days'."""
    print(f"[{datetime.now()}] Starting database cleanup (retention: {days} days)...")
    
    # Initialize storage which handles connection pool
    db = storage.DataStorage()
    
    if not db.use_postgres:
        print("Database not configured (NO-DB mode). Skipping cleanup.")
        return

    try:
        with db.get_connection() as conn:
            if not conn:
                print("Failed to get connection from pool.")
                return

            cursor = conn.cursor()
            
            cutoff_date = datetime.now() - timedelta(days=days)
            print(f"Deleting data older than: {cutoff_date}")

            # Cleanup error_events
            cursor.execute("SELECT COUNT(*) FROM error_events WHERE timestamp < %s", (cutoff_date,))
            count_errors = cursor.fetchone()[0]
            
            if count_errors > 0:
                cursor.execute("DELETE FROM error_events WHERE timestamp < %s", (cutoff_date,))
                print(f"Deleted {count_errors} old error_events.")
            else:
                print("No old error_events found.")

            conn.commit()
            print("Cleanup completed successfully.")
            
    except Exception as e:
        print(f"Error during cleanup: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleanup old database records.")
    parser.add_argument("--days", type=int, default=365, help="Delete data older than N days (default: 365)")
    args = parser.parse_args()
    
    cleanup_old_data(args.days)
