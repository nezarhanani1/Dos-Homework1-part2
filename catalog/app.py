import argparse
import os
import sqlite3
import threading

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

# --- Lab 2: configurable replica (port, name, peer, frontend for cache invalidation) ---
CATALOG_PORT = int(os.environ.get("CATALOG_PORT", "5001"))
REPLICA_NAME = os.environ.get("REPLICA_NAME", f"catalog-replica-{CATALOG_PORT}")
PEER_CATALOG_URL = os.environ.get("PEER_CATALOG_URL", "")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://127.0.0.1:5000")
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "5"))

DB_PATH = os.path.join(
    os.path.dirname(__file__), "data", f"catalog_{CATALOG_PORT}.db"
)
stock_lock = threading.Lock()

# All 7 books: Lab 1 (4) + Lab 2 (3 new)
SEED_BOOKS = [
    (1, "How to get a good grade in DOS in 40 minutes a day", "distributed systems", 10, 100),
    (2, "RPCs for Noobs", "distributed systems", 10, 50),
    (3, "Xen and the Art of Surviving Undergraduate School", "undergraduate school", 10, 80),
    (4, "Cooking for the Impatient Undergrad", "undergraduate school", 10, 40),
    (5, "How to finish Project 3 on time", "distributed systems", 10, 120),
    (6, "Why theory classes are so hard.", "theory", 10, 90),
    (7, "Spring in the Pioneer Valley", "spring", 10, 60),
]


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create DB, seed if empty, and insert any missing Lab 2 books."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                topic TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price INTEGER NOT NULL
            )
            """
        )
        count = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO books (id, title, topic, quantity, price) VALUES (?, ?, ?, ?, ?)",
                SEED_BOOKS,
            )
            conn.commit()
            print(f"[{REPLICA_NAME}] Database seeded with {len(SEED_BOOKS)} books", flush=True)
        else:
            # Safe migration: add new books if they are missing
            existing_ids = {
                row[0]
                for row in conn.execute("SELECT id FROM books").fetchall()
            }
            added = 0
            for book in SEED_BOOKS:
                if book[0] not in existing_ids:
                    conn.execute(
                        "INSERT INTO books (id, title, topic, quantity, price) VALUES (?, ?, ?, ?, ?)",
                        book,
                    )
                    added += 1
            if added:
                conn.commit()
                print(f"[{REPLICA_NAME}] Added {added} missing book(s) to catalog", flush=True)
    finally:
        conn.close()


def reseed_db():
    """Reset all books to seed quantities (for testing). POST /admin/reseed"""
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM books")
        conn.executemany(
            "INSERT INTO books (id, title, topic, quantity, price) VALUES (?, ?, ?, ?, ?)",
            SEED_BOOKS,
        )
        conn.commit()
        print(f"[{REPLICA_NAME}] Catalog reseeded", flush=True)
    finally:
        conn.close()


def row_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "topic": row["topic"],
        "quantity": row["quantity"],
        "price": row["price"],
    }


def invalidate_frontend_cache(item_id):
    """Push cache invalidation to frontend before writes (strong consistency)."""
    try:
        requests.post(
            f"{FRONTEND_URL}/cache/invalidate/{item_id}",
            timeout=REQUEST_TIMEOUT,
        )
        print(f"[{REPLICA_NAME}] Invalidated frontend cache for item {item_id}", flush=True)
    except requests.RequestException as exc:
        print(
            f"[{REPLICA_NAME}] Warning: frontend cache invalidation failed: {exc}",
            flush=True,
        )


def sync_to_peer(item_id, payload):
    """Forward stock update to peer replica; peer /sync/update does not forward again."""
    if not PEER_CATALOG_URL:
        return
    try:
        requests.post(
            f"{PEER_CATALOG_URL}/sync/update/{item_id}",
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        print(f"[{REPLICA_NAME}] Synced update for item {item_id} to peer", flush=True)
    except requests.RequestException as exc:
        print(f"[{REPLICA_NAME}] Warning: peer sync failed: {exc}", flush=True)


def apply_update(item_id, data):
    """Apply quantity/price update locally. Returns (dict, status_code) or (error_dict, code)."""
    with stock_lock:
        conn = get_db_connection()
        try:
            row = conn.execute("SELECT * FROM books WHERE id = ?", (item_id,)).fetchone()
            if row is None:
                return {"error": "Book not found"}, 404

            quantity = row["quantity"]
            if "quantity_change" in data:
                change = data["quantity_change"]
                new_quantity = quantity + change
                if new_quantity < 0:
                    return {"error": "Quantity cannot be negative"}, 400
                conn.execute(
                    "UPDATE books SET quantity = ? WHERE id = ?",
                    (new_quantity, item_id),
                )
                print(
                    f"[{REPLICA_NAME}] Updated quantity for item {item_id} by {change}",
                    flush=True,
                )

            if "price" in data:
                conn.execute(
                    "UPDATE books SET price = ? WHERE id = ?",
                    (data["price"], item_id),
                )
                print(
                    f"[{REPLICA_NAME}] Updated price for item {item_id} to {data['price']}",
                    flush=True,
                )

            conn.commit()
            updated = conn.execute(
                "SELECT * FROM books WHERE id = ?", (item_id,)
            ).fetchone()
            return row_to_dict(updated), 200
        finally:
            conn.close()


@app.route("/health", methods=["GET"])
def health():
    return jsonify(
        {
            "service": "catalog",
            "status": "ok",
            "replica": REPLICA_NAME,
            "port": CATALOG_PORT,
        }
    )


@app.route("/search/<path:topic>", methods=["GET"])
def search(topic):
    print(f"[{REPLICA_NAME}] Search request for topic: {topic}", flush=True)
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT id, title, topic FROM books").fetchall()
        results = [
            {"id": row["id"], "title": row["title"]}
            for row in rows
            if row["topic"].lower() == topic.lower()
        ]
        return jsonify(results)
    finally:
        conn.close()


@app.route("/info/<int:item_id>", methods=["GET"])
def info(item_id):
    print(f"[{REPLICA_NAME}] Info request for item: {item_id}", flush=True)
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM books WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            return jsonify({"error": "Book not found"}), 404
        return jsonify(row_to_dict(row))
    finally:
        conn.close()


@app.route("/update/<int:item_id>", methods=["POST"])
def update(item_id):
    """Public write: invalidate cache, update locally, sync to peer."""
    data = request.get_json(silent=True) or {}
    if data.get("sync"):
        return jsonify({"error": "Use /sync/update for replicated writes"}), 400

    invalidate_frontend_cache(item_id)
    result, code = apply_update(item_id, data)
    if code == 200:
        sync_to_peer(item_id, data)
    return jsonify(result), code


@app.route("/sync/update/<int:item_id>", methods=["POST"])
def sync_update(item_id):
    """Internal sync from peer — apply locally only, no re-forward (avoids loops)."""
    data = request.get_json(silent=True) or {}
    print(f"[{REPLICA_NAME}] Applying sync update for item {item_id}", flush=True)
    result, code = apply_update(item_id, data)
    return jsonify(result), code


@app.route("/admin/reseed", methods=["POST"])
def admin_reseed():
    """Reset catalog to seed data (testing)."""
    reseed_db()
    return jsonify({"success": True, "message": f"{REPLICA_NAME} catalog reseeded"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=CATALOG_PORT)
    args = parser.parse_args()
    port = args.port or CATALOG_PORT
    init_db()
    print(f"[{REPLICA_NAME}] Starting on port {port}", flush=True)
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
