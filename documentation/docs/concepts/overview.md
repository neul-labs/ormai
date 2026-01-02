# Core Concepts

OrmAI is built on a few key principles that ensure safe, auditable database access for AI agents.

## The Problem

AI agents need database access to be useful, but giving them raw ORM handles is dangerous:

- **No access control**: Agents can read any data
- **No tenant isolation**: Cross-tenant data leakage is possible
- **Unbounded queries**: Agents can execute expensive queries
- **No audit trail**: No visibility into what agents accessed

## The Solution

OrmAI provides a **policy-compiled execution layer** that sits between agents and your database:

```
Agent Request → Policy Validation → Query Compilation → Execution → Redaction → Response
```

## Key Concepts

### 1. Principals

A `Principal` represents the identity making the request:

```python
principal = Principal(
    tenant_id="acme-corp",
    user_id="user-123",
    roles=["admin"],
)
```

Principals enable automatic scoping and role-based access control.

### 2. Policies

Policies define what can be accessed and how:

```python
policy = Policy(
    models={
        "User": ModelPolicy(
            allowed=True,
            fields={
                "email": FieldPolicy(action=FieldAction.Mask),
            },
            scoping={"tenant_id": "principal.tenant_id"},
        ),
    },
    budget=Budget(max_rows=1000),
)
```

### 3. Adapters

Adapters translate OrmAI's query DSL to your ORM's native operations:

- **SQLAlchemyAdapter**: Sync and async SQLAlchemy support
- **TortoiseAdapter**: Async Tortoise ORM support
- **PeeweeAdapter**: Sync Peewee support
- **DjangoAdapter**: Django ORM support

### 4. Tools

Tools are the interface agents use to interact with data:

| Tool | Purpose |
|------|---------|
| `DescribeSchemaTool` | Discover available models and fields |
| `QueryTool` | Query records with filters |
| `GetTool` | Fetch a single record by ID |
| `AggregateTool` | Compute aggregations |
| `CreateTool` | Create new records |
| `UpdateTool` | Update existing records |
| `DeleteTool` | Delete records |

### 5. Audit Store

Every operation is logged to an audit store:

```python
store = JsonlAuditStore(path="./audit.jsonl")

# Or database-backed
store = TortoiseAuditStore()
```

Audit records include:
- Request ID and timestamp
- Principal information
- Tool called and sanitized inputs
- Policy decisions
- Row counts and execution time

## Execution Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    1. Request Arrives                        │
│    Agent calls tool with model, filters, select, etc.       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    2. Policy Validation                      │
│    - Is model allowed?                                       │
│    - Are requested fields allowed?                          │
│    - Is include depth within budget?                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    3. Scope Injection                        │
│    - Add tenant_id = principal.tenant_id                    │
│    - Add user_id = principal.user_id (if configured)        │
│    - Apply row-level policies                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    4. Query Compilation                      │
│    - DSL → Native ORM query                                 │
│    - Apply select, filters, order, limit                    │
│    - Apply budget constraints (timeout, row limit)          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    5. Execution                              │
│    - Execute query against database                         │
│    - Track execution time and row count                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    6. Post-Processing                        │
│    - Apply field redaction (mask, hash, deny)               │
│    - Validate row count within budget                       │
│    - Build response with pagination info                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    7. Audit Logging                          │
│    - Record operation to audit store                        │
│    - Include sanitized request and policy decisions         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    8. Response                               │
│    - Return data to agent                                   │
│    - Include pagination cursor if applicable                │
└─────────────────────────────────────────────────────────────┘
```

## Design Principles

### 1. Defense in Depth

Security is applied at multiple layers:
- Input validation (model/field allowlists)
- Query compilation (scope injection)
- Execution (budget enforcement)
- Output (redaction)

### 2. Fail Closed

If something is not explicitly allowed, it's denied:
- Models must be in the allowlist
- Fields default to denied unless specified
- Scoping is required for multi-tenant models

### 3. Minimal Privilege

Agents get the minimum access needed:
- Only allowed fields are visible
- Only allowed operations are available
- Only own-tenant data is accessible

### 4. Complete Auditability

Every operation is logged:
- Who (principal)
- What (tool, model, filters)
- When (timestamp)
- How (policy decisions)
- Outcome (success/error, row count)

## Next Steps

- [Policies](policies.md) - Deep dive into policy configuration
- [Adapters](adapters.md) - ORM adapter details
- [Tools](tools.md) - Available tools and usage
