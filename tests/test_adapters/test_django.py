"""Tests for the Django adapter.

Note: These tests require Django to be configured. They will be skipped if Django
is not properly set up. To run these tests:

1. Set DJANGO_SETTINGS_MODULE environment variable
2. Or configure Django before importing this module

Example:
    import django
    from django.conf import settings
    settings.configure(
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
        INSTALLED_APPS=['django.contrib.contenttypes'],
    )
    django.setup()
"""

from __future__ import annotations

import pytest

# Try to import Django, skip tests if not available or not configured
django_available = False
try:
    import django
    from django.conf import settings

    # Check if Django is configured
    if not settings.configured:
        # Configure Django for testing
        settings.configure(
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
            ],
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        )
        django.setup()

    from django.db import models

    django_available = True
except ImportError:
    pass
except Exception:
    pass

pytestmark = pytest.mark.skipif(
    not django_available,
    reason="Django is not available or not configured",
)


if django_available:
    from ormai.adapters.django import DjangoAdapter
    from ormai.adapters.django.introspection import DjangoIntrospector
    from ormai.core.context import Principal, RunContext
    from ormai.core.dsl import (
        FilterClause,
        FilterOp,
        OrderClause,
        OrderDirection,
        QueryRequest,
    )
    from ormai.core.types import RelationType
    from ormai.policy.models import Budget, ModelPolicy, Policy, RowPolicy

    # Test models - defined only if Django is available
    class DjangoCustomer(models.Model):
        """Test customer model for Django."""

        name = models.CharField(max_length=100)
        email = models.CharField(max_length=200)
        tenant_id = models.CharField(max_length=50)
        is_active = models.BooleanField(default=True)

        class Meta:
            app_label = "test_ormai"

    class DjangoOrder(models.Model):
        """Test order model for Django."""

        customer = models.ForeignKey(
            DjangoCustomer, on_delete=models.CASCADE, related_name="orders"
        )
        total = models.DecimalField(max_digits=10, decimal_places=2)
        status = models.CharField(max_length=20)
        tenant_id = models.CharField(max_length=50)

        class Meta:
            app_label = "test_ormai"


@pytest.fixture
def django_models():
    """List of test Django models."""
    if not django_available:
        pytest.skip("Django not available")
    return [DjangoCustomer, DjangoOrder]


@pytest.fixture
def django_introspector(django_models):
    """Create a Django introspector."""
    return DjangoIntrospector(models=django_models)


@pytest.fixture
def django_schema(django_introspector):
    """Introspected schema from Django models."""
    return django_introspector.introspect()


@pytest.fixture
def django_policy():
    """Create a test policy."""
    return Policy(
        models={
            "DjangoCustomer": ModelPolicy(
                allowed=True,
                readable=True,
                row_policy=RowPolicy(tenant_scope_field="tenant_id"),
                budget=Budget(max_rows=100),
            ),
            "DjangoOrder": ModelPolicy(
                allowed=True,
                readable=True,
                row_policy=RowPolicy(tenant_scope_field="tenant_id"),
                budget=Budget(max_rows=100),
            ),
        },
        require_tenant_scope=True,
    )


@pytest.fixture
def django_adapter(django_models):
    """Create a Django adapter."""
    return DjangoAdapter(models=django_models)


@pytest.fixture
def test_context():
    """Create a test context."""
    return RunContext(
        principal=Principal(
            tenant_id="tenant-1",
            user_id="user-1",
            roles=["user"],
        ),
        request_id="req-1",
        db=None,
    )


class TestDjangoIntrospection:
    """Tests for Django schema introspection."""

    def test_introspect_models(self, django_schema):
        """Test that models are introspected correctly."""
        assert "DjangoCustomer" in django_schema.models
        assert "DjangoOrder" in django_schema.models

    def test_introspect_fields(self, django_schema):
        """Test that fields are introspected correctly."""
        customer = django_schema.models["DjangoCustomer"]

        # Check field existence
        assert "id" in customer.fields
        assert "name" in customer.fields
        assert "email" in customer.fields
        assert "tenant_id" in customer.fields

        # Check field types
        assert customer.fields["id"].field_type == "integer"
        assert customer.fields["name"].field_type == "string"
        assert customer.fields["is_active"].field_type == "boolean"

    def test_introspect_primary_key(self, django_schema):
        """Test that primary key is detected."""
        customer = django_schema.models["DjangoCustomer"]
        assert customer.primary_key == "id"

    def test_introspect_relations(self, django_schema):
        """Test that relations are introspected."""
        order = django_schema.models["DjangoOrder"]

        assert "customer" in order.relations
        rel = order.relations["customer"]
        assert rel.target_model == "DjangoCustomer"
        assert rel.relation_type == RelationType.MANY_TO_ONE


class TestDjangoAdapter:
    """Tests for Django adapter compilation."""

    def test_compile_basic_query(self, django_adapter, django_policy, django_schema, test_context):
        """Test compiling a basic query."""
        request = QueryRequest(
            model="DjangoCustomer",
            take=10,
        )

        compiled = django_adapter.compile_query(request, test_context, django_policy, django_schema)

        assert compiled.request == request
        assert "id" in compiled.select_fields
        assert "name" in compiled.select_fields
        # Should have injected tenant filter
        assert len(compiled.injected_filters) > 0

    def test_compile_query_with_filters(
        self, django_adapter, django_policy, django_schema, test_context
    ):
        """Test compiling a query with filters."""
        request = QueryRequest(
            model="DjangoCustomer",
            where=[
                FilterClause(field="is_active", op=FilterOp.EQ, value=True),
            ],
            take=10,
        )

        compiled = django_adapter.compile_query(request, test_context, django_policy, django_schema)

        assert compiled.request == request
        # User filter + injected tenant filter
        assert len(compiled.injected_filters) >= 1

    def test_compile_query_with_ordering(
        self, django_adapter, django_policy, django_schema, test_context
    ):
        """Test compiling a query with ordering."""
        request = QueryRequest(
            model="DjangoCustomer",
            order_by=[
                OrderClause(field="name", direction=OrderDirection.ASC),
            ],
            take=10,
        )

        compiled = django_adapter.compile_query(request, test_context, django_policy, django_schema)
        assert compiled.request == request

    def test_sync_introspect(self, django_adapter):
        """Test synchronous introspection."""
        schema = django_adapter.sync_introspect()

        assert "DjangoCustomer" in schema.models
        assert "DjangoOrder" in schema.models

    @pytest.mark.asyncio
    async def test_async_introspect(self, django_adapter):
        """Test asynchronous introspection."""
        schema = await django_adapter.introspect()

        assert "DjangoCustomer" in schema.models
        assert "DjangoOrder" in schema.models
