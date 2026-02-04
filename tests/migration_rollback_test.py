import os
import subprocess
from urllib.parse import urlparse

import pytest
from sqlalchemy import create_engine, text


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


def _get_db_url() -> str:
    raw = (os.getenv("DATABASE_URL") or "").strip()
    if raw:
        return raw.replace("postgres://", "postgresql://", 1) if raw.startswith("postgres://") else raw
    return "postgresql://postgres:password@localhost:5433/globemediapulse"


def test_alembic_upgrade_and_downgrade_roundtrip():
    db_url = _get_db_url()
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("SELECT 1"))

    from backend.core.models import Base

    Base.metadata.create_all(bind=engine)

    env = dict(os.environ)
    env["DATABASE_URL"] = db_url
    cmd = [os.sys.executable, "-m", "alembic", "-c", os.path.join("backend", "alembic.ini")]

    subprocess.run(cmd + ["upgrade", "head"], check=True, env=env)

    with engine.begin() as conn:
        present = conn.execute(text("SELECT to_regclass('__migration_smoke__')")).scalar()
        assert present is not None

    subprocess.run(cmd + ["downgrade", "base"], check=True, env=env)

    with engine.begin() as conn:
        present = conn.execute(text("SELECT to_regclass('__migration_smoke__')")).scalar()
        assert present is None

    subprocess.run(cmd + ["upgrade", "head"], check=True, env=env)
