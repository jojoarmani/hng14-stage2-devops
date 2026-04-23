from fastapi import FastAPI, HTTPException
import redis
import uuid
import os

app = FastAPI()

# Fix: Use environment variables for Redis host/port/password (not hardcoded localhost)
redis_host = os.getenv("REDIS_HOST", "redis")
redis_port = int(os.getenv("REDIS_PORT", "6379"))
redis_password = os.getenv("REDIS_PASSWORD", None)

redis_port = int(os.getenv("REDIS_PORT", "6379"))
r = redis.Redis(host=redis_host, port=redis_port, password=redis_password)


# No /health endpoint; Health check endpoint for container orchestration
@app.get("/health")
def health():
    """Health check endpoint for Docker HEALTHCHECK and dependency probing."""
    try:
        r.ping()
    except Exception:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"status": "ok"}



@app.post("/jobs")
def create_job():
    job_id = str(uuid.uuid4())
    # Fix: queue name was "job" (singular) in API but worker used brpop on "jobs" —
    # standardise to "jobs"
    r.lpush("jobs", job_id)
    r.hset(f"job:{job_id}", "status", "queued")
    return {"job_id": job_id}

@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    status = r.hget(f"job:{job_id}", "status")
    if not status:
        # Fix: return proper 404 HTTP status, not a 200 with error body
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, "status": status.decode()}

