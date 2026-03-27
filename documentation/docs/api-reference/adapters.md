# Adapters API Reference

Adapters translate OrmAI operations to native ORM calls.

## Base Interface

All adapters implement this interface:

```python
from ormai.adapters import Adapter

class Adapter(Protocol):
    def introspect(self) -> SchemaMetadata: ...
    def compile(self, request, policy, principal) -> CompiledQuery: ...
    async def execute(self, compiled, ctx) -> ExecutionResult: ...
    def transaction(self, ctx) -> ContextManager: ...
```

---

## SQLAlchemyAdapter

Adapter for SQLAlchemy ORM.

```python
from ormai.adapters import SQLAlchemyAdapter
```

### Constructor

```python
SQLAlchemyAdapter(
    engine: Engine,
    base: DeclarativeBase,
    schema_cache: SchemaCache | None = None,
)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `engine` | `Engine` | SQLAlchemy engine |
| `base` | `DeclarativeBase` | Declarative base class |
| `schema_cache` | `SchemaCache \| None` | Optional schema cache |

### Example

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base

engine = create_engine("postgresql://localhost/mydb")
Base = declarative_base()

adapter = SQLAlchemyAdapter(engine=engine, base=Base)
```

### Methods

#### introspect

```python
def introspect(self) -> SchemaMetadata:
    """Extract schema from SQLAlchemy models."""
```

#### compile

```python
def compile(
    self,
    request: QueryRequest | GetRequest | AggregateRequest,
    policy: Policy,
    principal: Principal,
) -> CompiledQuery:
    """Compile request to SQLAlchemy query."""
```

#### execute

```python
def execute(
    self,
    compiled: CompiledQuery,
    ctx: RunContext,
) -> ExecutionResult:
    """Execute synchronously."""
```

#### transaction

```python
@contextmanager
def transaction(self, ctx: RunContext):
    """Transaction context manager."""
```

---

## AsyncSQLAlchemyAdapter

Async version for SQLAlchemy 2.0+.

```python
from ormai.adapters import AsyncSQLAlchemyAdapter
```

### Constructor

```python
AsyncSQLAlchemyAdapter(
    engine: AsyncEngine,
    base: DeclarativeBase,
    schema_cache: SchemaCache | None = None,
)
```

### Example

```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine("postgresql+asyncpg://localhost/mydb")

adapter = AsyncSQLAlchemyAdapter(engine=engine, base=Base)
```

### Methods

#### execute

```python
async def execute(
    self,
    compiled: CompiledQuery,
    ctx: RunContext,
) -> ExecutionResult:
    """Execute asynchronously."""
```

#### transaction

```python
@asynccontextmanager
async def transaction(self, ctx: RunContext):
    """Async transaction context manager."""
```

---

## TortoiseAdapter

Adapter for Tortoise ORM (async only).

```python
from ormai.adapters import TortoiseAdapter
```

### Constructor

```python
TortoiseAdapter(
    models_module: str,
    schema_cache: SchemaCache | None = None,
)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `models_module` | `str` | Module path containing models |
| `schema_cache` | `SchemaCache \| None` | Optional schema cache |

### Example

```python
from tortoise import Tortoise

await Tortoise.init(
    db_url="postgres://localhost/mydb",
    modules={"models": ["myapp.models"]},
)

adapter = TortoiseAdapter(models_module="myapp.models")
```

---

## PeeweeAdapter

Adapter for Peewee ORM (sync only).

```python
from ormai.adapters import PeeweeAdapter
```

### Constructor

```python
PeeweeAdapter(
    database: Database,
    models: list[type],
    schema_cache: SchemaCache | None = None,
)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `database` | `Database` | Peewee database instance |
| `models` | `list[type]` | List of model classes |
| `schema_cache` | `SchemaCache \| None` | Optional schema cache |

### Example

```python
from peewee import PostgresqlDatabase

db = PostgresqlDatabase("mydb")

adapter = PeeweeAdapter(
    database=db,
    models=[User, Order, Item],
)
```

