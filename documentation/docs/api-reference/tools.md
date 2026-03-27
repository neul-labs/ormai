# Tools API Reference

Tools provide the interface for AI agents to interact with data.

## Tool Base Class

```python
from ormai.tools import Tool, ToolResult
```

### Tool

```python
class Tool(ABC):
    name: str
    description: str

    @abstractmethod
    async def execute(self, ctx: RunContext, **kwargs) -> ToolResult:
        ...
```

### ToolResult

```python
@dataclass
class ToolResult:
    success: bool
    data: Any
    error: str | None = None
    metadata: dict = field(default_factory=dict)
```

---

## Read Tools

### DescribeSchemaTool

Describe available models and fields.

```python
from ormai.tools import DescribeSchemaTool
```

#### Signature

```python
async def execute(
    self,
    ctx: RunContext,
) -> ToolResult:
```

#### Response

```python
{
    "models": {
        "User": {
            "fields": ["id", "name", "email"],
            "relations": ["orders"],
            "writable": false
        },
        "Order": {
            "fields": ["id", "status", "total"],
            "relations": ["user", "items"],
            "writable": true
        }
    }
}
```

---

### QueryTool

Query multiple records.

```python
from ormai.tools import QueryTool
```

#### Signature

```python
async def execute(
    self,
    ctx: RunContext,
    model: str,
    filters: list[dict] = [],
    select: list[str] | None = None,
    order: list[dict] = [],
    include: list[dict] = [],
    limit: int = 50,
    cursor: str | None = None,
) -> ToolResult:
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | `str` | Model name |
| `filters` | `list[dict]` | Filter conditions |
| `select` | `list[str] \| None` | Fields to return |
| `order` | `list[dict]` | Ordering directives |
| `include` | `list[dict]` | Relations to include |
| `limit` | `int` | Maximum rows (default: 50) |
| `cursor` | `str \| None` | Pagination cursor |

#### Response

```python
{
    "rows": [...],
    "total": 100,
    "has_more": true,
    "next_cursor": "eyJpZCI6MTIzfQ=="
}
```

---

### GetTool

Fetch a single record by ID.

```python
from ormai.tools import GetTool
```

#### Signature

```python
async def execute(
    self,
    ctx: RunContext,
    model: str,
    id: Any,
    select: list[str] | None = None,
    include: list[dict] = [],
) -> ToolResult:
```

#### Response

Returns single record or error if not found.

---

### AggregateTool

Compute aggregations.

```python
from ormai.tools import AggregateTool
```

#### Signature

```python
async def execute(
    self,
    ctx: RunContext,
    model: str,
    filters: list[dict] = [],
    aggregations: list[dict],
    group_by: list[str] = [],
) -> ToolResult:
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | `str` | Model name |
| `filters` | `list[dict]` | Filter conditions |
| `aggregations` | `list[dict]` | Aggregation operations |
| `group_by` | `list[str]` | Grouping fields |

#### Aggregation Format

```python
{
    "function": "count" | "sum" | "avg" | "min" | "max",
    "field": "field_name",  # Required for sum, avg, min, max
    "alias": "output_name"
}
```

---

## Write Tools

### CreateTool

Create a new record.

```python
from ormai.tools import CreateTool
```

#### Signature

```python
async def execute(
    self,
    ctx: RunContext,
    model: str,
    data: dict,
) -> ToolResult:
```

#### Response

Returns created record with generated fields (id, timestamps).

---

### UpdateTool

Update an existing record.

```python
from ormai.tools import UpdateTool
```

#### Signature

```python
async def execute(
    self,
    ctx: RunContext,
    model: str,
    id: Any,
    data: dict,
) -> ToolResult:
```

---

### DeleteTool

Delete a record.

```python
from ormai.tools import DeleteTool
```

#### Signature

```python
async def execute(
    self,
    ctx: RunContext,
    model: str,
    id: Any,
) -> ToolResult:
```

---

### BulkUpdateTool

Update multiple records.

```python
from ormai.tools import BulkUpdateTool
```

