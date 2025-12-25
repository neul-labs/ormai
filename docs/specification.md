# OrmAI Specification

OrmAI is a runtime/tooling layer that converts an application’s existing ORM models into safe, typed, auditable capabilities for automated agents. It extends mature ORMs (SQLAlchemy, Tortoise ORM, Peewee, with room for Django ORM/Pony/etc.) with policy-governed query/mutation execution, reliable tool schemas, and MCP exposure—without forcing teams to rewrite service logic.

---

## 0. Summary

OrmAI provides:

- Pydantic-style typed tool signatures and responses.
- Policy-compiled, adapter-specific query/mutation execution instead of raw ORM exposure.
- Built-in tenant scoping, ACL enforcement, and field-level redaction.
- Automatic pagination, cost/budget controls, and query complexity guards.
- Immutable audit logging plus tracing hooks.
- Optional approval workflows for write operations.
- MCP server/client mounting so tools can be consumed consistently.

Adapters target SQLAlchemy (sync/async), Tortoise ORM (async), and Peewee (sync) initially, with a backend-agnostic policy/DSL core for future ORMs.

---

## 1. Goals vs. Non-goals

### Goals

1. **Drop-in integration** – reuse existing models and contexts rather than rewriting data layers.
2. **Safety by default** – apply scoping, field allowlists, redaction, and budgets server-side.
3. **Typed surface area** – expose Pydantic (or compatible) request/response models for reliability and regression tests.
4. **Ergonomics** – let developers expose domain tools in a PydanticAI-like fashion plus offer a constrained generic query DSL.
5. **ORM-agnostic core** – keep policies, DSL, and runtime independent from ORM specifics.
6. **Auditability** – generate an audit event for every tool call and optionally capture before/after snapshots for writes.
7. **MCP readiness** – mount OrmAI tools via MCP with auth → context → dependency injection.

### Non-goals

- Replacing full agent frameworks—OrmAI is a DB capability layer and runtime.
- Delivering perfect text-to-SQL—OrmAI emphasizes structured queries and domain tools.
- Replacing existing auth/ACL systems—OrmAI integrates with them.

---

## 2. Key Concepts

### Capability, not ORM exposure

- Agents see curated **domain tools** (Python functions with policy wrappers) and a **generic DSL toolset**, never sessions or query builders.

### Policy-compiled execution

- Policies are evaluated at validation, compile time (injected filters), and post-execution (redaction, row caps).
- Write policies govern approval, affected rows, and reasons.

### Views / Projection Models

- Responses are Pydantic view models, not ORM entities.
- Views stabilize schemas for LLMs, simplify redaction, and reduce coupling to ORM internals.

---

## 3. Architecture Overview

### Module layout

1. **`ormai.core`**
   - Tool runtime, execution context, error taxonomy, DSL schemas.
2. **`ormai.adapters`**
   - `SQLAlchemyAdapter`, `TortoiseAdapter`, `PeeweeAdapter`, `DjangoAdapter`, `SQLModelAdapter` implementing introspection, compile, execute, and session lifecycle.
3. **`ormai.policy`**
   - Allowlist configuration, scoping hooks, budget enforcement, write controls, redaction logic.
4. **`ormai.store`**
   - Audit log storage and optional conversation/tool history stores.
5. **`ormai.mcp`**
   - MCP server exposing OrmAI tools with auth/context injection.
6. **`ormai.generators`**
   - Optional utilities to derive domain tools or view models from ORM metadata and policy definitions.
7. **`ormai.utils`**
   - Defaults, policy builders, view/tool factories, session/audit helpers, schema cache, testing utilities, and MCP mounting helpers for fast integration.
8. **`ormai.integrations`**
   - FastAPI integration (`OrmAIRouter`, `mount_ormai`)
   - LangGraph/LangChain integration (`OrmAIToolkit`, `ormai_toolset_to_langchain`)
9. **`ormai.control_plane`**
   - Policy Registry for versioned policy management
   - Audit Aggregator for cross-instance log querying
   - Client SDK for connecting instances to control plane
   - Server for centralized management

---

## 4. Runtime & Context Model

### Execution context

OrmAI runs each tool call inside a `RunContext`-style object that carries:

- `principal` – user/tenant identifiers, roles.
- `request_id` plus trace IDs.
- `db` – adapter-specific session/transaction handle.
- `now`, locale, environment tags as needed.

### Dependency/session management

- `DepsBuilder` builds request-scoped dependencies from auth claims.
- OrmAI enforces correct session/transaction lifecycle per tool call, rolling back on errors and closing resources predictably.

