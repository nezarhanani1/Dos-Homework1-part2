# Bazar.com: A Multi-tier Online Book Store

A small distributed online bookstore built for a Distributed and Operating Systems lab. The system demonstrates a **multi-tier microservices architecture** using three independent Flask services that communicate only through **HTTP REST**.

## Description

Bazar.com sells four books across two topics (`distributed systems` and `undergraduate school`). Customers can search by topic, view book details, and purchase books. Stock is managed by the Catalog Service; orders are recorded by the Order Service; the Frontend Service is the public API gateway.

## Architecture

```
Client / Browser / curl
        |
        v
Frontend Service :5000
        |
        |---- search/info requests ----> Catalog Service :5001
        |
        |---- purchase requests -------> Order Service :5002
                                             |
                                             |---- check stock/update ----> Catalog Service :5001
```

- **Frontend** — Public gateway; forwards requests to backend services.
- **Catalog** — Owns book catalog and inventory (SQLite).
- **Order** — Owns purchase records (SQLite); coordinates stock updates via Catalog REST APIs.

## Technologies Used

- Python 3.11
- Flask (micro web framework)
- requests (inter-service HTTP calls)
- SQLite (persistence)
- Docker & Docker Compose

## Project Structure

```
bazar-bookstore/
├── frontend/
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── catalog/
│   ├── app.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── data/          # catalog.db created at runtime
├── order/
│   ├── app.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── data/          # orders.db created at runtime
├── client/
│   └── client.py
├── docs/
│   ├── design.md
│   └── sample-output.txt
├── docker-compose.yml
├── README.md
└── .gitignore
```

Database files (`*.db`) are **not** committed. The `data/` folders are kept in Git via `.gitkeep`; SQLite databases are created automatically when each service starts.

## API Documentation

All public APIs are exposed through the **Frontend** on port **5000**.

**Web UI:** Open [http://localhost:5000](http://localhost:5000) in your browser for a simple bookstore interface (search, view details, purchase). JSON API welcome is at `GET /api`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health check |
| GET | `/` | Welcome message and endpoint list |
| GET | `/search/<topic>` | Search books by topic (case-insensitive) |
| GET | `/info/<item_id>` | Get book details |
| POST | `/purchase/<item_id>` | Purchase a book |

### Catalog Service (port 5001)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/search/<topic>` | Books matching topic |
| GET | `/info/<item_id>` | Full book record |
| POST | `/update/<item_id>` | Update quantity or price |

### Order Service (port 5002)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/purchase/<item_id>` | Process purchase |
| GET | `/orders` | List all orders |

## How to Run with Docker Compose

From the project root:

```bash
docker compose up --build
```

Services will be available at:

- Frontend: http://localhost:5000
- Catalog: http://localhost:5001
- Order: http://localhost:5002

Stop with `Ctrl+C`, or run detached with `docker compose up --build -d`.

## How to Test with curl

```bash
curl http://localhost:5000/health
curl http://localhost:5000/search/distributed%20systems
curl http://localhost:5000/info/2
curl -X POST http://localhost:5000/purchase/2
```

After a purchase, check that quantity decreased:

```bash
curl http://localhost:5000/info/2
```

List orders directly:

```bash
curl http://localhost:5002/orders
```

## How to Run the Python Client

With Docker Compose running:

```bash
pip install requests
python client/client.py
```

Optional environment variables:

```bash
set FRONTEND_URL=http://localhost:5000
set ORDER_URL=http://localhost:5002
python client/client.py
```

## Example Outputs

**Search:**

```json
[
  {"id": 1, "title": "How to get a good grade in DOS in 40 minutes a day"},
  {"id": 2, "title": "RPCs for Noobs"}
]
```

**Purchase:**

```json
{
  "success": true,
  "message": "bought book RPCs for Noobs",
  "order": {
    "id": 1,
    "book_id": 2,
    "book_title": "RPCs for Noobs",
    "price": 50,
    "status": "completed",
    "created_at": "2026-05-19T12:00:00+00:00"
  }
}
```

See `docs/sample-output.txt` for full sample terminal output.

## Distributed Design Notes

- Each service is a **separate process** with its own codebase and Docker container.
- Services communicate **only via HTTP REST** — no shared imports between services.
- The Frontend is the **single entry point** for clients.
- The Order Service is the **orchestrator** for purchases: it queries Catalog for stock, decrements inventory, then saves the order.
- Environment variables (`CATALOG_URL`, `ORDER_URL`) allow the same code to run locally or inside Docker networks.

## Known Limitations

- No authentication or authorization.
- No payment processing — purchases always succeed if stock is available.
- SQLite is suitable for a lab demo but not for high-concurrency production workloads.
- `depends_on` in Docker Compose does not wait for services to be fully ready — you may need a few seconds after startup before testing.
- Race conditions are partially mitigated with a threading lock in Catalog, but distributed transactions are not fully atomic across services.

## Possible Improvements

- Add health-check wait scripts in Docker Compose.
- Use connection pooling and WAL mode for SQLite.
- Add retry logic for transient network failures.
- Implement idempotent purchase requests.
- Add structured logging and metrics.
- Replace SQLite with a shared database only if moving away from strict microservice data ownership.

## Student Explanation

This lab shows how a real-world web application can be split into **small, focused microservices**. Instead of one large application, we have three services that each do one job well. When you buy a book, your request hits the Frontend, which asks the Order Service to handle the purchase. The Order Service talks to the Catalog Service to make sure the book exists and is in stock, then tells Catalog to reduce stock by one, and finally saves your order in its own database.

The important lesson is **separation of concerns**: catalog data lives in one place, order history in another, and the client never talks to the backend services directly. This is the foundation of distributed systems — independent components cooperating over the network.
