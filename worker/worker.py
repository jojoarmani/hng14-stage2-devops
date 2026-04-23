import redis
import time
import os
import signal
import sys

# Fix: Use environment variables for Redis connection (not hardcoded localhost)
redis_host = os.getenv("REDIS_HOST", "redis")
redis_port = int(os.getenv("REDIS_PORT", "6379"))
redis_password = os.getenv("REDIS_PASSWORD", None)

r = redis.Redis(host=redis_host, port=redis_port, password=redis_password)

# Fix: Graceful shutdown on SIGTERM (required for rolling deploys / Docker stop)
shutdown = False

def handle_signal(signum, frame):
    global shutdown
    print("Received shutdown signal, finishing current job then exiting...")
    shutdown = True

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

def process_job(job_id):
    print(f"Processing job {job_id}")
    time.sleep(2)  # simulate work
    r.hset(f"job:{job_id}", "status", "completed")
    print(f"Done: {job_id}")

# Fix: queue name was "job" (singular) — changed to "jobs" to match API
while True:
    try:
        job = r.brpop("jobs", timeout=5)
        if job:
          _, job_id = job
        process_job(job_id.decode())

    except redis.exceptions.ConnectionError as e:
        print(f"Redis connection error: {e}. Retrying in 5s...", flush=True)
        time.sleep(5)

print("Worker exiting cleanly.", flush=True)
sys.exit(0)
