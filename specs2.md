## Spec: OrmAI Utilities Pack

Goal: make OrmAI “complete” out of the box by shipping **utilities + safe defaults** that reduce integration work to ~1–2 files, while keeping production safety guarantees.

---

# 1) Package Layout

Add a top-level module: `ormai.utils`

### Submodules

* `ormai.utils.defaults`
* `ormai.utils.policies`
* `ormai.utils.views`
* `ormai.utils.tools`
* `ormai.utils.session`
* `ormai.utils.audit`
* `ormai.utils.schema_cache`
* `ormai.utils.errors`
* `ormai.utils.testing`
* `ormai.utils.mcp`

---

# 2) Easy Defaults

## 2.1 `DefaultsProfile`

A single config object that enables “sane safe mode” with minimal tuning.

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

### Built-in profiles

* `DEFAULT_PROD`: strict, read-only, low limits
* `DEFAULT_INTERNAL`: read-heavy with higher budgets
* `DEFAULT_DEV`: permissive-ish but still scoped, logs everything

**Acceptance criteria**

* A user can mount OrmAI with only `DefaultsProfile` + a list of ORM models and immediately have usable read tools.

---

# 3) Policy Utilities

## 3.1 `PolicyBuilder`

Builds policies from ORM models automatically.

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

### Features

* Auto-discover fields/relations
* Allow/deny with glob patterns
* Per-role overlays: `.for_role("support").mask_fields(...)`

**Defaults**

* Deny common secrets by pattern:

  * `password`, `hashed_password`, `token`, `api_key`, `secret`, `salt`, `ssn`, `private_key`
* Mask common PII by pattern:

  * `email`, `phone`, `address`, `ip`, `dob`

(Still configurable; patterns are shipped as defaults but transparent.)

---

# 4) View/Projection Utilities

## 4.1 `ViewFactory`

Generate safe Pydantic views from ORM models based on policy allowlists.

```py
OrderView = ViewFactory.from_model(Order, policy=policy)
```

### Rules

* Only include allowed fields
* Optionally “inline” nested relation views up to depth
* Output types inferred from ORM column types
* Supports per-resource “public view” vs “internal view”

### Why this utility matters

Most teams won’t handwrite dozens of view models at first. This gives them a safe default that matches policies.

---

# 5) Tool Utilities

## 5.1 `ToolsetFactory`

Instant tool surface with good defaults:

```py
toolset = ToolsetFactory.from_policy(
  policy=policy,
  profile=DEFAULT_PROD,
  adapter=SQLAlchemyAdapter(...)
)
```

### Tools created

* `db.describe_schema`
* `db.get`
* `db.query`
* `db.aggregate`
* `db.create` / `db.update` / `db.delete` (only if enabled by profile/policy)

### Built-in “auto-retry hints”

When rejecting a tool call (too broad, missing scope), the error includes:

* exact missing constraint (“must filter created_at within 30 days”)
* safe suggestion (“add where.created_at.gte …”)

OrmAI uses structured `ModelRetry`-style errors internally (even if not using PydanticAI directly), so LLM clients can self-correct.

---

# 6) Session & Transaction Utilities

## 6.1 `SessionManager` (SQLAlchemy)

Adapters often fail in the “last mile”: session lifecycle. Provide a utility that supports:

* request-scoped session
* tool-call scoped session
* nested transaction strategy
* automatic rollback on exceptions

```py
with SessionManager(sessionmaker) as db:
    ctx = build_ctx(db=db, principal=principal)
```

## 6.2 `TransactionManager` (Tortoise/Peewee)

* Tortoise: `in_transaction()` wrapper
* Peewee: `db.atomic()` wrapper

**Acceptance criteria**

* Mount examples for each ORM need no custom session boilerplate beyond calling `SessionManager/TransactionManager`.

---

# 7) Audit Utilities

## 7.1 `AuditStore` interface + 3 implementations

* `SqlAuditStore` (SQLAlchemy)
* `TortoiseAuditStore`
* `JsonlAuditStore` (dev default)

Record schema:

* tool_name, principal, request_id, timestamp
* inputs (sanitized)
* policy decisions (e.g., injected filters, redactions applied)
* row_count, affected_rows
* duration_ms
* error_type + message
* trace/span ids

