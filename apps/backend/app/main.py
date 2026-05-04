from fastapi import FastAPI, Request
import random
import time
from prometheus_client import make_asgi_app
from app.logger import observability_logger, logger
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

app = FastAPI()
metrics_app = make_asgi_app()
app.mount('/metrics', metrics_app)

# Instrument FastAPI with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)

@app.on_event("startup")
async def startup_event():
    observability_logger.start_scanning()
    logger.info("Observability services started")

@app.on_event("shutdown")
async def shutdown_event():
    observability_logger.stop_scanning()
    logger.info("Observability services stopped")

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(random.randint(100000, 999999))
    request.state.request_id = request_id

    start_time = time.time()
    response = await call_next(request)
    latency = (time.time() - start_time) * 1000  # ms

    observability_logger.log_request(
        endpoint=str(request.url.path),
        method=request.method,
        status=response.status_code,
        latency=latency,
        request_id=request_id
    )

    return response


@app.get("/fast")
def fast():
    return {"message": "fast"}


@app.get("/slow")
def slow():
    delay = random.uniform(0.5, 3)
    time.sleep(delay)
    return {"message": f"slow ({delay:.2f}s)"}


@app.get("/error")
def error():
    if random.random() < 0.3:
        observability_logger.log_error("simulated", "Simulated failure")
        raise Exception("Simulated error")
    return {"message": "ok"}


@app.get("/cpu")
def cpu():
    x = 0
    for i in range(10**8):  # Increased to 100 million for more CPU usage
        x += i
    return {"message": "cpu done"}


@app.get("/memory")
def memory():
    data = []
    for _ in range(10**6):  # Increased to 1 million for more memory usage
        data.append("x" * 1000)
    return {"message": "memory stress"}


@app.get("/ai-inference")
def ai_inference():
    # Simulate AI inference
    model_name = random.choice(["gpt-4", "bert", "resnet"])
    inference_time = random.uniform(50, 500)  # ms
    confidence = random.uniform(0.7, 0.99)
    input_tokens = random.randint(10, 100)
    output_tokens = random.randint(1, 50)

    observability_logger.log_inference(
        model_name=model_name,
        inference_time=inference_time,
        prediction_confidence=confidence,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model_version="v1.0"
    )

    return {
        "model": model_name,
        "prediction": "some output",
        "confidence": confidence,
        "tokens": {"input": input_tokens, "output": output_tokens}
    }


@app.get("/random")
def random_endpoint():
    choice = random.choice(["fast", "slow", "error", "cpu", "memory", "ai-inference"])

    if choice == "fast":
        return fast()
    elif choice == "slow":
        return slow()
    elif choice == "error":
        return error()
    elif choice == "cpu":
        return cpu()
    elif choice == "memory":
        return memory()
    else:
        return ai_inference()


@app.get("/health")
def health():
    return {"status": "ok", "app": "backend"}
