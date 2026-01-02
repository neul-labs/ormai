# Adapters

Adapters translate OrmAI's query DSL into native ORM operations. Each adapter handles the specifics of its target ORM while providing a consistent interface.

## Available Adapters

| Adapter | ORM | Sync/Async | Status |
|---------|-----|------------|--------|
| `SQLAlchemyAdapter` | SQLAlchemy | Both | Production |
| `TortoiseAdapter` | Tortoise ORM | Async | Production |
| `PeeweeAdapter` | Peewee | Sync | Production |
| `DjangoAdapter` | Django ORM | Both | Production |
| `SQLModelAdapter` | SQLModel | Both | Production |

## Adapter Interface

All adapters implement the same interface:

```python
class Adapter(Protocol):
    def introspect(self) -> SchemaMetadata:
        """Extract schema metadata from ORM models."""
        ...

    def compile(
        self,
        request: QueryRequest,
        policy: Policy,
        principal: Principal,
    ) -> CompiledQuery:
        """Compile DSL request to native query."""
        ...

    async def execute(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> ExecutionResult:
        """Execute compiled query."""
        ...

    def transaction(self, ctx: RunContext) -> ContextManager:
        """Get transaction context manager."""
        ...
```

## SQLAlchemy Adapter

### Setup

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ormai.adapters import SQLAlchemyAdapter

engine = create_engine("postgresql://localhost/mydb")
Session = sessionmaker(bind=engine)

adapter = SQLAlchemyAdapter(
    engine=engine,
    base=Base,  # Your declarative base
)
```

### Async SQLAlchemy

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from ormai.adapters import AsyncSQLAlchemyAdapter

engine = create_async_engine("postgresql+asyncpg://localhost/mydb")

adapter = AsyncSQLAlchemyAdapter(
    engine=engine,
    base=Base,
)
```

### Features

- Full relationship support (lazy, eager, joined)
- Async session management
- Transaction savepoints
- Composite primary keys
- Polymorphic models

## Tortoise Adapter

### Setup

```python
from tortoise import Tortoise
from ormai.adapters import TortoiseAdapter

await Tortoise.init(
    db_url="postgres://localhost/mydb",
    modules={"models": ["myapp.models"]},
)

adapter = TortoiseAdapter(
    models_module="myapp.models",
)
```

### Features

- Native async support
- Prefetch optimization
- Automatic schema discovery
- F/Q expression support

## Peewee Adapter

### Setup

```python
from peewee import PostgresqlDatabase
from ormai.adapters import PeeweeAdapter

db = PostgresqlDatabase("mydb")

adapter = PeeweeAdapter(
    database=db,
    models=[User, Order, Item],  # List of model classes
)
```

### Features

- Lightweight integration
- Prefetch support
- Transaction management
- SQLite/PostgreSQL/MySQL support

## Django Adapter

### Setup

```python
from ormai.adapters import DjangoAdapter

adapter = DjangoAdapter(
    app_labels=["myapp", "orders"],  # Django app labels
)
```

### Features

- Django ORM integration
- select_related/prefetch_related
- Django transaction support
- Model inheritance support

## Introspection

Adapters extract schema metadata from your ORM models:

```python
schema = adapter.introspect()

for model_name, model_meta in schema.models.items():
    print(f"Model: {model_name}")
    print(f"  Table: {model_meta.table_name}")
    print(f"  Primary key: {model_meta.primary_key}")

    for field_name, field_meta in model_meta.fields.items():
        print(f"  Field: {field_name}")
        print(f"    Type: {field_meta.python_type}")
        print(f"    Nullable: {field_meta.nullable}")

    for rel_name, rel_meta in model_meta.relations.items():
        print(f"  Relation: {rel_name}")
        print(f"    Target: {rel_meta.target_model}")
        print(f"    Type: {rel_meta.relation_type}")
```

### Schema Metadata

```python
@dataclass
class SchemaMetadata:
    models: dict[str, ModelMetadata]

@dataclass
class ModelMetadata:
    name: str
    table_name: str
    primary_key: str | list[str]
    fields: dict[str, FieldMetadata]
    relations: dict[str, RelationMetadata]

@dataclass
class FieldMetadata:
    name: str
    column_name: str
    python_type: type
    nullable: bool
    default: Any

@dataclass
class RelationMetadata:
    name: str
    target_model: str
    relation_type: RelationType  # ONE_TO_MANY, MANY_TO_ONE, etc.
    foreign_key: str | None
```

## Query Compilation

Adapters compile DSL requests to native queries:

```python
from ormai.core import QueryRequest, FilterClause

request = QueryRequest(
    model="Order",
    filters=[
        FilterClause(field="status", op="eq", value="pending"),
    ],
    select=["id", "total"],
    limit=10,
)

compiled = adapter.compile(request, policy, principal)
# Returns native ORM query object
```

### Compilation Steps

1. **Validate** - Check model/field access against policy
2. **Inject scopes** - Add tenant/user filters from policy
3. **Build query** - Construct native ORM query
4. **Apply budget** - Add limits and timeouts

## Execution

Execute compiled queries with context:

```python
result = await adapter.execute(compiled, ctx)

print(result.rows)       # Query results
print(result.row_count)  # Number of rows
print(result.execution_time_ms)  # Execution time
```

## Transaction Management

Adapters provide transaction support:

```python
async with adapter.transaction(ctx):
    await toolset.create(ctx, model="Order", data={...})
    await toolset.update(ctx, model="Inventory", ...)
    # Commits on success, rolls back on exception
```

### Savepoints

```python
async with adapter.transaction(ctx) as tx:
    await toolset.create(ctx, model="Order", data={...})

    async with tx.savepoint():
        try:
            await toolset.update(ctx, model="Inventory", ...)
        except InventoryError:
            # Savepoint rolled back, outer transaction continues
            pass
```

## Custom Adapters

Create adapters for unsupported ORMs:

```python
from ormai.adapters import BaseAdapter

class MyORMAdapter(BaseAdapter):
    def introspect(self) -> SchemaMetadata:
        # Extract metadata from your ORM
        ...

    def compile(
        self,
        request: QueryRequest,
        policy: Policy,
        principal: Principal,
    ) -> CompiledQuery:
        # Build native query
        ...

    async def execute(
        self,
        compiled: CompiledQuery,
        ctx: RunContext,
    ) -> ExecutionResult:
        # Execute and return results
        ...
```

## Schema Caching

Cache introspected schemas for performance:

```python
from ormai.utils import SchemaCache, PersistentSchemaCache

# In-memory cache
cache = SchemaCache()
schema = cache.get_or_introspect(adapter)

# Persistent cache (file-based)
cache = PersistentSchemaCache(path="./schema_cache.json")
schema = cache.get_or_introspect(adapter)
```

## Next Steps

- [Tools](tools.md) - Tools that use adapters
- [Policies](policies.md) - How policies affect compilation
- [Write Operations](../guides/write-operations.md) - Mutation handling
