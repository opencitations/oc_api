import os
import sys
import subprocess

# Worker configuration
workers = 5
worker_class = "gevent"
worker_connections = 300
timeout = 1200
graceful_timeout = 180
bind = "0.0.0.0:8080"

# Memory limits
max_requests = 10000
max_requests_jitter = 200

#The number of seconds to wait for requests on a Keep-Alive connection.
keepalive = 20

# Logging
accesslog = None
errorlog = "-"
loglevel = "info"

def on_starting(server):
    """
    Called just before the master process is initialized.
    This runs ONLY ONCE, before any workers are created.
    """
    print("=" * 60)
    print("Gunicorn master process starting...")
    print("=" * 60)
    
    # Check if sync is enabled
    sync_enabled = os.getenv("SYNC_ENABLED", "false").lower() == "true"
    
    if sync_enabled:
        print("Static sync enabled - running sync before starting workers...")
        try:
            subprocess.run([sys.executable, "sync_static.py", "--auto"], check=True)
            print("Static sync completed successfully!")
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Static sync failed: {e}")
        except Exception as e:
            print(f"ERROR: Unexpected error during sync: {e}")
    else:
        print("Static sync disabled")
    
    print("=" * 60)
    print("Master process initialized - spawning workers...")
    print("=" * 60)

def post_worker_init(worker):
    """
    Called just after a worker has been initialized.
    """
    print(f"Worker {worker.pid} initialized and ready")