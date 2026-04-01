"""
Shared test fixtures.
"""

from datetime import datetime

import pytest
from sqlalchemy import DateTime, Float, ForeignKey, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

from ormai.core.context import Principal, RunContext
from ormai.policy.models import (
    Budget,
    FieldAction,
    FieldPolicy,
    ModelPolicy,
    Policy,
    RelationPolicy,
    RowPolicy,
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
    password_hash: Mapped[str] = mapped_column(String(255))
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
def engine():
    """Create an in-memory SQLite engine."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create a database session."""
    with Session(engine) as session:
        yield session


@pytest.fixture
def principal():
    """Create a test principal."""
    return Principal(
        tenant_id="tenant-1",
        user_id="user-1",
        roles=("user",),
    )


@pytest.fixture
def context(session, principal):
    """Create a test run context."""
    return RunContext(
        principal=principal,
        db=session,
    )


@pytest.fixture
def basic_policy():
    """Create a basic test policy."""
    return Policy(
        models={
            "TestCustomer": ModelPolicy(
                allowed=True,
                readable=True,
                writable=False,
                fields={
                    "password_hash": FieldPolicy(action=FieldAction.DENY),
                    "email": FieldPolicy(action=FieldAction.MASK),
                },
                relations={
                    "orders": RelationPolicy(allowed=True, max_depth=1),
                },
                row_policy=RowPolicy(
                    tenant_scope_field="tenant_id",
                    require_scope=True,
                ),
            ),
            "TestOrder": ModelPolicy(
                allowed=True,
                readable=True,
                writable=False,
                relations={
                    "customer": RelationPolicy(allowed=True, max_depth=1),
                },
                row_policy=RowPolicy(
                    tenant_scope_field="tenant_id",
                    require_scope=True,
                ),
            ),
        },
        default_budget=Budget(
            max_rows=100,
            max_includes_depth=1,
            max_select_fields=40,
        ),
        require_tenant_scope=True,
    )


@pytest.fixture
def seeded_session(session):
    """Session with seeded test data."""
    # Add customers
    customer1 = TestCustomer(
        id=1,
        tenant_id="tenant-1",
        name="John Doe",
        email="john@example.com",
        password_hash="hashed_password",
    )
    customer2 = TestCustomer(
        id=2,
        tenant_id="tenant-2",
        name="Jane Smith",
        email="jane@example.com",
        password_hash="hashed_password",
    )
    session.add_all([customer1, customer2])

    # Add orders
    order1 = TestOrder(
        id=1,
        tenant_id="tenant-1",
        customer_id=1,
        status="pending",
        total=99.99,
    )
    order2 = TestOrder(
        id=2,
        tenant_id="tenant-1",
        customer_id=1,
        status="completed",
        total=149.99,
    )
    order3 = TestOrder(
        id=3,
        tenant_id="tenant-2",
        customer_id=2,
        status="pending",
        total=299.99,
    )
    session.add_all([order1, order2, order3])

    session.commit()
    return session
