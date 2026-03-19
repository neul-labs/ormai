"""Tests for testing utilities."""

import pytest

from ormai.utils.testing import (
    BudgetAssertion,
    LeakDetector,
    MockTenant,
    MockUser,
    MultiTenantFixture,
    create_test_harness,
    make_admin_context,
    make_context,
)


class TestMultiTenantFixture:
    """Tests for MultiTenantFixture."""

    def test_add_tenant(self):
        """Test adding a tenant."""
        fixture = MultiTenantFixture()
        tenant = fixture.add_tenant("tenant-1", name="Acme Corp")

        assert isinstance(tenant, MockTenant)
        assert tenant.tenant_id == "tenant-1"
        assert tenant.name == "Acme Corp"

    def test_add_tenant_with_data(self):
        """Test adding a tenant with seed data."""
        fixture = MultiTenantFixture()
        tenant = fixture.add_tenant(
            "tenant-1",
            data={
                "Customer": [
                    {"id": 1, "name": "Alice"},
                    {"id": 2, "name": "Bob"},
                ],
            },
        )

        assert len(tenant.data["Customer"]) == 2

    def test_add_user(self):
        """Test adding a user to a tenant."""
        fixture = MultiTenantFixture()
        fixture.add_tenant("tenant-1")
        user = fixture.add_user("user-1", "tenant-1", roles=["admin"])

        assert isinstance(user, MockUser)
        assert user.user_id == "user-1"
        assert user.tenant_id == "tenant-1"
        assert user.roles == ["admin"]

    def test_add_user_auto_creates_tenant(self):
        """Test that adding a user auto-creates tenant if missing."""
        fixture = MultiTenantFixture()
        user = fixture.add_user("user-1", "tenant-1")

        assert user.tenant_id == "tenant-1"
        # Tenant should have been auto-created
        ctx = fixture.context_for("tenant-1")
        assert ctx.principal.tenant_id == "tenant-1"

    def test_context_for(self):
        """Test creating a RunContext for a tenant."""
        fixture = MultiTenantFixture()
        fixture.add_tenant("tenant-1")

        ctx = fixture.context_for("tenant-1")

        assert ctx.principal.tenant_id == "tenant-1"
        assert ctx.principal.user_id == "user-tenant-1"  # Default user
        assert ctx.principal.roles == ["user"]
        assert ctx.request_id is not None

    def test_context_for_with_user(self):
        """Test creating context with specific user."""
        fixture = MultiTenantFixture()
        fixture.add_tenant("tenant-1")
        fixture.add_user("admin-1", "tenant-1", roles=["admin"])

        ctx = fixture.context_for("tenant-1", user_id="admin-1")

        assert ctx.principal.user_id == "admin-1"
        assert ctx.principal.roles == ["admin"]

    def test_context_for_with_explicit_roles(self):
        """Test creating context with explicit roles."""
        fixture = MultiTenantFixture()
        fixture.add_tenant("tenant-1")

        ctx = fixture.context_for("tenant-1", roles=["admin", "support"])

        assert ctx.principal.roles == ["admin", "support"]

    def test_get_tenant_data(self):
        """Test getting tenant data."""
        fixture = MultiTenantFixture()
        fixture.add_tenant(
            "tenant-1",
            data={"Customer": [{"id": 1, "name": "Alice"}]},
        )

        data = fixture.get_tenant_data("tenant-1", "Customer")

        assert len(data) == 1
        assert data[0]["name"] == "Alice"

    def test_get_tenant_data_missing(self):
        """Test getting data for missing tenant/model."""
        fixture = MultiTenantFixture()

        data = fixture.get_tenant_data("missing", "Customer")
        assert data == []

        fixture.add_tenant("tenant-1")
        data = fixture.get_tenant_data("tenant-1", "MissingModel")
        assert data == []

    def test_get_all_data(self):
        """Test getting data across all tenants."""
        fixture = MultiTenantFixture()
        fixture.add_tenant(
            "tenant-1",
            data={"Customer": [{"id": 1, "name": "Alice"}]},
        )
        fixture.add_tenant(
            "tenant-2",
            data={"Customer": [{"id": 2, "name": "Bob"}]},
        )

        data = fixture.get_all_data("Customer")

        assert len(data) == 2
        # Each row should have tenant_id added
        tenant_ids = {row["tenant_id"] for row in data}
        assert tenant_ids == {"tenant-1", "tenant-2"}

    def test_verify_isolation_pass(self):
        """Test verify_isolation with proper isolation."""
        fixture = MultiTenantFixture()
        fixture.add_tenant("tenant-1")

        results = [
            {"id": 1, "tenant_id": "tenant-1"},
            {"id": 2, "tenant_id": "tenant-1"},
        ]

        assert fixture.verify_isolation(results, "tenant-1")

    def test_verify_isolation_fail(self):
        """Test verify_isolation with data leak."""
        fixture = MultiTenantFixture()
        fixture.add_tenant("tenant-1")

        results = [
            {"id": 1, "tenant_id": "tenant-1"},
            {"id": 2, "tenant_id": "tenant-2"},  # Leak!
        ]

        assert not fixture.verify_isolation(results, "tenant-1")

    def test_verify_isolation_no_tenant_field(self):
        """Test verify_isolation with rows missing tenant_id."""
        fixture = MultiTenantFixture()
        fixture.add_tenant("tenant-1")

        results = [{"id": 1, "name": "Alice"}]  # No tenant_id

        # Should pass - can't verify without tenant_id
        assert fixture.verify_isolation(results, "tenant-1")

    def test_find_leaks(self):
        """Test finding leaked rows."""
        fixture = MultiTenantFixture()
        fixture.add_tenant("tenant-1")

        results = [
            {"id": 1, "tenant_id": "tenant-1"},
            {"id": 2, "tenant_id": "tenant-2"},
            {"id": 3, "tenant_id": "tenant-3"},
        ]

        leaks = fixture.find_leaks(results, "tenant-1")

        assert len(leaks) == 2
        leaked_tenants = {row["tenant_id"] for row in leaks}
        assert leaked_tenants == {"tenant-2", "tenant-3"}


