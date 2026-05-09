import logging
import json
import time
import uuid
import random
import psutil
import threading
import queue
import requests
from typing import Optional

# Prometheus Metrics
from prometheus_client import Counter, Histogram, Gauge, Summary

REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status', 'error_type'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency', ['method', 'endpoint'])
# Advanced App Metrics
APP_RETRY_COUNT = Counter('app_retries_total', 'Total application retries', ['endpoint'])
APP_QUEUE_SIZE = Gauge('app_queue_size', 'Current request queue size')
APP_ACTIVE_USERS = Gauge('app_active_users', 'Current active users simulated')
APP_THREAD_COUNT = Gauge('app_thread_count', 'Active application threads')
# System/Infra Metrics
SYSTEM_CPU = Gauge('system_cpu_percent', 'System CPU usage percent')
SYSTEM_MEMORY = Gauge('system_memory_percent', 'System memory usage percent')
NETWORK_IO_BYTES_SENT = Counter('network_io_bytes_sent_total', 'Network bytes sent')
NETWORK_IO_BYTES_RECV = Counter('network_io_bytes_recv_total', 'Network bytes received')
DISK_IO_READ_BYTES = Counter('disk_io_read_bytes_total', 'Disk read bytes')
DISK_IO_WRITE_BYTES = Counter('disk_io_write_bytes_total', 'Disk write bytes')
CONTAINER_RESTARTS = Counter('container_restarts_total', 'Simulated container restarts')
# AI Inference Metrics
INFERENCE_COUNT = Counter('ai_inferences_total', 'Total AI inferences', ['model_name'])
INFERENCE_LATENCY = Histogram('ai_inference_duration_seconds', 'AI inference latency', ['model_name'])
MODEL_ACCURACY = Gauge('ai_model_accuracy', 'AI model accuracy', ['model_name'])


class JSONFormatter(logging.Formatter):
    def __init__(self, service_name: str = "backend"):
        super().__init__()
        self.service_name = service_name
        self._lock = threading.Lock()

    def format(self, record):
        with self._lock:
            log_record = {
                "timestamp": record.created,
                "level": record.levelname,
                "message": record.getMessage(),
                "logger": record.name,
                "thread": record.thread,
                "process": record.process,
                "category": getattr(record, "category", "system"), # api, auth, db, cache, system, ml

                # Request metadata
                "endpoint": getattr(record, "endpoint", None),
                "method": getattr(record, "method", "GET"),
                "status": getattr(record, "status", None),
                "latency_ms": getattr(record, "latency", None),

                # System metrics snapshot
                "cpu_usage_percent": psutil.cpu_percent(interval=None),
                "memory_usage_percent": psutil.virtual_memory().percent,

                # Tracing
                "request_id": getattr(record, "request_id", str(uuid.uuid4())),
                "user_id": getattr(record, "user_id", None),

                # Error Context
                "error_type": getattr(record, "error_type", None),
                "stack_trace": getattr(record, "stack_trace", None),
                "incident_tag": getattr(record, "incident_tag", None),

                # Loki labels (used by Loki push handler for stream grouping)
                "labels": {
                    "level": record.levelname.lower(),
                    "service": self.service_name,
                    "category": getattr(record, "category", "system"),
                    "environment": "development"
                }
            }

            # Remove None values
            log_record["labels"] = {k: v for k, v in log_record["labels"].items() if v is not None}
            log_record = {k: v for k, v in log_record.items() if v is not None or k == "labels"}

            return json.dumps(log_record, default=str)


class LokiPushHandler(logging.Handler):
    """Asynchronous logging handler that pushes log records directly to Loki HTTP API."""
    def __init__(self, loki_url: str = "http://loki:3100/loki/api/v1/push", service_name: str = "backend"):
        super().__init__()
        self.loki_url = loki_url
        self.service_name = service_name
        self.queue = queue.Queue()
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

    def emit(self, record):
        try:
            formatted_record = self.format(record)
            cat = getattr(record, "category", "system")
            self.queue.put((record.created, record.levelname.lower(), cat, formatted_record))
        except Exception:
            self.handleError(record)

    def _worker(self):
        while self.running:
            batch = []
            start_time = time.time()
            while len(batch) < 100 and (time.time() - start_time) < 1.0:
                try:
                    item = self.queue.get(timeout=0.1)
                    batch.append(item)
                    self.queue.task_done()
                except queue.Empty:
                    break

            if batch:
                self._send_batch(batch)

    def _send_batch(self, batch):
        try:
            streams = {}
            for timestamp_s, level, cat, msg in batch:
                timestamp_ns = str(int(timestamp_s * 1e9))
                key = (self.service_name, level, cat)
                if key not in streams:
                    streams[key] = {
                        "stream": {
                            "service": self.service_name,
                            "level": level,
                            "category": cat
                        },
                        "values": []
                    }
                streams[key]["values"].append([timestamp_ns, msg])

            payload = {"streams": list(streams.values())}
            headers = {'Content-type': 'application/json'}
            requests.post(self.loki_url, data=json.dumps(payload), headers=headers, timeout=2)
        except Exception as e:
            pass # Silent fail

    def close(self):
        self.running = False
        super().close()


