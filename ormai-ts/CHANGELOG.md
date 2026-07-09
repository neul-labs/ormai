# Changelog

All notable changes to `@ormai/core` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-01-08

### Added

#### Core Features
- Policy-governed, auditable database capabilities for TypeScript agents
- Policy engine with model, field, relation, and budget validation
- Scope injection for tenant isolation and ownership scoping
- Field-level redaction (deny, mask, hash)
- Global deny/mask pattern enforcement

#### ORM Adapters
- Prisma adapter with full CRUD, aggregation, and soft delete
- Drizzle adapter with configurable server-side aggregation (`aggregateFn`)
- TypeORM adapter with server-side SQL aggregation (SUM, AVG, MIN, MAX)
- In-memory adapter for testing

#### Policy
- `PolicyBuilder` for declarative policy construction
- Row-level security with tenant and ownership scoping
- Write policies with readonly fields and reason requirements
- Budget enforcement (max rows, max select fields, max includes)

#### MCP Server
- Authentication with API keys and JWT (HMAC verification)
- Multi-tenant header extraction
- Dev auth middleware for local development

#### Integrations
- OpenAI function-calling integration
- Anthropic tool-use integration
- LangChain tool integration
- LlamaIndex tool integration
- Mastra tool integration
- Vercel AI SDK integration
- JSON Schema tool integration

#### Tools
- Generic query, get, aggregate, create, update, delete, and bulk update tools
- Toolset factory for creating grouped tool sets

#### Store
- In-memory audit store
- Memory store cleanup (auto-prune every 60s)

#### Utilities
- Cursor encoding/decoding (offset and keyset)
- Defaults and builder utilities

### Security
- JWT signature verification (HMAC-SHA256) for authentication
- Tenant scope enforcement at policy level
- Global deny/mask patterns for sensitive field protection
- Removed hardcoded cursor secret (now uses `os.urandom` or env var)