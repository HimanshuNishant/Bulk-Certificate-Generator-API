import os
import tempfile
from pathlib import Path

# Use an isolated database for tests.
tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
tmp.close()
os.environ["TEST_DB"] = tmp.name

from fastapi.testclient import TestClient
from app.main import app
from app import database
from app.database import Base
import app.main as main_module

# Recreate engine/session against the temporary DB for this test process.
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

test_engine = create_engine(f"sqlite:///{tmp.name}", connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=test_engine)

def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[database.get_db] = override_get_db
main_module.SessionLocal = TestSession
client = TestClient(app)


def test_create_generation_job():
    response = client.post("/api/jobs", json={
        "course_name": "Python Fundamentals",
        "recipients": [{"name": "Alice", "email": "alice@example.com"}],
    })
    assert response.status_code == 202
    data = response.json()
    assert data["total"] == 1
    assert "job_id" in data


def test_invalid_request():
    response = client.post("/api/jobs", json={"course_name": "", "recipients": []})
    assert response.status_code == 400


def test_certificate_generation_and_failure_isolation():
    response = client.post("/api/jobs", json={
        "course_name": "Backend Engineering",
        "recipients": [
            {"name": "Valid User", "email": "valid@example.com"},
            {"name": "Invalid User", "email": "not-an-email"},
        ],
    })
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    # BackgroundTasks execute before TestClient returns the response.
    status = client.get(f"/api/jobs/{job_id}")
    assert status.status_code == 200
    data = status.json()
    assert data["successful"] == 1
    assert data["failed"] == 1
    assert data["pending"] == 0
    assert any(c["status"] == "FAILED" for c in data["certificates"])
    success = next(c for c in data["certificates"] if c["status"] == "SUCCESS")
    download = client.get(success["download_url"])
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/pdf")