---

## DjangoAdapter

Adapter for Django ORM.

```python
from ormai.adapters import DjangoAdapter
```

### Constructor

```python
DjangoAdapter(
    app_labels: list[str],
    schema_cache: SchemaCache | None = None,
)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `app_labels` | `list[str]` | Django app labels to include |
| `schema_cache` | `SchemaCache \| None` | Optional schema cache |

### Example

```python
adapter = DjangoAdapter(app_labels=["users", "orders"])
```

---

## SQLModelAdapter

Adapter for SQLModel.

```python
from ormai.adapters import SQLModelAdapter
```

### Constructor

```python
SQLModelAdapter(
    engine: Engine,
    models: list[type],
    schema_cache: SchemaCache | None = None,
)
```

### Example

```python
from sqlmodel import create_engine

engine = create_engine("postgresql://localhost/mydb")

adapter = SQLModelAdapter(
    engine=engine,
    models=[User, Order],
)
```

---

## CompiledQuery

Result of query compilation.

```python
@dataclass
class CompiledQuery:
    native_query: Any      # ORM-specific query object
    model: str             # Target model name
    operation: str         # "select", "insert", "update", "delete"
    scopes_applied: list[str]  # Applied scoping rules
    budget_limits: dict    # Applied budget constraints
```

---

## ExecutionResult

Result of query execution.

```python
@dataclass
class ExecutionResult:
    rows: list[dict]       # Query results
    row_count: int         # Number of rows
    has_more: bool         # More results available
    next_cursor: str | None  # Pagination cursor
    execution_time_ms: float  # Execution time
```

---

## SchemaCache

Caches introspected schemas.

```python
from ormai.utils import SchemaCache
```

### Constructor

```python
SchemaCache(
    ttl_seconds: int = 3600,
)
```

### Methods

#### get_or_introspect

```python
def get_or_introspect(
    self,
    adapter: Adapter,
    force_refresh: bool = False,
) -> SchemaMetadata:
```

### Example

```python
cache = SchemaCache(ttl_seconds=3600)

# First call introspects
schema = cache.get_or_introspect(adapter)

# Subsequent calls use cache
schema = cache.get_or_introspect(adapter)

# Force refresh
schema = cache.get_or_introspect(adapter, force_refresh=True)
```

---

## PersistentSchemaCache

File-based schema cache.

```python
from ormai.utils import PersistentSchemaCache
```

### Constructor

```python
PersistentSchemaCache(
    path: str,
    ttl_seconds: int = 86400,
)
```

### Example

```python
cache = PersistentSchemaCache(
    path="./schema_cache.json",
    ttl_seconds=86400,  # 24 hours
)

schema = cache.get_or_introspect(adapter)
```

---

## TransactionManager

Advanced transaction management.

```python
from ormai.utils import TransactionManager
```

### Methods

#### begin

```python
@asynccontextmanager
async def begin(self, ctx: RunContext):
    """Start a transaction."""
```

#### savepoint

```python
@asynccontextmanager
async def savepoint(self, name: str | None = None):
    """Create a savepoint within a transaction."""
```

### Example

```python
manager = TransactionManager(adapter)

async with manager.begin(ctx) as tx:
    await toolset.create(ctx, model="Order", data={...})

    async with tx.savepoint("items"):
        try:
            await toolset.create(ctx, model="Item", data={...})
        except ValidationError:
            # Savepoint rolled back, transaction continues
            pass

    # Commits if no exception
```

---

## RetryConfig

Configuration for operation retries.

```python
from ormai.utils import RetryConfig
```

### Constructor

```python
RetryConfig(
    max_attempts: int = 3,
    initial_delay_ms: int = 100,
    max_delay_ms: int = 5000,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (DeadlockError, TimeoutError),
)
```

### Example

```python
from ormai.utils import retry_async

config = RetryConfig(max_attempts=3)

@retry_async(config)
async def create_order(ctx, data):
    return await toolset.create(ctx, model="Order", data=data)
```
