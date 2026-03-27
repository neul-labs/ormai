# Store API Reference

The store module provides audit logging infrastructure.

## AuditStore (Abstract)

Base class for audit storage backends.

```python
from ormai.store import AuditStore
```

### Interface

```python
class AuditStore(ABC):
    @abstractmethod
    async def write(self, record: AuditRecord) -> None:
        """Write an audit record."""

    @abstractmethod
    async def query(
        self,
        filters: dict = {},
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditRecord]:
        """Query audit records."""
```

---

## AuditRecord

Represents a single audit entry.

```python
from ormai.store import AuditRecord
```

### Fields

```python
@dataclass
class AuditRecord:
    id: str
    timestamp: datetime
    request_id: str
    trace_id: str | None

    # Principal
    tenant_id: str
    user_id: str
    roles: list[str]

    # Operation
    tool_name: str
    model: str
    action: str  # "read", "create", "update", "delete"

    # Sanitized inputs
    inputs: dict

    # Policy
    policies_applied: list[str]
    scopes_injected: list[str]
    fields_redacted: list[str]

    # Outcome
    success: bool
    error: ErrorInfo | None
    row_count: int
    execution_time_ms: float

    # Snapshots
    before_snapshot: dict | None
    after_snapshot: dict | None
```

---

## ErrorInfo

Error details for failed operations.

```python
from ormai.store import ErrorInfo
```

```python
@dataclass
class ErrorInfo:
    code: str
    message: str
    details: dict
    stack_trace: str | None = None
```

---

## JsonlAuditStore

File-based JSONL storage.

```python
from ormai.store import JsonlAuditStore
```

### Constructor

```python
JsonlAuditStore(
    path: str,
    rotate_size_mb: int = 100,
    max_files: int = 10,
    retention_days: int | None = None,
)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Path to JSONL file |
| `rotate_size_mb` | `int` | Rotate at this size |
| `max_files` | `int` | Keep this many rotated files |
| `retention_days` | `int \| None` | Delete after this many days |

### Example

```python
store = JsonlAuditStore(
    path="./logs/audit.jsonl",
    rotate_size_mb=100,
    max_files=10,
    retention_days=90,
)

await store.write(record)

records = await store.query(
    filters={"tenant_id": "acme-corp"},
    limit=100,
)
```

---

## TortoiseAuditStore

Database storage using Tortoise ORM.

```python
from ormai.store import TortoiseAuditStore
```

### Constructor

```python
TortoiseAuditStore(
    table_name: str = "audit_records",
)
```

### Example

```python
from tortoise import Tortoise

await Tortoise.init(
    db_url="postgres://localhost/mydb",
    modules={"models": ["ormai.store.tortoise_models"]},
)
await Tortoise.generate_schemas()

store = TortoiseAuditStore()
```

---

## PeeweeAuditStore

Database storage using Peewee.

```python
from ormai.store import PeeweeAuditStore
```

### Constructor

```python
PeeweeAuditStore(
    database: Database,
    table_name: str = "audit_records",
)
```

### Example

```python
from peewee import PostgresqlDatabase

db = PostgresqlDatabase("mydb")
store = PeeweeAuditStore(database=db)

# Create table
store.create_table()
```

---

## AuditMiddleware

Automatically logs all tool operations.

```python
from ormai.store import AuditMiddleware
```

### Constructor

```python
AuditMiddleware(
    store: AuditStore,
    include_snapshots: bool = False,
    snapshot_fields: list[str] | None = None,
    sanitize_inputs: bool = True,
    sanitize_fields: list[str] = ["password", "token", "secret"],
)
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `store` | `AuditStore` | Underlying storage |
| `include_snapshots` | `bool` | Capture before/after for writes |
| `snapshot_fields` | `list[str] \| None` | Fields to include in snapshots |
| `sanitize_inputs` | `bool` | Sanitize sensitive input data |
| `sanitize_fields` | `list[str]` | Field names to sanitize |

### Methods

#### wrap

```python
def wrap(self, toolset: ToolRegistry) -> ToolRegistry:
    """Wrap a toolset with audit logging."""
```

### Example

```python
middleware = AuditMiddleware(
    store=store,
    include_snapshots=True,
    sanitize_inputs=True,
)

audited_toolset = middleware.wrap(toolset)

# All operations are now logged
await audited_toolset.query(ctx, model="Order", ...)
```

---

## Query Filters

Available filters for querying audit records:

| Filter | Type | Description |
|--------|------|-------------|
| `tenant_id` | `str` | Filter by tenant |
| `user_id` | `str` | Filter by user |
| `tool_name` | `str` | Filter by tool |
| `model` | `str` | Filter by model |
| `action` | `str` | Filter by action |
| `success` | `bool` | Filter by success/failure |
| `timestamp_gte` | `datetime` | From timestamp |
| `timestamp_lt` | `datetime` | To timestamp |
| `request_id` | `str` | Filter by request ID |
| `trace_id` | `str` | Filter by trace ID |

### Example

```python
# Failed operations in last 24 hours
records = await store.query(
    filters={
        "success": False,
        "timestamp_gte": datetime.now() - timedelta(hours=24),
    },
    limit=100,
)

# All deletes by a user
records = await store.query(
    filters={
        "user_id": "user-123",
        "action": "delete",
    },
)
```

---

## Export

Export audit records to external formats.

### Methods

```python
await store.export(
    format: str,           # "csv", "json", "parquet"
    output: str,           # Output file path
    filters: dict = {},    # Query filters
    limit: int | None = None,
)
```

### Example

```python
# Export to CSV
await store.export(
    format="csv",
    output="./export/audit_2024.csv",
    filters={
        "timestamp_gte": datetime(2024, 1, 1),
        "timestamp_lt": datetime(2025, 1, 1),
    },
)

# Export to Parquet for analytics
await store.export(
    format="parquet",
    output="./export/audit.parquet",
)
```

---

## Plugins

### LoggingPlugin

Log operations to standard logger.

```python
from ormai.utils import LoggingPlugin
```

```python
plugin = LoggingPlugin(
    logger=my_logger,
    level="INFO",
    include_inputs=True,
    include_outputs=False,
)

toolset.add_plugin(plugin)
```

### MetricsPlugin

Emit metrics for monitoring.

```python
from ormai.utils import MetricsPlugin
```

```python
plugin = MetricsPlugin(
    client=statsd_client,
    prefix="ormai",
    tags={"env": "production"},
)

toolset.add_plugin(plugin)

# Emits:
# ormai.query.count
# ormai.query.duration
# ormai.query.error_rate
# ormai.create.count
# ...
```

### ErrorPlugin

Custom error handling.

```python
from ormai.utils import ErrorPlugin
```

```python
async def handle_error(error: Exception, ctx: RunContext):
    await notify_team(error, ctx)

plugin = ErrorPlugin(handler=handle_error)
toolset.add_plugin(plugin)
```

### PluginChain

Combine multiple plugins.

```python
from ormai.utils import PluginChain

chain = PluginChain([
    LoggingPlugin(logger),
    MetricsPlugin(client),
    ErrorPlugin(handler),
])

toolset.add_plugin(chain)
```
