"""Tests for quickstart module."""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from peewee import (
    BooleanField,
    CharField,
    DecimalField,
    ForeignKeyField,
    IntegerField,
    Model,
    SqliteDatabase,
)
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from tortoise import fields
from tortoise.models import Model as TortoiseModel

from ormai.adapters.peewee import PeeweeAdapter
from ormai.adapters.sqlalchemy import SQLAlchemyAdapter
from ormai.adapters.tortoise import TortoiseAdapter
from ormai.quickstart import mount_peewee, mount_sqlalchemy, mount_tortoise
from ormai.quickstart.peewee import PeeweeMount
from ormai.quickstart.sqlalchemy import OrmAIMount
from ormai.quickstart.tortoise import TortoiseMount
from ormai.utils.defaults import DEFAULT_DEV, DEFAULT_INTERNAL, DEFAULT_PROD


# === SQLAlchemy Test Models ===
SABase = declarative_base()


class SACustomer(SABase):
    """SQLAlchemy test customer model."""

    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(200))
    tenant_id = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)


class SAOrder(SABase):
    """SQLAlchemy test order model."""

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    total = Column(Integer)
    status = Column(String(20))
    tenant_id = Column(String(50), nullable=False)


# === Peewee Test Models ===
peewee_db = SqliteDatabase(":memory:")


class PeeweeBase(Model):
    """Peewee base model."""

    class Meta:
        database = peewee_db


class PWCustomer(PeeweeBase):
    """Peewee test customer model."""

    name = CharField(max_length=100)
    email = CharField(max_length=200)
    tenant_id = CharField(max_length=50)
    is_active = BooleanField(default=True)

    class Meta:
        table_name = "customers"


class PWOrder(PeeweeBase):
    """Peewee test order model."""

    customer = ForeignKeyField(PWCustomer, backref="orders")
    total = DecimalField(max_digits=10, decimal_places=2)
    status = CharField(max_length=20)
    tenant_id = CharField(max_length=50)

    class Meta:
        table_name = "orders"


# === Tortoise Test Models ===
class TortCustomer(TortoiseModel):
    """Tortoise test customer model."""

    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    email = fields.CharField(max_length=200)
    tenant_id = fields.CharField(max_length=50)
    is_active = fields.BooleanField(default=True)

    class Meta:
        table = "customers"


class TortOrder(TortoiseModel):
    """Tortoise test order model."""

    id = fields.IntField(pk=True)
    total = fields.DecimalField(max_digits=10, decimal_places=2)
    status = fields.CharField(max_length=20)
    tenant_id = fields.CharField(max_length=50)

    class Meta:
        table = "orders"


