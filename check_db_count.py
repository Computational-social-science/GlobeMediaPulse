
from sqlalchemy import create_engine, text
from backend.core.config import settings

def check_count():
    url = settings.DATABASE_URL
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    
    engine = create_engine(url)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT count(*) FROM media_sources"))
        count = result.scalar()
        print(f"Media Sources Count: {count}")
        
        # Optional: List some names to verify new ones
        result = conn.execute(text("SELECT name FROM media_sources ORDER BY id DESC LIMIT 5"))
        print("Latest 5 Sources:")
        for row in result:
            print(f"- {row[0]}")

if __name__ == "__main__":
    check_count()
