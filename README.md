# Bazar.com — Multi-tier Online Book Store  
## Lab 1 + Lab 2: Microservices, Replication, Caching and Consistency

Bazar.com is a small distributed online bookstore project for the **Distributed and Operating Systems** course.  
The project starts in **Lab 1** as a three-service microservices system, then extends in **Lab 2** with **replication**, **frontend caching**, **Round Robin load balancing**, **cache invalidation**, and **performance measurements**.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Lab 1 Requirements Covered](#lab-1-requirements-covered)
- [Lab 2 Requirements Covered](#lab-2-requirements-covered)
- [Architecture](#architecture)
- [Services](#services)
- [Books Catalog](#books-catalog)
- [Project Structure](#project-structure)
- [Technologies Used](#technologies-used)
- [API Documentation](#api-documentation)
- [How the System Works](#how-the-system-works)
- [Caching and Cache Invalidation](#caching-and-cache-invalidation)
- [Round Robin Load Balancing](#round-robin-load-balancing)
- [Replication and Consistency](#replication-and-consistency)
- [How to Run Lab 1 with Docker Compose](#how-to-run-lab-1-with-docker-compose)
- [How to Run Lab 2 Locally](#how-to-run-lab-2-locally)
- [Testing with curl](#testing-with-curl)
- [Python Client](#python-client)
- [Performance Test](#performance-test)
- [Documentation Files](#documentation-files)
- [Known Limitations](#known-limitations)
- [Possible Improvements](#possible-improvements)

---

## Project Overview

The system simulates a small online bookstore. A user can:

1. **Search** books by topic.
2. View **book information** by item ID.
3. **Purchase** a book.
4. Observe that inventory decreases after purchase.
5. In Lab 2, observe cache hits/misses and replicated backend services.

The main goal is not building a production bookstore, but demonstrating important distributed systems concepts:

- Multi-tier architecture
- Microservices
- REST communication
- Persistent data storage
- Replication
- Load balancing
- Caching
- Cache consistency
- Basic performance evaluation

---

## Lab 1 Requirements Covered

Lab 1 builds the base version of **Bazar.com** using three independent services.

### Implemented Lab 1 Features

- Three separate Flask microservices:
  - Frontend Service
  - Catalog Service
  - Order Service
- REST APIs for:
  - `search(topic)`
  - `info(item_number)`
  - `purchase(item_number)`
  - catalog `update(item_number)`
- Persistent storage using SQLite.
- Docker Compose setup for the basic three-service version.
- Python test client.
- Sample output and design document under `docs/`.
- Purchase flow prints the required message:

```text
bought book <book_name>
```

---

## Lab 2 Requirements Covered

Lab 2 extends the system to handle higher workload using caching and replication.

### Implemented Lab 2 Features

- Added **3 new books**, making the catalog contain **7 books**.
- Two Catalog replicas:
  - Catalog Replica 1 on port `5001`
  - Catalog Replica 2 on port `5003`
- Two Order replicas:
  - Order Replica 1 on port `5002`
  - Order Replica 2 on port `5004`
- Frontend remains a single service on port `5000`.
- Frontend includes an in-memory **LRU cache**.
- Cache is used only for read requests:
  - `GET /search/<topic>`
  - `GET /info/<id>`
- Write requests are never served from cache:
  - `POST /purchase/<id>`
  - `POST /update/<id>`
- Round Robin load balancing across replicas.
- Failover if a replica is down.
- Cache invalidation after purchase/update.
- Internal synchronization routes between replicas.
- Performance test script that generates:
  - `docs/performance_results.csv`
  - `docs/performance_results.md`
  - `docs/performance_plot.png` if matplotlib is installed

---

## Architecture

### Lab 1 Architecture

```text
Client / Browser / curl
        |
        v
Frontend Service :5000
        |
        |---- search/info ----> Catalog Service :5001
        |
        |---- purchase -------> Order Service :5002
                                      |
                                      |---- info/update ----> Catalog Service :5001
```

### Lab 2 Architecture

```text
Client / Browser / curl
        |
        v
Frontend Service :5000
        |
        |-- In-Memory LRU Cache
        |
        |-- Round Robin / Failover --> Catalog Replica 1 :5001
        |-- Round Robin / Failover --> Catalog Replica 2 :5003
        |
        |-- Round Robin / Failover --> Order Replica 1 :5002
        |-- Round Robin / Failover --> Order Replica 2 :5004
                                             |
                                             |-- Round Robin --> Catalog Replicas
```

---

## Services

### 1. Frontend Service

**Port:** `5000`

The frontend is the public entry point.  
Clients should send requests to the frontend, not directly to backend services.

Responsibilities:

- Provides the web UI.
- Exposes public REST APIs.
- Checks cache before forwarding read requests.
- Uses Round Robin to choose backend replicas.
- Invalidates cache after successful purchases.
- Adds debug metadata such as `served_by` and `cache`.

Important file:

```text
frontend/app.py
```

Important Lab 2 functions:

```python
next_replica(...)
request_with_failover(...)
cache_get(...)
cache_set(...)
invalidate_cache_for_item(...)
```

---

### 2. Catalog Service

**Lab 1 port:** `5001`  
**Lab 2 ports:** `5001`, `5003`

The Catalog service owns book data and inventory.

Responsibilities:

- Stores books.
- Searches by topic.
- Returns item details.
- Updates price or quantity.
- In Lab 2, syncs updates to the peer catalog replica.
- Sends invalidate requests to the frontend before writes.

Important file:

```text
catalog/app.py
```

---

### 3. Order Service

**Lab 1 port:** `5002`  
**Lab 2 ports:** `5002`, `5004`

The Order service handles purchases.

Responsibilities:

- Receives purchase requests.
- Checks book stock through Catalog.
- Decrements stock through Catalog update API.
- Saves completed orders.
- In Lab 2, syncs completed orders to the peer order replica.

Important file:

```text
order/app.py
```

---

## Books Catalog

### Original Lab 1 Books

| ID | Title | Topic |
|----|-------|-------|
| 1 | How to get a good grade in DOS in 40 minutes a day | distributed systems |
| 2 | RPCs for Noobs | distributed systems |
| 3 | Xen and the Art of Surviving Undergraduate School | undergraduate school |
| 4 | Cooking for the Impatient Undergrad | undergraduate school |

### New Lab 2 Books

| ID | Title | Topic |
|----|-------|-------|
| 5 | How to finish Project 3 on time | distributed systems |
| 6 | Why theory classes are so hard. | theory |
| 7 | Spring in the Pioneer Valley | spring |

---

## Project Structure

```text
bazar-bookstore/
├── frontend/
│   ├── app.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── templates/
│       └── index.html
│
├── catalog/
│   ├── app.py
│   ├── reseed_catalog.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── data/
│       └── catalog_*.db        # created at runtime
│
├── order/
│   ├── app.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── data/
│       └── orders_*.db         # created at runtime
│
├── client/
│   ├── client.py
│   └── performance_test.py
│
├── docs/
│   ├── design.md
│   ├── design_document.md
│   ├── run_instructions.md
│   ├── sample-output.txt
│   ├── sample_output.md
│   ├── performance_results.csv
│   └── performance_results.md
│
├── docker-compose.yml
├── README.md
└── .gitignore
```

SQLite database files are created automatically at runtime and should not be committed to GitHub.

---

## Technologies Used

- Python 3
- Flask
- requests
- SQLite
- Docker
- Docker Compose
- PowerShell / curl
- matplotlib for optional performance chart generation

---

## API Documentation

## Frontend Service — Port 5000

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Web UI |
| GET | `/api` | JSON welcome and route list |
| GET | `/health` | Frontend health check |
| GET | `/search/<topic>` | Search books by topic, cached in Lab 2 |
| GET | `/info/<item_id>` | Get book details, cached in Lab 2 |
| POST | `/purchase/<item_id>` | Purchase book |
| GET | `/cache/status` | Show current cache keys |
| DELETE | `/cache/clear` | Clear all cache entries |
| DELETE/POST | `/cache/invalidate/<item_id>` | Remove stale cache entries for an item |
| GET | `/proxy/health/all` | Check health of frontend and replicas |

---

## Catalog Service — Ports 5001 and 5003

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Catalog health check |
| GET | `/search/<topic>` | Search books by topic |
| GET | `/info/<item_id>` | Get full book record |
| POST | `/update/<item_id>` | Update quantity or price |
| POST | `/sync/update/<item_id>` | Internal peer-replication update |
| POST | `/admin/reseed` | Reset catalog data for testing |

Example update body:

```json
{
  "quantity_change": -1
}
```

or:

```json
{
  "price": 75
}
```

---

## Order Service — Ports 5002 and 5004

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Order health check |
| POST | `/purchase/<item_id>` | Process purchase |
| POST | `/sync/order` | Internal peer order sync |
| GET | `/orders` | List stored orders |

---

## How the System Works

### Search Flow

```text
User -> Frontend -> Cache check
                  -> if HIT: return cached result
                  -> if MISS: choose catalog replica using Round Robin
                             -> Catalog returns books
                             -> Frontend stores result in cache
                             -> User receives result
```

### Info Flow

```text
User -> Frontend -> Cache check
                  -> if HIT: return cached item info
                  -> if MISS: choose catalog replica
                             -> Catalog returns item info
                             -> Frontend caches item info
                             -> User receives result
```

### Purchase Flow

```text
User -> Frontend
     -> choose order replica using Round Robin
     -> Order checks stock from Catalog
     -> Order asks Catalog to decrement quantity
     -> Catalog invalidates frontend cache
     -> Catalog updates local database
     -> Catalog syncs update to peer catalog replica
     -> Order saves completed order
     -> Order syncs order to peer order replica
     -> Frontend invalidates cache for the purchased item
     -> User receives purchase result
```

Successful purchase message:

```text
bought book RPCs for Noobs
```

---

## Caching and Cache Invalidation

The frontend uses an in-memory LRU cache:

```python
memory_cache = OrderedDict()
CACHE_MAX_SIZE = 10
```

### Cached Requests

Only read requests are cached:

```text
GET /search/<topic>
GET /info/<item_id>
```

### Not Cached

Write requests are not cached:

```text
POST /purchase/<item_id>
POST /update/<item_id>
```

### Cache HIT

If the user requests a book already in cache:

```text
Frontend -> Cache HIT -> response returned immediately
```

### Cache MISS

If the book is not in cache:

```text
Frontend -> Cache MISS -> Catalog Replica -> cache_set(...) -> response
```

### Invalidation

When stock changes, stale cache must be removed.  
The project removes:

- `info:<item_id>`
- all `search:*` cache keys, because search results may include stock-related or stale list data.

Important function:

```python
invalidate_cache_for_item(item_id)
```

Frontend invalidates cache after a successful purchase.  
Catalog also sends invalidation to the frontend before applying writes.

---

## Round Robin Load Balancing

Round Robin is implemented in the frontend using indexes:

```python
catalog_rr_index = 0
order_rr_index = 0
```

Every new request chooses the next replica:

```text
Request 1 -> catalog replica 1
Request 2 -> catalog replica 2
Request 3 -> catalog replica 1
Request 4 -> catalog replica 2
```

Important function:

```python
next_replica(replicas, lock, counter_name)
```

The system also supports failover through:

```python
request_with_failover(...)
```

If one replica fails, the frontend tries the next replica.

---

## Replication and Consistency

### Catalog Replication

Catalog replicas keep inventory synchronized using:

```text
POST /sync/update/<item_id>
```

When one catalog replica receives a write:

1. It invalidates frontend cache.
2. It updates its local SQLite database.
3. It forwards the update to the peer catalog replica.

### Order Replication

Order replicas sync completed orders using:

```text
POST /sync/order
```

When one order replica completes a purchase:

1. It stores the order locally.
2. It sends the order to the peer order replica.

This demonstrates basic replicated state synchronization.

---

## How to Run Lab 1 with Docker Compose

The included `docker-compose.yml` runs the original Lab 1 style deployment with three services:

- Frontend on `5000`
- Catalog on `5001`
- Order on `5002`

From the project root:

```bash
docker compose up --build
```

Then open:

```text
http://localhost:5000
```

Stop with:

```bash
Ctrl + C
```

Run detached:

```bash
docker compose up --build -d
```

Stop detached containers:

```bash
docker compose down
```

> Note: The current Docker Compose file runs the basic single-catalog/single-order setup.  
> For the full Lab 2 replica setup, use the manual multi-terminal commands below.

---

## How to Run Lab 2 Locally

Open **5 terminals** and run the following commands.

> Use your actual project folder path.  
> The examples below assume you are in the project root.

---

### Terminal 1 — Catalog Replica 1

```powershell
cd catalog
$env:CATALOG_PORT="5001"
$env:REPLICA_NAME="catalog-replica-1"
$env:PEER_CATALOG_URL="http://127.0.0.1:5003"
$env:FRONTEND_URL="http://127.0.0.1:5000"
py -3 app.py
```

---

### Terminal 2 — Catalog Replica 2

```powershell
cd catalog
$env:CATALOG_PORT="5003"
$env:REPLICA_NAME="catalog-replica-2"
$env:PEER_CATALOG_URL="http://127.0.0.1:5001"
$env:FRONTEND_URL="http://127.0.0.1:5000"
py -3 app.py
```

---

### Terminal 3 — Order Replica 1

```powershell
cd order
$env:ORDER_PORT="5002"
$env:REPLICA_NAME="order-replica-1"
$env:PEER_ORDER_URL="http://127.0.0.1:5004"
$env:CATALOG_REPLICAS="http://127.0.0.1:5001,http://127.0.0.1:5003"
py -3 app.py
```

---

### Terminal 4 — Order Replica 2

```powershell
cd order
$env:ORDER_PORT="5004"
$env:REPLICA_NAME="order-replica-2"
$env:PEER_ORDER_URL="http://127.0.0.1:5002"
$env:CATALOG_REPLICAS="http://127.0.0.1:5001,http://127.0.0.1:5003"
py -3 app.py
```

---

### Terminal 5 — Frontend

```powershell
cd frontend
$env:CATALOG_REPLICAS="http://127.0.0.1:5001,http://127.0.0.1:5003"
$env:ORDER_REPLICAS="http://127.0.0.1:5002,http://127.0.0.1:5004"
py -3 app.py
```

Open:

```text
http://127.0.0.1:5000
```

---

## Testing with curl

### Health Checks

```powershell
curl http://127.0.0.1:5000/health
curl http://127.0.0.1:5001/health
curl http://127.0.0.1:5002/health
curl http://127.0.0.1:5003/health
curl http://127.0.0.1:5004/health
```

Check all through frontend:

```powershell
curl http://127.0.0.1:5000/proxy/health/all
```

---

### Search

```powershell
curl "http://127.0.0.1:5000/search/distributed%20systems"
```

Expected result contains books like:

```json
[
  {
    "id": 1,
    "title": "How to get a good grade in DOS in 40 minutes a day"
  },
  {
    "id": 2,
    "title": "RPCs for Noobs"
  }
]
```

---

### Info

```powershell
curl http://127.0.0.1:5000/info/2
```

Example response:

```json
{
  "id": 2,
  "title": "RPCs for Noobs",
  "topic": "distributed systems",
  "quantity": 5,
  "price": 50,
  "served_by": "catalog-replica-5001",
  "cache": "miss"
}
```

Run the same command again and it should return:

```json
"cache": "hit"
```

---

### Purchase

```powershell
curl -X POST http://127.0.0.1:5000/purchase/2
```

Example response:

```json
{
  "success": true,
  "message": "bought book RPCs for Noobs",
  "served_by": "order-replica-5002",
  "cache": "invalidated"
}
```

After purchase, check item again:

```powershell
curl http://127.0.0.1:5000/info/2
```

The quantity should be decreased by one.

---

### Cache Status

```powershell
curl http://127.0.0.1:5000/cache/status
```

Clear cache:

```powershell
curl -X DELETE http://127.0.0.1:5000/cache/clear
```

Invalidate one item:

```powershell
curl -X DELETE http://127.0.0.1:5000/cache/invalidate/2
```

---

## Python Client

With services running:

```powershell
py -3 client/client.py
```

The client tests:

- Health check
- Search distributed systems
- Search undergraduate school
- Info item 2
- Purchase item 2
- Info item 2 after purchase
- Invalid purchase
- Order listing

---

## Performance Test

Lab 2 requires measurements for caching and consistency overhead.

Run:

```powershell
py -3 client/performance_test.py
```

The script measures:

- `GET /info` cache miss
- `GET /info` cache hit
- `GET /search` cache miss
- `GET /search` cache hit
- `POST /purchase`
- `GET /info` after purchase invalidation

Generated files:

```text
docs/performance_results.csv
docs/performance_results.md
docs/performance_plot.png
```

The expected conclusion is:

- Cache hits should be faster than cache misses.
- Purchase requests are slower than reads because they require writes and replica synchronization.
- After cache invalidation, the next read becomes a cache miss and is slower than a cache hit.

---

## Documentation Files

| File | Purpose |
|------|---------|
| `docs/design.md` | Original Lab 1 design document |
| `docs/design_document.md` | Lab 2 design document |
| `docs/run_instructions.md` | Detailed local run instructions |
| `docs/sample-output.txt` | Lab 1 style sample output |
| `docs/sample_output.md` | Lab 2 sample output |
| `docs/performance_results.csv` | Raw measurement data |
| `docs/performance_results.md` | Markdown performance table |
| `docs/performance_plot.png` | Optional generated graph |

---

## Known Limitations

- The current Docker Compose file runs the basic Lab 1 deployment, not the full 5-service Lab 2 replica topology.
- This project uses simple peer-to-peer synchronization, not a full consensus protocol.
- If a replica is down during a sync request, it may miss updates until manually reseeded or restarted with consistent data.
- SQLite is suitable for this lab but not ideal for high-concurrency production systems.
- No authentication or authorization is implemented.
- No real payment system exists.
- The frontend is not replicated, as required by the lab specification.
- Cache is in-memory, so it is lost when the frontend restarts.

---

## Possible Improvements

- Add a full Lab 2 Docker Compose file with five containers.
- Add retry queue for failed replica synchronization.
- Add stronger consistency using a primary/backup protocol or consensus.
- Add timestamps or version numbers to catalog records.
- Add structured logging.
- Add automated tests.
- Add API request tracing.
- Add authentication for admin endpoints.
- Replace manual terminal startup with scripts.
- Add CI workflow on GitHub.

---

## Quick Demo Script

Use this sequence during discussion or demo:

```powershell
curl http://127.0.0.1:5000/proxy/health/all
curl "http://127.0.0.1:5000/search/distributed%20systems"
curl http://127.0.0.1:5000/info/2
curl http://127.0.0.1:5000/info/2
curl http://127.0.0.1:5000/cache/status
curl -X POST http://127.0.0.1:5000/purchase/2
curl http://127.0.0.1:5000/info/2
py -3 client/performance_test.py
```

What to explain:

1. First `info` request is a **cache miss**.
2. Second `info` request is a **cache hit**.
3. Purchase goes to an **order replica**.
4. Order calls a **catalog replica** to update stock.
5. Cache is **invalidated** after purchase.
6. Next `info` request becomes a **cache miss** again.
7. Performance test shows cache improvement.

---

## Student Explanation

This project demonstrates how a distributed application can be divided into small services. The frontend acts as the user-facing gateway, while the catalog service owns inventory data and the order service owns purchase history. In Lab 2, replication improves availability and load distribution, while caching improves read latency. Because cached data can become stale after purchases or stock updates, the project uses cache invalidation to maintain consistency.

The most important distributed systems concepts shown here are **service separation**, **REST communication**, **replication**, **load balancing**, **cache consistency**, and **performance measurement**.
