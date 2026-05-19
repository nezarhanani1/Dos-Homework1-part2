import os
import sys

import requests

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5000")
ORDER_URL = os.environ.get("ORDER_URL", "http://localhost:5002")
TIMEOUT = 5


def print_section(title):
    print(f"\n=== {title} ===")


def main():
    print("Bazar.com Client - Testing Frontend Service")
    print(f"Frontend URL: {FRONTEND_URL}")

    # 1. Health check
    print_section("Health Check")
    resp = requests.get(f"{FRONTEND_URL}/health", timeout=TIMEOUT)
    print(resp.json())

    # 2. Search distributed systems
    print_section("Search: distributed systems")
    resp = requests.get(
        f"{FRONTEND_URL}/search/distributed%20systems", timeout=TIMEOUT
    )
    for item in resp.json():
        print(f"{item['id']} - {item['title']}")

    # 3. Search undergraduate school
    print_section("Search: undergraduate school")
    resp = requests.get(
        f"{FRONTEND_URL}/search/undergraduate%20school", timeout=TIMEOUT
    )
    for item in resp.json():
        print(f"{item['id']} - {item['title']}")

    # 4. Info for item 2
    print_section("Info: Item 2")
    resp = requests.get(f"{FRONTEND_URL}/info/2", timeout=TIMEOUT)
    if resp.status_code == 200:
        data = resp.json()
        print(f"Title: {data['title']}")
        print(f"Quantity: {data['quantity']}")
        print(f"Price: {data['price']}")
    else:
        print(resp.json())

    # 5. Purchase item 2
    print_section("Purchase: Item 2")
    resp = requests.post(f"{FRONTEND_URL}/purchase/2", timeout=TIMEOUT)
    data = resp.json()
    if data.get("success"):
        print(data["message"])
    else:
        print(data)

    # 6. Info for item 2 again
    print_section("Info: Item 2 (after purchase)")
    resp = requests.get(f"{FRONTEND_URL}/info/2", timeout=TIMEOUT)
    if resp.status_code == 200:
        data = resp.json()
        print(f"Title: {data['title']}")
        print(f"Quantity: {data['quantity']}")
        print(f"Price: {data['price']}")
    else:
        print(resp.json())

    # 7. Invalid item purchase
    print_section("Purchase: Invalid Item 999")
    resp = requests.post(f"{FRONTEND_URL}/purchase/999", timeout=TIMEOUT)
    print(resp.json())

    # 8. List orders from order service
    print_section("Orders (from Order Service)")
    print(f"Note: Orders are listed directly from {ORDER_URL}/orders")
    try:
        resp = requests.get(f"{ORDER_URL}/orders", timeout=TIMEOUT)
        orders = resp.json()
        if orders:
            for order in orders:
                print(
                    f"Order #{order['id']}: {order['book_title']} "
                    f"(${order['price']}) - {order['status']} at {order['created_at']}"
                )
        else:
            print("No orders yet.")
    except requests.RequestException as exc:
        print(f"Could not reach order service: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
