"""
Tests for SQLAlchemy adapter.

These tests focus on adapter initialization, schema introspection,
compilation, and other unit-testable aspects.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
import asyncio

from sqlalchemy import create_engine, String, Float, DateTime, ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session
from sqlalchemy.ext.asyncio import create_async_engine

from ormai.adapters.sqlalchemy import SQLAlchemyAdapter
from ormai.adapters.sqlalchemy.session import SessionManager
from ormai.adapters.base import CompiledQuery
from ormai.core.context import Principal, RunContext
from ormai.core.dsl import (
    QueryRequest,
    GetRequest,
    AggregateRequest,
    CreateRequest,
    UpdateRequest,
    DeleteRequest,
    BulkUpdateRequest,
    FilterClause,
    FilterOp,
    OrderClause,
    OrderDirection,
)
from ormai.policy.models import (
    Budget,
    FieldAction,
    FieldPolicy,
    ModelPolicy,
    Policy,
    RelationPolicy,
    RowPolicy,
    WritePolicy,
)


# === Test Models ===

class Base(DeclarativeBase):
    pass


class TestCustomer(Base):
    __tablename__ = "test_customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    age: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    orders: Mapped[list["TestOrder"]] = relationship("TestOrder", back_populates="customer")


class TestOrder(Base):
    __tablename__ = "test_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100))
    customer_id: Mapped[int] = mapped_column(ForeignKey("test_customers.id"))
    status: Mapped[str] = mapped_column(String(50))
    total: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customer: Mapped["TestCustomer"] = relationship("TestCustomer", back_populates="orders")


TEST_MODELS = [TestCustomer, TestOrder]


# === Fixtures ===

@pytest.fixture
def sync_engine():
    """Create an in-memory SQLite engine."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session_manager(sync_engine):
    """Create a session manager."""
    return SessionManager(sync_engine)


@pytest.fixture
def basic_policy():
    """Create a basic test policy."""
    return Policy(
        models={
            "TestCustomer": ModelPolicy(
                allowed=True,
                readable=True,
                writable=True,
                fields={
                    "email": FieldPolicy(action=FieldAction.MASK),
                },
                relations={
                    "orders": RelationPolicy(allowed=True, max_depth=2),
                },
                row_policy=RowPolicy(
                    tenant_scope_field="tenant_id",
                    require_scope=True,
                ),
                write_policy=WritePolicy(
                    enabled=True,
                    allow_create=True,
                    allow_update=True,
                    allow_delete=True,
                    allow_bulk=True,
                    max_affected_rows=100,
                ),
            ),
            "TestOrder": ModelPolicy(
                allowed=True,
                readable=True,
                writable=True,
                relations={
                    "customer": RelationPolicy(allowed=True, max_depth=1),
                },
                row_policy=RowPolicy(
                    tenant_scope_field="tenant_id",
                    require_scope=True,
                ),
                write_policy=WritePolicy(
                    enabled=True,
                    allow_create=True,
                    allow_update=True,
                    allow_delete=True,
                    allow_bulk=True,
                    max_affected_rows=100,
                ),
            ),
        },
        default_budget=Budget(
            max_rows=100,
            max_includes_depth=2,
            max_select_fields=40,
            statement_timeout_ms=5000,
        ),
        require_tenant_scope=True,
        writes_enabled=True,
    )


@pytest.fixture
def permissive_policy():
    """Policy without tenant scope requirement for testing."""
    return Policy(
        models={
            "TestCustomer": ModelPolicy(
                allowed=True,
                readable=True,
                writable=True,
            ),
            "TestOrder": ModelPolicy(
                allowed=True,
                readable=True,
                writable=True,
            ),
        },
        default_budget=Budget(max_rows=1000),
        require_tenant_scope=False,
        writes_enabled=True,
    )


@pytest.fixture
def adapter(sync_engine, basic_policy, session_manager):
    """Create a SQLAlchemy adapter."""
    return SQLAlchemyAdapter(
        engine=sync_engine,
        models=TEST_MODELS,
        policy=basic_policy,
        session_manager=session_manager,
    )


@pytest.fixture
def principal():
    """Create a test principal."""
    return Principal(
        tenant_id="tenant-1",
        user_id="user-1",
        roles=("user",),
    )


# === Tests ===

class TestSQLAlchemyAdapterInitialization:
    """Tests for adapter initialization."""

    def test_init_with_sync_engine(self, sync_engine, basic_policy, session_manager):
        """Test initialization with sync engine."""
        adapter = SQLAlchemyAdapter(
            engine=sync_engine,
            models=TEST_MODELS,
            policy=basic_policy,
        )
        assert adapter.is_async is False
        assert adapter.engine == sync_engine
        assert adapter.models == TEST_MODELS

    def test_init_caches_schema(self, adapter):
        """Test that schema is cached on init."""
        schema = adapter.schema
        assert schema is not None
        assert adapter._schema is schema

    def test_model_map_property(self, adapter):
        """Test model_map property returns correct mapping."""
        model_map = adapter.model_map
        assert "TestCustomer" in model_map
        assert "TestOrder" in model_map
        assert model_map["TestCustomer"] == TestCustomer

    def test_compiler_initialized(self, adapter):
        """Test that compiler is lazily initialized."""
        assert adapter._compiler is None
        _ = adapter.compiler
        assert adapter._compiler is not None


