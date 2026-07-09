"""Tests for health check functionality."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from ormai.health.checks import (
    ComponentHealth,
    HealthChecker,
    HealthStatus,
    OverallHealth,
    check_audit_store,
    check_database,
)


class TestHealthStatus:
    def test_status_values(self):
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"

    def test_status_is_string_enum(self):
        assert isinstance(HealthStatus.HEALTHY, str)
        assert HealthStatus.HEALTHY == "healthy"


class TestComponentHealth:
    def test_to_dict_minimal(self):
        health = ComponentHealth(name="db", status=HealthStatus.HEALTHY)
        result = health.to_dict()
        assert result == {"name": "db", "status": "healthy"}

    def test_to_dict_with_latency(self):
        health = ComponentHealth(
            name="db", status=HealthStatus.HEALTHY, latency_ms=42.156
        )
        result = health.to_dict()
        assert result["latency_ms"] == 42.16

    def test_to_dict_with_message(self):
        health = ComponentHealth(
            name="db", status=HealthStatus.UNHEALTHY, message="Connection refused"
        )
        result = health.to_dict()
        assert result["message"] == "Connection refused"

    def test_to_dict_with_details(self):
        health = ComponentHealth(
            name="db",
            status=HealthStatus.HEALTHY,
            details={"models_count": 5},
        )
        result = health.to_dict()
        assert result["details"] == {"models_count": 5}

    def test_to_dict_omits_none_fields(self):
        health = ComponentHealth(name="db", status=HealthStatus.HEALTHY)
        result = health.to_dict()
        assert "latency_ms" not in result
        assert "message" not in result
        assert "details" not in result


class TestOverallHealth:
    def test_to_dict(self):
        components = [
            ComponentHealth(name="db", status=HealthStatus.HEALTHY),
            ComponentHealth(name="cache", status=HealthStatus.DEGRADED),
        ]
        health = OverallHealth(
            status=HealthStatus.DEGRADED,
            components=components,
            version="1.0.0",
        )
        result = health.to_dict()
        assert result["status"] == "degraded"
        assert result["version"] == "1.0.0"
        assert len(result["components"]) == 2


class TestHealthChecker:
    @pytest.fixture
    def checker(self):
        return HealthChecker(version="1.0.0")

    def test_add_check(self, checker):
        async def db_check():
            return ComponentHealth(name="db", status=HealthStatus.HEALTHY)

        checker.add_check("database", db_check)
        assert "database" in checker._checks

    def test_remove_check(self, checker):
        async def db_check():
            return ComponentHealth(name="db", status=HealthStatus.HEALTHY)

        checker.add_check("database", db_check)
        checker.remove_check("database")
        assert "database" not in checker._checks

    def test_remove_nonexistent_check(self, checker):
        checker.remove_check("nonexistent")

    @pytest.mark.asyncio
    async def test_check_all_empty(self, checker):
        result = await checker.check_all()
        assert result.status == HealthStatus.HEALTHY
        assert len(result.components) == 0

    @pytest.mark.asyncio
    async def test_check_all_healthy(self, checker):
        async def db_check():
            return ComponentHealth(name="db", status=HealthStatus.HEALTHY, latency_ms=1.5)

        checker.add_check("database", db_check)
        result = await checker.check_all()
        assert result.status == HealthStatus.HEALTHY
        assert len(result.components) == 1
        assert result.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_check_all_unhealthy(self, checker):
        async def db_check():
            return ComponentHealth(name="db", status=HealthStatus.UNHEALTHY, message="Down")

        checker.add_check("database", db_check)
        result = await checker.check_all()
        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_check_all_mixed_degraded(self, checker):
        async def db_check():
            return ComponentHealth(name="db", status=HealthStatus.HEALTHY)

        async def cache_check():
            return ComponentHealth(name="cache", status=HealthStatus.DEGRADED)

        checker.add_check("database", db_check)
        checker.add_check("cache", cache_check)
        result = await checker.check_all()
        assert result.status == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_check_all_handles_exceptions(self, checker):
        async def failing_check():
            raise RuntimeError("Connection failed")

        checker.add_check("failing", failing_check)
        result = await checker.check_all()
        assert result.status == HealthStatus.UNHEALTHY
        assert result.components[0].message == "Health check failed: Connection failed"

    @pytest.mark.asyncio
    async def test_check_all_handles_timeout(self, checker):
        async def slow_check():
            await asyncio.sleep(10)
            return ComponentHealth(name="slow", status=HealthStatus.HEALTHY)

        checker.add_check("slow", slow_check)
        result = await checker.check_all(timeout=0.1)
        assert result.status == HealthStatus.UNHEALTHY
        assert "timed out" in result.components[0].message

    @pytest.mark.asyncio
    async def test_check_liveness(self, checker):
        result = await checker.check_liveness()
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_check_readiness(self, checker):
        async def db_check():
            return ComponentHealth(name="db", status=HealthStatus.HEALTHY)

        checker.add_check("database", db_check)
        result = await checker.check_readiness()
        assert result.status == HealthStatus.HEALTHY


class TestCheckDatabase:
    @pytest.mark.asyncio
    async def test_check_database_healthy(self):
        from ormai.core.types import SchemaMetadata

        mock_schema = SchemaMetadata(models={})
        mock_adapter = MagicMock()
        mock_adapter.introspect.return_value = mock_schema

        result = await check_database(mock_adapter)
        assert result.status == HealthStatus.HEALTHY
        assert result.name == "database"
        assert result.latency_ms is not None
        assert result.details["models_count"] == 0

    @pytest.mark.asyncio
    async def test_check_database_with_models(self):
        from ormai.core.types import FieldMetadata, ModelMetadata, SchemaMetadata

        mock_schema = SchemaMetadata(
            models={
                "User": ModelMetadata(
                    name="User",
                    table_name="users",
                    fields={"id": FieldMetadata(name="id", field_type="string", nullable=False, primary_key=True)},
                    relations={},
                    primary_key="id",
                ),
            }
        )
        mock_adapter = MagicMock()
        mock_adapter.introspect.return_value = mock_schema

        result = await check_database(mock_adapter)
        assert result.status == HealthStatus.HEALTHY
        assert result.details["models_count"] == 1

    @pytest.mark.asyncio
    async def test_check_database_unhealthy(self):
        mock_adapter = MagicMock()
        mock_adapter.introspect.side_effect = RuntimeError("Connection refused")

        result = await check_database(mock_adapter)
        assert result.status == HealthStatus.UNHEALTHY
        assert "Connection refused" in result.message


class TestCheckAuditStore:
    @pytest.mark.asyncio
    async def test_check_audit_store_healthy(self):
        store = AsyncMock()
        store.query = AsyncMock(return_value=[])

        result = await check_audit_store(store)
        assert result.status == HealthStatus.HEALTHY
        assert result.name == "audit_store"

    @pytest.mark.asyncio
    async def test_check_audit_store_unhealthy(self):
        store = AsyncMock()
        store.query = AsyncMock(side_effect=RuntimeError("Not connected"))

        result = await check_audit_store(store)
        assert result.status == HealthStatus.UNHEALTHY
        assert "Not connected" in result.message