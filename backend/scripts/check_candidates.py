import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.operators.storage.postgres_storage import PostgresStorageOperator

def check_candidates():
    op = PostgresStorageOperator()
    try:
        with op.get_connection() as conn:
            with conn.cursor() as cursor:
                # Check if table exists first
                cursor.execute("SELECT to_regclass('candidate_sources')")
                if not cursor.fetchone()[0]:
                    print("Table 'candidate_sources' does not exist!")
                    return

                # Check columns
                cursor.execute("SELECT * FROM candidate_sources LIMIT 0")
                columns = [desc[0] for desc in cursor.description]
                print(f"Columns: {columns}")

                cursor.execute("SELECT COUNT(*) FROM candidate_sources")
                count = cursor.fetchone()[0]
                print(f"Candidate Sources Count: {count}")
                
                if count > 0:
                    cursor.execute("SELECT domain, citation_count FROM candidate_sources ORDER BY citation_count DESC LIMIT 5")
                    rows = cursor.fetchall()
                    print("Top 5 Candidates:")
                    for row in rows:
                        print(row)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_candidates()
