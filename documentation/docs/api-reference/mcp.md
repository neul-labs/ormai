# MCP API Reference

The MCP (Model Context Protocol) module provides integration with Claude and other MCP-compatible clients.

## McpServerFactory

Factory for creating MCP servers.

```python
from ormai.mcp import McpServerFactory
```

### Constructor

```python
McpServerFactory(
    toolset: ToolRegistry,
    adapter: Adapter,
    policy: Policy,
)
```

### Methods

#### create

```python
def create(
    self,
    config: McpServerConfig,
) -> McpServer:
    """Create an MCP server instance."""
```

### Example

```python
factory = McpServerFactory(
    toolset=toolset,
    adapter=adapter,
    policy=policy,
)

server = factory.create(
    McpServerConfig(
        name="ormai-server",
        version="1.0.0",
    )
)
```

---

## McpServerConfig

Configuration for MCP server.

```python
from ormai.mcp import McpServerConfig
```

### Fields

```python
@dataclass
class McpServerConfig:
    name: str = "ormai"
    version: str = "1.0.0"
    description: str = "OrmAI database tools"

    # Transport
    transport: str = "stdio"  # "stdio", "http", "websocket"
    host: str = "localhost"
    port: int = 8080

    # Auth
    auth_required: bool = False
    auth_type: str = "bearer"  # "bearer", "api_key"
    auth_secret: str | None = None

    # Tools
    include_tools: list[str] | None = None  # None = all
    exclude_tools: list[str] = []
```

---

## OrmAIServerConfig

Extended configuration for OrmAI-specific features.

```python
from ormai.mcp import OrmAIServerConfig
```

### Fields

```python
@dataclass
class OrmAIServerConfig(McpServerConfig):
    # Principal extraction
    extract_principal_from_headers: bool = True
    tenant_header: str = "X-Tenant-ID"
    user_header: str = "X-User-ID"

    # Default principal (for testing)
    default_tenant_id: str | None = None
    default_user_id: str | None = None

    # Audit
    audit_store: AuditStore | None = None

    # Rate limiting
    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = 100
```

---

## Running the Server

### STDIO Transport

For Claude Desktop integration:

```python
server = factory.create(McpServerConfig(transport="stdio"))
await server.run()
```

### HTTP Transport

For HTTP-based access:

```python
server = factory.create(
    McpServerConfig(
        transport="http",
        host="0.0.0.0",
        port=8080,
        auth_required=True,
        auth_type="bearer",
        auth_secret="your-secret",
    )
)
await server.run()
```

---

## McpConfigGenerator

Generate Claude Desktop configuration.

```python
from ormai.mcp import McpConfigGenerator
```

### Methods

#### generate

```python
def generate(
    self,
    command: str,
    args: list[str] = [],
    env: dict[str, str] = {},
) -> dict:
    """Generate Claude Desktop config."""
```

### Example

```python
generator = McpConfigGenerator()

config = generator.generate(
    command="python",
    args=["-m", "myapp.mcp_server"],
    env={
        "DATABASE_URL": "postgres://localhost/mydb",
    },
)

# Output:
{
    "mcpServers": {
        "ormai": {
            "command": "python",
            "args": ["-m", "myapp.mcp_server"],
            "env": {
                "DATABASE_URL": "postgres://localhost/mydb"
            }
        }
    }
}
```

### Save to File

```python
generator.save(
    path="~/.config/claude/claude_desktop_config.json",
    command="python",
    args=["-m", "myapp.mcp_server"],
)
```

---

## Authentication

### Bearer Token

```python
from ormai.mcp import BearerAuthHandler

handler = BearerAuthHandler(
    secret=os.environ["MCP_SECRET"],
    extract_principal=True,
)

server = factory.create(
    McpServerConfig(
        auth_required=True,
        auth_handler=handler,
    )
)
```

### API Key

```python
from ormai.mcp import ApiKeyAuthHandler

handler = ApiKeyAuthHandler(
    valid_keys={"key-1": "tenant-a", "key-2": "tenant-b"},
    header_name="X-API-Key",
)
```

### JWT

```python
from ormai.mcp import JwtAuthHandler

handler = JwtAuthHandler(
    secret=os.environ["JWT_SECRET"],
    algorithm="HS256",
    tenant_claim="org_id",
    user_claim="sub",
)
```

---

## Tool Exposure

Control which tools are exposed via MCP:

```python
config = McpServerConfig(
    # Only expose these tools
    include_tools=["describe_schema", "query", "get"],

    # Or exclude specific tools
    exclude_tools=["delete", "bulk_update"],
)
```

---

## Complete Example

```python
from ormai.quickstart import mount_sqlalchemy
from ormai.mcp import McpServerFactory, OrmAIServerConfig

# Setup toolset
toolset = mount_sqlalchemy(engine, Base, policy)

# Create MCP server
factory = McpServerFactory(toolset, adapter, policy)

config = OrmAIServerConfig(
    name="my-database",
    description="Access to my application database",
    transport="stdio",
    extract_principal_from_headers=True,
    audit_store=JsonlAuditStore("./mcp_audit.jsonl"),
)

server = factory.create(config)

if __name__ == "__main__":
    import asyncio
    asyncio.run(server.run())
```

### Claude Desktop Configuration

```json
{
    "mcpServers": {
        "my-database": {
            "command": "python",
            "args": ["-m", "myapp.mcp_server"],
            "env": {
                "DATABASE_URL": "postgres://localhost/mydb"
            }
        }
    }
}
```

---

## Control Plane

For multi-instance deployments.

### PolicyRegistry

```python
from ormai.control_plane import PolicyRegistry, JsonFilePolicyRegistry
```

```python
registry = JsonFilePolicyRegistry(path="./policies")

# Save policy version
await registry.save(policy, version="v1.2.0")

# Load latest policy
policy = await registry.load_latest()

# Load specific version
policy = await registry.load("v1.1.0")
```

### AuditAggregator

```python
from ormai.control_plane import AuditAggregator
```

```python
aggregator = AuditAggregator(stores=[store1, store2, store3])

# Query across instances
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

### ControlPlaneClient

```python
from ormai.control_plane import ControlPlaneClient
```

```python
client = ControlPlaneClient(url="http://control-plane:8080")

# Fetch latest policy
policy = await client.fetch_policy()

# Report audit records
await client.report_audit(records)
```
