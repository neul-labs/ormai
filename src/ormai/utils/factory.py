"""
Toolset factory for building tool registries from policy.
"""

from ormai.adapters.base import OrmAdapter
from ormai.core.types import SchemaMetadata
from ormai.policy.models import Policy
from ormai.tools.generic import (
    AggregateTool,
    BulkUpdateTool,
    CreateTool,
    DeleteTool,
    DescribeSchemaTool,
    GetTool,
    QueryTool,
    UpdateTool,
)
from ormai.tools.registry import ToolRegistry
from ormai.utils.plugins import ErrorPlugin, PluginChain


class ToolsetFactory:
    """
    Factory for creating tool registries from policy configuration.

    Creates the appropriate set of tools based on policy settings.
    Supports plugins for error customization and monitoring.
    """

    def __init__(
        self,
        adapter: OrmAdapter,
        policy: Policy,
        schema: SchemaMetadata,
        plugins: list[ErrorPlugin] | None = None,
    ) -> None:
        """
        Initialize the factory.

        Args:
            adapter: The ORM adapter to use
            policy: Policy configuration
            schema: Schema metadata
            plugins: Optional error plugins for customization
        """
        self.adapter = adapter
        self.policy = policy
        self.schema = schema
        self.plugin_chain = PluginChain(plugins)

    def create(self, include_writes: bool | None = None) -> ToolRegistry:
        """
        Create a tool registry with all enabled tools.

        Args:
            include_writes: Override to force-include/exclude write tools.
                           If None, uses policy.writes_enabled.

        Returns a ToolRegistry containing:
        - db.describe_schema (always)
        - db.query (if reads enabled)
        - db.get (if reads enabled)
        - db.aggregate (if reads enabled)
        - db.create, db.update, db.delete (if writes enabled)
        - db.bulk_update (if bulk writes enabled)
        """
        registry = ToolRegistry()

        # Always register describe_schema
        registry.register(
            DescribeSchemaTool(schema=self.schema, policy=self.policy)
        )

        # Register read tools
        registry.register(
            QueryTool(adapter=self.adapter, policy=self.policy, schema=self.schema)
        )
        registry.register(
            GetTool(adapter=self.adapter, policy=self.policy, schema=self.schema)
        )
        registry.register(
            AggregateTool(adapter=self.adapter, policy=self.policy, schema=self.schema)
        )

        # Determine if writes should be included
        writes_enabled = include_writes if include_writes is not None else self.policy.writes_enabled

        if writes_enabled:
            self._register_write_tools(registry)

        return registry

    def _register_write_tools(self, registry: ToolRegistry) -> None:
        """Register write tools based on policy permissions."""
        # Check which write operations are enabled across models
        has_create = False
        has_update = False
        has_delete = False
        has_bulk = False

        for model_name, model_policy in self.policy.models.items():
            if not model_policy.writable:
                continue
            wp = model_policy.write_policy
            if wp is None:
                continue
            if wp.allow_create:
                has_create = True
            if wp.allow_update:
                has_update = True
            if wp.allow_delete:
                has_delete = True
            if wp.allow_bulk:
                has_bulk = True

        # Register tools for enabled operations
        if has_create:
            registry.register(
                CreateTool(adapter=self.adapter, policy=self.policy, schema=self.schema)
            )

        if has_update:
            registry.register(
                UpdateTool(adapter=self.adapter, policy=self.policy, schema=self.schema)
            )

        if has_delete:
            registry.register(
                DeleteTool(adapter=self.adapter, policy=self.policy, schema=self.schema)
            )

        if has_bulk:
            registry.register(
                BulkUpdateTool(adapter=self.adapter, policy=self.policy, schema=self.schema)
            )

    def add_plugin(self, plugin: ErrorPlugin) -> "ToolsetFactory":
        """Add a plugin to the factory."""
        self.plugin_chain.add(plugin)
        return self

    def remove_plugin(self, name: str) -> "ToolsetFactory":
        """Remove a plugin by name."""
        self.plugin_chain.remove(name)
        return self

    def get_plugin(self, name: str) -> ErrorPlugin | None:
        """Get a plugin by name."""
        return self.plugin_chain.get(name)

    @classmethod
    def from_policy(
        cls,
        policy: Policy,
        adapter: OrmAdapter,
        schema: SchemaMetadata | None = None,
        plugins: list[ErrorPlugin] | None = None,
    ) -> ToolRegistry:
        """
        Convenience method to create a toolset from policy.

        If schema is not provided, it will be introspected from the adapter.
        """
        if schema is None:
            schema = adapter.sync_introspect()

        factory = cls(adapter=adapter, policy=policy, schema=schema, plugins=plugins)
        return factory.create()
