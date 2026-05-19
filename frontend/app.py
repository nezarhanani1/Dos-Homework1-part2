import os
from urllib.parse import quote

import requests
from flask import Flask, jsonify, render_template

app = Flask(__name__)

CATALOG_URL = os.environ.get("CATALOG_URL", "http://localhost:5001")
ORDER_URL = os.environ.get("ORDER_URL", "http://localhost:5002")
REQUEST_TIMEOUT = 10


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
            "ui": "Open http://localhost:5000/ in your browser",
            "endpoints": [
                "GET /search/<topic>",
                "GET /info/<item_id>",
                "POST /purchase/<item_id>",
            ],
        }
    )


@app.route("/search/<path:topic>", methods=["GET"])
def search(topic):
    print(f"[Frontend] Received search request for topic {topic}", flush=True)
    try:
        resp = requests.get(
            f"{CATALOG_URL}/search/{quote(topic)}", timeout=REQUEST_TIMEOUT
        )
    except requests.RequestException:
        return jsonify({"error": "Catalog service unavailable"}), 503

    if resp.status_code != 200:
        return jsonify({"error": "Catalog service unavailable"}), 503

    results = resp.json()
    for item in results:
        print(f"  {item['id']} - {item['title']}", flush=True)
    return jsonify(results)


@app.route("/info/<int:item_id>", methods=["GET"])
def info(item_id):
    print(f"[Frontend] Received info request for item {item_id}", flush=True)
    try:
        resp = requests.get(
            f"{CATALOG_URL}/info/{item_id}", timeout=REQUEST_TIMEOUT
        )
    except requests.RequestException:
        return jsonify({"error": "Catalog service unavailable"}), 503

    if resp.status_code == 503:
        return jsonify({"error": "Catalog service unavailable"}), 503

    data = resp.json()
    if resp.status_code == 200:
        print(
            f"  Title: {data['title']}, Quantity: {data['quantity']}, Price: {data['price']}",
            flush=True,
        )
    return jsonify(data), resp.status_code


@app.route("/purchase/<int:item_id>", methods=["POST"])
def purchase(item_id):
    print(f"[Frontend] Received purchase request for item {item_id}", flush=True)
    try:
        resp = requests.post(
            f"{ORDER_URL}/purchase/{item_id}", timeout=REQUEST_TIMEOUT
        )
    except requests.RequestException:
        return jsonify({"error": "Order service unavailable"}), 503

    if resp.status_code == 503:
        return jsonify(resp.json()), 503

    return jsonify(resp.json()), resp.status_code


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
