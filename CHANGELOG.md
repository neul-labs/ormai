# Changelog

All notable changes to OrmAI are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Spider Benchmark Demo**: New `examples/spider_demo.py` comparing OrmAI vs text-to-SQL
  - Rich split-screen CLI with live progress
  - Concurrent execution across GPT-4 and Claude
  - Safety metrics (policy blocks, unsafe query detection)
  - Spider dataset auto-download and caching
- **Benchmark dependencies**: New `ormai[benchmark]` extra with `rich`, `openai`, `anthropic`

## [0.2.0] - 2025-01-08

### Added

#### Production Readiness
- **Environment Detection**: `ORMAI_ENV` environment variable for production vs development mode
- **Rate Limiting**: New `ormai.middleware` module with `RateLimiter` supporting per-tenant/user limits
- **Health Checks**: New `ormai.health` module with `HealthChecker`, `/health`, `/health/live`, `/health/ready` endpoints
- **Structured Logging**: New `ormai.logging` module with JSON and text formatters, context injection
- **Audit Retention**: `RetentionPolicy` and `RetentionManager` for automated log cleanup
- **Security Scanning**: GitHub Actions workflow for pip-audit, CodeQL, and Gitleaks
- **Dependabot**: Automated dependency update configuration

#### Security Improvements
- Production-safe authentication defaults (enforced by default in production)
- Warnings when running without authentication in production mode
- Rate limiting integration in MCP server and FastAPI

### Changed
- `enforce_auth` in `McpServerFactory` now auto-detects based on `ORMAI_ENV` (defaults to True in production)
- Development principals renamed from `DEFAULT_DEV_*` to `_DEV_*` (internal use only)
- Improved error logging in background tasks (policy sync, heartbeat, audit flush)
- Fixed test fixture naming issues across test suite

### Breaking Changes
- MCP server now requires authentication by default. Set `ORMAI_ENV=development` for local development or provide an `auth` function.

### Migration from 0.1.x
1. Set `ORMAI_ENV=development` for local development environments
2. Configure authentication for production deployments
3. Consider enabling rate limiting for production

## [0.1.0] - 2025-01-08

### Added

#### Core Features
- ORM-native capability runtime for AI agents
- Policy-based access control with tenant isolation
- Field-level redaction for sensitive data
- Budget enforcement for query cost control
- Cursor-based pagination (offset and keyset)

#### ORM Adapters
- SQLAlchemy adapter with sync/async support
- Tortoise ORM adapter (async)
- Peewee adapter (sync)
- Full CRUD operations (create, update, delete, bulk_update) for all adapters

#### Audit Logging
- Audit logging infrastructure with multiple store backends
- JSONL file-based store for development
- SQLAlchemy-based store for production
- Peewee-based store
- Tortoise ORM-based store
- Audit middleware for automatic logging

#### Integrations
- MCP (Model Context Protocol) server for AI agent integration
- FastAPI integration
- LangGraph integration

#### Tools
- Generic query, get, and aggregate tools
- Domain-specific tool generation
- Deferred execution with approval workflows

#### Control Plane
- Policy registry with versioning
- Instance management
- Federated audit aggregation
- Health monitoring

#### Developer Experience
- Code generation for views and domain tools
- Comprehensive type annotations
- Property-based testing with Hypothesis

### Security
- Automatic tenant_id injection into all queries
- Field masking and redaction based on policy
- Policy validation before query execution
- Audit trail for all operations

## TypeScript

See [ormai-ts](./ormai-ts/CHANGELOG.md) for TypeScript package changes.
