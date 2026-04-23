# hng14-stage2-devops — Job Processing System

A containerised microservices job-processing application consisting of:

| Service | Tech | Purpose |
|---------|------|---------|
| **frontend** | Node.js / Express | Web UI — submit and track jobs |
| **api** | Python / FastAPI | REST API — create jobs, serve status |
| **worker** | Python | Background processor — consumes job queue |
| **redis** | Redis 7 | Shared message queue between API and worker |

---

## Prerequisites

| Tool | Minimum Version | Install |
|------|----------------|---------|
| Docker | 24.x | https://docs.docker.com/engine/install/ |
| Docker Compose | v2.x (plugin) | bundled with Docker Desktop / `apt install docker-compose-plugin` |
| Git | any | `apt install git` |

Verify your installation:
```bash
docker --version          # Docker version 24.x.x
docker compose version    # Docker Compose version v2.x.x
```

---

## Quickstart — Bring the Full Stack Up

### 1. Clone the repository

```bash
git clone https://github.com/<YOUR_USERNAME>/hng14-stage2-devops.git
cd hng14-stage2-devops
```

### 2. Create your `.env` file

```bash
cp .env.example .env
```

Open `.env` and set a strong Redis password:

```dotenv
REDIS_PASSWORD=your_strong_password_here
FRONTEND_PORT=3000
```

> **Never commit `.env` to git.** It is listed in `.gitignore`.

### 3. Build and start the stack

```bash
docker compose up --build -d
```

This will:
1. Build all three service images from their Dockerfiles
2. Start Redis first, wait for its health check to pass
3. Start API, wait for its health check to pass (which also verifies Redis connectivity)
4. Start the Worker (depends on Redis being healthy)
5. Start the Frontend (depends on the API being healthy)

### 4. Verify a successful startup

```bash
docker compose ps
```

Expected output — every service should show **healthy** status:

```
NAME                SERVICE    STATUS          PORTS
stage2-redis-1      redis      Up (healthy)
stage2-api-1        api        Up (healthy)
stage2-worker-1     worker     Up (healthy)
stage2-frontend-1   frontend   Up (healthy)    0.0.0.0:3000->3000/tcp
```

Check health endpoints directly:

```bash
curl http://localhost:3000/health    # {"status":"ok"}
```

### 5. Submit a job via the API

```bash
# Submit a job
curl -s -X POST http://localhost:3000/submit | python3 -m json.tool

# Poll its status (replace with your job_id)
curl -s http://localhost:3000/status/<job_id> | python3 -m json.tool
# status goes from "queued" to "completed" within ~5s
```

### 6. Stop the stack

```bash
docker compose down           # stops and removes containers
docker compose down -v        # also removes the Redis volume
```

---

## Environment Variables

| Variable | Service | Description | Default |
|----------|---------|-------------|---------|
| `REDIS_PASSWORD` | redis, api, worker | Redis auth password | *(required)* |
| `REDIS_HOST` | api, worker | Redis hostname | `redis` |
| `REDIS_PORT` | api, worker | Redis port | `6379` |
| `API_URL` | frontend | Base URL of the API | `http://api:8000` |
| `PORT` | frontend | Listening port | `3000` |
| `FRONTEND_PORT` | host | Host port to bind frontend to | `3000` |

---

## Running Tests Locally

```bash
cd api
pip install -r requirements.txt pytest pytest-cov
pytest --cov=main --cov-report=term-missing
```

---

## CI/CD Pipeline

The GitHub Actions pipeline at `.github/workflows/ci.yml` runs 6 stages in strict order.

```
lint → test → build → security scan → integration test → deploy
```

| Stage | What it does |
|-------|-------------|
| **lint** | flake8 (Python), eslint (JavaScript), hadolint (Dockerfiles) |
| **test** | pytest with mocked Redis; uploads coverage.xml as artifact |
| **build** | Builds all 3 images, tags with git SHA + latest, pushes to local registry |
| **security** | Trivy scans all images; fails pipeline on CRITICAL CVEs; uploads SARIF |
| **integration** | Starts full stack, submits a job, polls until completed, tears down |
| **deploy** | Rolling update on `main` pushes — new container health-checked before old is stopped |

### Secrets required for the deploy stage

Set these in **GitHub repo Settings → Secrets and variables → Actions**:

| Secret | Description |
|--------|-------------|
| `DEPLOY_HOST` | IP or hostname of your production server |
| `DEPLOY_USER` | SSH username on the server |
| `DEPLOY_KEY` | Private SSH key (contents of `~/.ssh/id_rsa`) |
| `REDIS_PASSWORD` | Production Redis password |

---

## Architecture

```
Browser
  │
  ▼
┌─────────────┐   POST /jobs    ┌─────────────┐
│  Frontend   │────────────────▶│     API     │
│  (Node.js)  │   GET  /jobs/:id│  (FastAPI)  │
│   :3000     │◀────────────────│    :8000    │
└─────────────┘                 └──────┬──────┘
                                       │ lpush "jobs"
                                       ▼
                               ┌───────────────┐
                               │     Redis     │
                               │  (queue+hash) │
                               └──────┬────────┘
                                      │ brpop "jobs"
                                      ▼
                               ┌─────────────┐
                               │   Worker    │
                               │  (Python)   │
                               └─────────────┘
```

All services run on an internal Docker network. Redis is **not** exposed on the host machine. All containers run as non-root users.
