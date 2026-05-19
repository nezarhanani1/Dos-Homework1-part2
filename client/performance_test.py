"""
Lab 2 performance measurements.
Run with all 5 services up (2 catalog, 2 order, 1 frontend).

  py -3 client/performance_test.py

Results: docs/performance_results.csv and docs/performance_results.md
Optional chart: docs/performance_plot.png (if matplotlib installed)
"""

import csv
import os
import statistics
import time
from pathlib import Path

import requests

FRONTEND = os.environ.get("FRONTEND_URL", "http://127.0.0.1:5000")
RUNS = int(os.environ.get("PERF_RUNS", "10"))
ITEM_ID = int(os.environ.get("PERF_ITEM_ID", "1"))
DOCS = Path(__file__).resolve().parent.parent / "docs"


def timed_request(method, url, **kwargs):
    start = time.perf_counter()
    resp = requests.request(method, url, timeout=15, **kwargs)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return resp, elapsed_ms


def run_test(name, fn, runs=RUNS):
    times = []
    notes = ""
    for i in range(runs):
        try:
            ms = fn()
            times.append(ms)
        except Exception as exc:
            notes = str(exc)
            break
    if not times:
        return {
            "test_name": name,
            "runs": 0,
            "average_ms": 0,
            "min_ms": 0,
            "max_ms": 0,
            "notes": notes or "failed",
        }
    return {
        "test_name": name,
        "runs": len(times),
        "average_ms": round(statistics.mean(times), 2),
        "min_ms": round(min(times), 2),
        "max_ms": round(max(times), 2),
        "notes": notes,
    }


def clear_cache():
    requests.delete(f"{FRONTEND}/cache/clear", timeout=10)


def reseed_catalogs():
    for port in (5001, 5003):
        try:
            requests.post(f"http://127.0.0.1:{port}/admin/reseed", timeout=10)
        except requests.RequestException:
            pass


def main():
    print("Bazar.com Lab 2 — Performance Test")
    print(f"Frontend: {FRONTEND}  Runs per test: {RUNS}\n")

    reseed_catalogs()
    clear_cache()

    results = []

    # 1) Info without cache (always miss after clear)
    def info_miss():
        clear_cache()
        _, ms = timed_request("GET", f"{FRONTEND}/info/{ITEM_ID}")
        return ms

    results.append(run_test("GET /info (cache miss)", info_miss))

    # 2) Info with cache (warm then hit)
    def info_hit():
        requests.get(f"{FRONTEND}/info/{ITEM_ID}", timeout=10)
        _, ms = timed_request("GET", f"{FRONTEND}/info/{ITEM_ID}")
        return ms

    results.append(run_test("GET /info (cache hit)", info_hit))

    # 3) Search cache miss
    def search_miss():
        clear_cache()
        _, ms = timed_request(
            "GET", f"{FRONTEND}/search/distributed%20systems"
        )
        return ms

    results.append(run_test("GET /search (cache miss)", search_miss))

    # 4) Search cache hit
    def search_hit():
        requests.get(f"{FRONTEND}/search/distributed%20systems", timeout=10)
        _, ms = timed_request(
            "GET", f"{FRONTEND}/search/distributed%20systems"
        )
        return ms

    results.append(run_test("GET /search (cache hit)", search_hit))

    # 5) Purchase (fewer runs to save stock)
    purchase_runs = min(3, RUNS)

    def purchase():
        reseed_catalogs()
        clear_cache()
        _, ms = timed_request("POST", f"{FRONTEND}/purchase/{ITEM_ID}")
        return ms

    results.append(
        run_test("POST /purchase", purchase, runs=purchase_runs)
    )

    # 6) Miss after invalidation
    def after_invalidation():
        requests.get(f"{FRONTEND}/info/{ITEM_ID}", timeout=10)
        requests.post(f"{FRONTEND}/purchase/{ITEM_ID}", timeout=15)
        _, ms = timed_request("GET", f"{FRONTEND}/info/{ITEM_ID}")
        return ms

    results.append(
        run_test("GET /info after purchase (invalidated)", after_invalidation)
    )

    DOCS.mkdir(exist_ok=True)
    csv_path = DOCS / "performance_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "test_name",
                "runs",
                "average_ms",
                "min_ms",
                "max_ms",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(results)

    md_path = DOCS / "performance_results.md"
    lines = [
        "# Performance Results — Lab 2\n",
        f"Frontend: `{FRONTEND}`  |  Runs: {RUNS} (purchase: {purchase_runs})\n",
        "| Test | Runs | Avg Response Time (ms) | Min | Max | Notes |",
        "|------|------|-------------------------|-----|-----|-------|",
    ]
    for r in results:
        lines.append(
            f"| {r['test_name']} | {r['runs']} | {r['average_ms']} | "
            f"{r['min_ms']} | {r['max_ms']} | {r['notes']} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    try:
        import matplotlib.pyplot as plt

        names = [r["test_name"][:28] for r in results]
        avgs = [r["average_ms"] for r in results]
        plt.figure(figsize=(10, 5))
        plt.bar(names, avgs, color="#e94560")
        plt.ylabel("Avg response time (ms)")
        plt.title("Bazar.com Lab 2 Performance")
        plt.xticks(rotation=25, ha="right")
        plt.tight_layout()
        plot_path = DOCS / "performance_plot.png"
        plt.savefig(plot_path)
        print(f"Chart saved: {plot_path}")
    except ImportError:
        print("matplotlib not installed — skipped chart")

    print("\nResults:")
    for r in results:
        print(
            f"  {r['test_name']}: avg={r['average_ms']}ms "
            f"(min={r['min_ms']}, max={r['max_ms']})"
        )
    print(f"\nWrote {csv_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
