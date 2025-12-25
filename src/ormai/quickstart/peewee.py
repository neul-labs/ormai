"""
Peewee quickstart.

One-function setup for Peewee integration.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from peewee import Database

from ormai.adapters.peewee import PeeweeAdapter
from ormai.core.context import Principal
from ormai.core.types import SchemaMetadata
from ormai.mcp.server import McpServer, McpServerFactory
from ormai.policy.models import Policy
from ormai.store.base import AuditStore
from ormai.store.jsonl import JsonlAuditStore
from ormai.tools.registry import ToolRegistry
from ormai.utils.builder import PolicyBuilder
from ormai.utils.cache import SchemaCache
from ormai.utils.defaults import DEFAULT_DEV, DEFAULT_INTERNAL, DEFAULT_PROD, DefaultsProfile
from ormai.utils.factory import ToolsetFactory
from ormai.views.factory import ViewFactory


@dataclass
class PeeweeMount:
    """
    Result of mounting OrmAI on Peewee.

    Contains all the components needed to use OrmAI.
    """

    # Core components
    adapter: PeeweeAdapter
    policy: Policy
    schema: SchemaMetadata
    toolset: ToolRegistry

    # Optional components
    mcp_server: McpServer | None = None
    audit_store: AuditStore | None = None
    view_factory: ViewFactory | None = None


def mount_peewee(
    database: Database,
    models: list[type],
    *,
    tenant_field: str | None = "tenant_id",
    profile: str | DefaultsProfile = "prod",
    auth: Callable[[dict[str, Any]], Principal] | None = None,
    enable_mcp: bool = True,
    audit_path: str | None = None,
    deny_fields: list[str] | None = None,
    mask_fields: list[str] | None = None,
) -> PeeweeMount:
    """
    Mount OrmAI on a Peewee database.

    This is the quickest way to get started with OrmAI and Peewee. It:
    1. Creates an adapter for your models
    2. Builds a policy from the profile
    3. Creates a toolset with all read tools
    4. Optionally sets up MCP server and audit logging

    Note: Peewee is synchronous; the adapter wraps sync operations
    to provide an async interface for tool execution.

    Args:
        database: Peewee database instance
        models: List of Peewee model classes
        tenant_field: Field name for tenant scoping (default: "tenant_id")
        profile: Profile name ("prod", "internal", "dev") or DefaultsProfile
        auth: Optional auth function for MCP
        enable_mcp: Whether to create an MCP server
        audit_path: Path for audit log file (enables audit logging)
        deny_fields: Additional field patterns to deny
        mask_fields: Additional field names to mask

    Returns:
        PeeweeMount with all configured components

    Example:
        from peewee import SqliteDatabase
        from ormai.quickstart import mount_peewee

        db = SqliteDatabase("app.db")

        ormai = mount_peewee(
            database=db,
            models=[Customer, Order, Subscription],
            tenant_field="tenant_id",
            profile="prod",
        )

        # Use the toolset
        result = await ormai.toolset.execute(
            "db.query",
            {"model": "Order", "take": 10},
            ctx,
        )
    """
    # Resolve profile
    if isinstance(profile, str):
        profile_map = {
            "prod": DEFAULT_PROD,
            "internal": DEFAULT_INTERNAL,
            "dev": DEFAULT_DEV,
        }
        resolved_profile = profile_map.get(profile, DEFAULT_PROD)
    else:
        resolved_profile = profile

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

    # Create adapter
    adapter = PeeweeAdapter(
        database=database,
        models=models,
        policy=policy,
    )

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

    return PeeweeMount(
        adapter=adapter,
        policy=policy,
        schema=schema,
        toolset=toolset,
        mcp_server=mcp_server,
        audit_store=audit_store,
        view_factory=view_factory,
    )
