import os
from pathlib import Path


chdir = str(Path(__file__).resolve().parent / "valour_tech_sectors")
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", "4"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
graceful_timeout = 25
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
accesslog = "-"
errorlog = "-"
capture_output = True
# Log paths, not query strings/cookies or signed storage URLs.
access_log_format = '%(t)s "%(m)s %(U)s %(H)s" %(s)s %(b)s %(L)s'
# Render's edge is the only public ingress. A different deployment must put
# Gunicorn behind a trusted proxy; never expose this port directly to clients.
forwarded_allow_ips = "*"
secure_scheme_headers = {"X-FORWARDED-PROTO": "https"}