class TestBudgetAssertion:
    """Tests for BudgetAssertion."""

    def test_assert_within_budget_pass(self):
        """Test assertion passes when within budget."""
        assertion = BudgetAssertion(max_rows=10)

        class Result:
            data = [{"id": i} for i in range(5)]

        # Should not raise
        assertion.assert_within_budget(Result())

    def test_assert_within_budget_fail(self):
        """Test assertion fails when over budget."""
        assertion = BudgetAssertion(max_rows=10)

        class Result:
            data = [{"id": i} for i in range(15)]

        with pytest.raises(AssertionError) as exc_info:
            assertion.assert_within_budget(Result())

        assert "15" in str(exc_info.value)
        assert "10" in str(exc_info.value)

    def test_assert_within_budget_with_context(self):
        """Test assertion includes context in error."""
        assertion = BudgetAssertion(max_rows=10)

        class Result:
            data = [{"id": i} for i in range(15)]

        with pytest.raises(AssertionError) as exc_info:
            assertion.assert_within_budget(Result(), context="Customer query")

        assert "Customer query" in str(exc_info.value)

    def test_assert_row_count_exact(self):
        """Test exact row count assertion."""
        assertion = BudgetAssertion()

        class Result:
            data = [{"id": i} for i in range(5)]

        # Should not raise
        assertion.assert_row_count(Result(), expected=5)

        with pytest.raises(AssertionError):
            assertion.assert_row_count(Result(), expected=3)

    def test_assert_max_rows(self):
        """Test max rows assertion."""
        assertion = BudgetAssertion()

        class Result:
            data = [{"id": i} for i in range(5)]

        # Should not raise
        assertion.assert_max_rows(Result(), max_rows=10)

        with pytest.raises(AssertionError):
            assertion.assert_max_rows(Result(), max_rows=3)


