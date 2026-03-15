# OrmAI

OrmAI is an ORM-native capability runtime that turns existing SQLAlchemy, Tortoise, and Peewee models into a safe, typed, auditable tool surface for agents. It layers policy-compiled data access, tenant isolation, and audit logging on top of your current application without exposing direct ORM handles to the LLM.

## Why OrmAI

- **Safety first** – Tenant scoping, field allowlists, redaction, budgets, and blast-radius limits are enforced before any query or mutation runs.
- **Typed capabilities** – All tools expose Pydantic-style input/output schemas so automated agents can plan reliably.
- **Drop-in adoption** – Point OrmAI at existing models and sessions; adapters handle SQLAlchemy (sync/async), Tortoise (async), and Peewee (sync).
- **Auditability & approvals** – Every call is logged with sanitized inputs, policy decisions, and row counts; writes can require reasons or human approval.
- **MCP-native** – Ships an MCP server facade so clients get a consistent `describe_schema/query/get/aggregate/mutate` toolset with built-in auth/context wiring.

## Core Concepts

- **Capabilities over ORM access** – Agents interact with curated domain tools or a constrained query DSL rather than raw sessions.
- **Policy-compiled execution** – Scoping, field filters, budgets, redaction, and write rules are injected automatically at compile/run time.
- **View models** – Results are projection models that stabilize schemas, enable redaction, and decouple responses from ORM internals.
- **Adapters** – Backend-specific compilers transform the shared DSL into SQLAlchemy/Tortoise/Peewee queries and enforce transaction hygiene.
- **Audit store** – Tool calls produce immutable audit records with trace context and optional before/after snapshots for writes.

## Architecture

| Module            | Responsibility |
| ----------------- | -------------- |
| `ormai.core`      | Tool runtime, execution context, error taxonomy, DSL schemas |
| `ormai.adapters`  | Backend adapters (SQLAlchemy, Tortoise, Peewee) for introspection, compile, execute, and session lifecycle helpers |
| `ormai.policy`    | Resource/field/relation/row policies, budgeting, write approvals, redaction |
| `ormai.store`     | Audit log storage plus optional message/tool history |
| `ormai.mcp`       | MCP server glue, auth to context translation, tool schema exposure |
| `ormai.generators`| Optional codegen for domain tools and view models |
| `ormai.utils`     | Defaults, builders, tool factories, session helpers, schema cache, testing utilities, MCP mounting |

## Tool Surface

- **Generic tools** (controlled escape hatch)
  - `db.describe_schema` – allow-listed schema metadata.
  - `db.query` / `db.get` – structured DSL with select/where/order/include, cursor pagination, strict scoping and budgets.
  - `db.aggregate` – safe aggregations (count/sum/min/max) on approved fields.
  - `db.create`, `db.update`, `db.delete`, `db.bulk_update_by_ids` – opt-in mutations that require reasons, enforce max affected rows, and prefer soft deletes.
- **Domain tools** (preferred) – Developers register Python functions with typed signatures; OrmAI enforces policy hooks, safe sessions, and auditing around them.

## Policy Highlights

- Per-model read/write allowlists with tenant/user scoping rules.
- Field-level allow/deny/mask/hash controls and default secret/PII guards.
- Relation depth caps and include allowlists.
- Budgets for max rows, includes, selected fields, and statement timeouts; “broad query guard” blocks unfiltered scans.
- Write controls such as primary-key-only updates, bulk-by-ids, reason requirements, and optional approval workflows.

## Quickstart Flow

1. Choose your adapter (`SQLAlchemyAdapter`, `TortoiseAdapter`, `PeeweeAdapter`) and provide the existing engine/DB handle.
2. Configure policies either manually or via the utilities `PolicyBuilder` and `DefaultsProfile` safe presets.
3. Generate projection models with `ViewFactory` or supply custom Pydantic views.
4. Build a toolset (`ToolsetFactory.from_policy(...)`) and wrap it with the MCP server factory or call directly from your orchestration layer.
5. Wire audit store implementations and session/transaction managers; OrmAI ensures each tool call runs inside a correctly scoped transaction with trace IDs.

Consult the docs in `docs/` for detailed guides on policy configuration, the utilities pack, PydanticAI integration guidance, and staged roadmap milestones.

## Roadmap Snapshot

- **Phase 1 (MVP)** – SQLAlchemy/Tortoise/Peewee adapters, read-only generic tools, policies for allowlists/scoping/redaction/budgets, base MCP server, audit logging.
- **Phase 2 (Controlled writes)** – Create/update/delete tool family, approval gates, before/after auditing, stricter mutation policies.
- **Phase 3 (DX & reliability)** – Generators for views/tools, advanced pagination/cursor stability, replay/eval harnesses, richer cost models, schema-aware utilities.

See `docs/roadmap.md` for detailed milestones and acceptance criteria.
