import os
import sqlite3
import threading
from flask import Flask, jsonify, request

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "catalog.db")
stock_lock = threading.Lock()

SEED_BOOKS = [
    (1, "How to get a good grade in DOS in 40 minutes a day", "distributed systems", 5, 100),
    (2, "RPCs for Noobs", "distributed systems", 5, 50),
    (3, "Xen and the Art of Surviving Undergraduate School", "undergraduate school", 5, 80),
    (4, "Cooking for the Impatient Undergrad", "undergraduate school", 5, 40),
]


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
            print("[Catalog] Database seeded with 4 books", flush=True)
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


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"service": "catalog", "status": "ok"})


@app.route("/search/<path:topic>", methods=["GET"])
def search(topic):
    print(f"[Catalog] Search request for topic: {topic}", flush=True)
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
    print(f"[Catalog] Info request for item: {item_id}", flush=True)
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
    data = request.get_json(silent=True) or {}

    with stock_lock:
        conn = get_db_connection()
        try:
            row = conn.execute("SELECT * FROM books WHERE id = ?", (item_id,)).fetchone()
            if row is None:
                return jsonify({"error": "Book not found"}), 404

            quantity = row["quantity"]
            price = row["price"]

            if "quantity_change" in data:
                change = data["quantity_change"]
                new_quantity = quantity + change
                if new_quantity < 0:
                    return jsonify({"error": "Quantity cannot be negative"}), 400
                conn.execute(
                    "UPDATE books SET quantity = ? WHERE id = ?",
                    (new_quantity, item_id),
                )
                print(
                    f"[Catalog] Updated quantity for item {item_id} by {change}",
                    flush=True,
                )

            if "price" in data:
                price = data["price"]
                conn.execute(
                    "UPDATE books SET price = ? WHERE id = ?",
                    (price, item_id),
                )
                print(f"[Catalog] Updated price for item {item_id} to {price}", flush=True)

            conn.commit()
            updated = conn.execute("SELECT * FROM books WHERE id = ?", (item_id,)).fetchone()
            return jsonify(row_to_dict(updated))
        finally:
            conn.close()


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)
