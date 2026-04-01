"""
Load and performance tests for ormai adapters and queries.

These tests measure the performance of common operations to ensure
the library remains performant as features are added.
"""

import pytest
import time
from datetime import datetime
import statistics

from sqlalchemy import create_engine, String, Integer, DateTime, Float, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from ormai.adapters.sqlalchemy import SQLAlchemyAdapter
from ormai.core.context import Principal, RunContext
from ormai.core.dsl import (
    QueryRequest,
    GetRequest,
    AggregateRequest,
    CreateRequest,
    UpdateRequest,
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
    RowPolicy,
    WritePolicy,
)


# === Test Models ===

class Base(DeclarativeBase):
    pass


class PerformanceUser(Base):
    __tablename__ = "perf_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    value: Mapped[int] = mapped_column(Integer, default=0)


class PerformanceOrder(Base):
    __tablename__ = "perf_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50))


TEST_PERF_MODELS = [PerformanceUser, PerformanceOrder]


# === Fixtures ===

@pytest.fixture
def perf_engine():
    """Create an in-memory SQLite engine for performance testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def perf_policy():
    """Create a performance test policy."""
    return Policy(
        models={
            "PerformanceUser": ModelPolicy(
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
                    max_affected_rows=1000,
                ),
            ),
            "PerformanceOrder": ModelPolicy(
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
                    max_affected_rows=1000,
                ),
            ),
        },
        default_budget=Budget(
            max_rows=1000,
            max_includes_depth=2,
            max_select_fields=50,
        ),
        require_tenant_scope=True,
        writes_enabled=True,
    )


@pytest.fixture
def perf_principal():
    """Create a test principal."""
    return Principal(
        tenant_id="tenant-perf",
        user_id="user-1",
        roles=("user",),
    )


@pytest.fixture
def perf_adapter(perf_engine, perf_policy):
    """Create a SQLAlchemy adapter for performance testing."""
    return SQLAlchemyAdapter(
        engine=perf_engine,
        models=TEST_PERF_MODELS,
        policy=perf_policy,
    )


@pytest.fixture
def populated_perf_db(perf_engine, perf_principal):
    """Populate the database with test data for performance testing."""
    session = sessionmaker(bind=perf_engine)()
    tenant_id = perf_principal.tenant_id

    # Create 1000 users
    users = []
    for i in range(1000):
        user = PerformanceUser(
            id=i + 1,
            tenant_id=tenant_id,
            name=f"User {i}",
            email=f"user{i}@example.com",
            value=i % 100,
        )
        users.append(user)

    # Create 5000 orders
    orders = []
    for i in range(5000):
        order = PerformanceOrder(
            id=i + 1,
            tenant_id=tenant_id,
            user_id=(i % 1000) + 1,
            amount=i * 10.5,
            status="pending" if i % 3 == 0 else "completed",
        )
        orders.append(order)

    session.add_all(users + orders)
    session.commit()
    session.close()

    return perf_engine


# === Performance Test Classes ===

class TestQueryPerformance:
    """Performance tests for query operations."""

    def test_simple_query_performance(self, perf_adapter, populated_perf_db, perf_principal):
        """Test performance of simple queries."""
        ctx = RunContext(principal=perf_principal, db=None)
        request = QueryRequest(
            model="PerformanceUser",
            select=["id", "name"],
        )

        # Warm up
        for _ in range(10):
            perf_adapter.compile_query(request, ctx, perf_adapter.policy, perf_adapter.schema)

        # Measure
        times = []
        for _ in range(100):
            start = time.perf_counter()
            perf_adapter.compile_query(request, ctx, perf_adapter.policy, perf_adapter.schema)
            end = time.perf_counter()
            times.append(end - start)

        avg_time = statistics.mean(times)
        p95_time = sorted(times)[int(len(times) * 0.95)]

        # Assert performance thresholds (in seconds)
        assert avg_time < 0.01, f"Average query time too high: {avg_time:.4f}s"
        assert p95_time < 0.02, f"P95 query time too high: {p95_time:.4f}s"

    def test_filtered_query_performance(self, perf_adapter, populated_perf_db, perf_principal):
        """Test performance of filtered queries."""
        ctx = RunContext(principal=perf_principal, db=None)
        request = QueryRequest(
            model="PerformanceUser",
            select=["id", "name", "value"],
            where=[FilterClause(field="value", op=FilterOp.GTE, value=50)],
        )

        # Warm up
        for _ in range(10):
            perf_adapter.compile_query(request, ctx, perf_adapter.policy, perf_adapter.schema)

        # Measure
        times = []
        for _ in range(100):
            start = time.perf_counter()
            perf_adapter.compile_query(request, ctx, perf_adapter.policy, perf_adapter.schema)
            end = time.perf_counter()
            times.append(end - start)

        avg_time = statistics.mean(times)
        p95_time = sorted(times)[int(len(times) * 0.95)]

        assert avg_time < 0.01, f"Average filtered query time too high: {avg_time:.4f}s"
        assert p95_time < 0.02, f"P95 filtered query time too high: {p95_time:.4f}s"

    def test_aggregate_query_performance(self, perf_adapter, populated_perf_db, perf_principal):
        """Test performance of aggregate queries."""
        ctx = RunContext(principal=perf_principal, db=None)
        request = AggregateRequest(
            model="PerformanceOrder",
            operation="count",
            field="id",
        )

        # Warm up
        for _ in range(10):
            perf_adapter.compile_aggregate(request, ctx, perf_adapter.policy, perf_adapter.schema)

        # Measure
        times = []
        for _ in range(100):
            start = time.perf_counter()
            perf_adapter.compile_aggregate(request, ctx, perf_adapter.policy, perf_adapter.schema)
            end = time.perf_counter()
            times.append(end - start)

        avg_time = statistics.mean(times)
        p95_time = sorted(times)[int(len(times) * 0.95)]

        assert avg_time < 0.005, f"Aggregate query time too high: {avg_time:.4f}s"
        assert p95_time < 0.01, f"P95 aggregate query time too high: {p95_time:.4f}s"


class TestCompilationPerformance:
    """Performance tests for query compilation."""

    def test_compilation_is_repeated_fast(self, perf_adapter, perf_principal):
        """Test that repeated compilations are fast."""
        ctx = RunContext(principal=perf_principal, db=None)
        request = QueryRequest(
            model="PerformanceUser",
            select=["id", "name", "email", "value"],
            where=[
                FilterClause(field="name", op=FilterOp.CONTAINS, value="User"),
                FilterClause(field="value", op=FilterOp.GTE, value=10),
            ],
        )

        # First compilation (cold)
        start = time.perf_counter()
        perf_adapter.compile_query(request, ctx, perf_adapter.policy, perf_adapter.schema)
        cold_time = time.perf_counter() - start

        # Repeated compilations (warm)
        times = []
        for _ in range(100):
            start = time.perf_counter()
            perf_adapter.compile_query(request, ctx, perf_adapter.policy, perf_adapter.schema)
            times.append(time.perf_counter() - start)

        avg_warm_time = statistics.mean(times)

        # Warm compilations should be faster
        assert avg_warm_time < cold_time * 2, (
            f"Warm compilation not faster than cold: {cold_time:.4f}s vs {avg_warm_time:.4f}s"
        )


class TestMutationPerformance:
    """Performance tests for mutation operations."""

    def test_bulk_update_compilation_performance(self, perf_adapter, perf_principal):
        """Test performance of bulk update compilation."""
        ctx = RunContext(principal=perf_principal, db=None)
        ids = list(range(1, 101))  # 100 ids
        request = BulkUpdateRequest(
            model="PerformanceUser",
            ids=ids,
            data={"value": 999},
        )

        # Warm up
        for _ in range(10):
            perf_adapter.compile_bulk_update(request, ctx, perf_adapter.policy, perf_adapter.schema)

        # Measure
        times = []
        for _ in range(100):
            start = time.perf_counter()
            perf_adapter.compile_bulk_update(request, ctx, perf_adapter.policy, perf_adapter.schema)
            end = time.perf_counter()
            times.append(end - start)

        avg_time = statistics.mean(times)

        assert avg_time < 0.01, f"Bulk update compilation too slow: {avg_time:.4f}s"


class TestSchemaIntrospectionPerformance:
    """Performance tests for schema introspection."""

    def test_schema_caching_performance(self, perf_adapter, perf_principal):
        """Test that schema is cached and retrieved quickly."""
        ctx = RunContext(principal=perf_principal, db=None)

        # First access (introspection)
        start = time.perf_counter()
        schema = perf_adapter.schema
        introspect_time = time.perf_counter() - start

        # Subsequent accesses (cached)
        times = []
        for _ in range(100):
            start = time.perf_counter()
            _ = perf_adapter.schema
            times.append(time.perf_counter() - start)

        avg_cached_time = statistics.mean(times)

        # Cached access should be much faster
        assert avg_cached_time < introspect_time / 10, (
            f"Schema caching not effective: {introspect_time:.4f}s vs {avg_cached_time:.4f}s"
        )


class TestPolicyValidationPerformance:
    """Performance tests for policy validation."""

    def test_policy_validation_performance(self, perf_adapter, perf_principal):
        """Test performance of policy validation during compilation."""
        ctx = RunContext(principal=perf_principal, db=None)

        requests = [
            QueryRequest(model="PerformanceUser", select=["id", "name"]),
            QueryRequest(model="PerformanceUser", select=["id", "name", "email"]),
            AggregateRequest(model="PerformanceOrder", operation="count", field="id"),
            BulkUpdateRequest(
                model="PerformanceUser",
                ids=[1, 2, 3],
                data={"value": 100},
            ),
        ]

        # Warm up
        for req in requests:
            if hasattr(req, 'model'):
                if isinstance(req, QueryRequest):
                    perf_adapter.compile_query(req, ctx, perf_adapter.policy, perf_adapter.schema)
                elif isinstance(req, AggregateRequest):
                    perf_adapter.compile_aggregate(req, ctx, perf_adapter.policy, perf_adapter.schema)
                elif isinstance(req, BulkUpdateRequest):
                    perf_adapter.compile_bulk_update(req, ctx, perf_adapter.policy, perf_adapter.schema)

        # Measure
        times = []
        for req in requests:
            for _ in range(10):
                start = time.perf_counter()
                if isinstance(req, QueryRequest):
                    perf_adapter.compile_query(req, ctx, perf_adapter.policy, perf_adapter.schema)
                elif isinstance(req, AggregateRequest):
                    perf_adapter.compile_aggregate(req, ctx, perf_adapter.policy, perf_adapter.schema)
                elif isinstance(req, BulkUpdateRequest):
                    perf_adapter.compile_bulk_update(req, ctx, perf_adapter.policy, perf_adapter.schema)
                times.append(time.perf_counter() - start)

        avg_time = statistics.mean(times)
        p95_time = sorted(times)[int(len(times) * 0.95)]

        assert avg_time < 0.01, f"Policy validation too slow: {avg_time:.4f}s"
        assert p95_time < 0.02, f"P95 policy validation too high: {p95_time:.4f}s"


class TestAdapterCreationPerformance:
    """Performance tests for adapter creation."""

    def test_adapter_creation_performance(self, perf_engine, perf_policy):
        """Test that adapter creation is fast."""
        times = []
        for _ in range(50):
            start = time.perf_counter()
            adapter = SQLAlchemyAdapter(
                engine=perf_engine,
                models=TEST_PERF_MODELS,
                policy=perf_policy,
            )
            times.append(time.perf_counter() - start)

        avg_time = statistics.mean(times)

        # Adapter creation should be fast (< 50ms on average)
        assert avg_time < 0.05, f"Adapter creation too slow: {avg_time:.4f}s"


class TestThroughputTests:
    """Throughput tests for common operations."""

    def test_query_throughput(self, perf_adapter, populated_perf_db, perf_principal):
        """Measure query throughput (queries per second)."""
        ctx = RunContext(principal=perf_principal, db=None)
        request = QueryRequest(
            model="PerformanceUser",
            select=["id", "name"],
        )

        # Warm up
        for _ in range(100):
            perf_adapter.compile_query(request, ctx, perf_adapter.policy, perf_adapter.schema)

        # Measure throughput
        duration = 1.0  # 1 second
        count = 0
        start = time.perf_counter()
        while time.perf_counter() - start < duration:
            perf_adapter.compile_query(request, ctx, perf_adapter.policy, perf_adapter.schema)
            count += 1

        # Should handle at least 500 queries per second
        assert count >= 500, f"Query throughput too low: {count} qps"

    def test_compilation_throughput(self, perf_adapter, populated_perf_db, perf_principal):
        """Measure compilation throughput (compilations per second)."""
        ctx = RunContext(principal=perf_principal, db=None)
        requests = [
            QueryRequest(model="PerformanceUser", select=["id", "name"]),
            QueryRequest(model="PerformanceOrder", select=["id", "amount"]),
            AggregateRequest(model="PerformanceOrder", operation="sum", field="amount"),
        ]

        duration = 1.0  # 1 second
        count = 0
        start = time.perf_counter()
        while time.perf_counter() - start < duration:
            for req in requests:
                if isinstance(req, QueryRequest):
                    perf_adapter.compile_query(req, ctx, perf_adapter.policy, perf_adapter.schema)
                elif isinstance(req, AggregateRequest):
                    perf_adapter.compile_aggregate(req, ctx, perf_adapter.policy, perf_adapter.schema)
                count += 1

        # Should handle at least 200 compilations per second
        assert count >= 200, f"Compilation throughput too low: {count} cps"