#### Signature

```python
async def execute(
    self,
    ctx: RunContext,
    model: str,
    filters: list[dict],
    data: dict,
) -> ToolResult:
```

#### Response

```python
{"updated_count": 15}
```

---

## ToolRegistry

Manages tool registration and lookup.

```python
from ormai.tools import ToolRegistry
```

### Constructor

```python
ToolRegistry()
```

### Methods

#### register

```python
def register(self, tool: Tool) -> None:
```

#### get

```python
def get(self, name: str) -> Tool | None:
```

#### items

```python
def items(self) -> Iterator[tuple[str, Tool]]:
```

#### to_openai_functions

```python
def to_openai_functions(self) -> list[dict]:
```

#### to_anthropic_tools

```python
def to_anthropic_tools(self) -> list[dict]:
```

### Example

```python
registry = ToolRegistry()

registry.register(QueryTool(adapter, policy))
registry.register(GetTool(adapter, policy))
registry.register(CreateTool(adapter, policy))

# Get tool by name
tool = registry.get("query")

# Export for LLM
functions = registry.to_openai_functions()
```

---

## DeferredExecutor

Handles operations requiring approval.

```python
from ormai.tools import DeferredExecutor, DeferredResult
```

### Constructor

```python
DeferredExecutor(
    approval_gate: ApprovalGate,
    timeout_seconds: int = 3600,
)
```

### Methods

#### defer

```python
async def defer(
    self,
    tool: Tool,
    ctx: RunContext,
    **kwargs,
) -> DeferredResult:
```

#### execute

```python
async def execute(self, deferred_id: str) -> ToolResult:
```

#### cancel

```python
async def cancel(self, deferred_id: str) -> None:
```

#### status

```python
async def status(self, deferred_id: str) -> str:
```

### DeferredResult

```python
@dataclass
class DeferredResult:
    id: str
    status: str  # "pending_approval", "approved", "rejected", "expired"
    tool_name: str
    model: str
    created_at: datetime
    expires_at: datetime
```

---

## Approval Gates

### ApprovalGate (Abstract)

```python
from ormai.utils import ApprovalGate

class ApprovalGate(ABC):
    @abstractmethod
    async def request_approval(self, operation: dict) -> str:
        """Returns approval request ID."""

    @abstractmethod
    async def check_approval(self, request_id: str) -> str:
        """Returns status: pending, approved, rejected."""
```

### AutoApproveGate

Automatically approves all operations (for testing).

```python
from ormai.utils import AutoApproveGate

gate = AutoApproveGate()
```

### CallbackApprovalGate

Uses a callback for approval decisions.

```python
from ormai.utils import CallbackApprovalGate

async def check(operation: dict) -> bool:
    # Custom approval logic
    return await my_approval_service.check(operation)

gate = CallbackApprovalGate(callback=check)
```

### InMemoryApprovalQueue

Queue-based approval for development.

```python
from ormai.utils import InMemoryApprovalQueue

queue = InMemoryApprovalQueue()

# In your application
pending = await queue.get_pending()
await queue.approve(pending[0].id)
# or
await queue.reject(pending[0].id, reason="Invalid operation")
```

---

## ToolsetFactory

Generate complete toolsets.

```python
from ormai.utils import ToolsetFactory
```

### Constructor

```python
ToolsetFactory(
    adapter: Adapter,
    policy: Policy,
    audit_store: AuditStore | None = None,
)
```

### Methods

#### create_read_toolset

```python
def create_read_toolset(self) -> ToolRegistry:
    """Create toolset with read-only tools."""
```

#### create_full_toolset

```python
def create_full_toolset(
    self,
    approval_gate: ApprovalGate | None = None,
) -> ToolRegistry:
    """Create toolset with all tools."""
```

### Example

```python
factory = ToolsetFactory(adapter, policy, audit_store)

# Read-only for agents
read_toolset = factory.create_read_toolset()

# Full access with approval
full_toolset = factory.create_full_toolset(
    approval_gate=approval_gate,
)
```
