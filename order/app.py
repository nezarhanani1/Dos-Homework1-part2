import os
import sqlite3
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify

app = Flask(__name__)

CATALOG_URL = os.environ.get("CATALOG_URL", "http://localhost:5001")
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "orders.db")
REQUEST_TIMEOUT = 10


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


def catalog_unavailable():
    return jsonify({"success": False, "message": "Catalog service unavailable"}), 503


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"service": "order", "status": "ok"})


@app.route("/purchase/<int:item_id>", methods=["POST"])
def purchase(item_id):
    print(f"[Order] Purchase request for item {item_id}", flush=True)
    print("[Order] Checking stock through Catalog Service", flush=True)

    try:
        info_resp = requests.get(
            f"{CATALOG_URL}/info/{item_id}", timeout=REQUEST_TIMEOUT
        )
    except requests.RequestException:
        return catalog_unavailable()

    if info_resp.status_code == 404:
        return jsonify({"success": False, "message": "Book not found"}), 404

    if info_resp.status_code != 200:
        return catalog_unavailable()

    book = info_resp.json()
    if book.get("quantity", 0) <= 0:
        return jsonify({"success": False, "message": "Book is out of stock"}), 400

    try:
        update_resp = requests.post(
            f"{CATALOG_URL}/update/{item_id}",
            json={"quantity_change": -1},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException:
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
    print(f"[Order] {message}", flush=True)
    print(message, flush=True)

    return jsonify({"success": True, "message": message, "order": order})


@app.route("/orders", methods=["GET"])
def list_orders():
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM orders ORDER BY id").fetchall()
        return jsonify([row_to_dict(row) for row in rows])
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5002, debug=False, threaded=True)
