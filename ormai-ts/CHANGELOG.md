# Changelog

All notable changes to `@ormai/core` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-05-09

### Fixed
- **CI/CD** — All GitHub Actions workflows now pass (test, lint, typecheck, validate, security audit, CodeQL, secrets scan).
- **TypeScript compilation** — Resolved zod v4 breaking changes (`z.record()` arity, `.default()` factory requirement, `ZodTypeDef` removal) and TypeScript v6 strict narrowing.
- **Build order** — Fixed cross-package `.d.ts` resolution by running `npm run build` before `npm run typecheck` in CI and publish workflows.
- **NPM lockfile** — Fixed `npm ci` failure on Linux when lockfile was generated on macOS by switching to `npm install` in CI.

### Changed
- **Dependencies** — Bumped TypeScript to 6.0.3, Vitest to 4.1.5, and Zod to 4.4.3.
- **README** — Rewritten with architecture diagrams, feature matrices, framework integration tables, and SEO-friendly keywords.
- **Publish workflow** — Switched from token-based (`secrets.NPM_TOKEN`) to OIDC trusted publishing with automatic provenance attestations.

### Security
- Added CodeQL analysis for JavaScript/TypeScript.
- Added npm audit to scheduled security scans.
- Added TruffleHog secrets scanning on every push and PR.

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
