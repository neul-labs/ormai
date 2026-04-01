"""
End-to-end integration tests for ORM operations.

Tests the full request lifecycle: request -> policy validation -> compilation.
"""

import pytest
from datetime import datetime

from sqlalchemy import create_engine, String, Integer, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from sqlalchemy.pool import StaticPool

from ormai.adapters.sqlalchemy import SQLAlchemyAdapter
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


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    age: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100))
    user_id: Mapped[int] = mapped_column(Integer)
    amount: Mapped[float] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


TEST_MODELS = [User, Order]


# === Fixtures ===

@pytest.fixture
def sync_engine():
    """Create an in-memory SQLite engine with shared connection."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def policy():
    """Create a comprehensive test policy."""
    return Policy(
        models={
            "User": ModelPolicy(
                allowed=True,
                readable=True,
                writable=True,
                fields={
                    "email": FieldPolicy(action=FieldAction.MASK),
                    "age": FieldPolicy(action=FieldAction.MASK),
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
            "Order": ModelPolicy(
                allowed=True,
                readable=True,
                writable=True,
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
            max_select_fields=20,
        ),
        require_tenant_scope=True,
        writes_enabled=True,
    )


@pytest.fixture
def tenant_principal():
    """Create a test principal."""
    return Principal(
        tenant_id="tenant-1",
        user_id="user-1",
        roles=("user",),
    )


@pytest.fixture
def run_context(tenant_principal):
    """Create a run context."""
    return RunContext(
        principal=tenant_principal,
        db=None,
    )


@pytest.fixture
def adapter(sync_engine, policy):
    """Create a SQLAlchemy adapter."""
    return SQLAlchemyAdapter(
        engine=sync_engine,
        models=TEST_MODELS,
        policy=policy,
    )


# === Integration Tests ===

class TestQueryCompilationIntegration:
    """Integration tests for query compilation with policy."""

    def test_compile_query_with_policy(self, adapter, run_context):
        """Test complete query compilation with policy enforcement."""
        request = QueryRequest(
            model="User",
            select=["id", "name", "email"],
        )

        # Compile query with policy
        compiled = adapter.compile_query(request, run_context, adapter.policy, adapter.schema)

        assert compiled is not None
        assert compiled.request == request
        assert compiled.select_fields == ["id", "name", "email"]

    def test_compile_query_with_filters(self, adapter, run_context):
        """Test query compilation with user filters combined with policy filters."""
        request = QueryRequest(
            model="User",
            select=["id", "name"],
            where=[FilterClause(field="name", op=FilterOp.CONTAINS, value="Ali")],
        )

        compiled = adapter.compile_query(request, run_context, adapter.policy, adapter.schema)

        assert compiled is not None
        assert len(compiled.injected_filters) == 1  # Tenant filter injected
        assert compiled.injected_filters[0].field == "tenant_id"
        assert compiled.injected_filters[0].value == "tenant-1"

    def test_compile_query_with_pagination(self, adapter, run_context):
        """Test query compilation with pagination."""
        request = QueryRequest(
            model="User",
            select=["id", "name"],
            take=10,
        )

        compiled = adapter.compile_query(request, run_context, adapter.policy, adapter.schema)

        assert compiled is not None
        assert compiled.request.take == 10

    def test_compile_get_with_policy(self, adapter, run_context):
        """Test get by ID compilation with policy enforcement."""
        request = GetRequest(
            model="User",
            id=1,
            select=["id", "name", "email"],
        )

        compiled = adapter.compile_get(request, run_context, adapter.policy, adapter.schema)

        assert compiled is not None
        assert compiled.request.id == 1

    def test_compile_aggregate_with_policy(self, adapter, run_context):
        """Test aggregate compilation with policy enforcement."""
        request = AggregateRequest(
            model="Order",
            operation="count",
            field="id",
        )

        compiled = adapter.compile_aggregate(request, run_context, adapter.policy, adapter.schema)

        assert compiled is not None
        assert compiled.request.operation == "count"


class TestMutationCompilationIntegration:
    """Integration tests for mutation compilation with policy."""

    def test_compile_create_with_policy(self, adapter, run_context):
        """Test create compilation with policy enforcement."""
        request = CreateRequest(
            model="User",
            data={
                "tenant_id": "tenant-1",
                "name": "New User",
                "email": "new@example.com",
                "age": 28,
            },
        )

        compiled = adapter.compile_create(request, run_context, adapter.policy, adapter.schema)

        assert compiled is not None
        assert compiled.request.model == "User"
        assert len(compiled.injected_filters) == 1
        assert compiled.injected_filters[0].field == "tenant_id"

    def test_compile_update_with_policy(self, adapter, run_context):
        """Test update compilation with policy enforcement."""
        request = UpdateRequest(
            model="User",
            id=1,
            data={"name": "Updated Alice"},
        )

        compiled = adapter.compile_update(request, run_context, adapter.policy, adapter.schema)

        assert compiled is not None
        assert compiled.request.id == 1

    def test_compile_delete_with_policy(self, adapter, run_context):
        """Test delete compilation with policy enforcement."""
        request = DeleteRequest(
            model="User",
            id=1,
        )

        compiled = adapter.compile_delete(request, run_context, adapter.policy, adapter.schema)

        assert compiled is not None
        assert compiled.request.id == 1

    def test_compile_bulk_update_with_policy(self, adapter, run_context):
        """Test bulk update compilation with policy enforcement."""
        request = BulkUpdateRequest(
            model="Order",
            ids=[1, 2],
            data={"status": "processed"},
        )

        compiled = adapter.compile_bulk_update(request, run_context, adapter.policy, adapter.schema)

        assert compiled is not None
        assert len(compiled.request.ids) == 2


class TestPolicyDecisionIntegration:
    """Integration tests for policy decisions."""

    def test_query_injects_tenant_filter(self, adapter, run_context):
        """Test that tenant scope filter is injected for queries."""
        request = QueryRequest(
            model="User",
            select=["id", "name"],
        )

        compiled = adapter.compile_query(request, run_context, adapter.policy, adapter.schema)

        # Verify tenant filter was injected
        assert len(compiled.injected_filters) == 1
        assert compiled.injected_filters[0].field == "tenant_id"
        assert compiled.injected_filters[0].value == "tenant-1"

    def test_create_injects_tenant_filter(self, adapter, run_context):
        """Test that tenant filter is injected for creates."""
        request = CreateRequest(
            model="User",
            data={"name": "New User"},
        )

        compiled = adapter.compile_create(request, run_context, adapter.policy, adapter.schema)

        assert len(compiled.injected_filters) == 1
        assert compiled.injected_filters[0].field == "tenant_id"

    def test_policy_tracks_allowed_fields(self, adapter, run_context):
        """Test that policy tracks allowed fields."""
        request = QueryRequest(
            model="User",
            select=["id", "name", "email"],
        )

        compiled = adapter.compile_query(request, run_context, adapter.policy, adapter.schema)

        # Check that allowed fields are tracked
        assert "email" in compiled.select_fields


class TestErrorHandlingIntegration:
    """Integration tests for error handling during compilation."""

    def test_invalid_model_raises_error(self, adapter, run_context):
        """Test that invalid model raises appropriate error."""
        from ormai.core.errors import ModelNotAllowedError

        request = QueryRequest(
            model="NonExistentModel",
            select=["id"],
        )

        with pytest.raises(ModelNotAllowedError):
            adapter.compile_query(request, run_context, adapter.policy, adapter.schema)

    def test_unauthorized_field_raises_error(self, adapter, run_context):
        """Test that unauthorized fields raise error."""
        from ormai.core.errors import FieldNotAllowedError

        request = QueryRequest(
            model="User",
            select=["id", "name", "ssn"],  # ssn not in schema
        )

        with pytest.raises(FieldNotAllowedError):
            adapter.compile_query(request, run_context, adapter.policy, adapter.schema)

    def test_disallowed_model_write_raises_error(self, run_context):
        """Test that writes to disallowed model raise error."""
        from ormai.core.errors import ModelNotAllowedError

        # Model not in policy
        restrictive_policy = Policy(
            models={},
            default_budget=Budget(max_rows=100),
            writes_enabled=True,
        )

        adapter = SQLAlchemyAdapter(
            engine=create_engine("sqlite:///:memory:"),
            models=TEST_MODELS,
            policy=restrictive_policy,
        )

        request = CreateRequest(
            model="User",
            data={"name": "Test"},
        )

        with pytest.raises(ModelNotAllowedError):
            adapter.compile_create(request, run_context, restrictive_policy, adapter.schema)


class TestAdapterSchemaIntegration:
    """Integration tests for adapter schema integration."""

    def test_adapter_schema_matches_models(self, adapter):
        """Test that adapter schema matches registered models."""
        schema = adapter.schema

        assert "User" in schema.models
        assert "Order" in schema.models

        user_model = schema.models["User"]
        assert "id" in user_model.fields
        assert "name" in user_model.fields
        assert "email" in user_model.fields

    def test_adapter_schema_caching(self, adapter):
        """Test that schema is cached."""
        schema1 = adapter.schema
        schema2 = adapter.schema

        assert schema1 is schema2  # Same reference

    def test_adapter_model_map(self, adapter):
        """Test that model map is correct."""
        model_map = adapter.model_map

        assert "User" in model_map
        assert "Order" in model_map
        assert model_map["User"] == User
        assert model_map["Order"] == Order


class TestTransactionIntegration:
    """Integration tests for transaction support."""

    def test_transaction_method_exists(self, adapter):
        """Test that transaction method exists and is callable."""
        assert hasattr(adapter, 'transaction')
        assert callable(adapter.transaction)

    def test_transaction_signature(self, adapter):
        """Test that transaction has expected signature."""
        import inspect
        sig = inspect.signature(adapter.transaction)
        params = list(sig.parameters.keys())

        # Should have: self, ctx, fn, *args, **kwargs
        assert "ctx" in params or params[1] == "ctx"
