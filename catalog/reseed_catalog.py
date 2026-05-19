"""Reseed all catalog replicas. Usage: py -3 reseed_catalog.py"""

import requests

PORTS = [5001, 5003]

for port in PORTS:
    url = f"http://127.0.0.1:{port}/admin/reseed"
    try:
        r = requests.post(url, timeout=5)
        print(f"Port {port}: {r.json()}")
    except requests.RequestException as e:
        print(f"Port {port}: failed — {e}")
