# Sample Output — Lab 2

## GET /health (frontend)

```json
{"service": "frontend", "status": "ok"}
```

## GET /health (catalog replica 1)

```json
{
  "service": "catalog",
  "status": "ok",
  "replica": "catalog-replica-1",
  "port": 5001
}
```

## GET /health (catalog replica 2)

```json
{
  "service": "catalog",
  "status": "ok",
  "replica": "catalog-replica-2",
  "port": 5003
}
```

## GET /health (order replica 1)

```json
{
  "service": "order",
  "status": "ok",
  "replica": "order-replica-1",
  "port": 5002
}
```

## GET /search/distributed systems

Headers: `X-Served-By: catalog-replica-5001`, `X-Cache: miss`

```json
[
  {"id": 1, "title": "How to get a good grade in DOS in 40 minutes a day"},
  {"id": 2, "title": "RPCs for Noobs"},
  {"id": 5, "title": "How to finish Project 3 on time"}
]
```

## GET /info/2 (cache miss)

```json
{
  "id": 2,
  "title": "RPCs for Noobs",
  "topic": "distributed systems",
  "quantity": 10,
  "price": 50,
  "served_by": "catalog-replica-5003",
  "cache": "miss"
}
```

## GET /info/2 (cache hit — second request)

```json
{
  "id": 2,
  "title": "RPCs for Noobs",
  "topic": "distributed systems",
  "quantity": 10,
  "price": 50,
  "served_by": "catalog-replica-5003",
  "cache": "hit"
}
```

## POST /purchase/2 (success)

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
    "created_at": "2026-05-19T20:00:00+00:00"
  },
  "served_by": "order-replica-5002",
  "catalog_replica": "http://127.0.0.1:5001",
  "cache": "invalidated"
}
```

## POST /purchase/2 (out of stock)

```json
{
  "success": false,
  "message": "Book is out of stock"
}
```

## POST /purchase/999 (not found)

```json
{
  "success": false,
  "message": "Book not found"
}
```

## GET /cache/status

```json
{
  "size": 2,
  "max_size": 10,
  "keys": ["info:2", "search:distributed systems"]
}
```

## DELETE /cache/invalidate/2

```json
{
  "success": true,
  "item_id": 2,
  "removed_keys": ["info:2", "search:distributed systems"]
}
```

## DELETE /cache/clear

```json
{
  "success": true,
  "message": "Cache cleared"
}
```

## Catalog log (purchase sync)

```
[catalog-replica-1] Invalidated frontend cache for item 2
[catalog-replica-1] Updated quantity for item 2 by -1
[catalog-replica-1] Synced update for item 2 to peer
[catalog-replica-2] Applying sync update for item 2
```

## Order log

```
[order-replica-1] Purchase request for item 2
[order-replica-1] Checking stock via http://127.0.0.1:5001
[order-replica-1] bought book RPCs for Noobs (catalog: http://127.0.0.1:5001)
```
