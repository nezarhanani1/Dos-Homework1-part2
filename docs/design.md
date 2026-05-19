# Bazar.com — System Design Document

## 1. Overall Design

Bazar.com is a minimal distributed online bookstore implemented as three cooperating microservices. The design follows a classic **multi-tier architecture**:

1. **Presentation tier** — Frontend Service (API gateway)
2. **Application tier** — Order Service (business workflow)
3. **Data tier** — Catalog Service and Order Service each own their own SQLite database

Clients (browser, curl, Postman, or `client.py`) interact only with the Frontend. The Frontend never accesses databases directly; it delegates to Catalog and Order services using HTTP REST. This enforces **loose coupling** and demonstrates how real distributed systems are structured.

```
+----------+     HTTP      +----------+     HTTP      +----------+
|  Client  | ------------> | Frontend | ------------> | Catalog  |
+----------+               +----------+               +----------+
                                 |                          ^
                                 | HTTP                     | HTTP
                                 v                          |
                           +----------+                     |
                           |  Order   | ---------------------+
                           +----------+
                                 |
                                 v
                           orders.db
```

## 2. Microservice Descriptions

### Frontend Service (port 5000)

**Responsibility:** Public API gateway.

- Exposes `/`, `/health`, `/search/<topic>`, `/info/<item_id>`, `/purchase/<item_id>`
- Forwards search and info requests to Catalog
- Forwards purchase requests to Order
- Returns 503 if a backend service is unreachable
- Logs incoming requests and formatted results

**Configuration:** `CATALOG_URL`, `ORDER_URL` (defaults to localhost for local development)

### Catalog Service (port 5001)

**Responsibility:** Book catalog and inventory management.

- Stores four seed books in `catalog/data/catalog.db`
- Supports search by topic (case-insensitive)
- Returns full book info by ID
- Updates price or quantity via POST `/update/<item_id>`
- Uses a **threading lock** around stock updates to reduce race conditions

**Data model:**

| Column   | Type    | Description        |
|----------|---------|--------------------|
| id       | INTEGER | Primary key        |
| title    | TEXT    | Book title         |
| topic    | TEXT    | Category           |
| quantity | INTEGER | Stock count        |
| price    | INTEGER | Price in dollars   |

### Order Service (port 5002)

**Responsibility:** Purchase processing and order history.

- Orchestrates the purchase workflow by calling Catalog REST APIs
- Persists completed orders in `order/data/orders.db`
- Exposes `/orders` for inspection and testing

**Data model:**

| Column     | Type    | Description              |
|------------|---------|--------------------------|
| id         | INTEGER | Auto-increment primary key |
| book_id    | INTEGER | Purchased book ID        |
| book_title | TEXT    | Title at time of purchase |
| price      | INTEGER | Price at time of purchase |
| status     | TEXT    | e.g. "completed"         |
| created_at | TEXT    | ISO 8601 timestamp       |

## 3. REST Communication

All inter-service communication uses **HTTP REST** with JSON payloads. No shared Python modules exist between services.

| From     | To      | Call                                      | Purpose              |
|----------|---------|-------------------------------------------|----------------------|
| Frontend | Catalog | GET `/search/<topic>`                     | Search books         |
| Frontend | Catalog | GET `/info/<id>`                          | Book details         |
| Frontend | Order   | POST `/purchase/<id>`                     | Buy a book           |
| Order    | Catalog | GET `/info/<id>`                          | Check stock          |
| Order    | Catalog | POST `/update/<id>` body `quantity_change: -1` | Decrement stock |

Each HTTP call uses a **3-second timeout** and try/except handling for connection errors. Docker Compose sets service hostnames (`catalog`, `order`) so containers can resolve each other on the internal network.

## 4. Data Persistence

Both Catalog and Order use **SQLite** with one database file per service:

- `catalog/data/catalog.db` — books table
- `order/data/orders.db` — orders table

On startup, each service:

1. Creates the `data/` directory if missing
2. Creates tables if they do not exist
3. Seeds catalog data if the books table is empty

Docker volumes map host `./catalog/data` and `./order/data` to `/app/data` inside containers so data survives container restarts.

## 5. Purchase Workflow

The purchase flow is the most important distributed interaction:

```
Client -> POST /purchase/2 -> Frontend
Frontend -> POST /purchase/2 -> Order
Order -> GET /info/2 -> Catalog          (check book exists & stock > 0)
Order -> POST /update/2 {quantity_change: -1} -> Catalog
Order -> INSERT into orders.db
Order -> response -> Frontend -> Client
```

**Error handling:**

| Condition              | HTTP | Response message                    |
|------------------------|------|-------------------------------------|
| Book not found         | 404  | Book not found                      |
| Out of stock           | 400  | Book is out of stock                |
| Catalog unreachable    | 503  | Catalog service unavailable         |
| Update would go negative | 400 | (via Catalog) quantity error       |

The success message format is: `bought book <title>` (e.g. `bought book RPCs for Noobs`).

## 6. Design Tradeoffs

**Microservices vs monolith:** Three services add deployment complexity but clearly demonstrate service boundaries, independent scaling concepts, and network-based integration — core DOS lab goals.

**SQLite vs shared database:** Each service owns its data. Catalog and Order do not share a database, which is architecturally correct for microservices but requires REST calls for cross-service operations (stock check on purchase).

**Synchronous REST:** All calls are blocking HTTP requests. Simple to understand and debug; latency adds up under load but is acceptable for a lab.

**No message queue:** Purchases are processed immediately. A production system might use async events for inventory and notifications.

## 7. Concurrency Consideration

When two clients purchase the last copy of a book simultaneously, both Order services might read `quantity = 1` before either decrements stock. Mitigations in this project:

1. **Catalog threading lock** — `stock_lock` serializes `/update` operations within one Catalog process
2. **Quantity validation** — update rejects negative quantity with HTTP 400
3. **Order re-check** — if Catalog update fails with 400, Order returns out-of-stock

This does not provide full distributed transaction semantics (no two-phase commit), but it reduces lost updates in a single Catalog instance — sufficient for the lab scope.

## 8. Known Limitations

- No authentication; any client can purchase or query
- No distributed transactions across Catalog and Order
- SQLite file locking limits write throughput
- Docker `depends_on` does not guarantee readiness
- No API versioning
- No automated integration tests in CI

## 9. Possible Improvements

- Implement saga pattern for purchase rollback if order save fails after stock decrement
- Add `/ready` endpoints and Compose healthchecks
- Use optimistic locking (version column) on books
- Add request IDs for distributed tracing
- Containerize client as a test job in Compose

## 10. How to Run the System

```bash
# From project root
docker compose up --build

# In another terminal
curl http://localhost:5000/health
curl http://localhost:5000/search/distributed%20systems
curl http://localhost:5000/info/2
curl -X POST http://localhost:5000/purchase/2
python client/client.py
```

For local development without Docker, run each service in a separate terminal:

```bash
cd catalog && python app.py    # port 5001
cd order && python app.py      # port 5002
cd frontend && python app.py   # port 5000
```

Ensure `requests` is installed for Order and Frontend services.