class MetricsScanner:
    def __init__(self, logger: logging.Logger, interval: int = 5):
        self.logger = logger
        self.interval = interval
        self._running = False
        self._thread = None
        
        # Keep track of initial IO counters to report diffs if needed, though Counters usually take monotonic totals
        try:
            self.net_io_start = psutil.net_io_counters()
            self.disk_io_start = psutil.disk_io_counters()
        except:
            pass

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._scan_metrics, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()

    def _scan_metrics(self):
        while self._running:
            try:
                cpu = psutil.cpu_percent(interval=None)
                memory = psutil.virtual_memory().percent
                
                SYSTEM_CPU.set(cpu)
                SYSTEM_MEMORY.set(memory)
                APP_THREAD_COUNT.set(threading.active_count())

                # Simulate some random network/disk I/O based on current activity
                NETWORK_IO_BYTES_SENT.inc(random.randint(1000, 50000))
                NETWORK_IO_BYTES_RECV.inc(random.randint(1000, 50000))
                DISK_IO_READ_BYTES.inc(random.randint(500, 20000))
                DISK_IO_WRITE_BYTES.inc(random.randint(500, 20000))

                # We don't log every scan to Loki to save noise, but metrics are updated
            except Exception as e:
                self.logger.error(f"Metrics scan error: {e}", extra={"error_type": "metrics_scan", "category": "system"})
            time.sleep(self.interval)


class ObservabilityLogger:
    def __init__(self, service_name: str = "backend"):
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)
        self.formatter = JSONFormatter(service_name)
        
        self.console_handler = logging.StreamHandler()
        self.console_handler.setFormatter(self.formatter)
        
        self.loki_handler = LokiPushHandler(service_name=service_name)
        self.loki_handler.setFormatter(self.formatter)

        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(self.console_handler)
        self.logger.addHandler(self.loki_handler)
        self.logger.propagate = False

        self.metrics_scanner = MetricsScanner(self.logger)

    def start_scanning(self):
        self.metrics_scanner.start()

    def stop_scanning(self):
        self.metrics_scanner.stop()

    def log_request(self, endpoint: str, method: str, status: int, latency: float,
                    request_id: Optional[str] = None, user_id: Optional[int] = None,
                    error_type: str = "none", **kwargs):
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=str(status), error_type=error_type).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(latency / 1000)

        extra = {
            "category": "api",
            "endpoint": endpoint,
            "method": method,
            "status": status,
            "latency": latency,
            "request_id": request_id or str(uuid.uuid4()),
            "user_id": user_id,
            "error_type": error_type,
            **kwargs
        }
        level = logging.INFO
        if status >= 500:
            level = logging.ERROR
        elif status >= 400:
            level = logging.WARNING
            
        self.logger.log(level, f"Request {method} {endpoint} - {status}", extra=extra)

    def log_event(self, level: int, message: str, category: str = "system", **kwargs):
        extra = {"category": category, **kwargs}
        self.logger.log(level, message, extra=extra)

    def update_gauge(self, name: str, value: float):
        if name == 'queue_size':
            APP_QUEUE_SIZE.set(value)
        elif name == 'active_users':
            APP_ACTIVE_USERS.set(value)

    def log_error(self, category: str, error_type: str, message: str, request_id: Optional[str] = None, **kwargs):
        extra = {
            "category": category,
            "error_type": error_type,
            "request_id": request_id,
            **kwargs
        }
        self.logger.error(message, extra=extra)


observability_logger = ObservabilityLogger()
logger = observability_logger.logger