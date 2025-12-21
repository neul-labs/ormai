# OrmAI Utilities Pack

The utilities pack makes OrmAI “complete out of the box” by shipping defaults, builders, and helpers so teams can integrate in one or two files while retaining production-grade safety.

---

## 1. Package Layout

`ormai.utils` contains:

- `defaults` – prebuilt safe profiles.
- `policies` – `PolicyBuilder` and helpers.
- `views` – `ViewFactory` for projection models.
- `tools` – `ToolsetFactory`, structured error hints.
- `session` – session/transaction managers for each adapter.
- `audit` – audit store implementations and middleware.
- `schema_cache` – cached ORM introspection.
- `errors` – shared error taxonomy.
- `testing` – fixtures/eval harness helpers.
- `mcp` – MCP server factory, auth/context helpers.

---

## 2. Easy Defaults

### `DefaultsProfile`

```py
DefaultsProfile(
    mode="prod" | "internal" | "dev",
    max_rows=100,
    max_includes_depth=1,
    max_select_fields=40,
    statement_timeout_ms=2000,
    require_tenant_scope=True,
    require_reason_for_writes=True,
    writes_enabled=False,
    soft_delete=True,
    redact_strategy="deny" | "mask",
    allow_generic_query=True,
    allow_generic_mutations=False,
)
```

Built-in profiles:

- `DEFAULT_PROD` – strict, read-only, low budgets.
- `DEFAULT_INTERNAL` – read-heavy internal agents with higher limits.
- `DEFAULT_DEV` – permissive but still scoped; logs everything.

With a profile plus model list, OrmAI exposes functional read tools immediately.

---

## 3. Policy Utilities

### `PolicyBuilder`

```py
builder = PolicyBuilder(profile=DEFAULT_PROD)
policy = (
    builder
    .register_models([Customer, Order, Subscription])
    .deny_fields(glob="*password*")
    .mask_fields(["email", "phone"])
    .allow_relations({"Order": ["customer", "items"]})
    .tenant_scope(field="tenant_id")
    .build()
)
```

Features:

- Auto-discovers fields/relations from ORM metadata.
- Glob-based allow/deny/mask operations.
- Per-role overlays (`.for_role("support")...`).
- Default rules: deny secrets (`password`, `token`, `api_key`, etc.) and mask common PII (`email`, `phone`, `address`, `ip`, `dob`).

---

## 4. View/Projection Utilities

### `ViewFactory`

Generates Pydantic views aligned with policies:

- Includes only allowed fields.
- Optionally inlines nested relation views up to the allowed depth.
- Infers types from ORM columns.
- Supports multiple named views (e.g., `public` vs `internal`) per resource.

This removes the need to handwrite dozens of view models when bootstrapping.

---

## 5. Tool Utilities

### `ToolsetFactory`

```py
toolset = ToolsetFactory.from_policy(
    policy=policy,
    profile=DEFAULT_PROD,
    adapter=SQLAlchemyAdapter(...)
)
```

Produces:

- `db.describe_schema`
- `db.get`
- `db.query`
- `db.aggregate`
- `db.create` / `db.update` / `db.delete` / `db.bulk_update_by_ids` (enabled only if profile/policy allow writes)

Each rejection carries structured “retry hints” (e.g., “must filter `created_at` within 30 days”) so LLM clients can self-correct.

---

## 6. Session & Transaction Utilities

- **SQLAlchemy `SessionManager`** – request or tool scoped sessions using `sessionmaker`, with automatic rollback/cleanup and nested transaction strategy.
- **Tortoise `TransactionManager`** – wraps `in_transaction()` for async contexts.
- **Peewee `TransactionManager`** – wraps `db.atomic()` with consistent error handling.

Mount examples rely solely on these helpers—no bespoke session boilerplate required.

---

## 7. Audit Utilities

### `AuditStore` interface & implementations

- `SqlAuditStore` (SQLAlchemy), `TortoiseAuditStore`, `PeeweeAuditStore`, `JsonlAuditStore` (dev default).
- Records: tool name, principal, request ID, timestamp, sanitized inputs, policy decisions, row counts, duration, error info, trace IDs.

### `AuditMiddleware`

- Wraps every tool call to guarantee audit entries even if developers forget to log manually.

---

## 8. Schema Cache

`SchemaCache` memoizes adapter introspection:

- In-memory with TTL (default 5 minutes).
- Optional persistent cache keyed by migration hash/version.
- Invalidation hooks for deployments.

Usage:

```py
schema = SchemaCache(ttl_seconds=300).get_or_build(adapter.introspect)
```

---

## 9. Error & Safety Utilities

- Standard error classes/codes: `ORM_ACCESS_DENIED`, `MODEL_NOT_ALLOWED`, `FIELD_NOT_ALLOWED`, `RELATION_NOT_ALLOWED`, `TENANT_SCOPE_REQUIRED`, `QUERY_TOO_BROAD`, `QUERY_BUDGET_EXCEEDED`, `WRITE_DISABLED`, `WRITE_APPROVAL_REQUIRED`, `MAX_AFFECTED_ROWS_EXCEEDED`, `VALIDATION_ERROR`, etc.
- `SafeNotFound` option (default on) returns “not found” when scoping filters remove a record, preventing data leakage.

---

## 10. Testing & Eval Utilities

- Temp DB fixtures for SQLite (SQLAlchemy), in-memory Tortoise, and Peewee.
- Seed helpers for multi-tenant datasets.
- Eval harness helpers to record/replay tool calls, assert budget enforcement, ensure no cross-tenant leakage, and snapshot view outputs.

---

## 11. MCP Utilities

### `McpServerFactory`

```py
server = McpServerFactory(
    toolset=toolset,
    auth=JwtAuth(...),
    ctx_builder=DefaultContextBuilder(...)
).build()
```

- Includes stock auth helpers (`JwtAuth`, `ApiKeyAuth`) and a context builder injecting tenant/user IDs, roles, DB session, request IDs.

---

## 12. Quickstart Helper

`ormai.quickstart.mount_sqlalchemy` (and equivalents for other ORMs) provide a one-function onboarding:

```py
from ormai.quickstart import mount_sqlalchemy

ormai = mount_sqlalchemy(
    engine=engine,
    models=[Customer, Order, Subscription],
    auth=my_auth,
    tenant_field="tenant_id",
    profile="prod",
)
```

Returns:

- Toolset
- MCP server (optional)
- Policy object
- Generated view registry

Works with <30 lines of integration code for a typical FastAPI + SQLAlchemy app.

---

## 13. Default Behaviors

- Reads: default `limit=25`, max `limit=100` (profile dependent); include depth default 0/max 1; tenant scope mandatory unless disabled; `describe_schema` only lists allow-listed resources/fields.
- Writes: disabled by default; when enabled, updates require PKs, bulk operations require explicit IDs, deletes are soft, reason metadata mandatory, max affected rows = 1 unless configured.
- Redaction: denies secrets by pattern, masks PII by pattern, never returns sensitive tokens even if selected.
- Budgets: statement timeout enforced, broad query guard enabled, aggregations allow-list only.

---

## 14. Extensibility

- Utilities are optional—advanced users can configure OrmAI manually.
- Components are composable: `PolicyBuilder` feeds `ToolsetFactory`, schema cache feeds adapters, etc.
- Adapter-friendly: new ORMs only implement the adapter + introspection contract; utilities continue to function.
