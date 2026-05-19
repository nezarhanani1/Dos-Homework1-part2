import argparse
import os
import sqlite3
import threading
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

# --- Lab 2: configurable order replica ---
ORDER_PORT = int(os.environ.get("ORDER_PORT", "5002"))
REPLICA_NAME = os.environ.get("REPLICA_NAME", f"order-replica-{ORDER_PORT}")
PEER_ORDER_URL = os.environ.get("PEER_ORDER_URL", "")
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "10"))

# Round-robin across catalog replicas for reads/writes
_default_catalog = "http://127.0.0.1:5001,http://127.0.0.1:5003"
CATALOG_REPLICAS = [
    u.strip()
    for u in os.environ.get("CATALOG_REPLICAS", _default_catalog).split(",")
    if u.strip()
]

DB_PATH = os.path.join(os.path.dirname(__file__), "data", f"orders_{ORDER_PORT}.db")
catalog_rr_lock = threading.Lock()
catalog_rr_index = 0


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                book_title TEXT NOT NULL,
                price INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row):
    return {
        "id": row["id"],
        "book_id": row["book_id"],
        "book_title": row["book_title"],
        "price": row["price"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def catalog_request(method, path, **kwargs):
    """
    Round Robin across catalog replicas with failover.
    Returns (response, catalog_url_used) or (None, None) if all fail.
    """
    global catalog_rr_index
    with catalog_rr_lock:
        start_idx = catalog_rr_index % len(CATALOG_REPLICAS)
        catalog_rr_index += 1
    ordered = [
        CATALOG_REPLICAS[(start_idx + i) % len(CATALOG_REPLICAS)]
        for i in range(len(CATALOG_REPLICAS))
    ]
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
            print(f"[{REPLICA_NAME}] Catalog {base} failed: {exc}", flush=True)
    return None, None


def sync_order_to_peer(order):
    """Replicate completed order to peer order replica."""
    if not PEER_ORDER_URL:
        return
    try:
        requests.post(
            f"{PEER_ORDER_URL}/sync/order",
            json={"order": order, "source": REPLICA_NAME},
            timeout=REQUEST_TIMEOUT,
        )
        print(f"[{REPLICA_NAME}] Synced order {order['id']} to peer", flush=True)
    except requests.RequestException as exc:
        print(f"[{REPLICA_NAME}] Warning: peer order sync failed: {exc}", flush=True)


def catalog_unavailable():
    return jsonify({"success": False, "message": "Catalog service unavailable"}), 503


@app.route("/health", methods=["GET"])
def health():
    return jsonify(
        {
            "service": "order",
            "status": "ok",
            "replica": REPLICA_NAME,
            "port": ORDER_PORT,
        }
    )


@app.route("/purchase/<int:item_id>", methods=["POST"])
def purchase(item_id):
    print(f"[{REPLICA_NAME}] Purchase request for item {item_id}", flush=True)

    info_resp, used_catalog = catalog_request("GET", f"/info/{item_id}")
    print(f"[{REPLICA_NAME}] Checking stock via {used_catalog}", flush=True)
    if info_resp is None:
        return catalog_unavailable()

    if info_resp.status_code == 404:
        return jsonify({"success": False, "message": "Book not found"}), 404

    if info_resp.status_code != 200:
        return catalog_unavailable()

    book = info_resp.json()
    if book.get("quantity", 0) <= 0:
        return jsonify({"success": False, "message": "Book is out of stock"}), 400

    update_resp, _ = catalog_request(
        "POST",
        f"/update/{item_id}",
        json={"quantity_change": -1},
    )
    if update_resp is None:
        return catalog_unavailable()

    if update_resp.status_code == 404:
        return jsonify({"success": False, "message": "Book not found"}), 404

    if update_resp.status_code == 400:
        return jsonify({"success": False, "message": "Book is out of stock"}), 400

    if update_resp.status_code != 200:
        return catalog_unavailable()

    title = book["title"]
    price = book["price"]
    created_at = datetime.now(timezone.utc).isoformat()

    conn = get_db_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO orders (book_id, book_title, price, status, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (item_id, title, price, "completed", created_at),
        )
        conn.commit()
        order_id = cursor.lastrowid
        order = {
            "id": order_id,
            "book_id": item_id,
            "book_title": title,
            "price": price,
            "status": "completed",
            "created_at": created_at,
        }
    finally:
        conn.close()

    message = f"bought book {title}"
    print(f"[{REPLICA_NAME}] {message} (catalog: {used_catalog})", flush=True)

    sync_order_to_peer(order)

    return jsonify(
        {
            "success": True,
            "message": message,
            "order": order,
            "served_by": REPLICA_NAME,
            "catalog_replica": used_catalog,
        }
    )


@app.route("/sync/order", methods=["POST"])
def sync_order():
    """Apply order from peer — no re-sync (avoids loops)."""
    body = request.get_json(silent=True) or {}
    order = body.get("order")
    if not order:
        return jsonify({"error": "Missing order"}), 400

    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO orders (book_id, book_title, price, status, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                order["book_id"],
                order["book_title"],
                order["price"],
                order.get("status", "completed"),
                order["created_at"],
            ),
        )
        conn.commit()
        print(f"[{REPLICA_NAME}] Applied synced order for book {order['book_id']}", flush=True)
    finally:
        conn.close()

    return jsonify({"success": True, "message": "order synced"})


@app.route("/orders", methods=["GET"])
def list_orders():
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM orders ORDER BY id").fetchall()
        return jsonify([row_to_dict(row) for row in rows])
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=ORDER_PORT)
    args = parser.parse_args()
    port = args.port or ORDER_PORT
    init_db()
    print(f"[{REPLICA_NAME}] Starting on port {port}", flush=True)
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
