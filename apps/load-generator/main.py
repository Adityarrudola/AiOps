import asyncio
import os
import random
import httpx

BACKEND_HOST = os.getenv('BACKEND_HOST', 'backend')
BACKEND_PORT = os.getenv('BACKEND_PORT', '8000')
BASE_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"

endpoints = ["/fast", "/slow", "/error", "/cpu", "/memory", "/ai-inference", "/random"]


async def hit_endpoint(client):
    endpoint = random.choice(endpoints)
    try:
        await client.get(BASE_URL + endpoint)
    except Exception:
        pass


async def generate_load():
    async with httpx.AsyncClient(timeout=10) as client:
        while True:

            # burst traffic
            if random.random() < 0.2:
                tasks = [hit_endpoint(client) for _ in range(50)]
            else:
                tasks = [hit_endpoint(client) for _ in range(random.randint(5, 20))]

            await asyncio.gather(*tasks)

            await asyncio.sleep(random.uniform(0.2, 2))


if __name__ == "__main__":
    asyncio.run(generate_load())