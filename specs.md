Below is a detailed spec for an **ORM-native, PydanticAI-style agent runtime/tooling layer** that works as a *drop-in* for existing apps built on **SQLAlchemy, Tortoise ORM, Peewee** (and extensible to Django ORM / others).

I’ll name it **OrmAI** in this doc (placeholder).

---

# OrmAI Specification

## 0. Summary

OrmAI turns an existing Python application’s ORM layer into a **safe, typed, auditable set of agent-callable capabilities** with:

* Pydantic-style typed tool signatures and outputs
* policy-compiled query/mutation execution (no raw ORM exposure)
* multi-tenant / ACL enforcement by construction
* automatic pagination + cost budgets
* audit logging + tracing
* optional approval gates for writes
* MCP server + client mounting (tool exposure)

OrmAI supports multiple ORM backends via adapters:

* SQLAlchemy (sync + async)
* Tortoise ORM (async)
* Peewee (sync)
* (future) Django ORM, Pony, etc.

---

# 1. Goals and Non-goals

## Goals

1. **Drop-in**: integrate with existing apps without rewriting models or service logic.
2. **Safety by default**: tenant scoping, field allowlists, redaction, budgets, and write constraints are enforced server-side.
3. **Typed interface**: tool inputs/outputs are Pydantic models (or compatible) for schema reliability and testing.
4. **Ergonomic**: developers can expose domain tools in a PydanticAI-like way; plus a controlled generic query tool for exploration.
5. **ORM-agnostic core**: shared policy engine + tool runtime; backend-specific compilers/executors.
6. **Auditability**: every tool call produces an audit record; optional before/after for writes.
7. **MCP-ready**: expose a consistent tool surface via MCP server, with auth → context → deps injection.

## Non-goals

* A full agent framework replacement. OrmAI is a **DB capability layer** + runtime.
* Automatic “perfect” text-to-SQL. OrmAI is structured-query and domain-tool-first.
* Replacing your existing auth/ACL model. OrmAI integrates with it.

---

# 2. Key Concepts

## 2.1 Capability, not ORM access

The LLM never sees ORM sessions or raw query builders. It sees:

* **Domain tools** (preferred): business operations implemented in Python.
* **Generic tools** (escape hatch): allow-listed structured query DSL.

## 2.2 Policy-compiled execution

Policies are applied:

* pre-compile (validate)
* compile-time (inject scoping filters)
* post-execution (redaction, shaping, row caps)
* write-time (approval gates, max affected rows)

## 2.3 Views (Projection models)

Results return **Pydantic “views”** rather than ORM objects:

* stable schema
* redaction-friendly
* safe for LLM consumption
* decoupled from ORM internals

---

# 3. Architecture Overview

### Modules

1. **ormai.core**

   * Tool runtime + context + error model
   * Policy engine interfaces
   * DSL schemas + validation
2. **ormai.adapters**

   * SQLAlchemyAdapter
   * TortoiseAdapter
   * PeeweeAdapter
3. **ormai.policy**

   * allowlists, scoping, budgets, write rules
   * field redaction & output shaping
   * query complexity heuristics
4. **ormai.store**

   * audit log store
   * conversation/tool history store (optional)
5. **ormai.mcp**

   * MCP server exposing OrmAI tools
   * auth/context injection hooks
6. **ormai.generators** (optional but high leverage)

   * generate domain tools / view models from ORM metadata + policy config

---

# 4. Runtime & Context Model

## 4.1 Execution Context

A `RunContext` equivalent, carrying:

* `principal`: user_id, roles, org/tenant_id
* `request_id`, trace ids
* `db`: ORM session/transaction handle (adapter-specific)
* `now`, locale, environment tags

### Deps injection

OrmAI provides:

* `DepsBuilder(auth)->Deps` hook
* ensures DB session/transaction lifecycle is correct for each request

---

# 5. Policy Engine

## 5.1 Policy objects

Policies are configured per “resource” (model or view) and per tool.

**Policy layers**:

* **Model policy**: which models can be accessed, read/write allowed
* **Field policy**: which fields can be selected/exposed, which are redacted
* **Relation policy**: which relations can be expanded, max depth
* **Row policy**: scoping rules (tenant/user), soft-delete rules
* **Budget policy**: max rows, max time, max includes, max complexity score
* **Write policy**: allowed ops, max affected rows, approval required, id-required updates

## 5.2 Scoping (Row-level)

Scoping is injected automatically:

