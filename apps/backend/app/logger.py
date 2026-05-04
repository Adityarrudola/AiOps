import logging
import json
import time
import uuid
import random
import psutil
import threading
from typing import Optional, Dict, Any
import asyncio
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor


# Prometheus Metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency', ['method', 'endpoint'])
INFERENCE_COUNT = Counter('ai_inferences_total', 'Total AI inferences', ['model_name'])
INFERENCE_LATENCY = Histogram('ai_inference_duration_seconds', 'AI inference latency', ['model_name'])
SYSTEM_CPU = Gauge('system_cpu_percent', 'System CPU usage percent')
SYSTEM_MEMORY = Gauge('system_memory_percent', 'System memory usage percent')
MODEL_ACCURACY = Gauge('ai_model_accuracy', 'AI model accuracy', ['model_name'])


class JSONFormatter(logging.Formatter):
    def __init__(self, service_name: str = "backend"):
        super().__init__()
        self.service_name = service_name
        self._lock = threading.Lock()

    def format(self, record):
        with self._lock:
            log_record = {
                "timestamp": time.time(),
                "level": record.levelname,
                "message": record.getMessage(),
                "logger": record.name,
                "thread": record.thread,
                "process": record.process,

                # Request metadata
                "endpoint": getattr(record, "endpoint", None),
                "method": getattr(record, "method", "GET"),
                "status": getattr(record, "status", None),
                "latency_ms": getattr(record, "latency", None),

                # System metrics
                "cpu_usage_percent": psutil.cpu_percent(interval=0.1),
                "memory_usage_percent": psutil.virtual_memory().percent,
                "disk_usage_percent": psutil.disk_usage('/').percent,

                # Tracing
                "request_id": getattr(record, "request_id", str(uuid.uuid4())),
                "trace_id": getattr(record, "trace_id", None),
                "span_id": getattr(record, "span_id", None),
                "user_id": getattr(record, "user_id", random.randint(1, 1000)),

                # AI-specific observability
                "model_name": getattr(record, "model_name", None),
                "inference_time_ms": getattr(record, "inference_time", None),
                "prediction_confidence": getattr(record, "prediction_confidence", None),
                "input_tokens": getattr(record, "input_tokens", None),
                "output_tokens": getattr(record, "output_tokens", None),
                "error_type": getattr(record, "error_type", None),
                "model_version": getattr(record, "model_version", None),
                "drift_score": getattr(record, "drift_score", None),

                # Loki labels
                "labels": {
                    "level": record.levelname.lower(),
                    "service": self.service_name,
                    "environment": getattr(record, "environment", "development"),
                    "model": getattr(record, "model_name", "unknown") if getattr(record, "model_name", None) else None
                },

                # Service info
                "service": self.service_name,
                "version": getattr(record, "version", "1.0.0"),
                "environment": getattr(record, "environment", "development")
            }

            # Remove None values and clean labels
            log_record["labels"] = {k: v for k, v in log_record["labels"].items() if v is not None}
            log_record = {k: v for k, v in log_record.items() if v is not None or k == "labels"}

            return json.dumps(log_record, default=str)


class MetricsScanner:
    def __init__(self, logger: logging.Logger, interval: int = 30):
        self.logger = logger
        self.interval = interval
        self._running = False
        self._thread = None

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
                cpu = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory().percent
                disk = psutil.disk_usage('/').percent

                SYSTEM_CPU.set(cpu)
                SYSTEM_MEMORY.set(memory)

                self.logger.info("System metrics scanned", extra={
                    "cpu_usage_percent": cpu,
                    "memory_usage_percent": memory,
                    "disk_usage_percent": disk,
                    "metric_type": "system_scan"
                })
            except Exception as e:
                self.logger.error(f"Metrics scan error: {e}", extra={"error_type": "metrics_scan"})

            time.sleep(self.interval)


class ObservabilityLogger:
    def __init__(self, service_name: str = "backend"):
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)
        self.formatter = JSONFormatter(service_name)
        self.handler = logging.StreamHandler()
        self.handler.setFormatter(self.formatter)

        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(self.handler)
        self.logger.propagate = False

        # Metrics scanner
        self.metrics_scanner = MetricsScanner(self.logger)

        # OpenTelemetry setup
        self._setup_tracing()

    def _setup_tracing(self):
        trace.set_tracer_provider(TracerProvider())
        otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
        span_processor = BatchSpanProcessor(otlp_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)
        self.tracer = trace.get_tracer(__name__)

    def start_metrics_server(self, port: int = 8001):
        """Start Prometheus metrics server."""
        start_http_server(port)
        self.logger.info(f"Prometheus metrics server started on port {port}")

    def start_scanning(self):
        """Start periodic metrics scanning."""
        self.metrics_scanner.start()

    def stop_scanning(self):
        """Stop metrics scanning."""
        self.metrics_scanner.stop()

    def log_request(self, endpoint: str, method: str, status: int, latency: float,
                    request_id: Optional[str] = None, user_id: Optional[int] = None,
                    **kwargs):
        """Log HTTP requests with AI observability context."""
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=str(status)).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(latency / 1000)  # Convert to seconds

        extra = {
            "endpoint": endpoint,
            "method": method,
            "status": status,
            "latency": latency,
            "request_id": request_id or str(uuid.uuid4()),
            "user_id": user_id,
            **kwargs
        }
        self.logger.info(f"Request to {endpoint}", extra=extra)

    def log_inference(self, model_name: str, inference_time: float,
                      prediction_confidence: Optional[float] = None,
                      input_tokens: Optional[int] = None,
                      output_tokens: Optional[int] = None,
                      model_version: Optional[str] = None,
                      drift_score: Optional[float] = None,
                      request_id: Optional[str] = None, **kwargs):
        """Log AI model inference events."""
        INFERENCE_COUNT.labels(model_name=model_name).inc()
        INFERENCE_LATENCY.labels(model_name=model_name).observe(inference_time / 1000)

        if prediction_confidence is not None:
            MODEL_ACCURACY.labels(model_name=model_name).set(prediction_confidence)

        extra = {
            "model_name": model_name,
            "inference_time": inference_time,
            "prediction_confidence": prediction_confidence,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "model_version": model_version,
            "drift_score": drift_score,
            "request_id": request_id,
            **kwargs
        }
        self.logger.info(f"Inference completed for {model_name}", extra=extra)

    def log_error(self, error_type: str, message: str, request_id: Optional[str] = None, **kwargs):
        """Log errors with context."""
        extra = {
            "error_type": error_type,
            "request_id": request_id,
            **kwargs
        }
        self.logger.error(message, extra=extra)

    def create_span(self, name: str, **attributes):
        """Create an OpenTelemetry span."""
        with self.tracer.start_as_span(name) as span:
            for key, value in attributes.items():
                span.set_attribute(key, value)
            return span


# Global logger instance
observability_logger = ObservabilityLogger()
logger = observability_logger.logger