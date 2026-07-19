"""
A-1: Launch 10,000 async requests against the load balancer (N=3 servers
by default) and plot how many requests each server handled.

Run this AFTER `make up` and after confirming `curl localhost:5000/rep`
returns 3 healthy replicas.

    pip install aiohttp matplotlib
    python a1_load_distribution.py
"""
import asyncio
import collections
import aiohttp
import matplotlib.pyplot as plt

BASE_URL = "http://localhost:5000"
NUM_REQUESTS = 10000


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
    results = asyncio.run(run_load_test(NUM_REQUESTS))
    counts = collections.Counter(results)

    print(f"Sent {NUM_REQUESTS} requests. Distribution:")
    for server, count in sorted(counts.items()):
        print(f"  {server}: {count}")

    labels = list(counts.keys())
    values = [counts[k] for k in labels]

    plt.figure(figsize=(8, 5))
    plt.bar(labels, values, color="steelblue")
    plt.xlabel("Server")
    plt.ylabel("Requests handled")
    plt.title(f"A-1: Load distribution across servers ({NUM_REQUESTS} requests)")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig("a1_load_distribution.png")
    print("\nSaved chart to a1_load_distribution.png")


if __name__ == "__main__":
    main()