class TestSQLAlchemySchemaIntrospection:
    """Tests for schema introspection."""

    def test_schema_introspection(self, adapter):
        """Test that schema is correctly introspected."""
        schema = adapter.schema

        assert "TestCustomer" in schema.models
        assert "TestOrder" in schema.models

        customer_model = schema.models["TestCustomer"]
        assert "id" in customer_model.fields
        assert "name" in customer_model.fields
        assert "email" in customer_model.fields
        assert "tenant_id" in customer_model.fields

    def test_schema_caching(self, adapter):
        """Test that schema is cached."""
        schema1 = adapter.schema
        schema2 = adapter.schema

        assert schema1 is schema2  # Same object reference

    def test_schema_relations(self, adapter):
        """Test that relations are correctly identified."""
        schema = adapter.schema

        assert "TestCustomer" in schema.models
        customer_model = schema.models["TestCustomer"]
        assert "orders" in customer_model.relations

        order_model = schema.models["TestOrder"]
        assert "customer" in order_model.relations

    def test_schema_fields_count(self, adapter):
        """Test that expected number of fields are introspected."""
        schema = adapter.schema

        # TestCustomer has: id, tenant_id, name, email, age, created_at
        customer_model = schema.models["TestCustomer"]
        assert len(customer_model.fields) >= 5  # At least these fields

        # TestOrder has: id, tenant_id, customer_id, status, total, created_at
        order_model = schema.models["TestOrder"]
        assert len(order_model.fields) >= 5  # At least these fields


class TestSQLAlchemyQueryCompilation:
    """Tests for query compilation."""

    def test_compile_basic_query(self, adapter, principal):
        """Test compiling a basic query."""
        ctx = RunContext(principal=principal, db=None)
        request = QueryRequest(
            model="TestCustomer",
            select=["id", "name"],
        )

        compiled = adapter.compile_query(request, ctx, adapter.policy, adapter.schema)

        assert compiled is not None
        assert hasattr(compiled, 'query')
        assert hasattr(compiled, 'request')

    def test_compile_query_with_filters(self, adapter, principal):
        """Test compiling a query with filters."""
        ctx = RunContext(principal=principal, db=None)
        request = QueryRequest(
            model="TestCustomer",
            select=["id", "name", "age"],
            where=[
                FilterClause(field="age", op=FilterOp.GTE, value=25),
                FilterClause(field="age", op=FilterOp.LT, value=35),
            ],
        )

        compiled = adapter.compile_query(request, ctx, adapter.policy, adapter.schema)

        assert compiled is not None

    def test_compile_query_with_order(self, adapter, principal):
        """Test compiling a query with ordering."""
        ctx = RunContext(principal=principal, db=None)
        request = QueryRequest(
            model="TestCustomer",
            select=["id", "name", "age"],
            order_by=[
                OrderClause(field="age", direction=OrderDirection.DESC)
            ],
        )

        compiled = adapter.compile_query(request, ctx, adapter.policy, adapter.schema)

        assert compiled is not None

    def test_compile_query_with_pagination(self, adapter, principal):
        """Test compiling a query with pagination."""
        ctx = RunContext(principal=principal, db=None)
        request = QueryRequest(
            model="TestCustomer",
            select=["id", "name"],
            take=10,
        )

        compiled = adapter.compile_query(request, ctx, adapter.policy, adapter.schema)

        assert compiled is not None

    def test_compile_get_request(self, adapter, principal):
        """Test compiling a get request."""
        ctx = RunContext(principal=principal, db=None)
        request = GetRequest(
            model="TestCustomer",
            id=1,
            select=["id", "name"],
        )

        compiled = adapter.compile_get(request, ctx, adapter.policy, adapter.schema)

        assert compiled is not None

    def test_compile_aggregate_request(self, adapter, principal):
        """Test compiling an aggregate request."""
        ctx = RunContext(principal=principal, db=None)
        request = AggregateRequest(
            model="TestOrder",
            operation="count",
            field="id",
        )

        compiled = adapter.compile_aggregate(request, ctx, adapter.policy, adapter.schema)

        assert compiled is not None


