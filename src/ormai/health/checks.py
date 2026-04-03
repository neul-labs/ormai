"""
Health check implementations for OrmAI.

Provides health check functionality for database connections,
audit stores, and other components.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ormai.adapters.base import OrmAdapter
    from ormai.store.base import AuditStore


class HealthStatus(str, Enum):
    """Health status values for components."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """
    Health status of a single component.

    Attributes:
        name: Component name (e.g., "database", "audit_store")
        status: Health status
        latency_ms: Check latency in milliseconds
        message: Optional status message
        details: Optional additional details
    """

    name: str
    status: HealthStatus
    latency_ms: float | None = None
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        result: dict[str, Any] = {
            "name": self.name,
            "status": self.status.value,
        }
        if self.latency_ms is not None:
            result["latency_ms"] = round(self.latency_ms, 2)
        if self.message:
            result["message"] = self.message
        if self.details:
            result["details"] = self.details
        return result


@dataclass
class OverallHealth:
    """
    Overall health status aggregating all components.

    Attributes:
        status: Aggregate health status
        components: Individual component health statuses
        version: Application version
    """

    status: HealthStatus
    components: list[ComponentHealth]
    version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "status": self.status.value,
            "version": self.version,
            "components": [c.to_dict() for c in self.components],
        }


# Type for async health check functions
HealthCheckFn = Callable[[], Coroutine[Any, Any, ComponentHealth]]


class HealthChecker:
    """
    Aggregates and runs health checks for OrmAI components.

    Usage:
        checker = HealthChecker(version="0.2.0")
        checker.add_check("database", lambda: check_database(adapter))
        checker.add_check("audit", lambda: check_audit_store(store))

        # Run all checks
        health = await checker.check_all()
        print(health.status)  # "healthy", "degraded", or "unhealthy"
    """

    def __init__(self, version: str | None = None) -> None:
        """
        Initialize the health checker.

        Args:
            version: Application version to include in health response
        """
        self.version = version
        self._checks: dict[str, HealthCheckFn] = {}

    def add_check(self, name: str, check: HealthCheckFn) -> None:
        """
        Register a health check.

        Args:
            name: Component name
            check: Async function that returns ComponentHealth
        """
        self._checks[name] = check

    def remove_check(self, name: str) -> None:
        """
        Remove a health check.

        Args:
            name: Component name to remove
        """
        self._checks.pop(name, None)

    async def check_all(self, timeout: float = 5.0) -> OverallHealth:
        """
        Run all health checks and aggregate results.

        Args:
            timeout: Maximum time to wait for all checks (seconds)

        Returns:
            OverallHealth with aggregate status and component details
        """
        if not self._checks:
            return OverallHealth(
                status=HealthStatus.HEALTHY,
                components=[],
                version=self.version,
            )

        # Run all checks concurrently with timeout
        async def run_check(name: str, check: HealthCheckFn) -> ComponentHealth:
            try:
                return await asyncio.wait_for(check(), timeout=timeout)
            except asyncio.TimeoutError:
                return ComponentHealth(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check timed out after {timeout}s",
                )
            except Exception as e:
                return ComponentHealth(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check failed: {e}",
                )

        tasks = [run_check(name, check) for name, check in self._checks.items()]
        components = await asyncio.gather(*tasks)

        # Aggregate status
        statuses = [c.status for c in components]
        if all(s == HealthStatus.HEALTHY for s in statuses):
            overall_status = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall_status = HealthStatus.UNHEALTHY
        else:
            overall_status = HealthStatus.DEGRADED

        return OverallHealth(
            status=overall_status,
            components=list(components),
            version=self.version,
        )

    async def check_liveness(self) -> dict[str, str]:
        """
        Simple liveness check.

        Returns a simple response indicating the service is running.
        This check should be fast and not depend on external services.
        """
        return {"status": "ok"}

    async def check_readiness(self, timeout: float = 5.0) -> OverallHealth:
        """
        Readiness check.

        Runs all health checks to determine if the service is ready
        to accept traffic.

        Args:
            timeout: Maximum time to wait for all checks

        Returns:
            OverallHealth with full status
        """
        return await self.check_all(timeout=timeout)


async def check_database(adapter: OrmAdapter) -> ComponentHealth:
    """
    Check database connectivity via adapter.

    Args:
        adapter: The ORM adapter to check

    Returns:
        ComponentHealth with database status
    """
    start = time.perf_counter()
    try:
        # Try to get schema as a simple connectivity test
        schema = adapter.introspect()
        latency = (time.perf_counter() - start) * 1000

        return ComponentHealth(
            name="database",
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            details={"models_count": len(schema.models)},
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="database",
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency,
            message=f"Database connection failed: {e}",
        )


async def check_audit_store(store: AuditStore) -> ComponentHealth:
    """
    Check audit store connectivity.

    Args:
        store: The audit store to check

    Returns:
        ComponentHealth with audit store status
    """
    start = time.perf_counter()
    try:
        # Try to query recent records as a connectivity test
        await store.query(limit=1)
        latency = (time.perf_counter() - start) * 1000

        return ComponentHealth(
            name="audit_store",
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            message="Audit store connected",
            details={"type": type(store).__name__},
        )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            name="audit_store",
            status=HealthStatus.UNHEALTHY,
            latency_ms=latency,
            message=f"Audit store check failed: {e}",
        )


def create_health_router(
    checker: HealthChecker,
) -> Any:
    """
    Create a FastAPI router with health endpoints.

    Args:
        checker: The health checker instance

    Returns:
        FastAPI APIRouter with /health, /health/live, /health/ready endpoints

    Raises:
        ImportError: If FastAPI is not installed
    """
    try:
        from fastapi import APIRouter
        from fastapi.responses import JSONResponse
    except ImportError as err:
        raise ImportError(
            "FastAPI is not installed. Install with: pip install fastapi"
        ) from err

    router = APIRouter(tags=["health"])

    @router.get("/health")
    async def health() -> JSONResponse:
        """Full health check with all components."""
        result = await checker.check_all()
        status_code = 200 if result.status == HealthStatus.HEALTHY else 503
        return JSONResponse(content=result.to_dict(), status_code=status_code)

    @router.get("/health/live")
    async def liveness() -> dict[str, str]:
        """Simple liveness probe."""
        return await checker.check_liveness()

    @router.get("/health/ready")
    async def readiness() -> JSONResponse:
        """Readiness probe with full health check."""
        result = await checker.check_readiness()
        status_code = 200 if result.status == HealthStatus.HEALTHY else 503
        return JSONResponse(content=result.to_dict(), status_code=status_code)

    return router
