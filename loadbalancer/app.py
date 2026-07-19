"""
Task 3: Load Balancer.

Responsibilities:
  - Maintain N healthy server replicas at all times (respawn on failure)
  - Route client requests to a replica using the ConsistentHashMap
  - Expose /rep, /add, /rm, /<path> as described in the assignment

Requires the Docker socket to be mounted into this container
(see docker-compose.yml) and the container to run with privileged: true,
so it can spawn/stop sibling containers via the docker-py SDK.
"""
import os
import time
import random
import string
import threading

import docker
import requests
from flask import Flask, request, jsonify

from consistent_hash import ConsistentHashMap

app = Flask(__name__)
docker_client = docker.from_env()

# Load configuration from environment variables so the application can
# be easily configured through Docker Compose without changing the code
NETWORK_NAME = os.environ.get("NETWORK_NAME", "net1")
SERVER_IMAGE = os.environ.get("SERVER_IMAGE", "server:latest")
DEFAULT_N = int(os.environ.get("N", 3))
NUM_SLOTS = int(os.environ.get("NUM_SLOTS", 512))
NUM_VIRTUAL = int(os.environ.get("NUM_VIRTUAL", 9))  # log2(512) = 9
HEARTBEAT_INTERVAL_SEC = float(os.environ.get("HEARTBEAT_INTERVAL_SEC", 5))
HEARTBEAT_TIMEOUT_SEC = float(os.environ.get("HEARTBEAT_TIMEOUT_SEC", 2))

# Create the consistent hash ring used to map requests to server replicas
chm = ConsistentHashMap(num_slots=NUM_SLOTS, num_virtual=NUM_VIRTUAL)
servers = {}  # hostname -> {"id": int}
state_lock = threading.RLock()


def random_hostname():
    """Generate a unique hostname for replicas created automatically."""
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"Server_{suffix}"


def spawn_container(hostname):
    """Launches a new server container on the shared docker network."""
    docker_client.containers.run(
        SERVER_IMAGE,
        name=hostname,
        hostname=hostname,
        network=NETWORK_NAME,
        environment={"SERVER_ID": hostname},
        detach=True,
        remove=False,
    )


def stop_and_remove_container(hostname):
    """
    Stop and remove a server container.
    Missing containers are ignored to simplify cleanup.
    """
    try:
        c = docker_client.containers.get(hostname)
        c.stop(timeout=3)
        c.remove(force=True)
    except docker.errors.NotFound:
        pass
    except Exception as e:
        print(f"[warn] could not clean up container {hostname}: {e}")


def cleanup_old_servers():
    """Remove any leftover server containers from previous runs."""
    try:
        for container in docker_client.containers.list(all=True):
            if container.name.startswith("Server_"):
                print(f"[startup] Removing stale container {container.name}")
                container.remove(force=True)
    except Exception as e:
        print(f"[startup] Cleanup failed: {e}")


def add_server_internal(hostname=None):
    """Spawns a container (if it doesn't already exist) and registers it
    in the consistent hash ring. Returns the hostname used."""
    if hostname is None:
        hostname = random_hostname()

    with state_lock:
        if hostname in servers:
            return hostname  # already present, no-op
        spawn_container(hostname)
        sid = chm.add_server(hostname)
        servers[hostname] = {"id": sid}
    return hostname


def remove_server_internal(hostname):
    with state_lock:
        if hostname not in servers:
            return
        chm.remove_server(hostname)
        servers.pop(hostname, None)
    stop_and_remove_container(hostname)


def init_servers(n):
    for _ in range(n):
        add_server_internal()


# Endpoints

# Returns the current number of active replicas and their hostnames.
@app.route("/rep", methods=["GET"])
def rep():
    with state_lock:
        replicas = list(servers.keys())
    return jsonify({
        "message": {"N": len(replicas), "replicas": replicas},
        "status": "successful"
    }), 200


@app.route("/add", methods=["POST"])
def add():
    payload = request.get_json(force=True, silent=True) or {}
    n = payload.get("n", 0)
    hostnames = payload.get("hostnames", [])

    if len(hostnames) > n:
        return jsonify({
            "message": "<Error> Length of hostname list is more than newly added instances",
            "status": "failure"
        }), 400

    for h in hostnames:
        add_server_internal(h)
    for _ in range(n - len(hostnames)):
        add_server_internal()

    with state_lock:
        replicas = list(servers.keys())
    return jsonify({
        "message": {"N": len(replicas), "replicas": replicas},
        "status": "successful"
    }), 200


@app.route("/rm", methods=["DELETE"])
def rm():
    payload = request.get_json(force=True, silent=True) or {}
    n = payload.get("n", 0)
    hostnames = payload.get("hostnames", [])

    if len(hostnames) > n:
        return jsonify({
            "message": "<Error> Length of hostname list is more than removable instances",
            "status": "failure"
        }), 400

    with state_lock:
        all_hosts = list(servers.keys())

    # Validate requested hostnames actually exist; ignore ones that don't
    to_remove = [h for h in hostnames if h in all_hosts]
    remaining_needed = n - len(to_remove)
    candidates = [h for h in all_hosts if h not in to_remove]
    random.shuffle(candidates)
    to_remove += candidates[:remaining_needed]

    for h in to_remove:
        remove_server_internal(h)

    with state_lock:
        replicas = list(servers.keys())
    return jsonify({
        "message": {"N": len(replicas), "replicas": replicas},
        "status": "successful"
    }), 200


@app.route("/<path:subpath>", methods=["GET"])
def route_request(subpath):
    endpoint = "/" + subpath
    request_id = random.randint(100000, 999999)  # 6-digit id per spec

    with state_lock:
        target = chm.get_server(request_id)

    if target is None:
        return jsonify({
            "message": f"<Error> '{subpath}' endpoint does not exist in server replicas",
            "status": "failure"
        }), 400

    try:
        resp = requests.get(f"http://{target}:5000{endpoint}", timeout=3)

        # Convert backend 404 into the assignment's required JSON response
        if resp.status_code == 404:
            return jsonify({
                "message": f"<Error> '{endpoint}' endpoint does not exist in server replicas",
                "status": "failure"
            }), 400
        
        return (resp.content, resp.status_code, {"Content-Type": "application/json"})

    except Exception:
        return jsonify({
            "message": f"<Error> '{subpath}' endpoint does not exist in server replicas",
            "status": "failure"
        }), 400


# Background health check / auto-respawn

def heartbeat_loop():
    """
    Periodically checks the health of every replica.
    If a replica fails its heartbeat, it is removed from the hash ring
    and immediately replaced with a new container.
    """
    while True:
        time.sleep(HEARTBEAT_INTERVAL_SEC)
        with state_lock:
            hosts = list(servers.keys())

        for h in hosts:
            try:
                r = requests.get(f"http://{h}:5000/heartbeat", timeout=HEARTBEAT_TIMEOUT_SEC)
                if r.status_code != 200:
                    raise ValueError("bad heartbeat status")
            except Exception:
                print(f"[heartbeat] {h} failed health check -> removing and respawning")
                remove_server_internal(h)
                add_server_internal()


if __name__ == "__main__":
    cleanup_old_servers()         #Remove old Server_* containers
    init_servers(DEFAULT_N)

    # Start the heartbeat monitor in the background
    t = threading.Thread(target=heartbeat_loop, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000)
