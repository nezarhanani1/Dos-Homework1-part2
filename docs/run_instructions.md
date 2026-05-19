# How to Run Bazar.com — Lab 2 (PowerShell)

Start **5 terminals** in this order. Use `py -3` (not `python`).

## Terminal 1 — Catalog Replica 1 (port 5001)

```powershell
cd "c:\Users\nezar\Desktop\dos homework\bazar-bookstore\catalog"
$env:CATALOG_PORT="5001"
$env:REPLICA_NAME="catalog-replica-1"
$env:PEER_CATALOG_URL="http://127.0.0.1:5003"
$env:FRONTEND_URL="http://127.0.0.1:5000"
py -3 app.py
```

## Terminal 2 — Catalog Replica 2 (port 5003)

```powershell
cd "c:\Users\nezar\Desktop\dos homework\bazar-bookstore\catalog"
$env:CATALOG_PORT="5003"
$env:REPLICA_NAME="catalog-replica-2"
$env:PEER_CATALOG_URL="http://127.0.0.1:5001"
$env:FRONTEND_URL="http://127.0.0.1:5000"
py -3 app.py
```

## Terminal 3 — Order Replica 1 (port 5002)

```powershell
cd "c:\Users\nezar\Desktop\dos homework\bazar-bookstore\order"
$env:ORDER_PORT="5002"
$env:REPLICA_NAME="order-replica-1"
$env:PEER_ORDER_URL="http://127.0.0.1:5004"
$env:CATALOG_REPLICAS="http://127.0.0.1:5001,http://127.0.0.1:5003"
py -3 app.py
```

## Terminal 4 — Order Replica 2 (port 5004)

```powershell
cd "c:\Users\nezar\Desktop\dos homework\bazar-bookstore\order"
$env:ORDER_PORT="5004"
$env:REPLICA_NAME="order-replica-2"
$env:PEER_ORDER_URL="http://127.0.0.1:5002"
$env:CATALOG_REPLICAS="http://127.0.0.1:5001,http://127.0.0.1:5003"
py -3 app.py
```

## Terminal 5 — Frontend (port 5000)

```powershell
cd "c:\Users\nezar\Desktop\dos homework\bazar-bookstore\frontend"
$env:CATALOG_REPLICAS="http://127.0.0.1:5001,http://127.0.0.1:5003"
$env:ORDER_REPLICAS="http://127.0.0.1:5002,http://127.0.0.1:5004"
py -3 app.py
```

## Browser (UI)

- http://127.0.0.1:5000/
- http://localhost:5000/

## Reseed catalog (reset stock)

```powershell
cd "c:\Users\nezar\Desktop\dos homework\bazar-bookstore\catalog"
py -3 reseed_catalog.py
```

## Performance test (all services must be running)

```powershell
cd "c:\Users\nezar\Desktop\dos homework\bazar-bookstore"
py -3 client/performance_test.py
```

## Quick curl tests

```powershell
curl http://127.0.0.1:5000/health
curl http://127.0.0.1:5001/health
curl http://127.0.0.1:5003/health
curl "http://127.0.0.1:5000/search/distributed%20systems"
curl http://127.0.0.1:5000/info/2
curl -X POST http://127.0.0.1:5000/purchase/2
curl http://127.0.0.1:5000/cache/status
```
