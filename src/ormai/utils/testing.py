"""
Testing utilities for OrmAI.

Provides fixtures, assertions, and helpers for testing OrmAI integrations.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ormai.core.context import Principal, RunContext
from ormai.eval.harness import EvalHarness, no_cross_tenant_data, no_denied_fields


@dataclass
class MockTenant:
    """Mock tenant configuration for testing."""

    tenant_id: str
    name: str = ""
    data: dict[str, list[dict[str, Any]]] = field(default_factory=dict)


@dataclass
class MockUser:
    """Mock user configuration for testing."""

    user_id: str
    tenant_id: str
    roles: list[str] = field(default_factory=list)
    name: str = ""


class MultiTenantFixture:
    """
    Fixture for testing multi-tenant data isolation.

    Creates test data for multiple tenants and provides utilities
    for verifying tenant isolation.

    Usage:
        fixture = MultiTenantFixture()
        fixture.add_tenant("tenant-1", data={
            "Customer": [{"id": 1, "name": "Alice"}],
        })
        fixture.add_tenant("tenant-2", data={
            "Customer": [{"id": 2, "name": "Bob"}],
        })

        # Test that tenant-1 can't see tenant-2's data
        ctx = fixture.context_for("tenant-1")
        results = await query_customers(ctx)
        assert fixture.verify_isolation(results, "tenant-1")
    """

    def __init__(self) -> None:
        self._tenants: dict[str, MockTenant] = {}
        self._users: dict[str, MockUser] = {}

    def add_tenant(
        self,
        tenant_id: str,
        name: str | None = None,
        data: dict[str, list[dict[str, Any]]] | None = None,
    ) -> MockTenant:
        """Add a test tenant with optional seed data."""
        tenant = MockTenant(
            tenant_id=tenant_id,
            name=name or f"Tenant {tenant_id}",
            data=data or {},
        )
        self._tenants[tenant_id] = tenant
        return tenant

    def add_user(
        self,
        user_id: str,
        tenant_id: str,
        roles: list[str] | None = None,
        name: str | None = None,
    ) -> MockUser:
        """Add a test user to a tenant."""
        if tenant_id not in self._tenants:
            self.add_tenant(tenant_id)

        user = MockUser(
            user_id=user_id,
            tenant_id=tenant_id,
            roles=roles or ["user"],
            name=name or f"User {user_id}",
        )
        self._users[user_id] = user
        return user

    def context_for(
        self,
        tenant_id: str,
        user_id: str | None = None,
        roles: list[str] | None = None,
        db: Any = None,
    ) -> RunContext:
        """Create a RunContext for a tenant."""
        if user_id is None:
            user_id = f"user-{tenant_id}"

        if roles is None:
            user = self._users.get(user_id)
            roles = user.roles if user else ["user"]

        return RunContext(
            principal=Principal(
                tenant_id=tenant_id,
                user_id=user_id,
                roles=roles,
            ),
            request_id=str(uuid4()),
            now=datetime.now(timezone.utc),
            db=db,
        )

    def get_tenant_data(self, tenant_id: str, model: str) -> list[dict[str, Any]]:
        """Get test data for a tenant and model."""
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            return []
        return tenant.data.get(model, [])

    def get_all_data(self, model: str) -> list[dict[str, Any]]:
        """Get all test data for a model across tenants."""
        result = []
        for tenant in self._tenants.values():
            for row in tenant.data.get(model, []):
                result.append({**row, "tenant_id": tenant.tenant_id})
        return result

    def verify_isolation(
        self,
        results: list[dict[str, Any]],
        expected_tenant: str,
        tenant_field: str = "tenant_id",
    ) -> bool:
        """
        Verify that results only contain data for the expected tenant.

        Returns True if isolation is maintained.
        """
        for row in results:
            if tenant_field in row and row[tenant_field] != expected_tenant:
                return False
        return True

    def find_leaks(
        self,
        results: list[dict[str, Any]],
        expected_tenant: str,
        tenant_field: str = "tenant_id",
    ) -> list[dict[str, Any]]:
        """Find any rows that belong to a different tenant."""
        leaks = []
        for row in results:
            if tenant_field in row and row[tenant_field] != expected_tenant:
                leaks.append(row)
        return leaks


class BudgetAssertion:
    """
    Assertion helper for testing budget enforcement.

    Usage:
        assertion = BudgetAssertion(max_rows=100)

        result = await tool.execute(...)
        assertion.assert_within_budget(result)
    """

    def __init__(
        self,
        max_rows: int = 100,
        max_includes_depth: int = 2,
        max_select_fields: int = 50,
    ) -> None:
        self.max_rows = max_rows
        self.max_includes_depth = max_includes_depth
        self.max_select_fields = max_select_fields

    def assert_within_budget(
        self,
        result: Any,
        context: str = "",
    ) -> None:
        """Assert that result is within budget limits."""
        # Check row count
        if hasattr(result, "data") and isinstance(result.data, list):
            row_count = len(result.data)
            if row_count > self.max_rows:
                raise AssertionError(
                    f"Row count {row_count} exceeds budget {self.max_rows}"
                    + (f" ({context})" if context else "")
                )

    def assert_row_count(
        self,
        result: Any,
        expected: int,
        context: str = "",
    ) -> None:
        """Assert exact row count."""
        if hasattr(result, "data") and isinstance(result.data, list):
            actual = len(result.data)
            if actual != expected:
                raise AssertionError(
                    f"Expected {expected} rows, got {actual}"
                    + (f" ({context})" if context else "")
                )

    def assert_max_rows(
        self,
        result: Any,
        max_rows: int,
        context: str = "",
    ) -> None:
        """Assert row count is at most max_rows."""
        if hasattr(result, "data") and isinstance(result.data, list):
            actual = len(result.data)
            if actual > max_rows:
                raise AssertionError(
                    f"Row count {actual} exceeds max {max_rows}"
                    + (f" ({context})" if context else "")
                )


class LeakDetector:
    """
    Utility for detecting cross-tenant data leaks.

    Records all query results and checks for isolation violations.

    Usage:
        detector = LeakDetector()

        # Run queries as different tenants
        detector.record("tenant-1", await query_as_tenant_1())
        detector.record("tenant-2", await query_as_tenant_2())

        # Check for leaks
        leaks = detector.find_all_leaks()
        assert len(leaks) == 0
    """

    def __init__(self, tenant_field: str = "tenant_id") -> None:
        self._records: list[tuple[str, list[dict[str, Any]]]] = []
        self.tenant_field = tenant_field

    def record(self, tenant_id: str, results: list[dict[str, Any]]) -> None:
        """Record query results for a tenant."""
        self._records.append((tenant_id, results))

    def clear(self) -> None:
        """Clear all records."""
        self._records.clear()

    def find_all_leaks(self) -> list[dict[str, Any]]:
        """Find all cross-tenant data leaks."""
        leaks = []
        for expected_tenant, results in self._records:
            for row in results:
                if self.tenant_field in row and row[self.tenant_field] != expected_tenant:
                    leaks.append({
                        "expected_tenant": expected_tenant,
                        "actual_tenant": row[self.tenant_field],
                        "row": row,
                    })
        return leaks

    def assert_no_leaks(self) -> None:
        """Assert that no leaks were detected."""
        leaks = self.find_all_leaks()
        if leaks:
            raise AssertionError(
                f"Found {len(leaks)} cross-tenant data leaks: {leaks}"
            )


def create_test_harness(
    denied_fields: list[str] | None = None,
    max_rows: int = 100,
) -> EvalHarness:
    """
    Create an EvalHarness with common invariants pre-configured.

    Args:
        denied_fields: Fields that should never appear in output
        max_rows: Maximum rows per response

    Returns:
        Configured EvalHarness
    """
    harness = EvalHarness()

    # Add cross-tenant isolation check
    harness.add_invariant("no_cross_tenant_data", no_cross_tenant_data)

    # Add denied fields check
    if denied_fields:
        harness.add_invariant(
            "no_denied_fields",
            no_denied_fields(denied_fields),
        )

    # Add budget check
    from ormai.eval.harness import response_within_budget
    harness.add_invariant(
        "response_within_budget",
        response_within_budget(max_rows),
    )

    return harness


# Convenience functions for pytest fixtures

def make_context(
    tenant_id: str = "test-tenant",
    user_id: str = "test-user",
    roles: list[str] | None = None,
    db: Any = None,
) -> RunContext:
    """Create a test RunContext."""
    return RunContext(
        principal=Principal(
            tenant_id=tenant_id,
            user_id=user_id,
            roles=roles or ["user"],
        ),
        request_id=str(uuid4()),
        now=datetime.now(timezone.utc),
        db=db,
    )


def make_admin_context(
    tenant_id: str = "test-tenant",
    user_id: str = "admin",
    db: Any = None,
) -> RunContext:
    """Create an admin test RunContext."""
    return make_context(
        tenant_id=tenant_id,
        user_id=user_id,
        roles=["admin"],
        db=db,
    )
