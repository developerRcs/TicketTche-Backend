"""
Gunicorn configuration for production (optimized for AWS t2.micro - 1GB RAM)

Memory allocation plan:
- Total RAM: 1024 MB
- OS (Linux): ~150 MB
- PostgreSQL: ~256 MB
- Redis: ~128 MB
- Available for Django: ~490 MB
- Reserved/buffer: ~90 MB

With 2 sync workers, each using ~100MB base + Django app ~100MB = ~400MB total
This leaves safe headroom for request processing.
"""

import multiprocessing
import os

# Worker processes
# CRITICAL: Don't use formula (2 × CPU + 1) - that would be 5 workers = too much RAM!
# Fixed at 2 workers for 1GB RAM instances
workers = 2

# Worker class - 'sync' uses least memory
# DO NOT use 'gevent' or 'eventlet' - they use more RAM
worker_class = 'sync'

# Alternative: Use threads instead of workers (if needed)
# Uncomment these and set workers=1 if you need more concurrency with less memory:
# workers = 1
# worker_class = 'gthread'
# threads = 4  # Threads share memory, workers don't

# Binding
bind = '0.0.0.0:8000'

# Memory management
max_requests = 500  # Restart worker after 500 requests (prevent memory leaks)
max_requests_jitter = 50  # Add randomness to prevent all workers restarting at once
preload_app = True  # Load app before forking (workers share memory)

# Timeouts
timeout = 30  # Reduced from 60 (shorter = less memory held)
graceful_timeout = 20
keepalive = 2

# Logging (minimize to save memory)
accesslog = None  # Don't log access (use nginx logs instead)
errorlog = '-'  # Only error logs to stderr
loglevel = 'warning'  # Only warnings and errors

# Process naming
proc_name = 'tickettche'

# Server mechanics
daemon = False
pidfile = None
user = None
group = None
tmp_upload_dir = None

# SSL (handled by nginx)
keyfile = None
certfile = None

# Debugging
reload = False  # Don't auto-reload in production
reload_engine = 'auto'

# Server hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("Gunicorn starting with %d workers (memory-optimized config)", workers)

def on_reload(server):
    """Called when configuration is reloaded."""
    server.log.info("Gunicorn reloading")

def worker_int(worker):
    """Called when worker receives INT or QUIT signal."""
    worker.log.info("Worker %s interrupted", worker.pid)

def worker_abort(worker):
    """Called when worker receives SIGABRT signal."""
    worker.log.error("Worker %s aborted (likely out of memory)", worker.pid)
