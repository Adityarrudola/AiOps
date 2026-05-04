import asyncio
import os
import uuid
from datetime import datetime

import httpx
from fastapi import FastAPI
from prometheus_client import Counter, make_asgi_app
from pydantic import BaseModel
from prometheus_api_client import PrometheusConnect
from sklearn.ensemble import IsolationForest

PROMETHEUS_URL = os.getenv('PROMETHEUS_URL', 'http://prometheus-server:9090')

app = FastAPI(title='AIOps Correlation Engine')
metrics_app = make_asgi_app()
app.mount('/metrics', metrics_app)

anomaly_count = Counter('aiops_anomalies_total', 'Total AIOps anomalies detected')
alerts = []

class Alert(BaseModel):
    id: str
    timestamp: str
    severity: str
    message: str
    correlation: str


def fetch_metric(prom: PrometheusConnect, query: str) -> dict:
    return prom.get_current_metric_value(query=query) or {}


def evaluate_anomalies(data):
    if not data:
        return []
    values = [[float(v)] for _, v in data.items()]
    model = IsolationForest(contamination=0.1, random_state=42)
    labels = model.fit_predict(values)
    return [key for key, label in zip(data.keys(), labels) if label == -1]


async def monitor_loop():
    prom = PrometheusConnect(url=PROMETHEUS_URL, disable_ssl=True)
    while True:
        try:
            window = '5m'
            cpu_query = 'avg(rate(container_cpu_usage_seconds_total[5m])) by (pod)'
            err_query = 'sum(rate(http_requests_total{status=~"5.."}[5m])) by (pod)'
            latency_query = 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, pod))'

            cpu = fetch_metric(prom, cpu_query)
            err = fetch_metric(prom, err_query)
            latency = fetch_metric(prom, latency_query)

            cpu_anomalies = evaluate_anomalies(cpu)
            err_anomalies = evaluate_anomalies(err)
            latency_anomalies = evaluate_anomalies(latency)

            combined = set(cpu_anomalies) | set(err_anomalies) | set(latency_anomalies)
            for pod in combined:
                severity = 'high' if pod in err_anomalies or pod in latency_anomalies else 'medium'
                correlation = []
                if pod in cpu_anomalies and pod in latency_anomalies:
                    correlation.append('cpu+latency bottleneck')
                if pod in err_anomalies and pod in cpu_anomalies:
                    correlation.append('error burst with high CPU')
                message = f'Detected anomaly for {pod}: cpu={pod in cpu_anomalies}, latency={pod in latency_anomalies}, errors={pod in err_anomalies}'
                alert = Alert(
                    id=str(uuid.uuid4()),
                    timestamp=datetime.utcnow().isoformat() + 'Z',
                    severity=severity,
                    message=message,
                    correlation=', '.join(correlation) or 'univariate anomaly',
                )
                alerts.append(alert.dict())
                anomaly_count.inc()
                print(f'ALERT: {alert.json()}')
        except Exception as exc:
            print(f'AIOps loop error: {exc}')

        await asyncio.sleep(30)


@app.on_event('startup')
async def startup_event():
    asyncio.create_task(monitor_loop())


@app.get('/health')
def health():
    return {'status': 'ok', 'prometheus': PROMETHEUS_URL}


@app.get('/alerts')
def get_alerts():
    return {'alerts': alerts[-20:]}
