import shutil
import multiprocessing
import os
from infra.config import PROMETHEUS_MULTIPROC_DIR

# PROMETHEUS_MULTIPROC_DIR must be set in os.environ before prometheus_client is imported anywhere
os.environ["PROMETHEUS_MULTIPROC_DIR"] = PROMETHEUS_MULTIPROC_DIR

import redis
from wsgiref.simple_server import make_server, WSGIRequestHandler
from prometheus_client import (
    Counter,
    CollectorRegistry,
    make_wsgi_app,
    multiprocess,
)
from prometheus_client.core import GaugeMetricFamily

from infra.logger import logger
from infra.config import (
    REDIS_HOST, REDIS_PORT, REDIS_DB, QUEUE_KEY, METRICS_PORT,
)


# Define the counters for various metrics

tasks_processed_total = Counter(
    "tasks_processed_total",
    "Total number of tasks successfully completed by workers",
)

tasks_recovered_total = Counter(
    "tasks_recovered_total",
    "Total number of tasks re-queued by the watchdog after failure",
)

worker_crashes_total = Counter(
    "worker_crashes_total",
    "Total number of worker process crashes detected by the supervisor",
)

leader_crashes_total = Counter(
    "leader_crashes_total",
    "Total number of leader candidate crashes detected by the supervisor",
)


# ------------------------------------------------------------------
# Custom collector: queue_size
# Queried live from Redis on every scrape, no background polling.
# ------------------------------------------------------------------

class QueueSizeCollector:
    """    
    Registered with the Prometheus registry once at server startup.
    Called by the registry on every GET /metrics request.
    """
    
    def __init__(self, host: str = REDIS_HOST, port: int = REDIS_PORT, db: int = REDIS_DB):
        self._r = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT,
            db=REDIS_DB, decode_responses=True,
        )
    
    def collect(self):
        try:
            size = self._r.llen(QUEUE_KEY)
        except redis.RedisError:
            size = 0
        
        metric = GaugeMetricFamily(
            "queue_size",
            "Current number of tasks waiting in the task queue",
        )
        metric.add_metric([], float(size))
        yield metric


# ------------------------------------------------------------------
# Metrics HTTP server
# ------------------------------------------------------------------

class _SilentHandler(WSGIRequestHandler):
    """Suppress the default pre-request stdout log lines."""
    def log_message(self, fmt, *args):
        pass


def _build_registry() -> CollectorRegistry:
    """
    Build an aggregating registry for multiprocess mode.
    Must be called inside the metrics server thread/process, after PROMETHEUS_MULTIPROC_DIR is set.
    """
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry=registry)
    registry.register(QueueSizeCollector())
    return registry

def _metrics_app(environ, start_response):
    registry = _build_registry()          # fresh registry every scrape
    return make_wsgi_app(registry)(environ, start_response)

def start_metrics_server(port: int = METRICS_PORT) -> multiprocessing.Process:
    """
    Start the proometheus metrics HTTP server in a daemon thread.
    Return the thread (caller can ignore it, it runs until process exits).
    """
    def _run():
        # registry = _build_registry()
        # app = make_wsgi_app(registry)
        httpd = make_server("", port, _metrics_app, handler_class=_SilentHandler)
    
        logger.info(f"Metrics Server: listening on http://localhost:{port}/metrics")
        httpd.serve_forever()
    
    # Create a separate process instead of thread, as MultiProcessCollector skips the current process's .db file when aggregating.
    # If main process (or any threads in it) have to use counters, then metrics server shouldn't run inside the main process.
    p = multiprocessing.Process(
        target=_run,
        daemon=True,
        name="Metrics Server",
    )
    p.start()
    
    return p