---

## 5. Policy Engine

### Policy objects

Policies exist per resource (model/view) and per tool. Layered elements include:

- **Model policies** – access allowlists, read/write flags.
- **Field policies** – allow, deny, mask, or hash fields.
- **Relation policies** – allowed expansions and max depth.
- **Row policies** – tenant/ownership scoping, soft-delete handling.
- **Budgets** – row limits, include depth, selected field counts, statement timeout, complexity thresholds.
- **Write policies** – permissible operations, max affected rows, approval requirements, primary-key enforcement.

### Scoping rules

- Automatic injection of tenant filters (e.g., `tenant_id == ctx.principal.tenant_id`) or ownership filters.
- Per-model scoping fields with optional overrides.
- Scoping is enforced in the compiler/executor rather than suggested to the LLM.

### Redaction

- Field-level redaction stages after query execution, applying deny/mask/hash rules to both domain and generic tools.

### Query budgeting

- Hard caps on `limit`, includes depth, selected field counts, and query duration.
- Complexity scoring penalizes filters, includes, and aggregations; requests exceeding thresholds are rejected.
- Broad query guard blocks unfiltered scans on large tables.

### Write controls

- Conservative defaults: updates require primary keys; deletes are soft; bulk operations require explicit IDs.
- Mutations require `reason` metadata and may trigger approval workflows.
- Max affected rows enforced per tool/resource.

---

## 6. Tool Surface

### Generic DB tools

- `db.describe_schema` – returns allow-listed models, fields, relations, and permitted operations.
- `db.query` – structured DSL specifying model, select fields, filters, order, pagination cursors, includes.
- `db.get` – fetch by primary key plus optional includes.
- `db.aggregate` – controlled aggregations (count/sum/min/max) on whitelisted numeric/date fields.
- `db.create`, `db.update`, `db.delete`, `db.bulk_update_by_ids` – strict write interfaces requiring reasons and enforcing policy guardrails.

### Domain tools

- Preferred approach where developers register Python functions with Pydantic signatures.
- OrmAI validates inputs, injects scoping, enforces policies, and performs auditing even if service code is imperfect.
- Domain tools access ORM sessions via OrmAI’s safe session context to avoid bypassing controls.

---

## 7. Structured Query DSL

### Operators

- Equality/inequality: `eq`, `ne`, `in`, `not_in`.
- Comparison: `lt`, `lte`, `gt`, `gte`.
- Null checks: `is_null`.
- String ops: `contains`, `startswith`, `endswith` (backend permitting).
- Date ops: `between`.
- Boolean checks via equality.
- Disallowed by default: regex, arbitrary SQL fragments, custom functions (unless allow-listed).

### Pagination

- Cursor-based pagination with deterministic `order_by` per page.
- Responses include `next_cursor` and `has_more`.

### Includes/expansion

- `include` array referencing allow-listed relations and optional per-relation field subsets.
- Max include depth enforced globally or per relation.

---

## 8. Adapter Requirements

Adapters must implement:

1. **Introspection**
   - Enumerate models/resources, fields, types, PKs, relations, and optional table size estimates.
2. **Compile**
   - Turn DSL requests into backend-specific query objects while injecting scoping, field selection, includes, budgets, ordering, and cursor handling.
3. **Execute**
   - Run queries, map rows to view models, apply redaction, and return pagination metadata.
4. **Transactions**
   - Provide tool-call scoped session management, nested transaction strategies, and per-request lifecycle hooks.

Backend considerations:

- SQLAlchemy uses selectable constructs with loader options and supports async sessions.
- Tortoise relies on `.filter()`, `.prefetch_related()`, `.only()` with async execution.
- Peewee leverages `select()/where()/join()` sequences with limited include support.

---

## 9. Storage & Auditing

### Audit log record schema

- Tool name, principal identifiers, timestamp, request/trace IDs.
- Sanitized inputs and policy decisions (e.g., injected filters).
- Row counts or affected rows, duration.
- Error type/message if applicable.
- Optional before/after snapshots for writes.

### Storage backends

- SQLAlchemy, Tortoise, Peewee-based stores plus a JSONL fallback for development.
- Optional conversation/tool history store for agent “memory” referencing audit IDs.

---

## 10. MCP Integration

- MCP server exposes all generic tools and registered domain tools with JSON schemas derived from Pydantic models.
- Auth middleware builds principals from tokens or API keys, opens sessions, and injects context per request.
- Even compromised MCP clients remain bounded by server-side policies, scoping, redaction, and budgets.

