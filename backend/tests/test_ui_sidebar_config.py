import os

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


os.environ.setdefault("AUTO_START_CRAWLER", "0")


def test_sidebar_config_roundtrip_requires_token_for_write(monkeypatch):
    monkeypatch.setenv("SYNC_TOKEN", "t")
    from backend.api.endpoints import router
    from backend.core.database import db_manager
    from backend.core.models import Base

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[db_manager.get_db] = override_get_db
    client = TestClient(app)

    res = client.put("/api/system/ui/sidebar-config", json={"config": {"version": 1}})
    assert res.status_code == 403

    res = client.put(
        "/api/system/ui/sidebar-config",
        json={"config": {"version": 1, "groups": []}},
        headers={"x-sync-token": "t"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body.get("ok") is True
    assert isinstance(body.get("updatedAtMs"), int)

    res = client.get("/api/system/ui/sidebar-config")
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body.get("config"), dict)
    assert isinstance(body.get("updatedAtMs"), int)
