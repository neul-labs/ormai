# Quick Start

Get OrmAI running with your existing database in under 5 minutes.

## Prerequisites

- An existing SQLAlchemy, Tortoise, or Peewee project
- Python 3.10+
- OrmAI installed (`pip install ormai[sqlalchemy]`)

## Step 1: Define Your Models

If you already have ORM models, you can skip this step. Otherwise, here's an example:

```python
from sqlalchemy import Column, Integer, String, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    email = Column(String, nullable=False)
    name = Column(String)

    tenant = relationship("Tenant")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="pending")
    total = Column(Integer)

    tenant = relationship("Tenant")
    user = relationship("User")
```

## Step 2: Create a Policy

Policies define what agents can access:

```python
from ormai.policy import Policy, ModelPolicy, FieldPolicy, FieldAction

policy = Policy(
    models={
        "User": ModelPolicy(
            allowed=True,
            fields={
                "id": FieldPolicy(action=FieldAction.Allow),
                "tenant_id": FieldPolicy(action=FieldAction.Allow),
                "email": FieldPolicy(action=FieldAction.Mask),  # Mask sensitive data
                "name": FieldPolicy(action=FieldAction.Allow),
            },
            scoping={"tenant_id": "principal.tenant_id"},  # Auto-filter by tenant
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
        ),
    },
)
```

## Step 3: Mount the Toolset

Use the quickstart helper to mount your models:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ormai.quickstart import mount_sqlalchemy

# Create engine and session
engine = create_engine("sqlite:///myapp.db")
Session = sessionmaker(bind=engine)

# Mount the toolset
toolset = mount_sqlalchemy(
    engine=engine,
    base=Base,
    policy=policy,
)
```

## Step 4: Execute Queries

Create a context and run queries:

```python
from ormai.core import Principal, RunContext

# Create execution context with principal
session = Session()
ctx = RunContext(
    principal=Principal(
        tenant_id="acme-corp",
        user_id="user-123",
        roles=["member"],
    ),
    db=session,
)

# Query orders for the current tenant
result = await toolset.query(
    ctx,
    model="Order",
    filters=[
        {"field": "status", "op": "eq", "value": "pending"}
    ],
    select=["id", "status", "total"],
    limit=10,
)

print(result.rows)
# [{"id": 1, "status": "pending", "total": 9900}, ...]
```

## Step 5: Expose via HTTP (Optional)

Integrate with FastAPI for HTTP access:

```python
from fastapi import FastAPI, Request, Depends
from sqlalchemy.orm import Session

app = FastAPI()

def get_db():
    db = Session()
    try:
        yield db
    finally:
        db.close()

def get_context(request: Request, db: Session = Depends(get_db)):
    return RunContext(
        principal=Principal(
            tenant_id=request.headers.get("X-Tenant-ID"),
            user_id=request.headers.get("X-User-ID"),
        ),
        db=db,
    )

@app.post("/query")
async def query(request: dict, ctx: RunContext = Depends(get_context)):
    return await toolset.query(
        ctx,
        model=request["model"],
        filters=request.get("filters", []),
        select=request.get("select"),
        limit=request.get("limit", 50),
    )
```

## What's Next?

- [First Steps](first-steps.md) - Learn more about contexts and principals
- [Policies](../concepts/policies.md) - Deep dive into policy configuration
- [Tools](../concepts/tools.md) - Explore available tools
- [Write Operations](../guides/write-operations.md) - Enable create, update, delete
