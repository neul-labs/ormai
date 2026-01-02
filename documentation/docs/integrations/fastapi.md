# FastAPI Integration

This guide covers integrating OrmAI with FastAPI applications.

## Basic Setup

### Installation

```bash
pip install ormai[fastapi]
```

### Project Structure

```
myapp/
├── main.py
├── models.py
├── policy.py
├── dependencies.py
└── routes/
    ├── __init__.py
    └── tools.py
```

## Complete Example

### Models (models.py)

```python
from sqlalchemy import Column, Integer, String, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False)
    email = Column(String, nullable=False)
    name = Column(String)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String, nullable=False)
    user_id = Column(String, ForeignKey("users.id"))
    status = Column(String, default="pending")
    total = Column(Integer)

    user = relationship("User")

engine = create_engine("postgresql://localhost/mydb")
SessionLocal = sessionmaker(bind=engine)
```

### Policy (policy.py)

```python
from ormai.policy import Policy, ModelPolicy, FieldPolicy, FieldAction, WritePolicy, WriteAction

policy = Policy(
    models={
        "User": ModelPolicy(
            allowed=True,
            fields={
                "id": FieldPolicy(action=FieldAction.Allow),
                "tenant_id": FieldPolicy(action=FieldAction.Allow),
                "email": FieldPolicy(action=FieldAction.Mask),
                "name": FieldPolicy(action=FieldAction.Allow),
            },
            scoping={"tenant_id": "principal.tenant_id"},
        ),
        "Order": ModelPolicy(
            allowed=True,
            fields={
                "id": FieldPolicy(action=FieldAction.Allow),
                "tenant_id": FieldPolicy(action=FieldAction.Allow),
                "user_id": FieldPolicy(action=FieldAction.Allow),
                "status": FieldPolicy(action=FieldAction.Allow),
                "total": FieldPolicy(action=FieldAction.Allow),
            },
            scoping={"tenant_id": "principal.tenant_id"},
            write_policy=WritePolicy(
                create=WriteAction.Allow,
                update=WriteAction.Allow,
                delete=WriteAction.Deny,
            ),
        ),
    },
)
```

### Dependencies (dependencies.py)

```python
from fastapi import Request, Depends, HTTPException
from sqlalchemy.orm import Session
from ormai.core import Principal, RunContext
from ormai.quickstart import mount_sqlalchemy

from .models import engine, Base, SessionLocal
from .policy import policy

# Create toolset once at startup
toolset = mount_sqlalchemy(engine=engine, base=Base, policy=policy)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_principal(request: Request) -> Principal:
    tenant_id = request.headers.get("X-Tenant-ID")
    user_id = request.headers.get("X-User-ID")

    if not tenant_id or not user_id:
        raise HTTPException(status_code=401, detail="Missing auth headers")

    return Principal(
        tenant_id=tenant_id,
        user_id=user_id,
        roles=request.headers.get("X-Roles", "").split(","),
    )

def get_context(
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> RunContext:
    return RunContext(
        principal=principal,
        db=db,
        request_id=request.headers.get("X-Request-ID"),
        trace_id=request.headers.get("X-Trace-ID"),
    )

def get_toolset():
    return toolset
```

### Main Application (main.py)

```python
from fastapi import FastAPI
from .routes import tools

app = FastAPI(title="My App with OrmAI")

app.include_router(tools.router, prefix="/api")

@app.get("/health")
def health():
    return {"status": "ok"}
```

### Routes (routes/tools.py)

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ormai.core import RunContext, ModelNotAllowedError, QueryBudgetExceededError

from ..dependencies import get_context, get_toolset

router = APIRouter(tags=["tools"])

# Request models
class QueryRequest(BaseModel):
    model: str
    filters: list[dict] = []
    select: list[str] | None = None
    order: list[dict] = []
    include: list[dict] = []
    limit: int = 50
    cursor: str | None = None

class GetRequest(BaseModel):
    model: str
    id: str | int
    select: list[str] | None = None
    include: list[dict] = []

class CreateRequest(BaseModel):
    model: str
    data: dict

class UpdateRequest(BaseModel):
    model: str
    id: str | int
    data: dict

# Endpoints
@router.get("/schema")
async def describe_schema(
    ctx: RunContext = Depends(get_context),
    toolset = Depends(get_toolset),
):
    result = await toolset.describe_schema(ctx)
    return result.data

@router.post("/query")
async def query(
    request: QueryRequest,
    ctx: RunContext = Depends(get_context),
    toolset = Depends(get_toolset),
):
    try:
        result = await toolset.query(
            ctx,
            model=request.model,
            filters=request.filters,
            select=request.select,
            order=request.order,
            include=request.include,
            limit=request.limit,
            cursor=request.cursor,
        )
        return result.data
    except ModelNotAllowedError:
        raise HTTPException(status_code=403, detail="Model not allowed")
    except QueryBudgetExceededError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/get")
