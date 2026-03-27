# Audit Logging

OrmAI provides comprehensive audit logging for all operations. Every tool call is recorded with context, inputs, policy decisions, and outcomes.

## Why Audit Logging?

When AI agents access your database, you need visibility into:

- What data was accessed or modified
- Who (which principal) made the request
- What policies were applied
- Whether operations succeeded or failed
- Performance characteristics

## Audit Record Structure

Each operation creates an `AuditRecord`:

```python
@dataclass
class AuditRecord:
    id: str                    # Unique record ID
    timestamp: datetime        # When the operation occurred
    request_id: str            # Request correlation ID
    trace_id: str | None       # Distributed tracing ID

    # Principal info
    tenant_id: str
    user_id: str
    roles: list[str]

    # Operation details
    tool_name: str             # e.g., "query", "create"
    model: str                 # Target model
    action: str                # "read", "create", "update", "delete"

    # Sanitized inputs (no sensitive data)
    inputs: dict

    # Policy decisions
    policies_applied: list[str]
    scopes_injected: list[str]
    fields_redacted: list[str]

    # Outcome
    success: bool
    error: ErrorInfo | None
    row_count: int
    execution_time_ms: float

    # Optional snapshots for writes
    before_snapshot: dict | None
    after_snapshot: dict | None
```

## Audit Stores

OrmAI supports multiple audit storage backends:

### JSONL Store

File-based storage in JSON Lines format:

```python
from ormai.store import JsonlAuditStore

store = JsonlAuditStore(
    path="./audit.jsonl",
    rotate_size_mb=100,  # Rotate at 100MB
    max_files=10,        # Keep 10 rotated files
)
```

Output format:

```json
{"id": "aud-123", "timestamp": "2024-01-15T10:30:00Z", "tool_name": "query", ...}
{"id": "aud-124", "timestamp": "2024-01-15T10:30:01Z", "tool_name": "get", ...}
```

### Tortoise Store

Database-backed storage using Tortoise ORM:

```python
from ormai.store import TortoiseAuditStore

store = TortoiseAuditStore()
# Uses your existing Tortoise connection
```

### Peewee Store

Database-backed storage using Peewee:

```python
from ormai.store import PeeweeAuditStore

store = PeeweeAuditStore(database=db)
```

### Custom Stores

Implement the `AuditStore` interface:

```python
from ormai.store import AuditStore, AuditRecord

class MyAuditStore(AuditStore):
    async def write(self, record: AuditRecord) -> None:
        # Write to your backend (Elasticsearch, CloudWatch, etc.)
        ...

    async def query(
        self,
        filters: dict,
        limit: int = 100,
    ) -> list[AuditRecord]:
        # Query records
        ...
```

## Audit Middleware

The `AuditMiddleware` automatically logs all tool calls:

```python
from ormai.store import AuditMiddleware

middleware = AuditMiddleware(
    store=store,
    include_snapshots=True,  # Capture before/after for writes
    sanitize_inputs=True,    # Remove sensitive data from inputs
)

# Wrap your toolset
audited_toolset = middleware.wrap(toolset)

# All operations are now logged
await audited_toolset.query(ctx, model="Order", ...)
```

### Input Sanitization

Sensitive fields are automatically sanitized:

```python
# Original input
{"model": "User", "filters": [{"field": "password", "op": "eq", "value": "secret123"}]}

# Sanitized in audit log
{"model": "User", "filters": [{"field": "password", "op": "eq", "value": "[REDACTED]"}]}
```

### Write Snapshots

For write operations, capture before and after states:

```python
AuditMiddleware(
    store=store,
    include_snapshots=True,
    snapshot_fields=["id", "status", "updated_at"],  # Limit captured fields
)
```

## Querying Audit Logs

Query audit records programmatically:

```python
# Find all operations by a user
records = await store.query(
    filters={"user_id": "u-123"},
    limit=100,
)

# Find failed operations
records = await store.query(
    filters={"success": False},
    limit=100,
)

# Find operations on a specific model
records = await store.query(
    filters={"model": "Order", "action": "delete"},
    limit=100,
)
```

### Time-Range Queries

```python
from datetime import datetime, timedelta

records = await store.query(
    filters={
        "timestamp_gte": datetime.now() - timedelta(hours=24),
        "timestamp_lt": datetime.now(),
    },
)
```

## Audit Aggregation

For multi-instance deployments, aggregate audit logs:

```python
from ormai.control_plane import AuditAggregator

aggregator = AuditAggregator(stores=[store1, store2, store3])

# Query across all instances
records = await aggregator.query(
    filters={"tenant_id": "acme-corp"},
    limit=1000,
)

# Aggregate metrics
metrics = await aggregator.metrics(
    group_by=["tool_name", "model"],
    time_range="last_24h",
)
```

## Compliance Features

### Immutability

Audit records are append-only. Once written, they cannot be modified or deleted through the OrmAI API.

### Retention Policies

Configure retention for compliance:

```python
store = JsonlAuditStore(
    path="./audit.jsonl",
    retention_days=90,  # Auto-delete after 90 days
)
```

### Export

Export audit logs for external analysis:

```python
# Export to CSV
await store.export(
    format="csv",
    output="./audit_export.csv",
    filters={"timestamp_gte": start_date},
)

# Export to Parquet
await store.export(
    format="parquet",
    output="./audit_export.parquet",
)
```

## Error Information

Failed operations include detailed error info:

```python
@dataclass
class ErrorInfo:
    code: str              # Error code (e.g., "MODEL_NOT_ALLOWED")
    message: str           # Human-readable message
    details: dict          # Additional context
    stack_trace: str | None  # Optional stack trace (dev only)
```

Example audit record for a failed operation:

```json
{
    "id": "aud-456",
    "success": false,
    "error": {
        "code": "QUERY_BUDGET_EXCEEDED",
        "message": "Query exceeds row limit of 1000",
        "details": {
            "requested_limit": 5000,
            "max_allowed": 1000
        }
    }
}
```

## Integration with Observability

### Structured Logging

```python
from ormai.utils import LoggingPlugin

plugin = LoggingPlugin(
    logger=my_logger,
    level="INFO",
    include_inputs=True,
)

toolset.add_plugin(plugin)
```

### Metrics

```python
from ormai.utils import MetricsPlugin

plugin = MetricsPlugin(
    client=my_metrics_client,
    prefix="ormai",
)

toolset.add_plugin(plugin)
# Emits: ormai.query.count, ormai.query.duration, ormai.query.error_rate
```

### Tracing

Pass trace IDs through context:

```python
ctx = RunContext(
    principal=principal,
    db=session,
    trace_id=request.headers.get("X-Trace-ID"),
)
```

Trace IDs appear in all audit records for correlation.

## Next Steps

- [Views](views.md) - Projection models
- [Evaluation & Testing](../guides/evaluation.md) - Replay and testing
- [Control Plane](../api-reference/mcp.md) - Centralized management