class TestMountSQLAlchemy:
    """Tests for mount_sqlalchemy."""

    @pytest.fixture
    def engine(self):
        """Create in-memory SQLite engine."""
        return create_engine("sqlite:///:memory:")

    @pytest.fixture
    def models(self):
        """List of SQLAlchemy models."""
        return [SACustomer, SAOrder]

    def test_mount_creates_all_components(self, engine, models):
        """Test that mount creates all expected components."""
        result = mount_sqlalchemy(
            engine=engine,
            models=models,
            enable_mcp=False,  # Avoid MCP setup complexity
        )

        assert isinstance(result, OrmAIMount)
        assert isinstance(result.adapter, SQLAlchemyAdapter)
        assert result.policy is not None
        assert result.schema is not None
        assert result.toolset is not None
        assert result.view_factory is not None

    def test_mount_with_prod_profile(self, engine, models):
        """Test mount with prod profile."""
        result = mount_sqlalchemy(
            engine=engine,
            models=models,
            profile="prod",
            enable_mcp=False,
        )

        # Verify policy has expected restrictions
        policy = result.policy
        assert policy.default_budget is not None
        assert policy.default_budget.max_rows <= 100

    def test_mount_with_dev_profile(self, engine, models):
        """Test mount with dev profile."""
        result = mount_sqlalchemy(
            engine=engine,
            models=models,
            profile="dev",
            enable_mcp=False,
        )

        # Dev profile should be more permissive
        policy = result.policy
        assert policy.default_budget.max_rows > 100

    def test_mount_with_tenant_scope(self, engine, models):
        """Test mount with tenant scoping."""
        result = mount_sqlalchemy(
            engine=engine,
            models=models,
            tenant_field="tenant_id",
            enable_mcp=False,
        )

        # Verify tenant scoping is in policy
        policy = result.policy
        for model_name in ["SACustomer", "SAOrder"]:
            model_policy = policy.get_model_policy(model_name)
            if model_policy and model_policy.row_policy:
                assert model_policy.row_policy.tenant_scope_field == "tenant_id"

    def test_mount_with_deny_fields(self, engine, models):
        """Test mount with denied fields."""
        result = mount_sqlalchemy(
            engine=engine,
            models=models,
            deny_fields=["password", "ssn"],
            enable_mcp=False,
        )

        assert result.policy is not None

    def test_mount_with_mask_fields(self, engine, models):
        """Test mount with masked fields."""
        result = mount_sqlalchemy(
            engine=engine,
            models=models,
            mask_fields=["email"],
            enable_mcp=False,
        )

        assert result.policy is not None

    def test_mount_with_audit_path(self, engine, models):
        """Test mount with audit logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = str(Path(tmpdir) / "audit.jsonl")

            result = mount_sqlalchemy(
                engine=engine,
                models=models,
                audit_path=audit_path,
                enable_mcp=False,
            )

            assert result.audit_store is not None

    def test_mount_with_custom_profile(self, engine, models):
        """Test mount with custom DefaultsProfile."""
        result = mount_sqlalchemy(
            engine=engine,
            models=models,
            profile=DEFAULT_INTERNAL,
            enable_mcp=False,
        )

        assert result.policy is not None


class TestMountPeewee:
    """Tests for mount_peewee."""

    @pytest.fixture
    def database(self):
        """Create in-memory SQLite database."""
        return SqliteDatabase(":memory:")

    @pytest.fixture
    def models(self):
        """List of Peewee models."""
        return [PWCustomer, PWOrder]

    def test_mount_creates_all_components(self, database, models):
        """Test that mount creates all expected components."""
        result = mount_peewee(
            database=database,
            models=models,
            enable_mcp=False,
        )

        assert isinstance(result, PeeweeMount)
        assert isinstance(result.adapter, PeeweeAdapter)
        assert result.policy is not None
        assert result.schema is not None
        assert result.toolset is not None
        assert result.view_factory is not None

    def test_mount_with_profiles(self, database, models):
        """Test mount with different profiles."""
        for profile in ["prod", "internal", "dev"]:
            result = mount_peewee(
                database=database,
                models=models,
                profile=profile,
                enable_mcp=False,
            )
            assert result.policy is not None

    def test_mount_with_audit(self, database, models):
        """Test mount with audit logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = str(Path(tmpdir) / "audit.jsonl")

            result = mount_peewee(
                database=database,
                models=models,
                audit_path=audit_path,
                enable_mcp=False,
            )

            assert result.audit_store is not None


class TestMountTortoise:
    """Tests for mount_tortoise."""

    @pytest.fixture
    def models(self):
        """List of Tortoise models."""
        return [TortCustomer, TortOrder]

    def test_mount_creates_all_components(self, models):
        """Test that mount creates all expected components."""
        result = mount_tortoise(
            models=models,
            enable_mcp=False,
        )

        assert isinstance(result, TortoiseMount)
        assert isinstance(result.adapter, TortoiseAdapter)
        assert result.policy is not None
        assert result.schema is not None
        assert result.toolset is not None
        assert result.view_factory is not None

    def test_mount_with_connection_name(self, models):
        """Test mount with custom connection name."""
        result = mount_tortoise(
            models=models,
            connection_name="secondary",
            enable_mcp=False,
        )

        assert result.adapter.connection_name == "secondary"

    def test_mount_with_profiles(self, models):
        """Test mount with different profiles."""
        for profile in ["prod", "internal", "dev"]:
            result = mount_tortoise(
                models=models,
                profile=profile,
                enable_mcp=False,
            )
            assert result.policy is not None

    def test_mount_with_audit(self, models):
        """Test mount with audit logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = str(Path(tmpdir) / "audit.jsonl")

            result = mount_tortoise(
                models=models,
                audit_path=audit_path,
                enable_mcp=False,
            )

            assert result.audit_store is not None


class TestQuickstartExports:
    """Test that quickstart module exports are correct."""

    def test_all_exports_available(self):
        """Test that all mount functions are exported."""
        from ormai import quickstart

        assert hasattr(quickstart, "mount_sqlalchemy")
        assert hasattr(quickstart, "mount_peewee")
        assert hasattr(quickstart, "mount_tortoise")

    def test_direct_imports(self):
        """Test direct imports work."""
        from ormai.quickstart import mount_peewee, mount_sqlalchemy, mount_tortoise

        assert callable(mount_sqlalchemy)
        assert callable(mount_peewee)
        assert callable(mount_tortoise)
