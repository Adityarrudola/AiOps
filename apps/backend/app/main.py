from fastapi import FastAPI, Request
import random
import time
import asyncio
import math
import logging
from prometheus_client import make_asgi_app
from app.logger import observability_logger, logger

app = FastAPI(title="Backend Chaos Engine")
metrics_app = make_asgi_app()
app.mount('/metrics', metrics_app)

# Chaos state variables
chaos_state = {
    "memory_leak_active": False,
    "memory_hog": [],
    "cpu_spike_active": False,
    "db_outage": False,
    "traffic_burst": False,
    "slow_api": False,
    "disk_pressure": False,
    "thread_deadlock": False,
    "random_packet_loss": False,
    "base_traffic_rate": 1.0  # requests per second
}

async def generate_cyclic_traffic():
    """Adjusts base traffic rate using a sine wave to simulate seasonal daily peaks."""
    start_time = time.time()
    while True:
        elapsed = time.time() - start_time
        # Simulate a 5-minute cycle for fast observability demonstration
        cycle_val = math.sin((elapsed / 300) * 2 * math.pi)
        # Scale between 0.5 and 5 requests per second
        chaos_state["base_traffic_rate"] = 2.75 + (cycle_val * 2.25)
        observability_logger.update_gauge("active_users", int(chaos_state["base_traffic_rate"] * 10))
        await asyncio.sleep(10)

async def memory_leak_worker():
    """Gradually eats memory if leak is active."""
    while True:
        if chaos_state["memory_leak_active"]:
            chaos_state["memory_hog"].append("A" * 1024 * 1024 * 5) # 5MB chunks
            observability_logger.log_event(logging.WARNING, "Memory leak growing...", category="system")
        else:
            chaos_state["memory_hog"] = [] # Release memory
        await asyncio.sleep(2)

async def traffic_generator():
    """Fires requests at the API based on current traffic rate and chaos conditions."""
    await asyncio.sleep(5)
    logger.info("Traffic & Chaos Engine started")
    
    while True:
        try:
            # 1. Evaluate Chaos Modifiers
            error_probability = 0.05
            latency_modifier = 1.0
            
            if chaos_state["traffic_burst"]:
                chaos_state["base_traffic_rate"] *= 5.0
                error_probability += 0.15
                
            if chaos_state["slow_api"]:
                latency_modifier += 8.0
                
            if chaos_state["disk_pressure"]:
                latency_modifier += 2.0
                error_probability += 0.05
                
            if chaos_state["thread_deadlock"]:
                latency_modifier += 20.0
                error_probability += 0.5
                
            if chaos_state["random_packet_loss"]:
                error_probability += 0.3
            
            if chaos_state["cpu_spike_active"]:
                latency_modifier += random.uniform(2.0, 5.0)
                error_probability += 0.2
                
            if chaos_state["db_outage"]:
                error_probability += 0.8
                
            if len(chaos_state["memory_hog"]) > 20: # Over 100MB leaked
                latency_modifier += 1.5
                error_probability += 0.1
            
            # Update Queue metric
            queue_size = int(chaos_state["base_traffic_rate"] * latency_modifier * random.uniform(0.5, 2.0))
            observability_logger.update_gauge("queue_size", queue_size)

            # 2. Simulate a single synthetic request cycle
            if random.random() < error_probability:
                err_type = random.choice(["timeout", "db_connection_fail", "auth_failure", "rate_limit", "dependency_fail", "network_drop", "cache_miss", "security_breach"])
                cat = "db" if "db" in err_type else "auth" if "auth" in err_type else "security" if "security" in err_type else "network" if "network" in err_type else "cache" if "cache" in err_type else "api"
                lvl = logging.ERROR if err_type != "timeout" else logging.CRITICAL
                msg = f"Simulated {err_type} occurred"
                if "auth" in err_type: msg = "Login failure due to invalid token"
                elif "security" in err_type: msg = "SECURITY WARNING: Unauthorized access attempt blocked"
                elif "network" in err_type: msg = "Packet retry / network instability detected"
                elif "cache" in err_type: msg = "Cache miss spike detected"
                
                observability_logger.log_error(cat, err_type, msg)
                observability_logger.log_request("/api/resource", "GET", random.choice([500, 502, 503, 504, 401, 403, 429]), random.uniform(10, 500) * latency_modifier, error_type=err_type)
            else:
                latency = random.uniform(5, 50) * latency_modifier
                cat = random.choice(["api", "cache", "system", "performance", "debug"])
                msg = f"Processed {cat} request normally"
                lvl = logging.INFO
                if latency > 150: 
                    cat = "performance"
                    msg = "Slow endpoint detection: execution delayed"
                    lvl = logging.WARNING
                if cat == "debug":
                    msg = "Query execution details: index hit"
                    lvl = logging.DEBUG
                
                observability_logger.log_event(lvl, msg, category=cat)
                observability_logger.log_request(f"/{cat}/data", "GET", 200, latency)

        except Exception as e:
            pass

        # Calculate sleep based on traffic rate
        sleep_time = 1.0 / max(0.1, chaos_state["base_traffic_rate"])
        await asyncio.sleep(sleep_time * random.uniform(0.8, 1.2))