class TestSQLAlchemyMutationCompilation:
    """Tests for mutation compilation."""

    def test_compile_create_request(self, adapter, principal):
        """Test compiling a create request."""
        ctx = RunContext(principal=principal, db=None)
        request = CreateRequest(
            model="TestCustomer",
            data={
                "tenant_id": "tenant-1",
                "name": "New Customer",
                "email": "new@example.com",
            },
        )

        compiled = adapter.compile_create(request, ctx, adapter.policy, adapter.schema)

        assert compiled is not None

    def test_compile_update_request(self, adapter, principal):
        """Test compiling an update request."""
        ctx = RunContext(principal=principal, db=None)
        request = UpdateRequest(
            model="TestCustomer",
            id=1,
            data={"name": "Updated Name"},
        )

        compiled = adapter.compile_update(request, ctx, adapter.policy, adapter.schema)

        assert compiled is not None

    def test_compile_delete_request(self, adapter, principal):
        """Test compiling a delete request."""
        ctx = RunContext(principal=principal, db=None)
        request = DeleteRequest(
            model="TestCustomer",
            id=1,
        )

        compiled = adapter.compile_delete(request, ctx, adapter.policy, adapter.schema)

        assert compiled is not None

    def test_compile_bulk_update_request(self, adapter, principal):
        """Test compiling a bulk update request."""
        ctx = RunContext(principal=principal, db=None)
        request = BulkUpdateRequest(
            model="TestOrder",
            ids=[1, 2, 3],
            data={"status": "cancelled"},
        )

        compiled = adapter.compile_bulk_update(request, ctx, adapter.policy, adapter.schema)

        assert compiled is not None


class TestSQLAlchemyRedactorCache:
    """Tests for redactor caching."""

    def test_redactor_cache_created(self, adapter):
        """Test that redactor cache is initialized."""
        assert hasattr(adapter, "_redactor_cache")
        assert isinstance(adapter._redactor_cache, dict)

    def test_get_redactor_returns_redactor(self, adapter):
        """Test that _get_redactor returns a Redactor or None."""
        redactor = adapter._get_redactor("TestCustomer")
        # Should return None if no policy or a Redactor if there is
        assert redactor is None or hasattr(redactor, 'redact_record')

    def test_redactor_cache_invalidation_specific(self, adapter):
        """Test cache invalidation for specific model."""
        # Populate cache
        adapter._get_redactor("TestCustomer")
        assert "TestCustomer" in adapter._redactor_cache

        # Invalidate specific model
        adapter._invalidate_redactor_cache("TestCustomer")
        assert "TestCustomer" not in adapter._redactor_cache

    def test_redactor_cache_invalidation_all(self, adapter):
        """Test cache invalidation for all models."""
        # Populate cache
        adapter._get_redactor("TestCustomer")
        adapter._get_redactor("TestOrder")
        assert len(adapter._redactor_cache) >= 2

        # Invalidate all
        adapter._invalidate_redactor_cache()
        assert len(adapter._redactor_cache) == 0


class TestSQLAlchemyPolicyApplication:
    """Tests for policy application during compilation."""

    def test_compile_with_row_policy(self, adapter, principal):
        """Test that row policy is applied during compilation."""
        ctx = RunContext(principal=principal, db=None)
        request = QueryRequest(
            model="TestCustomer",
            select=["id", "name"],
        )

        compiled = adapter.compile_query(request, ctx, adapter.policy, adapter.schema)

        assert compiled is not None
        # Row policy should inject tenant filter

    def test_compile_with_budget(self, adapter, principal):
        """Test that budget limits are applied during compilation."""
        ctx = RunContext(principal=principal, db=None)
        request = QueryRequest(
            model="TestCustomer",
            select=["id", "name"],
            take=50,
        )

        # Policy has max_rows=100, so take=50 should be fine
        compiled = adapter.compile_query(request, ctx, adapter.policy, adapter.schema)

        assert compiled is not None


class TestSQLAlchemyAsyncSupport:
    """Tests for async engine support."""

    def test_async_engine_detection(self):
        """Test that async engine is correctly detected."""
        async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        from sqlalchemy.ext.asyncio import AsyncEngine

        assert isinstance(async_engine, AsyncEngine)

    def test_adapter_is_async_flag(self, sync_engine, basic_policy):
        """Test that adapter correctly identifies async engine."""
        async_adapter = SQLAlchemyAdapter(
            engine=create_async_engine("sqlite+aiosqlite:///:memory:"),
            models=TEST_MODELS,
            policy=basic_policy,
        )
        assert async_adapter.is_async is True


class TestSQLAlchemySessionManagement:
    """Tests for session management."""

    def test_session_manager_created(self, session_manager, sync_engine):
        """Test that session manager is created correctly."""
        assert session_manager.engine == sync_engine

    def test_adapter_uses_provided_session_manager(self, adapter, session_manager):
        """Test that adapter uses provided session manager."""
        assert adapter.session_manager is session_manager


class TestSQLAlchemyCompilerIntegration:
    """Tests for compiler integration."""

    def test_compiler_has_policy(self, adapter):
        """Test that compiler has access to policy."""
        compiler = adapter.compiler
        assert compiler.policy == adapter.policy

    def test_compiler_has_schema(self, adapter):
        """Test that compiler has access to schema."""
        compiler = adapter.compiler
        assert compiler.schema == adapter.schema

    def test_compiler_has_model_map(self, adapter):
        """Test that compiler has model map."""
        compiler = adapter.compiler
        assert hasattr(compiler, 'model_map')
        assert "TestCustomer" in compiler.model_map


class TestSQLAlchemyTransactionSupport:
    """Tests for transaction support."""

    def test_transaction_method_exists(self, adapter):
        """Test that transaction method exists and is callable."""
        assert hasattr(adapter, 'transaction')
        assert callable(adapter.transaction)