class TestLeakDetector:
    """Tests for LeakDetector."""

    def test_record_and_find_no_leaks(self):
        """Test recording with no leaks."""
        detector = LeakDetector()

        detector.record("tenant-1", [{"id": 1, "tenant_id": "tenant-1"}])
        detector.record("tenant-2", [{"id": 2, "tenant_id": "tenant-2"}])

        leaks = detector.find_all_leaks()
        assert len(leaks) == 0

    def test_record_and_find_leaks(self):
        """Test detecting cross-tenant leaks."""
        detector = LeakDetector()

        detector.record("tenant-1", [
            {"id": 1, "tenant_id": "tenant-1"},
            {"id": 2, "tenant_id": "tenant-2"},  # Leak!
        ])

        leaks = detector.find_all_leaks()
        assert len(leaks) == 1
        assert leaks[0]["expected_tenant"] == "tenant-1"
        assert leaks[0]["actual_tenant"] == "tenant-2"

    def test_custom_tenant_field(self):
        """Test custom tenant field name."""
        detector = LeakDetector(tenant_field="org_id")

        detector.record("org-1", [{"id": 1, "org_id": "org-2"}])

        leaks = detector.find_all_leaks()
        assert len(leaks) == 1

    def test_clear(self):
        """Test clearing records."""
        detector = LeakDetector()
        detector.record("tenant-1", [{"id": 1, "tenant_id": "tenant-2"}])

        detector.clear()

        leaks = detector.find_all_leaks()
        assert len(leaks) == 0

    def test_assert_no_leaks_pass(self):
        """Test assert_no_leaks with no leaks."""
        detector = LeakDetector()
        detector.record("tenant-1", [{"id": 1, "tenant_id": "tenant-1"}])

        # Should not raise
        detector.assert_no_leaks()

    def test_assert_no_leaks_fail(self):
        """Test assert_no_leaks with leaks."""
        detector = LeakDetector()
        detector.record("tenant-1", [{"id": 1, "tenant_id": "tenant-2"}])

        with pytest.raises(AssertionError) as exc_info:
            detector.assert_no_leaks()

        assert "cross-tenant" in str(exc_info.value).lower()


class TestCreateTestHarness:
    """Tests for create_test_harness helper."""

    def test_creates_harness(self):
        """Test creating a harness with defaults."""
        from ormai.eval.harness import EvalHarness

        harness = create_test_harness()

        assert isinstance(harness, EvalHarness)

    def test_creates_harness_with_denied_fields(self):
        """Test creating harness with denied fields."""
        harness = create_test_harness(denied_fields=["password", "ssn"])

        # Verify invariants were added
        assert len(harness._invariants) >= 2  # cross-tenant + denied fields + budget


class TestContextHelpers:
    """Tests for context helper functions."""

    def test_make_context(self):
        """Test make_context helper."""
        ctx = make_context(
            tenant_id="test-tenant",
            user_id="test-user",
            roles=["admin"],
        )

        assert ctx.principal.tenant_id == "test-tenant"
        assert ctx.principal.user_id == "test-user"
        assert ctx.principal.roles == ["admin"]
        assert ctx.request_id is not None
        assert ctx.now is not None

    def test_make_context_defaults(self):
        """Test make_context with defaults."""
        ctx = make_context()

        assert ctx.principal.tenant_id == "test-tenant"
        assert ctx.principal.user_id == "test-user"
        assert ctx.principal.roles == ["user"]

    def test_make_admin_context(self):
        """Test make_admin_context helper."""
        ctx = make_admin_context()

        assert ctx.principal.tenant_id == "test-tenant"
        assert ctx.principal.user_id == "admin"
        assert ctx.principal.roles == ["admin"]

    def test_make_admin_context_custom_tenant(self):
        """Test make_admin_context with custom tenant."""
        ctx = make_admin_context(tenant_id="acme")

        assert ctx.principal.tenant_id == "acme"
        assert ctx.principal.roles == ["admin"]