## 7.2 `AuditMiddleware`

One-line wrapper that ensures every tool call gets audited even if developer forgets.

---

# 8) Schema Cache Utilities

## 8.1 `SchemaCache`

ORM introspection can be expensive and shouldn’t run every tool call.

Provide:

* in-memory cache with TTL (default 5 minutes)
* optional persistent cache keyed by migration version/hash
* invalidation hook (e.g., on deploy)

```py
schema = SchemaCache(ttl_seconds=300).get_or_build(adapter.introspect)
```

---

# 9) Error & Safety Utilities

## 9.1 Standard error taxonomy

Ship structured error classes with stable codes:

* `ORM_ACCESS_DENIED`
* `MODEL_NOT_ALLOWED`
* `FIELD_NOT_ALLOWED`
* `RELATION_NOT_ALLOWED`
* `TENANT_SCOPE_REQUIRED`
* `QUERY_TOO_BROAD`
* `QUERY_BUDGET_EXCEEDED`
* `WRITE_DISABLED`
* `WRITE_APPROVAL_REQUIRED`
* `MAX_AFFECTED_ROWS_EXCEEDED`
* `VALIDATION_ERROR`

## 9.2 `SafeNotFound`

If tenant scoping filters out a record, return “not found” rather than “forbidden” to avoid leakage.

Configurable:

* `leak_safe_not_found=True` default

---

# 10) Testing Utilities

## 10.1 Fixture helpers

* spin up temp SQLite (SQLAlchemy)
* in-memory Tortoise setup
* Peewee temp DB
* seed data helper

## 10.2 Eval harness helpers

* record/replay tool calls
* assert budget enforcement
* assert no leakage across tenants
* snapshot expected views

---

# 11) MCP Utilities

## 11.1 `McpServerFactory`

One-call MCP server mounting:

```py
server = McpServerFactory(
  toolset=toolset,
  auth=JwtAuth(...),
  ctx_builder=DefaultContextBuilder(...)
).build()
```

### Built-in auth/context helpers

* `JwtAuth` (decode token → principal)
* `ApiKeyAuth`
* `ContextBuilder` that injects:

  * tenant_id, user_id, roles
  * db session/tx
  * request_id

---

# 12) “One-file Quickstart” Default

Provide `ormai.quickstart`:

```py
from ormai.quickstart import mount_sqlalchemy

ormai = mount_sqlalchemy(
  engine=engine,
  models=[Customer, Order, Subscription],
  auth=my_auth,              # required
  tenant_field="tenant_id",  # default
  profile="prod"             # default
)
```

Returns:

* `toolset`
* `mcp_server` (optional)
* `policy`
* `views` registry (auto-generated)

**Acceptance criteria**

* For a typical FastAPI+SQLAlchemy app, this works with <30 lines of integration code.

---

# 13) Default Behaviors (What makes it “easy & complete”)

These defaults must exist and be safe:

### Read defaults

* `limit` default 25, max 100 (profile dependent)
* include depth default 0, max 1
* must have tenant scope unless explicitly disabled
* `describe_schema` returns only allow-listed resources/fields

### Write defaults

* disabled by default
* if enabled:

  * update requires primary key
  * bulk update requires ids
  * delete is soft delete unless overridden
  * every write requires `reason`
  * max affected rows = 1 unless configured

### Redaction defaults

* deny secrets by pattern
* mask PII by pattern
* never return raw tokens/secrets even if selected

### Budgets defaults

* statement timeout enabled
* broad query guard enabled (no “full table scan” queries)
* aggregation allowlist only

---

# 14) Backwards Compatibility / Extensibility

Utilities must be:

* optional: advanced users can bypass factories and configure manually
* composable: `PolicyBuilder` output feeds `ToolsetFactory`, etc.
* adapter-friendly: new ORMs only implement adapter + introspection mapping

---

If you want, next I can write:

* the **exact YAML policy schema** these utilities produce/consume, and
* a minimal “reference quickstart” for **SQLAlchemy async**, **Tortoise**, and **Peewee** showing the drop-in feel.

