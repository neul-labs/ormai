# FastAPI + SQLAlchemy Example

This example demonstrates how to integrate OrmAI with a FastAPI application using SQLAlchemy.

## Setup

```bash
cd examples/fastapi-sqlalchemy
uv sync
```

## Run

```bash
uv run uvicorn app.main:app --reload
```

## Endpoints

- `GET /` - Health check
- `GET /schema` - Get database schema
- `POST /query` - Execute a query
- `POST /get` - Get a record by ID
- `POST /aggregate` - Execute an aggregation

## Example Queries

### Get Schema
```bash
curl http://localhost:8000/schema
```

### Query Orders
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenant-1" \
  -H "X-User-ID: user-1" \
  -d '{
    "model": "Order",
    "take": 10,
    "where": [{"field": "status", "op": "eq", "value": "pending"}]
  }'
```

### Get Customer by ID
```bash
curl -X POST http://localhost:8000/get \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenant-1" \
  -H "X-User-ID: user-1" \
  -d '{
    "model": "Customer",
    "id": 1
  }'
```

### Count Orders
```bash
curl -X POST http://localhost:8000/aggregate \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenant-1" \
  -H "X-User-ID: user-1" \
  -d '{
    "model": "Order",
    "operation": "count"
  }'
```
