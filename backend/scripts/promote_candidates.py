import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.operators.storage.postgres_storage import PostgresStorageOperator

def promote_existing_candidates():
    op = PostgresStorageOperator()
    try:
        with op.get_connection() as conn:
            with conn.cursor() as cursor:
                # 1. Get all pending candidates
                cursor.execute("SELECT domain FROM candidate_sources WHERE status = 'pending'")
                candidates = cursor.fetchall()
                print(f"Found {len(candidates)} pending candidates.")
                
                promoted_count = 0
                for (domain,) in candidates:
                    # Check if exists in media_sources
                    cursor.execute("SELECT 1 FROM media_sources WHERE domain = %s", (domain,))
                    if cursor.fetchone():
                        continue
                        
                    # Promote
                    cursor.execute("""
                        INSERT INTO media_sources (domain, name, country_code, country_name, tier, type, created_at)
                        VALUES (%s, %s, 'UNK', 'Unknown', 'Tier-2', 'General', NOW())
                    """, (domain, domain))
                    
                    # Update status
                    cursor.execute("""
                        UPDATE candidate_sources SET status = 'promoted' WHERE domain = %s
                    """, (domain,))
                    
                    promoted_count += 1
                
                conn.commit()
                print(f"Promoted {promoted_count} candidates to Media Sources.")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    promote_existing_candidates()