* Always apply `tenant_id == ctx.principal.tenant_id` if configured
* Support per-model scoping keys
* Support ownership scoping: `owner_id == ctx.principal.user_id`

Scoping must be applied in the compiler/executor, never “recommended”.

## 5.3 Redaction

Field-level rules:

* `deny`: never return
* `mask`: return masked (e.g., email partially)
* `hash`: stable hash for joins (optional)
* `allow`: return as-is

Redaction happens post-query and must apply equally to domain tools and generic tools.

## 5.4 Query Budgeting

Hard limits:

* max `limit` per request (default 100)
* max includes depth (default 1)
* max total selected fields
* statement timeout (configurable)
* “broad query guard”: block queries without selective filters on large tables

Complexity scoring (heuristic):

* each filter adds cost
* each include adds cost
* each aggregation adds cost
* reject if score > threshold

## 5.5 Write Controls

Default write stance: **conservative**.

* `update` requires primary key (no blanket updates)
* bulk ops require explicit ids
* deletes are soft by default
* require `reason` metadata for any mutation
* optional approval workflow

---

# 6. Tool Surface

OrmAI exposes two families: **generic DB tools** + **domain tools**.

## 6.1 Generic DB tools (controlled)

### Tool: `db.describe_schema`

Returns allow-listed schema metadata:

* models/resources
* fields with types
* relations and allowed includes
* allowed operations per resource

### Tool: `db.query`

Takes structured DSL:

* model/resource
* select fields (must be allow-listed)
* where (safe ops only)
* order_by
* limit + cursor pagination
* include (allow-listed relations up to depth)

### Tool: `db.get`

Fetch by primary key (and optional include)

### Tool: `db.aggregate`

Safe aggregations (count/sum/min/max) on allow-listed numeric/date fields, with filters.

### Tool: `db.mutate` (split into specific ops in practice)

Prefer explicit tools:

* `db.create`
* `db.update`
* `db.delete` (soft)
* `db.bulk_update_by_ids`

Each requires `reason`, and returns:

* affected rows
* the updated view (or ids)
* audit id

## 6.2 Domain tools (preferred)

Developers register Python functions with typed Pydantic signatures and outputs. OrmAI enforces:

* tool arg validation
* scoping + ACL checks (policy hook + app hook)
* redaction
* auditing

Domain tools can call ORM directly **inside the app**, but must go through OrmAI’s “safe session” and “policy helpers” to avoid bypassing controls.

---

# 7. Structured Query DSL

## 7.1 Allowed operators

* `eq`, `ne`
* `in`, `not_in`
* `lt`, `lte`, `gt`, `gte`
* `is_null`
* string: `contains`, `startswith`, `endswith` (backend permitting)
* date: `between`
* boolean: `true/false` via eq

Disallowed by default:

* regex
* arbitrary SQL fragments
* custom functions unless allow-listed

## 7.2 Pagination

Cursor-based pagination:

* deterministic order_by required for cursor
* OrmAI returns `next_cursor`, `has_more`

## 7.3 Includes/expansion

`include: ["customer", "items"]` with:

* per-relation allowlist
* max depth
* optional per-relation field subset

---

# 8. Adapter Requirements

Each ORM adapter must implement:

## 8.1 Introspection

* list models/resources
* fields + types
* primary keys
* relations
* table size estimate (optional but useful for broad query guard)

## 8.2 Compile

DSL → backend query object:

* inject scoping filters
* apply field selection
* apply includes
* apply budgets (limit/timeout)
* apply ordering/cursor

## 8.3 Execute

* run query
* map results to view models
* apply redaction
* return page info

## 8.4 Transactions

* supports “tool call inside transaction”
* per-request session lifecycle hooks
* nested transaction strategy documented per backend

### Backend notes

* **SQLAlchemy**: use selectable constructs + loader options for includes; support async session.
* **Tortoise**: use `.filter()`, `.prefetch_related()`, `.only()`; async execution.
* **Peewee**: use `Model.select()`, `where()`, `join()` in allow-listed ways; likely more limited include strategy.

---

# 9. Storage and Auditing

## 9.1 Audit log record

For every tool call:

* tool name
* principal (user_id/tenant_id/roles)
* timestamp
* inputs (sanitized)
* policy decisions (e.g., injected tenant filter)
* row count returned/affected
* duration
* error details (if any)
* trace/span ids

Backends:

* SQLAlchemy store
* Tortoise store
* Peewee store
* fallback JSONL (dev)

## 9.2 Optional: message history store

