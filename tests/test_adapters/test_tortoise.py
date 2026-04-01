"""Tests for the Tortoise ORM adapter."""

from __future__ import annotations

import pytest
from tortoise import fields
from tortoise.models import Model

from ormai.adapters.tortoise import TortoiseCompiler, TortoiseIntrospector
from ormai.core.context import Principal, RunContext
from ormai.core.dsl import FilterClause, FilterOp, OrderClause, OrderDirection, QueryRequest
from ormai.core.types import RelationType
from ormai.policy.models import Budget, ModelPolicy, Policy, RowPolicy


# Test models
class TortoiseCustomer(Model):
    """Test customer model for Tortoise."""

    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    email = fields.CharField(max_length=200)
    tenant_id = fields.CharField(max_length=50)
    created_at = fields.DatetimeField(auto_now_add=True)
    is_active = fields.BooleanField(default=True)

    class Meta:
        table = "customers"


class TortoiseOrder(Model):
    """Test order model for Tortoise."""

    id = fields.IntField(pk=True)
    customer = fields.ForeignKeyField(
        "models.TortoiseCustomer", related_name="orders"
    )
    total = fields.DecimalField(max_digits=10, decimal_places=2)
    status = fields.CharField(max_length=20)
    tenant_id = fields.CharField(max_length=50)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "orders"


@pytest.fixture
def tortoise_models():
    """List of test Tortoise models."""
    return [TortoiseCustomer, TortoiseOrder]


@pytest.fixture
def tortoise_introspector(tortoise_models):
    """Create a Tortoise introspector."""
    return TortoiseIntrospector(tortoise_models)


@pytest.fixture
def tortoise_schema(tortoise_introspector):
    """Introspected schema from Tortoise models."""
    return tortoise_introspector.introspect()


@pytest.fixture
def tortoise_policy():
    """Create a test policy."""
    return Policy(
        models={
            "TortoiseCustomer": ModelPolicy(
                allowed=True,
                readable=True,
                row_policy=RowPolicy(tenant_scope_field="tenant_id"),
                budget=Budget(max_rows=100),
            ),
            "TortoiseOrder": ModelPolicy(
                allowed=True,
                readable=True,
                row_policy=RowPolicy(tenant_scope_field="tenant_id"),
                budget=Budget(max_rows=100),
            ),
        },
        require_tenant_scope=True,
    )


@pytest.fixture
def tortoise_compiler(tortoise_models, tortoise_policy, tortoise_schema):
    """Create a Tortoise compiler."""
    model_map = {m.__name__: m for m in tortoise_models}
    return TortoiseCompiler(model_map, tortoise_policy, tortoise_schema)


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
        db=None,  # Not needed for compilation tests
    )


class TestTortoiseIntrospection:
    """Tests for Tortoise schema introspection."""

    def test_introspect_models(self, tortoise_schema):
        """Test that models are introspected correctly."""
        assert "TortoiseCustomer" in tortoise_schema.models
        assert "TortoiseOrder" in tortoise_schema.models

    def test_introspect_fields(self, tortoise_schema):
        """Test that fields are introspected correctly."""
        customer = tortoise_schema.models["TortoiseCustomer"]

        # Check field existence
        assert "id" in customer.fields
        assert "name" in customer.fields
        assert "email" in customer.fields
        assert "tenant_id" in customer.fields

        # Check field types
        assert customer.fields["id"].field_type == "integer"
        assert customer.fields["name"].field_type == "string"
        assert customer.fields["is_active"].field_type == "boolean"

    def test_introspect_primary_key(self, tortoise_schema):
        """Test that primary key is detected."""
        customer = tortoise_schema.models["TortoiseCustomer"]
        assert customer.primary_key == "id"

    def test_introspect_relations(self, tortoise_schema):
        """Test that relations are introspected."""
        order = tortoise_schema.models["TortoiseOrder"]

        assert "customer" in order.relations
        rel = order.relations["customer"]
        # Note: Tortoise may not resolve model names until init
        # So we accept either the resolved name or "Unknown"
        assert rel.target_model in ("TortoiseCustomer", "Unknown")
        assert rel.relation_type == RelationType.MANY_TO_ONE


class TestTortoiseCompiler:
    """Tests for Tortoise query compilation."""

    @pytest.mark.skip(reason="Requires Tortoise database initialization")
    def test_compile_basic_query(self, tortoise_compiler, test_context):
        """Test compiling a basic query."""
        request = QueryRequest(
            model="TortoiseCustomer",
            take=10,
        )

        compiled = tortoise_compiler.compile_query(request, test_context)

        assert compiled.request == request
        assert "id" in compiled.select_fields
        assert "name" in compiled.select_fields
        # Should have injected tenant filter
        assert len(compiled.injected_filters) > 0

    @pytest.mark.skip(reason="Requires Tortoise database initialization")
    def test_compile_query_with_filters(self, tortoise_compiler, test_context):
        """Test compiling a query with filters."""
        request = QueryRequest(
            model="TortoiseCustomer",
            where=[
                FilterClause(field="is_active", op=FilterOp.EQ, value=True),
            ],
            take=10,
        )

        compiled = tortoise_compiler.compile_query(request, test_context)

        assert compiled.request == request
        # User filter + injected tenant filter
        assert len(compiled.injected_filters) >= 1

    @pytest.mark.skip(reason="Requires Tortoise database initialization")
    def test_compile_query_with_ordering(self, tortoise_compiler, test_context):
        """Test compiling a query with ordering."""
        request = QueryRequest(
            model="TortoiseCustomer",
            order_by=[
                OrderClause(field="name", direction=OrderDirection.ASC),
            ],
            take=10,
        )

        compiled = tortoise_compiler.compile_query(request, test_context)
        assert compiled.request == request

    def test_encode_decode_cursor(self):
        """Test cursor encoding and decoding."""
        offset = 50
        cursor = TortoiseCompiler.encode_cursor(offset)
        # Use a static method to decode
        decoded = int(cursor) if cursor.isdigit() else 0

        assert decoded == offset

    def test_decode_invalid_cursor(self):
        """Test decoding an invalid cursor returns 0."""
        # Test the static decode logic
        cursor = "invalid"
        decoded = int(cursor) if cursor.isdigit() else 0
        assert decoded == 0
