# OrmAI Roadmap

This roadmap captures the staged delivery plan for OrmAI, focusing on safety-critical foundations first, then controlled write capabilities, followed by developer-experience and reliability upgrades.

---

## Phase 1 – Read-Only MVP

**Objective:** Enable teams to expose safe, typed, auditable read capabilities for SQLAlchemy, Tortoise, and Peewee-backed apps.

**Scope**

- Core runtime (`ormai.core`) with execution context, DSL validation, and error taxonomy.
- Policy engine covering model/field/relation allowlists, tenant/ownership scoping, redaction, budgets, and complexity scoring.
- Generic toolset: `db.describe_schema`, `db.get`, `db.query`, `db.aggregate`.
- Adapter implementations for SQLAlchemy (sync/async), Tortoise (async), Peewee (sync) including introspection, compile, execute, and session lifecycle helpers.
- View/projection model support for safe responses.
- Audit logging infrastructure (SQL, Tortoise, Peewee, JSONL fallback) with trace IDs.
- Baseline MCP server exposing the toolset with auth/context injection hooks.

**Acceptance criteria**

- Drop-in integration for each ORM with <50 lines of app code.
- Tenant scoping enforced for all tools; mis-scoped queries are rejected with retryable errors.
- Field allowlists/redaction apply uniformly across domain and generic tools.
- Query budgets prevent unbounded scans; rejections include actionable hints.
- Every tool call produces an audit record accessible via the configured store.

---

## Phase 2 – Controlled Writes

**Objective:** Introduce safe mutation capabilities with conservative defaults and optional approval gates.

**Scope**

- Mutation tools: `db.create`, `db.update`, `db.delete` (soft), `db.bulk_update_by_ids`.
- Write policy extensions: reason metadata, max affected rows, approval workflow hooks, soft-delete enforcement.
- Before/after capture support for audit logs.
- Structured errors for approval-required conditions.
- Optional deferred tool pattern to support human-in-the-loop approvals.

**Acceptance criteria**

- Writes disabled by default; enabling requires explicit policy toggle.
- Updates require primary keys; bulk operations require explicit `ids`.
- Soft delete is the default behavior, with overrides documented.
- Approval gating is pluggable and can block/queue tool executions until approved.
- Audit records capture before/after snapshots (when configured) and store the supplied reason.

---

## Phase 3 – DX & Reliability Enhancements

**Objective:** Reduce integration effort further and improve operational resilience.

**Scope**

- Generators for view models and canonical domain tools derived from ORM metadata + policies.
- Advanced pagination with cursor stability guarantees under concurrent writes.
- Replay/eval harnesses to record tool calls, simulate policies, and assert invariants.
- Richer cost model for queries (e.g., factoring estimated cardinalities, includes).
- Schema-aware utilities (auto-refresh policy/view metadata when migrations run).
- Expanded testing utilities and fixtures for CI.

**Acceptance criteria**

- One-file quickstart path (via utilities pack) available for each ORM.
- Cursor pagination proven stable through regression tests.
- Eval harness enables replaying at least 100 tool calls with deterministic outcomes.
- Schema cache invalidation workflow documented and automated hooks provided.

---

## Beyond Phase 3

Potential extensions once core roadmap is complete:

- Additional ORM adapters (Django ORM, Pony, Prisma).
- Native integration with orchestration frameworks (FastAPI, LangGraph, etc.).
- Managed control plane for policy distribution and audit log aggregation.
- Deeper MCP client templates with auto-generated JSON schemas.
