# OrmAI Roadmap

This roadmap captures the staged delivery plan for OrmAI, focusing on safety-critical foundations first, then controlled write capabilities, followed by developer-experience and reliability upgrades.

---

## Phase 1 – Read-Only MVP

**Status:** ✅ Complete

**Objective:** Enable teams to expose safe, typed, auditable read capabilities for SQLAlchemy, Tortoise, and Peewee-backed apps, bundled with the first wave of utilities that make onboarding trivial.

**Tooling:** [uv](https://docs.astral.sh/uv/) for package management, ruff for linting/formatting, mypy for type checking, pytest for testing.

**Scope – Platform Core**

- ✅ Core runtime (`ormai.core`) with execution context, DSL validation, and error taxonomy.
- ✅ Policy engine covering model/field/relation allowlists, tenant/ownership scoping, redaction, budgets, and complexity scoring.
- ✅ Generic read-only toolset: `db.describe_schema`, `db.get`, `db.query`, `db.aggregate`.
- ✅ SQLAlchemy adapter (sync/async) with introspection, compile, execute, and session lifecycle.
- ✅ Tortoise ORM adapter (async) with introspection, compile, execute.
- ✅ Peewee adapter (sync) with introspection, compile, execute.
- ✅ View/projection model support for safe responses.
- ✅ Audit logging infrastructure (JSONL fallback) with trace IDs.
- ✅ SQL-based audit store for Tortoise/Peewee (`TortoiseAuditStore`, `PeeweeAuditStore`).
- ✅ Baseline MCP server exposing the toolset with auth/context injection hooks.

**Scope – Utilities Pack**

- ✅ `DefaultsProfile` with `DEFAULT_PROD`, `DEFAULT_INTERNAL`, `DEFAULT_DEV` presets controlling limits, redaction defaults, and write toggles.
- ✅ `PolicyBuilder` v1: register models, apply glob-based allow/deny/mask, configure tenant scope.
- ✅ `ViewFactory` v1 for projection generation aligned with policies.
- ✅ `ToolsetFactory` for read-only routes, including structured "retry hints" when requests violate policies.
- ✅ Session/transaction helpers (`SessionManager` for SQLAlchemy).
- ✅ Tortoise/Peewee adapters include transaction support.
- ✅ `SchemaCache` (in-memory) for adapter introspection.
- ✅ `AuditStore` implementations (JSONL) + `AuditMiddleware`.
- ✅ Initial `McpServerFactory` for mounting read-only toolsets with JWT/API-key auth helpers.

**Acceptance criteria**

- Drop-in integration for each ORM with <30 lines of app code.
- Tenant scoping enforced for all tools; mis-scoped queries are rejected with actionable retry hints.
- Field allowlists/redaction apply uniformly across domain and generic tools.
- Query budgets prevent unbounded scans; structured errors guide the LLM to self-correct.
- Every tool call produces an audit record accessible via the configured store.
- Quickstart path using `DefaultsProfile + PolicyBuilder + ToolsetFactory` validated against example SQLAlchemy/Tortoise/Peewee apps.
- MCP server quickstart available that mounts the generated toolset with minimal configuration.

---

## Phase 2 – Controlled Writes

**Status:** ✅ Complete

**Objective:** Introduce safe mutation capabilities with conservative defaults, approval gates, and write-focused utilities.

**Scope – Platform Core**

- ✅ Mutation DSL: `CreateRequest`, `UpdateRequest`, `DeleteRequest`, `BulkUpdateRequest` with result types.
- ✅ Mutation tools: `db.create`, `db.update`, `db.delete`, `db.bulk_update`.
- ✅ Write policy validation in PolicyEngine (reason requirement, readonly fields, max affected rows).
- ✅ SQLAlchemy adapter mutation implementation (create, update, delete, bulk_update).
- ✅ Soft-delete enforcement (configurable per model).
- ✅ Structured errors: `WriteDisabledError`, `MaxAffectedRowsExceededError`, `ValidationError`.
- ✅ Before/after capture support for audit logs.
- ✅ Optional deferred tool pattern to support human-in-the-loop approvals.

**Scope – Utilities Pack**

- ✅ `DefaultsProfile` gains write toggles (e.g., `require_reason_for_writes`, `allow_generic_mutations`).
- ✅ `PolicyBuilder` write overlays (`enable_writes`, `readonly_fields`, `require_approval`, `allow_bulk_updates`).
- ✅ `ToolsetFactory` auto-registers write tools when allowed and injects reason metadata requirements automatically.
- ✅ Approval helper interfaces plus canned implementations (`AutoApproveGate`, `CallbackApprovalGate`, `InMemoryApprovalQueue`).
- ✅ `AuditMiddleware` update to capture before/after snapshots when configured.
- ✅ Transaction helpers include automatic retries/rollback strategy for writes (`TransactionManager`, `retry_async`, `retry_sync`).

**Acceptance criteria**

- Writes disabled by default; enabling requires explicit policy toggle.
- Updates require primary keys; bulk operations require explicit `ids`.
- Soft delete is the default behavior, with overrides documented.
- Approval gating is pluggable and can block/queue tool executions until approved.
- Audit records capture before/after snapshots (when configured) and store the supplied reason.
- Utilities quickstart demonstrates enabling a single safe mutation (e.g., refund flow) without touching low-level policies.

---

## Phase 3 – DX & Reliability Enhancements

**Status:** ✅ Complete

**Objective:** Reduce integration effort further and improve operational resilience.

**Scope – Platform Core**

- ✅ Generators for view models and canonical domain tools derived from ORM metadata + policies (`ViewCodeGenerator`, `DomainToolGenerator`).
- ✅ Advanced pagination with cursor stability guarantees under concurrent writes (keyset-based `CursorEncoder`).
- ✅ Replay/eval harnesses to record tool calls, simulate policies, and assert invariants (`CallRecorder`, `ReplayEngine`, `EvalHarness`).
- ✅ Built-in invariants: `no_cross_tenant_data`, `no_denied_fields`, `response_within_budget`.
- ✅ `DeterminismChecker` for verifying tool call determinism.
- ✅ Richer cost model for queries (`QueryCostEstimator`, `CostBreakdown`, `CostBudget`, `CostTracker`).
- ✅ Schema-aware utilities (auto-refresh policy/view metadata when migrations run) via `compute_migration_hash`.

**Scope – Utilities Pack**

- ✅ `quickstart.mount_{sqlalchemy,tortoise,peewee}` returning toolset + MCP server + generated views/policies.
- ✅ Persistent `SchemaCache` (`PersistentSchemaCache`) keyed by migration hashes with invalidation hooks.
- ✅ `ToolsetFactory` plug-ins for custom error messaging (`ErrorPlugin`, `LocalizedErrorPlugin`, `MetricsPlugin`, `TerseErrorPlugin`).
- ✅ Testing fixtures for multi-tenant datasets (`MultiTenantFixture`), budget assertions (`BudgetAssertion`), and leak detection (`LeakDetector`) built into `ormai.utils.testing`.
- ✅ `make_context` and `make_admin_context` helpers for quick test setup.
- ✅ `create_test_harness` convenience function with pre-configured invariants.
- ✅ MCP utilities extended with templated configs (`McpTemplates`, `McpConfigGenerator`, `install_claude_desktop`).

**Acceptance criteria**

- ✅ One-file quickstart path (via utilities pack) available for each ORM.
- ✅ Cursor pagination proven stable through regression tests.
- ✅ Eval harness enables replaying at least 100 tool calls with deterministic outcomes.
- ✅ Schema cache invalidation workflow documented and automated hooks provided.
- ✅ Quickstart demos published in `docs/quickstart.md`.
- ✅ CI-ready testing utilities adopted in reference apps, proving no cross-tenant leakage across 50+ replayed scenarios.

---

## Beyond Phase 3

**Status:** ✅ Complete

Completed extensions:

- ✅ Additional ORM adapters: Django ORM (`DjangoAdapter`), SQLModel (`SQLModelAdapter`).
- ✅ Native integration with orchestration frameworks:
  - FastAPI integration (`ormai.integrations.fastapi`)
  - LangGraph/LangChain integration (`ormai.integrations.langgraph`)
- ✅ Managed control plane for policy distribution and audit log aggregation (`ormai.control_plane`):
  - Policy Registry with versioning, diffing, and activation (`PolicyRegistry`, `InMemoryPolicyRegistry`, `JsonFilePolicyRegistry`)
  - Audit Aggregator for cross-instance querying and statistics (`AuditAggregator`, `InMemoryAuditAggregator`, `FederatedAuditAggregator`)
  - Client SDK for connecting instances to control plane (`ControlPlaneClient`, `LocalControlPlaneClient`)
  - Server with instance management, deployment tracking, and dashboard API (`ControlPlaneServer`)
- ✅ MCP client templates with config generators (`McpTemplates`, `McpConfigGenerator`).

---

## Phase 4 – TypeScript Edition (ormai-ts)

**Objective:** Bring OrmAI's safety guarantees to the TypeScript/Node.js ecosystem, targeting Prisma, Drizzle, and TypeORM, with first-class integrations for popular agent frameworks.

**Prerequisites:** Python OrmAI Phase 1–3 complete; core DSL and policy semantics stabilized.

**Scope – Platform Core**

- Core runtime (`ormai-ts/core`) with execution context, shared DSL validation (Zod), and error taxonomy.
- Policy engine ported to TypeScript with identical semantics.
- Adapters for Prisma (priority), Drizzle, and TypeORM.
- Zod-based view/projection generation aligned with policies.
- Audit logging infrastructure with Prisma-based and file-based stores.
- MCP server exposing the same tool surface as Python OrmAI.
- Utilities pack: `DefaultsProfile`, `PolicyBuilder`, `ViewFactory`, `ToolsetFactory`, session helpers.
- Shared JSON DSL specification ensuring cross-language compatibility.

**Scope – Agent Framework Integrations**

- **Vercel AI SDK** (P0) – `toVercelAITools()` adapter for Next.js and React apps.
- **LangChain.js** (P0) – `toLangChainTools()` adapter returning `DynamicStructuredTool[]`.
- **LlamaIndex.ts** (P1) – `toLlamaIndexTools()` adapter for RAG-heavy use cases.
- **Mastra** (P1) – `toMastraTools()` adapter for TypeScript-native agents.
- **OpenAI SDK** (P1) – `toOpenAIFunctions()` for direct function calling.
- **Anthropic SDK** (P1) – `toAnthropicTools()` for Claude tool use.
- **Universal JSON Schema export** – `toJSONSchema()` for any tool-calling system.

**Acceptance criteria**

- Drop-in integration for Prisma apps with <30 lines of code.
- Feature parity with Python OrmAI Phase 1 (read-only tools, policies, scoping, budgets, auditing).
- Identical MCP tool schemas across Python and TypeScript implementations.
- Published npm package with TypeScript declarations.
- Vercel AI SDK and LangChain.js integrations working out of the box.
- Quickstart demos for Express + Prisma, Fastify + Drizzle, and Next.js + Vercel AI SDK.
- Example agents for each supported framework in the repository.

See `docs/ormai-ts-specification.md` for detailed design.
