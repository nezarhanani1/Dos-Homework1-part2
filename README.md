# Bazar Bookstore — Replication, Caching and Consistency

DOS Lab 2 extension of the Bazar.com microservices bookstore (Lab 1). Three-tier architecture with **two catalog replicas**, **two order replicas**, **in-memory LRU caching**, **Round Robin load balancing**, and **cache invalidation** for consistency.

## Architecture

```
Client / UI
     |
     v
Frontend :5000
  |-- In-Memory Cache (LRU, max 10)
  |-- Round Robin --> Catalog Replica 1 :5001
  |-- Round Robin --> Catalog Replica 2 :5003
  |-- Round Robin --> Order Replica 1   :5002
  \-- Round Robin --> Order Replica 2   :5004
```

## Features

- Microservices (Flask + requests + SQLite)
- **Replication** — 2 catalog + 2 order replicas with sync routes
- **In-memory caching** — info & search only
- **Cache invalidation** — on purchase and before catalog writes
- **Round Robin load balancing** with failover
- **Performance measurements** — `client/performance_test.py`
- **Web UI** — http://127.0.0.1:5000/

## Books (7 total)

| ID | Title | Topic |
|----|-------|-------|
| 1–4 | Lab 1 books | distributed systems / undergraduate school |
| 5 | How to finish Project 3 on time | distributed systems |
| 6 | Why theory classes are so hard. | theory |
| 7 | Spring in the Pioneer Valley | spring |

## How to Run (PowerShell)

See **`docs/run_instructions.md`** for full commands (5 terminals).

Quick summary:

```powershell
# Terminal 1-2: catalog replicas (5001, 5003)
# Terminal 3-4: order replicas (5002, 5004)
# Terminal 5: frontend (5000)
py -3 app.py
```

**UI:** http://127.0.0.1:5000/

**Reseed stock:** `py -3 catalog/reseed_catalog.py`

## API Routes

### Frontend (5000)

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Web UI |
| GET | `/api` | JSON welcome |
| GET | `/health` | Health |
| GET | `/search/<topic>` | Search (cached) |
| GET | `/info/<id>` | Book info (cached) |
| POST | `/purchase/<id>` | Purchase |
| GET | `/cache/status` | Cache keys |
| DELETE | `/cache/clear` | Clear cache |
| DELETE | `/cache/invalidate/<id>` | Invalidate item |
| POST | `/cache/invalidate/<id>` | Invalidate (backend push) |
| GET | `/proxy/health/all` | All replica health |

### Catalog (5001 / 5003)

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/health` | Health + replica name |
| GET | `/search/<topic>` | Search |
| GET | `/info/<id>` | Info |
| POST | `/update/<id>` | Update stock/price |
| POST | `/sync/update/<id>` | Peer sync (internal) |
| POST | `/admin/reseed` | Reset catalog |

### Order (5002 / 5004)

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/health` | Health + replica name |
| POST | `/purchase/<id>` | Purchase |
| POST | `/sync/order` | Peer order sync |
| GET | `/orders` | List orders |

## Performance Test

With all services running:

```powershell
py -3 client/performance_test.py
```

Outputs:

- `docs/performance_results.csv`
- `docs/performance_results.md`
- `docs/performance_plot.png` (if matplotlib installed)

## Documentation

| File | Content |
|------|---------|
| `docs/design_document.md` | Lab 2 design (2–3 pages) |
| `docs/sample_output.md` | Example API outputs |
| `docs/run_instructions.md` | PowerShell run commands |
| `docs/design.md` | Lab 1 design (original) |

## Docker

Docker is **optional**. Lab 2 is designed for local `py -3` execution. Original `docker-compose.yml` still runs Lab 1 single-replica mode; use manual terminals for Lab 2 replicas.

## curl Examples

```powershell
curl http://127.0.0.1:5000/health
curl "http://127.0.0.1:5000/search/distributed%20systems"
curl http://127.0.0.1:5000/info/2
curl -X POST http://127.0.0.1:5000/purchase/2
curl http://127.0.0.1:5000/cache/status
```

## Student Notes

The frontend cache makes repeated **read** requests faster. **Writes** (purchases) always go to order → catalog and invalidate stale cache entries so clients do not see old quantities. Round Robin spreads work across replicas; if one is down, the next is tried automatically.
