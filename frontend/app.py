import os
import threading
from collections import OrderedDict
from urllib.parse import quote

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "10"))
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://127.0.0.1:5000")

# Lab 2: replica lists for Round Robin load balancing
CATALOG_REPLICAS = [
    u.strip()
    for u in os.environ.get(
        "CATALOG_REPLICAS", "http://127.0.0.1:5001,http://127.0.0.1:5003"
    ).split(",")
    if u.strip()
]
ORDER_REPLICAS = [
    u.strip()
    for u in os.environ.get(
        "ORDER_REPLICAS", "http://127.0.0.1:5002,http://127.0.0.1:5004"
    ).split(",")
    if u.strip()
]

# Round Robin counters
catalog_rr_lock = threading.Lock()
order_rr_lock = threading.Lock()
catalog_rr_index = 0
order_rr_index = 0

# --- Lab 2: in-memory LRU cache (max 10 entries) ---
CACHE_MAX_SIZE = 10
cache_lock = threading.Lock()
memory_cache = OrderedDict()


def replica_label(base_url, prefix):
    port = base_url.rstrip("/").split(":")[-1]
    return f"{prefix}-replica-{port}"


def next_replica(replicas, lock, counter_name):
    global catalog_rr_index, order_rr_index
    with lock:
        if counter_name == "catalog":
            idx = catalog_rr_index % len(replicas)
            catalog_rr_index += 1
        else:
            idx = order_rr_index % len(replicas)
            order_rr_index += 1
        return replicas[idx], idx


def cache_get(key):
    """LRU cache lookup; move accessed key to end (most recent)."""
    with cache_lock:
        if key in memory_cache:
            memory_cache.move_to_end(key)
            return memory_cache[key]
    return None


def cache_set(key, value):
    """Store in cache; evict oldest (LRU) when over limit."""
    with cache_lock:
        memory_cache[key] = value
        memory_cache.move_to_end(key)
        while len(memory_cache) > CACHE_MAX_SIZE:
            memory_cache.popitem(last=False)


def invalidate_cache_for_item(item_id):
    """
    Cache consistency: remove info and all search entries after purchase.
  """
    removed = []
    with cache_lock:
        keys = list(memory_cache.keys())
        for key in keys:
            if key == f"info:{item_id}" or key.startswith("search:"):
                del memory_cache[key]
                removed.append(key)
    if removed:
        print(
            f"[Frontend] Cache invalidated for item {item_id}: {removed}",
            flush=True,
        )
    return removed


def request_with_failover(replicas, lock, counter_name, method, path, **kwargs):
    """Round Robin start + try next replica on failure."""
    first_url, start_idx = next_replica(replicas, lock, counter_name)
    ordered = [replicas[(start_idx + i) % len(replicas)] for i in range(len(replicas))]
    last_error = None
    for base in ordered:
        url = f"{base.rstrip('/')}{path}"
        try:
            if method == "GET":
                resp = requests.get(url, timeout=REQUEST_TIMEOUT, **kwargs)
            else:
                resp = requests.post(url, timeout=REQUEST_TIMEOUT, **kwargs)
            if resp.status_code < 500:
                return resp, base
        except requests.RequestException as exc:
            last_error = exc
            print(f"[Frontend] Replica {base} failed: {exc}", flush=True)
    return None, last_error


def add_meta_headers(resp, served_by, cache_status):
    """Attach debug metadata as HTTP headers (keeps JSON body unchanged for arrays)."""
    resp.headers["X-Served-By"] = served_by
    resp.headers["X-Cache"] = cache_status
    return resp


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"service": "frontend", "status": "ok"})


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/api", methods=["GET"])
def api_welcome():
    return jsonify(
        {
            "message": "Welcome to Bazar.com",
            "endpoints": [
                "GET /",
                "GET /api",
                "GET /health",
                "GET /search/<topic>",
                "GET /info/<item_id>",
                "POST /purchase/<item_id>",
                "GET /cache/status",
                "DELETE /cache/clear",
                "DELETE /cache/invalidate/<item_id>",
            ],
            "lab2_features": [
                "Frontend UI",
                "Catalog replication",
                "Order replication",
                "Round Robin load balancing",
                "In-memory caching",
                "Cache invalidation",
                "Performance measurements",
            ],
        }
    )


@app.route("/cache/status", methods=["GET"])
def cache_status():
    with cache_lock:
        keys = list(memory_cache.keys())
    return jsonify({"size": len(keys), "max_size": CACHE_MAX_SIZE, "keys": keys})


