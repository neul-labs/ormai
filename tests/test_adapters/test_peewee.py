"""Tests for the Peewee adapter."""

from __future__ import annotations

import pytest
from peewee import (
    BooleanField,
    CharField,
    DateTimeField,
    DecimalField,
    ForeignKeyField,
    IntegerField,
    Model,
    SqliteDatabase,
)

from ormai.adapters.peewee import PeeweeCompiler, PeeweeIntrospector
from ormai.core.context import Principal, RunContext
from ormai.core.dsl import FilterClause, FilterOp, OrderClause, OrderDirection, QueryRequest
from ormai.core.types import RelationType
from ormai.policy.models import Budget, ModelPolicy, Policy, RowPolicy


# Test database
test_db = SqliteDatabase(":memory:")


# Test models
class PeeweeBaseModel(Model):
    """Base model with database."""

    class Meta:
        database = test_db


class PeeweeCustomer(PeeweeBaseModel):
    """Test customer model for Peewee."""

    name = CharField(max_length=100)
    email = CharField(max_length=200)
    tenant_id = CharField(max_length=50)
    is_active = BooleanField(default=True)

    class Meta:
        table_name = "customers"


class PeeweeOrder(PeeweeBaseModel):
    """Test order model for Peewee."""

    customer = ForeignKeyField(PeeweeCustomer, backref="orders")
    total = DecimalField(max_digits=10, decimal_places=2)
    status = CharField(max_length=20)
    tenant_id = CharField(max_length=50)

    class Meta:
        table_name = "orders"


@pytest.fixture
def peewee_models():
    """List of test Peewee models."""
    return [PeeweeCustomer, PeeweeOrder]


@pytest.fixture
def peewee_introspector(peewee_models):
    """Create a Peewee introspector."""
    return PeeweeIntrospector(peewee_models)


@pytest.fixture
def peewee_schema(peewee_introspector):
    """Introspected schema from Peewee models."""
    return peewee_introspector.introspect()


@pytest.fixture
def peewee_policy():
    """Create a test policy."""
    return Policy(
        models={
            "PeeweeCustomer": ModelPolicy(
                allowed=True,
                readable=True,
                row_policy=RowPolicy(tenant_scope_field="tenant_id"),
                budget=Budget(max_rows=100),
            ),
            "PeeweeOrder": ModelPolicy(
                allowed=True,
                readable=True,
                row_policy=RowPolicy(tenant_scope_field="tenant_id"),
                budget=Budget(max_rows=100),
            ),
        },
        require_tenant_scope=True,
    )


@pytest.fixture
def peewee_compiler(peewee_models, peewee_policy, peewee_schema):
    """Create a Peewee compiler."""
    model_map = {m.__name__: m for m in peewee_models}
    return PeeweeCompiler(model_map, peewee_policy, peewee_schema)


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


class TestPeeweeIntrospection:
    """Tests for Peewee schema introspection."""

    def test_introspect_models(self, peewee_schema):
        """Test that models are introspected correctly."""
        assert "PeeweeCustomer" in peewee_schema.models
        assert "PeeweeOrder" in peewee_schema.models

    def test_introspect_fields(self, peewee_schema):
        """Test that fields are introspected correctly."""
        customer = peewee_schema.models["PeeweeCustomer"]

        # Check field existence
        assert "id" in customer.fields
        assert "name" in customer.fields
        assert "email" in customer.fields
        assert "tenant_id" in customer.fields

        # Check field types
        assert customer.fields["id"].field_type == "integer"
        assert customer.fields["name"].field_type == "string"
        assert customer.fields["is_active"].field_type == "boolean"

    def test_introspect_primary_key(self, peewee_schema):
        """Test that primary key is detected."""
        customer = peewee_schema.models["PeeweeCustomer"]
        assert customer.primary_key == "id"

    def test_introspect_relations(self, peewee_schema):
        """Test that relations are introspected."""
        order = peewee_schema.models["PeeweeOrder"]

        assert "customer" in order.relations
        rel = order.relations["customer"]
        assert rel.target_model == "PeeweeCustomer"
        assert rel.relation_type == RelationType.MANY_TO_ONE


class TestPeeweeCompiler:
    """Tests for Peewee query compilation."""

    def test_compile_basic_query(self, peewee_compiler, test_context):
        """Test compiling a basic query."""
        request = QueryRequest(
            model="PeeweeCustomer",
            take=10,
        )

        compiled = peewee_compiler.compile_query(request, test_context)

        assert compiled.request == request
        assert "id" in compiled.select_fields
        assert "name" in compiled.select_fields
        # Should have injected tenant filter
        assert len(compiled.injected_filters) > 0

    def test_compile_query_with_filters(self, peewee_compiler, test_context):
        """Test compiling a query with filters."""
        request = QueryRequest(
            model="PeeweeCustomer",
            where=[
                FilterClause(field="is_active", op=FilterOp.EQ, value=True),
            ],
            take=10,
        )

        compiled = peewee_compiler.compile_query(request, test_context)

        assert compiled.request == request
        # User filter + injected tenant filter
        assert len(compiled.injected_filters) >= 1

    def test_compile_query_with_ordering(self, peewee_compiler, test_context):
        """Test compiling a query with ordering."""
        request = QueryRequest(
            model="PeeweeCustomer",
            order_by=[
                OrderClause(field="name", direction=OrderDirection.ASC),
            ],
            take=10,
        )

        compiled = peewee_compiler.compile_query(request, test_context)
        assert compiled.request == request

    def test_encode_decode_cursor(self, peewee_compiler):
        """Test cursor encoding and decoding."""
        offset = 50
        cursor = PeeweeCompiler.encode_cursor(offset)
        decoded = peewee_compiler._decode_cursor(cursor)

        assert decoded == offset

    def test_decode_invalid_cursor(self, peewee_compiler):
        """Test decoding an invalid cursor returns 0."""
        decoded = peewee_compiler._decode_cursor("invalid")
        assert decoded == 0