@app.on_event("startup")
async def startup_event():
    observability_logger.start_scanning()
    asyncio.create_task(generate_cyclic_traffic())
    asyncio.create_task(memory_leak_worker())
    asyncio.create_task(traffic_generator())
    # Start a couple extra generator threads for volume
    asyncio.create_task(traffic_generator())
    logger.info("Backend services initialized")

@app.on_event("shutdown")
async def shutdown_event():
    observability_logger.stop_scanning()

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(random.randint(1000, 9999))
    start_time = time.time()
    response = await call_next(request)
    latency = (time.time() - start_time) * 1000
    observability_logger.log_request(str(request.url.path), request.method, response.status_code, latency, request_id)
    return response

# Interactive Chaos Endpoints
@app.post("/chaos/memory-leak")
def trigger_memory_leak(active: bool):
    chaos_state["memory_leak_active"] = active
    observability_logger.log_event(logging.WARNING, f"Memory leak set to {active}", category="system")
    return {"status": "memory_leak", "active": active}

@app.post("/chaos/cpu-spike")
def trigger_cpu_spike(active: bool):
    chaos_state["cpu_spike_active"] = active
    observability_logger.log_event(logging.CRITICAL if active else logging.INFO, f"CPU spike set to {active}", category="system")
    if active:
        # Block thread temporarily to simulate spike
        sum(i for i in range(10**7))
    return {"status": "cpu_spike", "active": active}

@app.post("/chaos/db-outage")
def trigger_db_outage(active: bool):
    chaos_state["db_outage"] = active
    observability_logger.log_event(logging.CRITICAL if active else logging.INFO, f"DB Outage set to {active}", category="db")
    return {"status": "db_outage", "active": active}

@app.post("/chaos/traffic-burst")
def trigger_traffic_burst(active: bool):
    chaos_state["traffic_burst"] = active
    observability_logger.log_event(logging.WARNING, f"Traffic burst set to {active}", category="network")
    return {"status": "traffic_burst", "active": active}

@app.post("/chaos/slow-api")
def trigger_slow_api(active: bool):
    chaos_state["slow_api"] = active
    observability_logger.log_event(logging.WARNING, f"Slow API set to {active}", category="performance")
    return {"status": "slow_api", "active": active}

@app.post("/chaos/disk-pressure")
def trigger_disk_pressure(active: bool):
    chaos_state["disk_pressure"] = active
    observability_logger.log_event(logging.ERROR, f"Disk pressure set to {active}", category="system")
    return {"status": "disk_pressure", "active": active}

@app.get("/health")
def health():
    return {"status": "ok"}
