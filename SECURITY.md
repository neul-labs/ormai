# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### How to Report

**Please DO NOT open a public GitHub issue for security vulnerabilities.**

Instead, please email security concerns to: **me@dipankar.name**

Include the following in your report:
- Description of the vulnerability
- Steps to reproduce the issue
- Potential impact assessment
- Suggested fix (if any)

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Resolution Timeline**: Depends on severity, typically within 30 days for critical issues

### What to Expect

1. We will acknowledge receipt of your report
2. We will investigate and validate the issue
3. We will work on a fix and coordinate disclosure
4. We will credit you in the release notes (unless you prefer anonymity)

## Security Features

OrmAI provides several built-in security features:

### Tenant Isolation
- Automatic `tenant_id` injection into all queries
- Row-level security through policy-based filtering
- Cross-tenant data leakage prevention

### Field-Level Security
- Field redaction (mask, hash, or deny)
- Sensitive field identification
- Policy-based field access control

### Audit Logging
- Complete audit trail of all operations
- Tamper-evident logging
- Configurable retention policies

### Access Control
- Policy validation before query execution
- Budget enforcement to prevent resource abuse
- Role-based permissions

## Production Deployment Security

### Environment Configuration

OrmAI uses environment variables to configure security behavior:

```bash
# REQUIRED for production - enforces authentication
export ORMAI_ENV=production

# Development mode (local development only)
export ORMAI_ENV=development
```

**Important**: In production mode (`ORMAI_ENV=production`, the default), authentication is enforced and anonymous access is denied.

### Authentication

Always provide an authentication function in production:

```python
from ormai.mcp import McpServerFactory

def jwt_auth(context: dict) -> Principal:
    token = context.get("authorization", "").replace("Bearer ", "")
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    return Principal(
        tenant_id=payload["tenant_id"],
        user_id=payload["user_id"],
        roles=tuple(payload.get("roles", [])),
    )

# Production configuration
server = McpServerFactory(
    toolset=toolset,
    auth=jwt_auth,  # Required in production
).build()
```

### Rate Limiting

Protect against abuse with rate limiting:

```python
from ormai.middleware import RateLimiter, RateLimitConfig

limiter = RateLimiter(
    config=RateLimitConfig(
        requests_per_minute=60,
        requests_per_hour=1000,
        burst_limit=10,
    )
)
```

## Security Best Practices

When deploying OrmAI in production:

### Secrets Management
```python
# DON'T: Hardcode secrets
config.with_jwt_auth("my-secret-key")

# DO: Use environment variables or secret managers
import os
config.with_jwt_auth(os.environ["JWT_SECRET"])
```

### Database Security
- Use SSL/TLS for database connections
- Implement least-privilege database users
- Regular security audits of database permissions

### Logging
- Enable audit logging in production
- Configure appropriate log retention (see `RetentionPolicy`)
- Use structured JSON logging for log aggregation
- Monitor for suspicious activity patterns

### Network Security
- Use HTTPS for all API endpoints
- Implement rate limiting (built-in with `RateLimiter`)
- Consider network segmentation for the control plane
- Configure appropriate CORS policies

## Vulnerability Disclosure Policy

We follow responsible disclosure principles:

1. **Embargo Period**: We may request an embargo period before public disclosure
2. **CVE Assignment**: We will work with security researchers to obtain CVE IDs for confirmed vulnerabilities
3. **Credit**: Security researchers will be credited in release notes and security advisories
4. **No Legal Action**: We will not pursue legal action against researchers who follow responsible disclosure

## Security Updates

Security updates will be announced via:
- GitHub Security Advisories
- Release notes in CHANGELOG.md
- Direct notification to affected users (for critical issues)

Subscribe to repository releases to stay informed about security updates.
