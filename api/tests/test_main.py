"""
Unit tests for the API with Redis mocked.
Run with: pytest --cov=main --cov-report=xml
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


# Patch redis before importing the app so the module-level connection is mocked
@pytest.fixture(autouse=True)
def mock_redis():
    with patch("main.r") as mock_r:
        # Default: ping succeeds
        mock_r.ping.return_value = True
        yield mock_r


@pytest.fixture()
def client(mock_redis):
    from main import app
    return TestClient(app)


# ── Health endpoint ──────────

def test_health_ok(client, mock_redis):
    """GET /health returns 200 when Redis is reachable."""
    mock_redis.ping.return_value = True
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_redis_down(client, mock_redis):
    """GET /health returns 503 when Redis is unreachable."""
    import redis as redis_lib
    mock_redis.ping.side_effect = redis_lib.exceptions.ConnectionError("down")
    response = client.get("/health")
    assert response.status_code == 503


# ── Create job ──────

def test_create_job_returns_job_id(client, mock_redis):
    """POST /jobs creates a job and returns a UUID job_id."""
    mock_redis.lpush.return_value = 1
    mock_redis.hset.return_value = 1
    response = client.post("/jobs")
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    # Verify it's a valid UUID4
    import uuid
    uuid.UUID(data["job_id"], version=4)  # raises ValueError if invalid


def test_create_job_pushes_to_correct_queue(client, mock_redis):
    """POST /jobs must push to the 'jobs' queue (not 'job')."""
    mock_redis.lpush.return_value = 1
    mock_redis.hset.return_value = 1
    client.post("/jobs")
    call_args = mock_redis.lpush.call_args
    assert call_args[0][0] == "jobs", "Queue name must be 'jobs', not 'job'"


def test_create_job_sets_queued_status(client, mock_redis):
    """POST /jobs must set initial status to 'queued' in Redis."""
    mock_redis.lpush.return_value = 1
    mock_redis.hset.return_value = 1
    client.post("/jobs")
    mock_redis.hset.assert_called_once()
    args = mock_redis.hset.call_args[0]
    assert args[1] == "status"
    assert args[2] == "queued"


# ── Get job ────

def test_get_existing_job(client, mock_redis):
    """GET /jobs/{id} returns status for a known job."""
    mock_redis.hget.return_value = b"queued"
    response = client.get("/jobs/some-uuid")
    assert response.status_code == 200
    assert response.json()["status"] == "queued"


def test_get_missing_job_returns_404(client, mock_redis):
    """GET /jobs/{id} returns 404 for an unknown job."""
    mock_redis.hget.return_value = None
    response = client.get("/jobs/nonexistent")
    assert response.status_code == 404


def test_get_completed_job(client, mock_redis):
    """GET /jobs/{id} returns status 'completed' correctly."""
    mock_redis.hget.return_value = b"completed"
    response = client.get("/jobs/done-uuid")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