@app.route("/cache/clear", methods=["DELETE"])
def cache_clear():
    with cache_lock:
        memory_cache.clear()
    print("[Frontend] Cache cleared", flush=True)
    return jsonify({"success": True, "message": "Cache cleared"})


@app.route("/cache/invalidate/<int:item_id>", methods=["DELETE", "POST"])
def cache_invalidate(item_id):
    removed = invalidate_cache_for_item(item_id)
    return jsonify(
        {"success": True, "item_id": item_id, "removed_keys": removed}
    )


@app.route("/search/<path:topic>", methods=["GET"])
def search(topic):
    print(f"[Frontend] Search request for topic: {topic}", flush=True)
    cache_key = f"search:{topic.lower()}"

    cached = cache_get(cache_key)
    if cached is not None:
        print(f"[Frontend] Cache HIT for {cache_key}", flush=True)
        resp = jsonify(cached["data"])
        return add_meta_headers(resp, cached.get("served_by", "cache"), "hit")

    print(f"[Frontend] Cache MISS for {cache_key}", flush=True)
    http_resp, catalog_base = request_with_failover(
        CATALOG_REPLICAS, catalog_rr_lock, "catalog", "GET", f"/search/{quote(topic)}"
    )
    if http_resp is None:
        return jsonify({"error": "Catalog service unavailable"}), 503

    if http_resp.status_code != 200:
        return jsonify({"error": "Catalog service unavailable"}), 503

    results = http_resp.json()
    served_by = replica_label(catalog_base, "catalog")
    print(f"[Frontend] Served by {served_by}", flush=True)

    cache_set(
        cache_key,
        {"data": results, "served_by": served_by},
    )

    resp = jsonify(results)
    return add_meta_headers(resp, served_by, "miss")


@app.route("/info/<int:item_id>", methods=["GET"])
def info(item_id):
    print(f"[Frontend] Info request for item {item_id}", flush=True)
    cache_key = f"info:{item_id}"

    cached = cache_get(cache_key)
    if cached is not None:
        print(f"[Frontend] Cache HIT for {cache_key}", flush=True)
        body = dict(cached["data"])
        body["served_by"] = cached.get("served_by", "cache")
        body["cache"] = "hit"
        return jsonify(body)

    print(f"[Frontend] Cache MISS for {cache_key}", flush=True)
    http_resp, catalog_base = request_with_failover(
        CATALOG_REPLICAS, catalog_rr_lock, "catalog", "GET", f"/info/{item_id}"
    )
    if http_resp is None:
        return jsonify({"error": "Catalog service unavailable"}), 503

    data = http_resp.json()
    served_by = replica_label(catalog_base, "catalog")
    print(f"[Frontend] Served by {served_by}", flush=True)

    if http_resp.status_code == 200:
        cache_set(cache_key, {"data": data, "served_by": served_by})
        data = dict(data)
        data["served_by"] = served_by
        data["cache"] = "miss"
        return jsonify(data)

    return jsonify(data), http_resp.status_code


@app.route("/purchase/<int:item_id>", methods=["POST"])
def purchase(item_id):
    print(f"[Frontend] Purchase request for item {item_id}", flush=True)

    http_resp, order_base = request_with_failover(
        ORDER_REPLICAS,
        order_rr_lock,
        "order",
        "POST",
        f"/purchase/{item_id}",
    )
    if http_resp is None:
        return jsonify({"error": "Order service unavailable"}), 503

    data = http_resp.json()
    served_by = replica_label(order_base, "order")
    print(f"[Frontend] Order served by {served_by}", flush=True)

    if http_resp.status_code == 200 and data.get("success"):
        invalidate_cache_for_item(item_id)
        print(f"[Frontend] Cache invalidated after purchase of item {item_id}", flush=True)

    if isinstance(data, dict):
        data["served_by"] = served_by
        data["cache"] = "invalidated" if data.get("success") else "n/a"

    return jsonify(data), http_resp.status_code


@app.route("/proxy/health/all", methods=["GET"])
def proxy_health_all():
    """Helper for UI: check all replicas."""
    results = {"frontend": {"status": "ok"}}
    for url in CATALOG_REPLICAS:
        try:
            r = requests.get(f"{url}/health", timeout=REQUEST_TIMEOUT)
            results[url] = r.json()
        except requests.RequestException as e:
            results[url] = {"status": "down", "error": str(e)}
    for url in ORDER_REPLICAS:
        try:
            r = requests.get(f"{url}/health", timeout=REQUEST_TIMEOUT)
            results[url] = r.json()
        except requests.RequestException as e:
            results[url] = {"status": "down", "error": str(e)}
    return jsonify(results)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
