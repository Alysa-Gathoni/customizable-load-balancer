"""
A-3: Exercise every load balancer endpoint, then kill a server container
directly (simulating a crash) and measure how quickly the load balancer
detects the failure and spawns a replacement.

    pip install requests
    python a3_failure_recovery.py
"""
import subprocess
import time
import requests

BASE_URL = "http://localhost:5000"


def show(label, resp):
    print(f"\n--- {label} ---")
    print(f"status: {resp.status_code}")
    try:
        print(resp.json())
    except Exception:
        print(resp.text)


def main():
    show("GET /rep (initial)", requests.get(f"{BASE_URL}/rep"))

    show("GET /home (routed request)", requests.get(f"{BASE_URL}/home"))

    show("GET /nonexistent (should 400)", requests.get(f"{BASE_URL}/nonexistent"))

    add_resp = requests.post(f"{BASE_URL}/add", json={"n": 2, "hostnames": ["TestA", "TestB"]})
    show("POST /add (n=2, named)", add_resp)

    rm_resp = requests.delete(f"{BASE_URL}/rm", json={"n": 1, "hostnames": ["TestA"]})
    show("DELETE /rm (n=1, named)", rm_resp)

    # --- Failure simulation ---
    replicas = requests.get(f"{BASE_URL}/rep").json()["message"]["replicas"]
    victim = replicas[0]
    print(f"\nSimulating crash of '{victim}' via `docker kill`...")
    t0 = time.time()
    subprocess.run(["docker", "kill", victim], check=False)

    # Poll /rep until the victim is gone and replica count is restored
    original_n = len(replicas)
    while True:
        current = requests.get(f"{BASE_URL}/rep").json()["message"]["replicas"]
        if victim not in current and len(current) == original_n:
            break
        time.sleep(0.5)
        if time.time() - t0 > 60:
            print("Timed out waiting for recovery (check heartbeat interval settings)")
            break

    elapsed = time.time() - t0
    print(f"\nRecovered in {elapsed:.1f} seconds.")
    show("GET /rep (post-recovery)", requests.get(f"{BASE_URL}/rep"))


if __name__ == "__main__":
    main()
