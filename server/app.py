"""
Task 1: Minimal web server for the load-balancer assignment.
Exposes /home and /heartbeat on port 5000.
The SERVER_ID env var is set when the container is launched, so each
replica can identify itself uniquely.
"""
import os
from flask import Flask, jsonify

app = Flask(__name__)

# Hostname/ID injected by the load balancer when it spawns this container
SERVER_ID = os.environ.get("SERVER_ID", "unknown")


@app.route("/home", methods=["GET"])
def home():
    return jsonify({
        "message": f"Hello from Server: {SERVER_ID}",
        "status": "successful"
    }), 200


@app.route("/heartbeat", methods=["GET"])
def heartbeat():
    # Empty body, 200 OK is enough for the load balancer's health checks
    return "", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