If you want “agent memory” stored in DB:

* store message list + tool call list
* store references to audit ids
* allow replay in eval harness

---

# 10. MCP Integration

OrmAI ships an MCP server that exposes the generic tools and any registered domain tools.

## 10.1 Auth → Context

MCP request comes with auth:

* decode token
* build principal
* open DB session
* attach to deps/context

## 10.2 Tool schemas

All tools expose JSON schemas derived from Pydantic models (or equivalent).

## 10.3 Safety invariants

Even if MCP client is compromised:

* policies still apply
* scoping still injects
* redaction still happens
* budgets still enforced

---

# 11. Developer Experience

## 11.1 Drop-in setup examples

### SQLAlchemy

* `OrmAI.from_sqlalchemy(engine, model_registry=..., policies=...)`
* or mount into existing session maker

### Tortoise

* `OrmAI.from_tortoise(models=..., policies=...)`

### Peewee

* `OrmAI.from_peewee(db, models=..., policies=...)`

## 11.2 Policy configuration format

YAML/JSON with:

* resources: model -> read/write settings
* fields: allow/deny/mask
* relations: allow + depth
* scoping rules
* budgets
* write rules (approval, max affected rows)

## 11.3 Generators (optional)

* generate view models from ORM models (allow-listed fields only)
* generate basic domain tools: `get_x`, `list_x`, `create_x`, `update_x_by_id`
* generate schema docs for LLM planning

---

# 12. Clear Use Cases

## 12.1 Customer Support Agent (read-heavy)

* “Find the user’s last 5 orders and shipment status”
* “Show subscription status and recent invoices”
  Constraints:
* strict tenant scoping
* redact PII
* budget queries
  Tools:
* domain tools for common flows + limited `db.query` for edge cases

## 12.2 Operations / Admin Console Agent (controlled write)

* “Refund order 123”
* “Pause subscription for customer 456”
  Constraints:
* approval required for write tools
* id-required updates
* audit + reason mandatory
* max affected rows = 1
  Tools:
* domain tools only; generic mutation tools disabled

## 12.3 Analytics-lite Agent (aggregations)

* “How many signups last week by plan?”
* “Top 10 products by revenue yesterday”
  Constraints:
* aggregation allowlist
* no raw joins beyond allowed relations
* timeout + complexity scoring
  Tools:
* `db.aggregate`, `db.query` with group-by support (optional v2)

## 12.4 Developer Copilot for Internal Debugging

* “Why is this customer failing checkout?”
* “Show related records for session_id X”
  Constraints:
* broader access but still role-gated
* higher budgets but capped
  Tools:
* `describe_schema`, `get`, `query` with includes

## 12.5 Migration-safe “Schema-aware” Agent (future)

* when schema changes, OrmAI introspection + policies update
* agent continues functioning using view models and schema metadata
  Constraints:
* versioned policies
* compatibility checks in CI

---

# 13. Security Model

Minimum required guarantees:

* No cross-tenant leakage (scoping injected)
* No PII leakage (redaction enforced)
* No runaway queries (budgets/timeouts)
* No mass writes (id-required, bulk-by-ids only)
* Full auditability (immutable logs)

Threats addressed:

* prompt injection
* malicious MCP clients
* accidental “SELECT *” or “UPDATE without WHERE”
* inference leaks via joins/includes

---

# 14. Phased Delivery Plan

## Phase 1 (MVP)

* SQLAlchemy adapter (sync/async)
* Tortoise adapter (async)
* Peewee adapter (sync, limited includes)
* tools: describe_schema, get, query, aggregate
* read-only by default + audit store
* policies: allowlists, scoping, redaction, budgets
* MCP server basic

## Phase 2 (Writes)

* create/update/delete tools with strict controls
* approval gates (deferred tool pattern)
* write audit with before/after option

## Phase 3 (DX + Reliability)

* generators for views/tools
* advanced pagination + cursor stability
* eval harness fixtures + replay
* richer cost model

---

# 15. Compatibility and Extensibility

To support “peewee etc” cleanly, keep the core independent:

* DSL + policies + tool runtime are backend-agnostic
* each adapter provides introspect/compile/execute
* policy engine never imports ORM-specific constructs

Add new ORM support by implementing `Adapter` interface.

---

If you want, next I can produce:

1. a **concrete policy config schema** (YAML) + examples (multi-tenant SaaS, admin console, support agent), and
2. the **exact JSON schemas** for the MCP tools (so you can start implementing the server + client immediately).

