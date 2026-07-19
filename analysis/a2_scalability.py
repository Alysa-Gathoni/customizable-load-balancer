"""
A-2: Increment N from 2 to 6, sending 10,000 requests at each step, and
plot the AVERAGE load per server at each N. Uses /add and /rm to resize
the fleet between runs (starting fleet is whatever N the LB booted with,
typically 3 -- this script adjusts up/down to hit each target N).

    pip install aiohttp requests matplotlib
    python a2_scalability.py
"""
import asyncio
import collections
import requests
import aiohttp
import matplotlib.pyplot as plt

BASE_URL = "http://localhost:5000"
NUM_REQUESTS = 10000
N_VALUES = [2, 3, 4, 5, 6]


def get_current_replicas():
    r = requests.get(f"{BASE_URL}/rep", timeout=5)
    return r.json()["message"]["replicas"]


def resize_to(target_n):
    current = get_current_replicas()
    diff = target_n - len(current)
    if diff > 0:
        requests.post(f"{BASE_URL}/add", json={"n": diff, "hostnames": []}, timeout=10)
    elif diff < 0:
        requests.delete(f"{BASE_URL}/rm", json={"n": -diff, "hostnames": []}, timeout=10)


async def fetch(session):
    try:
        async with session.get(f"{BASE_URL}/home") as resp:
            data = await resp.json()
            return data.get("message", "error")
    except Exception as e:
        return f"error:{e}"


async def run_load_test(n):
    connector = aiohttp.TCPConnector(limit=200)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch(session) for _ in range(n)]
        return await asyncio.gather(*tasks)


def main():
    avg_loads = []

    for n in N_VALUES:
        resize_to(n)
        results = asyncio.run(run_load_test(NUM_REQUESTS))
        counts = collections.Counter(results)
        actual_n = len(get_current_replicas())
        avg = NUM_REQUESTS / actual_n if actual_n else 0
        avg_loads.append(avg)
        print(f"N={n} (actual replicas={actual_n}): avg load/server = {avg:.1f}")
        print(f"  raw counts: {dict(counts)}")

    plt.figure(figsize=(8, 5))
    plt.plot(N_VALUES, avg_loads, marker="o", color="darkorange")
    plt.xlabel("Number of server replicas (N)")
    plt.ylabel("Average requests handled per server")
    plt.title(f"A-2: Average load vs. N ({NUM_REQUESTS} requests per run)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("a2_scalability.png")
    print("\nSaved chart to a2_scalability.png")


if __name__ == "__main__":
    main()
