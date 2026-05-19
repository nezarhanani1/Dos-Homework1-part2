# Bazar.com Lab 2 — Design Document

## 1. Overview

Bazar.com is a microservices online bookstore originally built for DOS Lab 1. Lab 2 extends the system with **replication**, an **in-memory cache**, **Round Robin load balancing**, and **cache invalidation** for consistency after purchases.

The goal is to show how distributed techniques improve scalability and response time while keeping the implementation small enough for a university homework project.

## 2. Architecture

```
Client / Browser UI
        |
        v
Frontend (:5000)
  |-- In-memory LRU cache (max 10 entries)
  |-- Round Robin --> Catalog Replica 1 (:5001)
  |-- Round Robin --> Catalog Replica 2 (:5003)
  |-- Round Robin --> Order Replica 1 (:5002)
  \-- Round Robin --> Order Replica 2 (:5004)

Catalog replicas sync stock via POST /sync/update
Order replicas sync orders via POST /sync/order
Catalog invalidates frontend cache via POST /cache/invalidate before writes
```

| Component | Role |
|-----------|------|
| Frontend | Gateway, cache, load balancer |
| Catalog (×2) | Book catalog + inventory (SQLite each) |
| Order (×2) | Purchases + order history (SQLite each) |

## 3. Request Flow

### Search

1. Client → `GET /search/<topic>` on Frontend.
2. Frontend checks cache key `search:<topic>`.
3. **Hit:** return cached list (header `X-Cache: hit`).
4. **Miss:** Round Robin to a catalog replica, store result, return (header `X-Cache: miss`).

### Info

1. Client → `GET /info/<id>`.
2. Cache key `info:<id>`.
3. Same hit/miss logic as search.
4. On hit, JSON includes `"cache": "hit"` and `served_by`.

### Purchase

1. Client → `POST /purchase/<id>` on Frontend.
2. Frontend Round Robin to an order replica.
3. Order replica Round Robin to a catalog replica: `GET /info`, then `POST /update` (quantity −1).
4. Catalog invalidates frontend cache **before** local DB write, updates DB, syncs peer.
5. Order saves order locally, syncs peer order DB.
6. Frontend invalidates cache again on success.
7. Response includes `served_by` and `cache: invalidated`.

## 4. Caching Design

**Cached:** `GET /info/<id>`, `GET /search/<topic>`  
**Not cached:** `POST /purchase`, health, cache admin routes

| Operation | Behavior |
|-----------|----------|
| Cache hit | Faster response from memory |
| Cache miss | Forward to catalog replica, then store |
| LRU eviction | Max 10 keys; oldest removed when full |
| Clear | `DELETE /cache/clear` |
| Invalidate item | `DELETE /cache/invalidate/<id>` removes `info:id` and all `search:*` |

## 5. Replication Design

### Catalog

- Two processes, ports **5001** and **5003**.
- Separate SQLite files: `catalog_5001.db`, `catalog_5003.db`.
- After a write on replica A, A calls `POST /sync/update` on replica B.
- Sync endpoint applies locally only — **no re-forward** (prevents infinite loops).

### Order

- Two processes, ports **5002** and **5004**.
- Separate SQLite files: `orders_5002.db`, `orders_5004.db`.
- After a successful purchase, replica syncs order record to peer via `POST /sync/order`.

Replication improves **read scalability** (more catalog/order processes) and **availability** (failover to second replica).

## 6. Consistency Design

Cached book quantities can become **stale** after another client purchases the same book.

**Solution:**

1. Catalog calls `POST /cache/invalidate/<id>` on Frontend **before** updating stock.
2. Frontend invalidates `info:<id>` and all search cache keys after successful purchase.
3. Next read is a cache miss → fresh data from catalog.

This is a simplified **strong consistency** pattern suitable for the lab. Production systems might use TTLs, version numbers, or distributed caches (Redis).

## 7. Load Balancing

**Algorithm:** Round Robin with failover.

- Frontend maintains counters for catalog and order replica lists.
- Each request uses the next replica in rotation.
- If that replica fails (timeout/connection error), try the next until one succeeds.

**Why Round Robin?** Simple to implement and explain; distributes load evenly when requests are similar. It does not consider replica load or latency (unlike weighted or least-connections balancers).

## 8. Design Tradeoffs

| Choice | Benefit | Limitation |
|--------|---------|------------|
| In-memory cache | Very fast | Lost on frontend restart; not shared across frontends |
| Round Robin | Simple | Ignores actual load |
| SQLite per replica | Easy setup | Not ideal for true distributed writes |
| HTTP sync | Clear boundaries | Eventual consistency window if sync fails |
| Two catalog DBs | Independent deploy | Must sync on every stock change |

## 9. Possible Improvements

- Redis for shared cache
- Nginx/HAProxy as external load balancer
- Docker Compose for all replicas
- Centralized database with replication
- Vector clocks or consensus (Raft) for stock
- Metrics (Prometheus) and tracing

## 10. How to Run

See `docs/run_instructions.md` for exact PowerShell commands (5 terminals).

## 11. How to Test

**Browser UI:** http://127.0.0.1:5000/ — health, search, info, purchase, cache controls.

**curl:**

```bash
curl http://127.0.0.1:5000/health
curl http://127.0.0.1:5001/health
curl "http://127.0.0.1:5000/search/theory"
curl http://127.0.0.1:5000/info/6
curl -X POST http://127.0.0.1:5000/purchase/6
curl http://127.0.0.1:5000/cache/status
```

**Performance:** `py -3 client/performance_test.py`