---

## 11. Developer Experience

### Drop-in setup examples

- SQLAlchemy: `OrmAI.from_sqlalchemy(engine, model_registry, policies)`
- Tortoise: `OrmAI.from_tortoise(models, policies)`
- Peewee: `OrmAI.from_peewee(db, models, policies)`
- Utilities pack quickstart: `ormai.quickstart.mount_sqlalchemy` (and peers) returning toolset + MCP server + generated views/policy defaults in under 30 lines.

### Policy configuration

- YAML/JSON describing resources, field controls, relations, scoping, budgets, and write rules.

### Generators

- Optionally generate view models and canonical domain tools (e.g., CRUD operations) from ORM metadata and policies.
- Utilities pack augments this with `DefaultsProfile`, `PolicyBuilder`, `ViewFactory`, `ToolsetFactory`, `SessionManager`, `AuditStore`, `SchemaCache`, MCP helpers, testing/eval utilities, and one-file quickstarts to minimize integration friction.

---

## 12. Use Cases

1. **Customer Support Agent** – read-heavy flows retrieving orders, subscriptions, invoices with strict tenant scoping, PII redaction, budgets.
2. **Operations/Admin Agent** – controlled writes such as refunds or subscription pauses requiring approvals, ID-constrained updates, and auditing.
3. **Analytics-lite Agent** – constrained aggregations (e.g., signups by plan) with allow-listed relations and timeouts.
4. **Developer Copilot** – debugging assistants with broader read access but still role-gated and budgeted.
5. **Schema-aware Agent** – future scenario where OrmAI updates schema metadata/views as migrations happen to keep agents functioning.

---

## 13. Security Model

Guarantees:

- Enforced cross-tenant isolation through injected scoping.
- PII protection via field-level redaction/masking.
- Runaway query prevention with budgets/timeouts/complexity scoring.
- Mass write prevention through ID requirements and affected-row caps.
- Full auditability for compliance.

Threats mitigated include prompt injection, malicious MCP clients, accidental `SELECT *`/bulk updates, and inference leaks from joins.

---

## 14. Delivery Plan

- **Phase 1 (Read-Only MVP)**
  - SQLAlchemy/Tortoise/Peewee adapters.
  - Read-only generic tools (`describe_schema`, `get`, `query`, `aggregate`).
  - Policies for allowlists, scoping, redaction, budgets.
  - Base MCP server and audit store.
- **Phase 2 (Controlled Writes)**
  - Mutation tools with approval gates and before/after audit support.
- **Phase 3 (DX & Reliability)**
  - Generators for views/tools, advanced pagination, replay/eval harnesses, improved cost models.
- **Phase 4 (TypeScript Edition)**
  - `ormai-ts` for Node.js with Prisma/Drizzle/TypeORM adapters, Zod validation, and identical MCP tool schemas.

See `docs/roadmap.md` for milestone details and `docs/ormai-ts-specification.md` for TypeScript edition design.

---

## 15. Compatibility & Extensibility

- Core runtime, DSL, and policy engine remain ORM-agnostic.
- Adding support for additional ORMs only requires implementing the adapter interface.

---

## 16. Project Tooling

### Package Management

OrmAI uses [uv](https://docs.astral.sh/uv/) as its package manager for fast, reliable dependency management.

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install OrmAI with extras
uv add ormai[sqlalchemy]
uv add ormai[tortoise]
uv add ormai[peewee]
uv add ormai[all]
```

### Development Setup

```bash
git clone https://github.com/anthropics/ormai.git
cd ormai
uv sync --dev
```

### Project Structure

```
ormai/
├── pyproject.toml      # Project metadata and dependencies (uv/PEP 621)
├── uv.lock             # Locked dependencies
├── src/ormai/
│   ├── core/
│   ├── adapters/
│   ├── policy/
│   ├── store/
│   ├── mcp/
│   ├── generators/
│   └── utils/
├── tests/
├── docs/
└── examples/
```

### Development Commands

```bash
uv run pytest                    # Run tests
uv run pytest --cov=ormai        # Run tests with coverage
uv run ruff check .              # Lint
uv run ruff format .             # Format
uv run mypy src/ormai            # Type check
uv run python -m ormai.cli       # Run CLI (if applicable)
```

### CI/CD

- GitHub Actions workflows use `uv` for reproducible builds.
- Lock file (`uv.lock`) ensures deterministic installs across environments.
