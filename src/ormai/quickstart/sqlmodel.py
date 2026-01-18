"""
SQLModel quickstart.

One-function setup for SQLModel integration.

Note: Requires SQLModel to be installed.
Install with: pip install sqlmodel
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.ext.asyncio import AsyncEngine

    from ormai.adapters.sqlmodel import SQLModelAdapter
    from ormai.core.types import SchemaMetadata
    from ormai.mcp.server import McpServer
    from ormai.policy.models import Policy
    from ormai.store.base import AuditStore
    from ormai.tools.registry import ToolRegistry
    from ormai.views.factory import ViewFactory


@dataclass
class SQLModelMount:
    """
    Result of mounting OrmAI on SQLModel.

    Contains all the components needed to use OrmAI.
    """

    # Core components
    adapter: SQLModelAdapter
    policy: Policy
    schema: SchemaMetadata
    toolset: ToolRegistry

    # Optional components
    mcp_server: McpServer | None = None
    audit_store: AuditStore | None = None
    view_factory: ViewFactory | None = None


def mount_sqlmodel(
    engine: Engine | AsyncEngine,
    models: list[type],
    *,
    tenant_field: str | None = "tenant_id",
    profile: str = "prod",
    auth: Callable[[dict[str, Any]], Any] | None = None,
    enable_mcp: bool = True,
    audit_path: str | None = None,
    deny_fields: list[str] | None = None,
    mask_fields: list[str] | None = None,
) -> SQLModelMount:
    """
    Mount OrmAI on a SQLModel engine.

    This is the quickest way to get started with OrmAI and SQLModel. It:
    1. Creates an adapter for your models
    2. Builds a policy from the profile
    3. Creates a toolset with all read tools
    4. Optionally sets up MCP server and audit logging

    SQLModel is built on SQLAlchemy, so the adapter inherits from
    SQLAlchemyAdapter with SQLModel-specific conveniences.

    Args:
        engine: SQLAlchemy/SQLModel engine (sync or async)
        models: List of SQLModel model classes
        tenant_field: Field name for tenant scoping (default: "tenant_id")
        profile: Profile name ("prod", "internal", "dev") or DefaultsProfile
        auth: Optional auth function for MCP
        enable_mcp: Whether to create an MCP server
        audit_path: Path for audit log file (enables audit logging)
        deny_fields: Additional field patterns to deny
        mask_fields: Additional field names to mask

    Returns:
        SQLModelMount with all configured components

    Example:
        from sqlmodel import SQLModel, Field, create_engine
        from ormai.quickstart import mount_sqlmodel

        class Customer(SQLModel, table=True):
            id: int | None = Field(default=None, primary_key=True)
            name: str
            tenant_id: str

        engine = create_engine("sqlite:///./app.db")
        SQLModel.metadata.create_all(engine)

        ormai = mount_sqlmodel(
            engine=engine,
            models=[Customer],
            tenant_field="tenant_id",
            profile="prod",
        )

        # Use the toolset
        result = await ormai.toolset.execute(
            "db.query",
            {"model": "Customer", "take": 10},
            ctx,
        )
    """
    # Lazy imports to handle optional dependencies
    from ormai.adapters.sqlmodel import SQLModelAdapter
    from ormai.mcp.server import McpServerFactory
    from ormai.store.jsonl import JsonlAuditStore
    from ormai.utils.builder import PolicyBuilder
    from ormai.utils.cache import SchemaCache
    from ormai.utils.defaults import DEFAULT_DEV, DEFAULT_INTERNAL, DEFAULT_PROD
    from ormai.utils.factory import ToolsetFactory
    from ormai.views.factory import ViewFactory

    # Resolve profile
    profile_map = {
        "prod": DEFAULT_PROD,
        "internal": DEFAULT_INTERNAL,
        "dev": DEFAULT_DEV,
    }
    resolved_profile = profile_map.get(profile, DEFAULT_PROD)

    # Build policy
    builder = PolicyBuilder(resolved_profile)
    builder.register_models(models)

    if tenant_field:
        builder.tenant_scope(tenant_field)

    if deny_fields:
        builder.deny_fields(*deny_fields)

    if mask_fields:
        builder.mask_fields(mask_fields)

    policy = builder.build()

    # Create adapter using the convenience factory
    adapter = SQLModelAdapter.from_models(engine, *models)

    # Get schema
    schema_cache = SchemaCache()
    schema = schema_cache.get_or_build(
        "main",
        lambda: adapter.introspector.introspect(),
    )

    # Create toolset
    toolset = ToolsetFactory.from_policy(
        policy=policy,
        adapter=adapter,
        schema=schema,
    )

    # Create MCP server if enabled
    mcp_server = None
    if enable_mcp:
        mcp_server = McpServerFactory(
            toolset=toolset,
            auth=auth,
        ).build()

    # Create audit store if path provided
    audit_store = None
    if audit_path:
        audit_store = JsonlAuditStore(audit_path)

    # Create view factory
    view_factory = ViewFactory(schema=schema, policy=policy)

    return SQLModelMount(
        adapter=adapter,
        policy=policy,
        schema=schema,
        toolset=toolset,
        mcp_server=mcp_server,
        audit_store=audit_store,
        view_factory=view_factory,
    )