async def get(
    request: GetRequest,
    ctx: RunContext = Depends(get_context),
    toolset = Depends(get_toolset),
):
    result = await toolset.get(
        ctx,
        model=request.model,
        id=request.id,
        select=request.select,
        include=request.include,
    )
    if not result.success:
        raise HTTPException(status_code=404, detail="Not found")
    return result.data

@router.post("/create")
async def create(
    request: CreateRequest,
    ctx: RunContext = Depends(get_context),
    toolset = Depends(get_toolset),
):
    result = await toolset.create(
        ctx,
        model=request.model,
        data=request.data,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return result.data

@router.post("/update")
async def update(
    request: UpdateRequest,
    ctx: RunContext = Depends(get_context),
    toolset = Depends(get_toolset),
):
    result = await toolset.update(
        ctx,
        model=request.model,
        id=request.id,
        data=request.data,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return result.data
```

## Usage

### Query Example

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: acme-corp" \
  -H "X-User-ID: user-123" \
  -d '{
    "model": "Order",
    "filters": [{"field": "status", "op": "eq", "value": "pending"}],
    "select": ["id", "status", "total"],
    "limit": 10
  }'
```

### Create Example

```bash
curl -X POST http://localhost:8000/api/create \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: acme-corp" \
  -H "X-User-ID: user-123" \
  -d '{
    "model": "Order",
    "data": {"status": "pending", "total": 5000, "user_id": "user-123"}
  }'
```

## Async SQLAlchemy

For async SQLAlchemy:

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

engine = create_async_engine("postgresql+asyncpg://localhost/mydb")
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

## Middleware

### Audit Logging Middleware

```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from ormai.store import JsonlAuditStore, AuditMiddleware

audit_store = JsonlAuditStore("./audit.jsonl")
audit_middleware = AuditMiddleware(store=audit_store)

class OrmAIAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Audit is handled at tool level
        response = await call_next(request)
        return response

app.add_middleware(OrmAIAuditMiddleware)
```

### Error Handling Middleware

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from ormai.core import OrmAIError

@app.exception_handler(OrmAIError)
async def ormai_exception_handler(request: Request, exc: OrmAIError):
    return JSONResponse(
        status_code=400,
        content={
            "error": exc.code,
            "message": exc.message,
            "details": exc.details,
        },
    )
```

## Authentication Integration

### JWT Authentication

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()

def get_principal(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Principal:
    try:
        payload = jwt.decode(
            credentials.credentials,
            "your-secret",
            algorithms=["HS256"],
        )
        return Principal(
            tenant_id=payload["org_id"],
            user_id=payload["sub"],
            roles=payload.get("roles", []),
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### API Key Authentication

```python
from fastapi import Header, HTTPException

API_KEYS = {
    "key-123": {"tenant_id": "acme", "user_id": "api-user"},
}

def get_principal(x_api_key: str = Header(...)) -> Principal:
    if x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")

    config = API_KEYS[x_api_key]
    return Principal(
        tenant_id=config["tenant_id"],
        user_id=config["user_id"],
    )
```

## OpenAPI Documentation

Add tool schemas to OpenAPI:

```python
from fastapi import FastAPI
from ormai.tools import ToolRegistry

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="My App API",
        version="1.0.0",
        routes=app.routes,
    )

    # Add OrmAI tool schemas
    openapi_schema["components"]["schemas"].update(
        toolset.get_openapi_schemas()
    )

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

## Testing

```python
from fastapi.testclient import TestClient
import pytest

@pytest.fixture
def client():
    return TestClient(app)

def test_query_orders(client):
    response = client.post(
        "/api/query",
        headers={
            "X-Tenant-ID": "test-tenant",
            "X-User-ID": "test-user",
        },
        json={
            "model": "Order",
            "limit": 10,
        },
    )
    assert response.status_code == 200
    assert "rows" in response.json()

def test_forbidden_model(client):
    response = client.post(
        "/api/query",
        headers={
            "X-Tenant-ID": "test-tenant",
            "X-User-ID": "test-user",
        },
        json={
            "model": "SecretModel",
        },
    )
    assert response.status_code == 403
```

## Next Steps

- [LangGraph Integration](langgraph.md) - Use with LangGraph agents
- [MCP Integration](../api-reference/mcp.md) - Expose via MCP
- [Multi-Tenant Setup](../guides/multi-tenant.md) - Tenant isolation
