"""
Django quickstart.

One-function setup for Django integration.

Note: Requires Django to be installed.
Install with: pip install django
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ormai.adapters.django import DjangoAdapter
    from ormai.core.types import SchemaMetadata
    from ormai.mcp.server import McpServer
    from ormai.policy.models import Policy
    from ormai.store.base import AuditStore
    from ormai.tools.registry import ToolRegistry
    from ormai.views.factory import ViewFactory


@dataclass
class DjangoMount:
    """
    Result of mounting OrmAI on Django.

    Contains all the components needed to use OrmAI.
    """

    # Core components
    adapter: DjangoAdapter
    policy: Policy
    schema: SchemaMetadata
    toolset: ToolRegistry

    # Optional components
    mcp_server: McpServer | None = None
    audit_store: AuditStore | None = None
    view_factory: ViewFactory | None = None


def mount_django(
    models: list[type],
    *,
    app_config: Any | None = None,
    tenant_field: str | None = "tenant_id",
    profile: str = "prod",
    auth: Callable[[dict[str, Any]], Any] | None = None,
    enable_mcp: bool = True,
    audit_path: str | None = None,
    deny_fields: list[str] | None = None,
    mask_fields: list[str] | None = None,
) -> DjangoMount:
    """
    Mount OrmAI on Django models.

    This is the quickest way to get started with OrmAI and Django. It:
    1. Creates an adapter for your models
    2. Builds a policy from the profile
    3. Creates a toolset with all read tools
    4. Optionally sets up MCP server and audit logging

    Note: Django adapter works with Django's synchronous ORM.
    Async operations are wrapped for tool execution.

    Args:
        models: List of Django model classes
        app_config: Optional Django AppConfig (alternative to models list)
        tenant_field: Field name for tenant scoping (default: "tenant_id")
        profile: Profile name ("prod", "internal", "dev") or DefaultsProfile
        auth: Optional auth function for MCP
        enable_mcp: Whether to create an MCP server
        audit_path: Path for audit log file (enables audit logging)
        deny_fields: Additional field patterns to deny
        mask_fields: Additional field names to mask

    Returns:
        DjangoMount with all configured components

    Example:
        from ormai.quickstart import mount_django
        from myapp.models import Customer, Order, Subscription

        ormai = mount_django(
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
    # Lazy imports to handle optional dependencies
    from ormai.adapters.django import DjangoAdapter
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

    # Create adapter
    adapter = DjangoAdapter(
        app_config=app_config,
        models=models,
    )

    # Get schema (sync introspection for Django)
    schema_cache = SchemaCache()
    schema = schema_cache.get_or_build(
        "main",
        lambda: adapter.sync_introspect(),
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

    return DjangoMount(
        adapter=adapter,
        policy=policy,
        schema=schema,
        toolset=toolset,
        mcp_server=mcp_server,
        audit_store=audit_store,
        view_factory=view_factory,
    )
