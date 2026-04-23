# FIXES.md — Bug Report & Resolution Log

Every issue found in the starter repository is documented below with file, line, root cause, and the fix applied.

---

## Bug 1 — Secret committed to the repository

**File:** `api/.env`  
**Line:** 1–2  
**Problem:** A real `.env` file containing `REDIS_PASSWORD=supersecretpassword123` was committed directly into the repository. This leaks credentials into git history and violates the task rules ("`.env` must never appear in your repository or git history").  
**Fix:** Deleted `api/.env` from the repository. Added `.env` and `*.env` to `.gitignore`. Created `.env.example` with placeholder values so developers know which variables are required without exposing real secrets.

---

## Bug 2 — Hardcoded `localhost` Redis host in API

**File:** `api/main.py`  
**Line:** 8  
**Problem:** `r = redis.Redis(host="localhost", port=6379)` hard-codes `localhost` as the Redis hostname. Inside Docker containers, each service has its own network namespace; `localhost` inside the `api` container refers to the container itself, not Redis. The API would fail to connect to Redis on every startup.  
**Fix:** Changed to read `REDIS_HOST`, `REDIS_PORT`, and `REDIS_PASSWORD` from environment variables with safe defaults:  
```python
redis_host = os.getenv("REDIS_HOST", "redis")
redis_port = int(os.getenv("REDIS_PORT", "6379"))
redis_password = os.getenv("REDIS_PASSWORD", None)
r = redis.Redis(host=redis_host, port=redis_port, password=redis_password)
```

---

## Bug 3 — Hardcoded `localhost` Redis host in Worker

**File:** `worker/worker.py`  
**Line:** 6  
**Problem:** Same issue as Bug 2. `r = redis.Redis(host="localhost", port=6379)` would fail inside Docker.  
**Fix:** Applied identical environment-variable-driven connection pattern as the API fix.

---

## Bug 4 — Queue name mismatch between API and Worker

**File:** `api/main.py` line 13 and `worker/worker.py` line 16  
**Problem:** The API pushes jobs to the queue named `"job"` (`r.lpush("job", job_id)`), while the worker reads from the queue named `"jobs"` (`r.brpop("jobs", ...)`). Jobs would be enqueued by the API and never consumed by the worker — they would sit in the `"job"` queue forever.  
**Fix:** Standardised both to `"jobs"`:
- `api/main.py`: `r.lpush("jobs", job_id)`
- `worker/worker.py`: `r.brpop("jobs", timeout=5)`

---

## Bug 5 — API returns HTTP 200 with error body for missing jobs (wrong status code)

**File:** `api/main.py`  
**Line:** 20–21  
**Problem:** `return {"error": "not found"}` returns an HTTP 200 response with an error body. HTTP clients (including the frontend poll loop and integration tests) that check the status code will treat this as a success. The correct behavior for a missing resource is HTTP 404.  
**Fix:** Replaced with `raise HTTPException(status_code=404, detail="Job not found")` which returns a proper 404 response.

---

## Bug 6 — API has no health check endpoint

**File:** `api/main.py`  
**Line:** (missing)  
**Problem:** There was no `/health` endpoint in the API. This meant Docker's `HEALTHCHECK` and the `depends_on: condition: service_healthy` directives in `docker-compose.yml` could not work — the compose dependency chain would be broken, causing the frontend to start before the API was ready, resulting in failed requests on startup.  
**Fix:** Added a `GET /health` endpoint that pings Redis and returns `{"status": "ok"}` (HTTP 200) or HTTP 503 if Redis is unavailable.

---

## Bug 7 — Frontend has no health check endpoint

**File:** `frontend/app.js`  
**Line:** (missing)  
**Problem:** Same as Bug 6 for the frontend — no `/health` endpoint, so Docker's `HEALTHCHECK` would fail or require a workaround.  
**Fix:** Added `app.get('/health', ...)` returning `{"status": "ok"}`.

---

## Bug 8 — Hardcoded `localhost` API URL in frontend

**File:** `frontend/app.js`  
**Line:** 6  
**Problem:** `const API_URL = "http://localhost:8000"` hard-codes `localhost`. Inside a Docker container the frontend cannot reach the API via `localhost` (same networking issue as Bugs 2 and 3).  
**Fix:** Changed to `const API_URL = process.env.API_URL || "http://api:8000"` so the URL is configurable via an environment variable, defaulting to the Docker Compose service name.

---

## Bug 9 — Frontend error handler does not propagate upstream HTTP status codes

**File:** `frontend/app.js`  
**Lines:** 18, 26  
**Problem:** Both `/submit` and `/status/:id` catch-blocks always respond with HTTP 500, regardless of what status the API returned. A 404 from the API (e.g., job not found) would be reported to the browser as a generic 500.  
**Fix:** Extract `err.response.status` when available and forward it: `const status = err.response ? err.response.status : 500`.

---

## Bug 10 — Worker has no graceful shutdown handling

**File:** `worker/worker.py`  
**Line:** (missing)  
**Problem:** The worker had no signal handlers for `SIGTERM` or `SIGINT`. When Docker stops a container it sends `SIGTERM` first, then (after a grace period) `SIGKILL`. Without a handler, the worker would be killed immediately mid-job, leaving a job in `queued` state permanently (never reaching `completed`). This also breaks rolling deployments.  
**Fix:** Added `signal.signal(SIGTERM, ...)` and `signal.signal(SIGINT, ...)` handlers that set a `shutdown` flag, allowing the current job to finish before the process exits cleanly.

---

## Bug 11 — Worker has no Redis connection error handling

**File:** `worker/worker.py`  
**Line:** 16  
**Problem:** If Redis is temporarily unreachable (e.g., during a rolling restart) the worker would crash with an unhandled `ConnectionError` instead of retrying.  
**Fix:** Wrapped the `brpop` call in a `try/except redis.exceptions.ConnectionError` block that logs the error and waits 5 seconds before retrying.

---

## Bug 12 — Unpinned dependencies in all `requirements.txt` files

**File:** `api/requirements.txt`, `worker/requirements.txt`  
**Line:** all lines  
**Problem:** All Python dependencies were unpinned (e.g., `fastapi`, `redis` with no version specifiers). Unpinned deps produce non-reproducible builds — different CI runs or deployments may install different versions, breaking the application silently.  
**Fix:** Pinned all dependencies to specific versions (`fastapi==0.111.0`, `uvicorn[standard]==0.29.0`, `redis==5.0.4`, `httpx==0.27.0`).

---

## Bug 13 — No `.gitignore` in the repository

**File:** `.gitignore` (missing)  
**Line:** (missing)  
**Problem:** No `.gitignore` was present. This allowed `.env` files, `__pycache__/`, `node_modules/`, and coverage artefacts to be accidentally committed.  
**Fix:** Added a root `.gitignore` covering `.env`, `*.env`, `__pycache__/`, `*.pyc`, `node_modules/`, `.coverage`, `coverage.xml`, `htmlcov/`, and `*.sarif`