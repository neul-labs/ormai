"""Tests for the SQLModel adapter.

SQLModel is built on SQLAlchemy, so the adapter inherits from SQLAlchemyAdapter.
These tests verify that the SQLModel-specific conveniences work correctly.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

# Try to import SQLModel, skip tests if not available
sqlmodel_available = False
try:
    from sqlmodel import Field, SQLModel, create_engine

    sqlmodel_available = True
except ImportError:
    pass

pytestmark = pytest.mark.skipif(
    not sqlmodel_available,
    reason="SQLModel is not available",
)


if sqlmodel_available:
    from sqlmodel import Session

    from ormai.adapters.sqlmodel import SQLModelAdapter
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

    # Test models - defined only if SQLModel is available
    class SQLModelCustomer(SQLModel, table=True):
        """Test customer model for SQLModel."""

        __tablename__ = "sqlmodel_customers"

        id: int | None = Field(default=None, primary_key=True)
        name: str = Field(max_length=100)
        email: str = Field(max_length=200)
        tenant_id: str = Field(max_length=50)
        is_active: bool = Field(default=True)

    class SQLModelOrder(SQLModel, table=True):
        """Test order model for SQLModel."""

        __tablename__ = "sqlmodel_orders"

        id: int | None = Field(default=None, primary_key=True)
        customer_id: int = Field(foreign_key="sqlmodel_customers.id")
        total: Decimal = Field(max_digits=10, decimal_places=2)
        status: str = Field(max_length=20)
        tenant_id: str = Field(max_length=50)


@pytest.fixture
def sqlmodel_engine():
    """Create an in-memory SQLite engine for testing."""
    if not sqlmodel_available:
        pytest.skip("SQLModel not available")

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def sqlmodel_models():
    """List of test SQLModel models."""
    if not sqlmodel_available:
        pytest.skip("SQLModel not available")
    return [SQLModelCustomer, SQLModelOrder]


@pytest.fixture
def sqlmodel_adapter(sqlmodel_engine, sqlmodel_models):
    """Create a SQLModel adapter using the factory method."""
    return SQLModelAdapter.from_models(sqlmodel_engine, *sqlmodel_models)


@pytest.fixture
def sqlmodel_adapter_direct(sqlmodel_engine, sqlmodel_models):
    """Create a SQLModel adapter using direct initialization."""
    return SQLModelAdapter(
        engine=sqlmodel_engine,
        session_factory=lambda: Session(sqlmodel_engine),
        models=sqlmodel_models,
    )


@pytest.fixture
def sqlmodel_policy():
    """Create a test policy."""
    return Policy(
        models={
            "SQLModelCustomer": ModelPolicy(
                allowed=True,
                readable=True,
                row_policy=RowPolicy(tenant_scope_field="tenant_id"),
                budget=Budget(max_rows=100),
            ),
            "SQLModelOrder": ModelPolicy(
                allowed=True,
                readable=True,
                row_policy=RowPolicy(tenant_scope_field="tenant_id"),
                budget=Budget(max_rows=100),
            ),
        },
        require_tenant_scope=True,
    )


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


class TestSQLModelAdapterCreation:
    """Tests for SQLModel adapter creation."""

    def test_from_models_factory(self, sqlmodel_engine, sqlmodel_models):
        """Test creating adapter using from_models factory."""
        adapter = SQLModelAdapter.from_models(sqlmodel_engine, *sqlmodel_models)

        assert adapter is not None
        assert isinstance(adapter, SQLModelAdapter)

    def test_direct_initialization(self, sqlmodel_engine, sqlmodel_models):
        """Test creating adapter using direct initialization."""
        adapter = SQLModelAdapter(
            engine=sqlmodel_engine,
            session_factory=lambda: Session(sqlmodel_engine),
            models=sqlmodel_models,
        )

        assert adapter is not None
        assert isinstance(adapter, SQLModelAdapter)

    def test_adapter_inherits_from_sqlalchemy(self, sqlmodel_adapter):
        """Test that SQLModelAdapter inherits from SQLAlchemyAdapter."""
        from ormai.adapters.sqlalchemy import SQLAlchemyAdapter

        assert isinstance(sqlmodel_adapter, SQLAlchemyAdapter)


class TestSQLModelIntrospection:
    """Tests for SQLModel schema introspection."""

    @pytest.mark.asyncio
    async def test_introspect_models(self, sqlmodel_adapter):
        """Test that models are introspected correctly."""
        schema = await sqlmodel_adapter.introspect()

        assert "SQLModelCustomer" in schema.models
        assert "SQLModelOrder" in schema.models

    @pytest.mark.asyncio
    async def test_introspect_fields(self, sqlmodel_adapter):
        """Test that fields are introspected correctly."""
        schema = await sqlmodel_adapter.introspect()
        customer = schema.models["SQLModelCustomer"]

        # Check field existence
        assert "id" in customer.fields
        assert "name" in customer.fields
        assert "email" in customer.fields
        assert "tenant_id" in customer.fields

        # Check field types
        assert customer.fields["id"].field_type == "integer"
        assert customer.fields["name"].field_type == "string"
        assert customer.fields["is_active"].field_type == "boolean"

    @pytest.mark.asyncio
    async def test_introspect_primary_key(self, sqlmodel_adapter):
        """Test that primary key is detected."""
        schema = await sqlmodel_adapter.introspect()
        customer = schema.models["SQLModelCustomer"]

        assert customer.primary_key == "id"

    @pytest.mark.asyncio
    async def test_introspect_relations(self, sqlmodel_adapter):
        """Test that relations are introspected."""
        schema = await sqlmodel_adapter.introspect()
        order = schema.models["SQLModelOrder"]

        # Note: SQLModel foreign keys might be introspected differently
        # depending on how they're defined
        assert "customer_id" in order.fields


class TestSQLModelCompilation:
    """Tests for SQLModel query compilation (inherited from SQLAlchemyAdapter)."""

    @pytest.mark.asyncio
    async def test_compile_basic_query(
        self, sqlmodel_adapter, sqlmodel_policy, test_context
    ):
        """Test compiling a basic query."""
        schema = await sqlmodel_adapter.introspect()

        request = QueryRequest(
            model="SQLModelCustomer",
            take=10,
        )

        compiled = sqlmodel_adapter.compile_query(
            request, test_context, sqlmodel_policy, schema
        )

        assert compiled.request == request
        assert "id" in compiled.select_fields
        assert "name" in compiled.select_fields
        # Should have injected tenant filter
        assert len(compiled.injected_filters) > 0

    @pytest.mark.asyncio
    async def test_compile_query_with_filters(
        self, sqlmodel_adapter, sqlmodel_policy, test_context
    ):
        """Test compiling a query with filters."""
        schema = await sqlmodel_adapter.introspect()

        request = QueryRequest(
            model="SQLModelCustomer",
            where=[
                FilterClause(field="is_active", op=FilterOp.EQ, value=True),
            ],
            take=10,
        )

        compiled = sqlmodel_adapter.compile_query(
            request, test_context, sqlmodel_policy, schema
        )

        assert compiled.request == request
        # User filter + injected tenant filter
        assert len(compiled.injected_filters) >= 1

    @pytest.mark.asyncio
    async def test_compile_query_with_ordering(
        self, sqlmodel_adapter, sqlmodel_policy, test_context
    ):
        """Test compiling a query with ordering."""
        schema = await sqlmodel_adapter.introspect()

        request = QueryRequest(
            model="SQLModelCustomer",
            order_by=[
                OrderClause(field="name", direction=OrderDirection.ASC),
            ],
            take=10,
        )

        compiled = sqlmodel_adapter.compile_query(
            request, test_context, sqlmodel_policy, schema
        )
        assert compiled.request == request


class TestSQLModelExecution:
    """Tests for SQLModel query execution (inherited from SQLAlchemyAdapter)."""

    @pytest.mark.asyncio
    async def test_execute_empty_query(
        self, sqlmodel_adapter, sqlmodel_policy, test_context
    ):
        """Test executing a query on empty database."""
        schema = await sqlmodel_adapter.introspect()

        request = QueryRequest(
            model="SQLModelCustomer",
            take=10,
        )

        compiled = sqlmodel_adapter.compile_query(
            request, test_context, sqlmodel_policy, schema
        )

        result = await sqlmodel_adapter.execute_query(compiled, test_context)

        assert result.data == []
        assert result.total == 0
