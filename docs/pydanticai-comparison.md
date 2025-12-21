# PydanticAI vs OrmAI

This document clarifies how OrmAI relates to and differs from PydanticAI. They are complementary layers: PydanticAI ensures type-correct LLM orchestration, while OrmAI ensures safe, policy-compliant data side effects.

---

## 1. Core Purpose

- **PydanticAI** – A type-safe LLM execution framework that validates tool inputs/outputs, manages retries, and provides observability/evals. Model-centric.
- **OrmAI** – A database capability runtime that exposes policy-bound access to existing ORM data, enforces domain invariants, and audits side effects. Data-centric.

OrmAI typically runs beneath PydanticAI, not instead of it.

---

## 2. Mental Model

| Dimension            | PydanticAI                           | OrmAI                                               |
| -------------------- | ------------------------------------ | --------------------------------------------------- |
| Primary abstraction  | Agent                                | Capability                                          |
| Safety focus         | Structured outputs                   | Safe data access and mutations                      |
| Main question        | “Is this JSON valid?”                | “Should this query/update be allowed?”              |
| Failure mode guarded | Schema errors                        | Tenant leakage, PII leaks, runaway queries/writes   |
| Control surface      | Types                                | Policies, budgets, scoping, redaction               |

---

## 3. Tool Behavior

- **PydanticAI tools** are arbitrary Python functions with typed signatures. They can execute any logic, including unsafe DB operations, unless developers add manual guards.
- **OrmAI tools** are always ORM-aware and executed inside a policy compiler. They enforce tenant scoping, field allowlists, pagination caps, write limits, and auditing automatically—even if developer code is imperfect.

---

## 4. Schema Awareness

- PydanticAI uses Pydantic purely for tool I/O and has no stance on DB schemas, relations, or migrations.
- OrmAI augments Pydantic with ORM introspection, view/projection models, relation awareness, and field-level redaction rules.

---

## 5. Data Access Model

- PydanticAI leaves all data access to user-defined tools/services.
- OrmAI provides a structured query DSL, aggregation and mutation APIs, redaction, and adapters for SQLAlchemy/Tortoise/Peewee, designed to drop into existing codebases.

---

## 6. Safety Guarantees

| Capability                       | PydanticAI | OrmAI |
| -------------------------------- | ---------- | ----- |
| Typed validation/retries         | ✅          | ✅ (via Pydantic models) |
| Tenant isolation                 | ❌          | ✅ |
| Field allowlists & redaction     | ❌          | ✅ |
| Query budget enforcement         | ❌          | ✅ |
| Write approvals/max affected rows| ❌          | ✅ |
| Audit logging of tool calls      | ❌          | ✅ |

OrmAI is defensive by default.

---

## 7. Multi-Tenancy & ACLs

- PydanticAI has no built-in understanding of tenants/users.
- OrmAI treats tenant/user scoping as first-class, automatically injecting filters and blocking queries that lack required scope.

---

## 8. Persistence & Auditing

- PydanticAI can serialize conversations but does not define an audit schema.
- OrmAI stores detailed audit events per tool call, including sanitized inputs, policy decisions, row counts, durations, and trace IDs. Optional before/after snapshots exist for writes.

---

## 9. Observability

- PydanticAI offers excellent tracing/logging around LLM/tool interactions.
- OrmAI inherits those benefits and adds DB-specific spans, policy annotations, and cost metrics.

---

## 10. MCP Integration

- PydanticAI can power MCP servers but does not prescribe tool surfaces.
- OrmAI ships a standard MCP tool surface (`describe_schema`, `query`, `get`, `aggregate`, optional mutations) with strict auth/context/policy flow.

---

## 11. Developer Effort

- With PydanticAI alone, teams must implement data access safety, persistence, and audits themselves.
- With OrmAI, teams configure policies, register models, and optionally add domain tools; everything else—scoping, budgets, auditing—is handled centrally.

---

## 12. One-Sentence Difference

> **PydanticAI keeps LLM outputs structurally correct. OrmAI keeps LLM side effects safe.**

Both layers are intended to be used together (`LLM → PydanticAI → OrmAI → ORM`).
