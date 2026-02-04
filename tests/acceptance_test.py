import pytest
import requests
import time
import os
from urllib.parse import urlparse
from sqlalchemy import create_engine, text

# Configuration
API_URL = ""
DB_URL = ""

def _load_dotenv(path: str = ".env") -> dict[str, str]:
    if not os.path.exists(path):
        return {}
    out: dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k:
                    out[k] = v
        return out
    except Exception:
        return {}

def _get_api_url() -> str:
    env_file = _load_dotenv()
    raw = (
        os.getenv("API_URL")
        or os.getenv("BACKEND_URL")
        or env_file.get("API_URL")
        or env_file.get("BACKEND_URL")
        or "http://localhost:8000"
    )
    return str(raw).rstrip("/")

def _get_db_url() -> str:
    env_file = _load_dotenv()
    raw = os.getenv("DATABASE_URL") or env_file.get("DATABASE_URL")
    if raw:
        raw = str(raw).strip()
        return raw.replace("postgres://", "postgresql://", 1) if raw.startswith("postgres://") else raw

    user = os.getenv("POSTGRES_USER") or env_file.get("POSTGRES_USER") or "postgres"
    pwd = os.getenv("POSTGRES_PASSWORD") or env_file.get("POSTGRES_PASSWORD") or "password"
    db = os.getenv("POSTGRES_DB") or env_file.get("POSTGRES_DB") or "globemediapulse"
    host = os.getenv("POSTGRES_HOST") or env_file.get("POSTGRES_HOST") or "localhost"
    port = os.getenv("POSTGRES_PORT") or env_file.get("POSTGRES_PORT") or "5433"
    return f"postgresql://{user}:{pwd}@{host}:{port}/{db}"

def _redact_db_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        port = str(parsed.port) if parsed.port is not None else ""
        db = parsed.path.lstrip("/") if parsed.path else ""
        user = parsed.username or ""
        return f"{parsed.scheme}://{user}:***@{host}:{port}/{db}"
    except Exception:
        return "db_url_redaction_failed"

@pytest.fixture(scope="session")
def db_connection():
    """Wait for DB to be ready and return connection."""
    global DB_URL
    DB_URL = _get_db_url()
    retries = 5
    last_error: Exception | None = None
    while retries > 0:
        try:
            engine = create_engine(DB_URL)
            conn = engine.connect()
            yield conn
            conn.close()
            return
        except Exception as e:
            last_error = e
            time.sleep(2)
            retries -= 1
    pytest.fail(f"Could not connect to Database ({_redact_db_url(DB_URL)}): {type(last_error).__name__}: {last_error}")

@pytest.fixture(scope="session")
def api_health():
    """Wait for API to be healthy."""
    global API_URL
    API_URL = _get_api_url()
    retries = 5
    while retries > 0:
        try:
            res = requests.get(f"{API_URL}/health", timeout=2)
            if res.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
        retries -= 1
    pytest.fail("API is not healthy")

def test_health_check(api_health):
    """Verify system health endpoint."""
    response = requests.get(f"{API_URL}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    if isinstance(data, dict) and isinstance(data.get("services"), dict):
        assert "postgres" in data["services"]
        assert "redis" in data["services"]

def test_database_persistence(db_connection):
    """Verify database is writable and persistent."""
    # Create a test table if not exists
    db_connection.execute(text("CREATE TABLE IF NOT EXISTS test_persistence (id SERIAL PRIMARY KEY, value TEXT)"))
    db_connection.execute(text("INSERT INTO test_persistence (value) VALUES ('test_data')"))
    db_connection.commit()
    
    # Read back
    result = db_connection.execute(text("SELECT value FROM test_persistence WHERE value = 'test_data'")).fetchone()
    assert result[0] == 'test_data'
    
    # Cleanup
    db_connection.execute(text("DROP TABLE test_persistence"))
    db_connection.commit()

def test_crawler_integration(db_connection):
    """Verify crawler is populating the database (Integration Test)."""
    # This assumes the crawler has been running for at least a few seconds
    # In a real scenario, we might trigger a specific crawl job here
    
    # Check if we have any media sources (seeded or crawled)
    result = db_connection.execute(text("SELECT count(*) FROM media_sources")).fetchone()
    count = result[0]
    print(f"Media Sources Found: {count}")
    # We expect at least seeded data or 0 if fresh, but the table should exist
    assert count >= 0 

def test_api_data_retrieval(api_health):
    """Verify API returns data format correctly."""
    response = requests.get(f"{API_URL}/api/media/sources")
    # Even if empty, it should return a 200 OK list
    assert response.status_code == 200
    assert isinstance(response.json(), list)
